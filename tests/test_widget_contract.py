"""The widget's executable type declarations must match the API's required fields."""
import json
import re
from pathlib import Path

from app.main import ChatRequest, ChatResponse


def test_widget_contract_matches_service_schema():
    js = (Path(__file__).resolve().parents[1] / "widget.js").read_text(encoding="utf-8")
    schema = ChatResponse.model_json_schema()
    response = json.loads(re.search(r"const responseContract = (\{[^;]+\});", js)[1])
    source = json.loads(re.search(r"const sourceContract = (\{[^;]+\});", js)[1])
    assert response == {k: v["type"] for k, v in schema["properties"].items()}
    assert set(response) == set(schema["required"])
    source_schema = schema["$defs"]["Source"]
    assert source == {k: v["type"] for k, v in source_schema["properties"].items()}
    assert set(source) == set(source_schema["required"])
    assert 'matchesContract(d, responseContract)' in js
    assert 'matchesContract(s, sourceContract)' in js
    assert set(ChatRequest.model_fields) == {"message", "language", "conversation_id"}
