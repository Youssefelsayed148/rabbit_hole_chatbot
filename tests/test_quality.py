import json

import pytest

from scripts.eval import JUDGE_SYSTEM, judge
from scripts.fakes import FakeChat
from scripts.quality import run


async def test_paid_quality_requires_explicit_env_flag(monkeypatch):
    monkeypatch.delenv("RUN_REAL_QUALITY", raising=False)
    with pytest.raises(RuntimeError, match="RUN_REAL_QUALITY=1"):
        await run(None)


async def test_replacement_judge_uses_evidence_and_semantics():
    chat = FakeChat()
    chat.next_raw = json.dumps({"pass": True, "reason": "Conditional replacement shipping is supported.", "unsupported_claims": []})
    evidence = [{"chunk_id": "refund-en-5", "text": "If approved, the replacement product will be shipped within 5-7 working days."}]
    answer = "According to the refund policy, if a replacement is approved, the replacement product will be shipped within 5-7 working days after the product is received and inspected."
    verdict = await judge(chat, {"question": "How long does an approved replacement take to ship?", "required_behavior": "Replacement dispatch, not normal delivery."}, answer, evidence=evidence)
    assert verdict["pass"]
    turn = chat.calls[0]["messages"][-1]["content"]
    assert answer in turn and "refund-en-5" in turn
    assert "not keyword matching" in JUDGE_SYSTEM
    assert "guaranteed arrival" in JUDGE_SYSTEM


@pytest.mark.parametrize("raw", ['{"pass":"true","reason":"x","unsupported_claims":[]}',
                               '{"pass":true,"reason":"x","unsupported_claims":["Normal delivery takes 5 days"]}',
                               'not json'])
async def test_invalid_or_unsupported_judge_verdict_fails_closed(raw):
    chat = FakeChat()
    chat.next_raw = raw
    assert not (await judge(chat, {"question": "x", "required_behavior": "x"}, "x", evidence=[]))["pass"]
