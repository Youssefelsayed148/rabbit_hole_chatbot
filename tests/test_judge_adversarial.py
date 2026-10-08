import json
import os
from pathlib import Path

import pytest

from app.config import Settings
from app.providers import OpenAIChat
from scripts.eval import judge, load_cases
from scripts.fakes import FakeChat

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = load_cases(ROOT / "data/judge_adversarial.jsonl")
CHUNKS = load_cases(ROOT / "data/chunks.jsonl")


def evidence_for(control):
    return [{"chunk_id": c["chunk_id"], "document_id": c["id"], "text": c["text"]}
            for c in CHUNKS if c["id"] == "refund-" + control["language"]]


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: c["id"])
async def test_adversarial_inputs_keep_policy_languages_separate(control):
    evidence = evidence_for(control)
    chat = FakeChat()
    chat.next_raw = json.dumps({"pass": False, "reason": "Unsupported promise.", "unsupported_claims": [control["answer"]]})
    verdict = await judge(chat, control, control["answer"], evidence=evidence)
    assert verdict["pass"] is False
    turn = chat.calls[-1]["messages"][-1]["content"]
    assert control["answer"] in turn
    assert len(evidence) == 5
    assert all(c["document_id"] == "refund-" + control["language"] for c in evidence)
    assert all(c["chunk_id"] in turn for c in evidence)


@pytest.mark.skipif(os.environ.get("RUN_REAL_JUDGE_CONTROLS") != "1", reason="Paid judge controls require RUN_REAL_JUDGE_CONTROLS=1")
async def test_real_adversarial_controls_all_fail():
    chat = OpenAIChat(Settings.from_env())
    verdicts = {}
    try:
        for control in CONTROLS:
            verdicts[control["id"]] = await judge(chat, control, control["answer"], evidence=evidence_for(control))
    finally:
        await chat.client.close()
    # A malformed judge response failing closed is not a successful semantic control.
    assert all(v["pass"] is False and v["unsupported_claims"] for v in verdicts.values()), verdicts
