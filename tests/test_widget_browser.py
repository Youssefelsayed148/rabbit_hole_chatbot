"""Chromium against a real HTTP FastAPI server and throwaway Postgres.

Fault/status and hostile-content cases intercept responses explicitly; ordinary
EN/AR flows use the real pipeline, ingestion, security and fake providers.
"""
import asyncio
import json
import os
import socket
import shutil
import subprocess
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import uvicorn

from app.config import Settings
from app.main import ChatResponse, create_app
from app.providers import OpenAIChat
from scripts.eval import judge, load_cases
from scripts.fakes import FakeChat, FakeEmbedder
from scripts.quality import RecordingChat


@contextmanager
def serve(settings, *, real=False, recorder=None):
    # Bind before starting uvicorn to avoid a port-selection race.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    settings = replace(settings, environment="development", allowed_origins=[origin],
                       site_keys=["pk_demo"], admin_token="dev-test", auto_ingest=True,
                       catalogue_enabled=False, include_unreviewed=False)
    app = create_app(settings, llm=recorder) if real else create_app(settings, FakeEmbedder(settings.embed_dimensions), FakeChat())
    if real:
        original = app.router.lifespan_context
        @asynccontextmanager
        async def lifespan(application):
            async with original(application):
                try:
                    yield
                finally:
                    await application.state.embedder.client.close()
                    if recorder:
                        await recorder.delegate.client.close()
        app.router.lifespan_context = lifespan
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + (180 if real else 30)
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Browser-test service failed to start")
            time.sleep(.05)
        yield origin
    finally:
        server.should_exit = True
        thread.join(timeout=30)
        sock.close()


def run_browser(origin, tmp_path, *, cases=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the Playwright browser tests")
    module = os.environ.get("PLAYWRIGHT_MODULE", "playwright-core")
    resolved = subprocess.run([node, "-e", "require(process.argv[1])", module], capture_output=True, text=True)
    if resolved.returncode:
        pytest.skip("Existing Playwright not found; set PLAYWRIGHT_MODULE to its package path")
    out = tmp_path / "widget-results.json"
    env = dict(os.environ, WIDGET_TEST_URL=origin, WIDGET_TEST_OUT=str(out))
    if cases:
        env["WIDGET_SMOKE_CASES"] = json.dumps(cases, ensure_ascii=False)
    runner = Path(__file__).resolve().parents[1] / "scripts" / "widget-e2e.cjs"
    result = subprocess.run([node, str(runner)], env=env, capture_output=True, text=True, timeout=480)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def test_widget_end_to_end(settings, tmp_path):
    with serve(replace(settings, rate_limit_per_min=100)) as origin:
        result = run_browser(origin, tmp_path)
    assert result["checks"] >= 35


async def grade_answers(settings, cases, answers, records):
    chat = OpenAIChat(settings)
    try:
        verdicts = [await judge(chat, case, row["answer"], evidence=record["evidence"])
                    for case, row, record in zip(cases, answers, records, strict=True)]
        # Permanent semantic regression: accepting conditional replacement shipping
        # must not admit normal-delivery/guaranteed-arrival substitutions.
        index = next(i for i, case in enumerate(cases) if case["id"] == "case-5")
        evidence = records[index]["evidence"]
        supported = "According to the refund policy, if a replacement is approved, the replacement product will be shipped within 5-7 working days after the product is received and inspected."
        positive = await judge(chat, cases[index], supported, evidence=evidence)
        negative = await judge(chat, cases[index], "All normal orders are guaranteed to arrive within 5-7 working days.", evidence=evidence)
        assert positive["pass"] is True, positive
        assert negative["pass"] is False and negative["unsupported_claims"], negative
        return verdicts
    finally:
        await chat.client.close()


@pytest.mark.skipif(os.environ.get("RUN_REAL_WIDGET_SMOKE") != "1", reason="Opt in to paid OpenAI smoke with RUN_REAL_WIDGET_SMOKE=1")
def test_real_openai_grounding_survives_widget(settings, tmp_path):
    live = Settings.from_env()
    assert live.openai_api_key, "OPENAI_API_KEY is required"
    live = replace(live, database_url=settings.database_url, store_messages=False)
    cases = [c for c in load_cases(live.data_dir / "evaluation.jsonl") if c["id"] in {"case-2", "case-3", "case-4", "case-5"}]
    cases.append({"id": "widget-ar", "question": "\u0645\u0627 \u0647\u064a \u0645\u0647\u0644\u0629 \u0627\u0644\u0625\u0628\u0644\u0627\u063a \u0639\u0646 \u0639\u064a\u0628 \u062a\u0635\u0646\u064a\u0639\u061f",
                  "expected_document_ids": ["refund-ar"],
                  "required_behavior": "Answer in Arabic from the Arabic refund policy: report within 7 days of delivery, inspection/confirmation required; invent no facts."})
    recorder = RecordingChat(OpenAIChat(live))
    with serve(live, real=True, recorder=recorder) as origin:
        results = run_browser(origin, tmp_path, cases=cases)
    verdicts = asyncio.run(grade_answers(live, cases, results["answers"], recorder.records))
    report = [{"case": case, "response": row, "verdict": verdict}
              for case, row, verdict in zip(cases, results["answers"], verdicts, strict=True)]
    (tmp_path / "grounding-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for case, row in zip(cases, results["answers"], strict=True):
        body = ChatResponse.model_validate(row)
        lang = "ar" if case["id"] == "widget-ar" else "en"
        assert body.language == lang and not body.needs_human
        assert set(case["expected_document_ids"]) <= {s.document_id for s in body.sources}
        assert all(s.document_id.endswith("-" + lang) for s in body.sources)
    failures = {case["id"]: verdict for case, verdict in zip(cases, verdicts, strict=True)
                if verdict.get("pass") is not True}
    assert not failures, failures
