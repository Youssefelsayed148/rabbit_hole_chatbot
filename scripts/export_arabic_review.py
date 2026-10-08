"""Export source text for review; never translates or changes production content."""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess

from app.pipeline import CATALOGUE_UNCONFIRMED, FALLBACK_TEXT
from app.router import SMALLTALK_REPLY

ROOT = Path(__file__).resolve().parents[1]


def widget_strings():
    code = """const fs=require('node:fs'), vm=require('node:vm');
const js=fs.readFileSync(process.argv[1],'utf8');
const literal=js.match(/const T = ([\\s\\S]*?);\\s*const reduceMotion/)[1];
process.stdout.write(JSON.stringify(vm.runInNewContext('('+literal+')')));"""
    result = subprocess.run(["node", "-e", code, str(ROOT / "widget.js")], check=True, capture_output=True, encoding="utf-8")
    return json.loads(result.stdout)


def build_rows(ui, quality):
    rows = []
    def add(kind, ref, source, arabic, status="UNREVIEWED", url=""):
        rows.append({"kind": kind, "source_reference": ref, "source_string_or_English_reference": source,
                     "Arabic_text": arabic, "corrections": "", "review_status": status, "source_url": url})

    for key, text in ui["ar"].items():
        if key == "chips":
            for index, (label, question) in enumerate(text):
                add("widget", f"widget.js T.ar.chips[{index}].label", ui["en"][key][index][0], label)
                add("widget", f"widget.js T.ar.chips[{index}].question", ui["en"][key][index][1], question)
        else:
            add("widget", f"widget.js T.ar.{key}", ui["en"][key], text)
    for name, strings in [("FALLBACK_TEXT", FALLBACK_TEXT), ("CATALOGUE_UNCONFIRMED", CATALOGUE_UNCONFIRMED), ("SMALLTALK_REPLY", SMALLTALK_REPLY)]:
        add("backend interface", name, strings["en"], strings["ar"])
    add("backend interface", "ChatService._email_suffix", " at {email}", " عبر {email}")

    chunks = [json.loads(line) for line in (ROOT / "data/chunks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {c["chunk_id"]: c for c in chunks}
    for chunk in chunks:
        if chunk["language"] != "ar":
            continue
        english = by_id.get(chunk["chunk_id"].replace("-ar-", "-en-"), {})
        for field in ("title", "heading", "text"):
            add("content chunk", f"{chunk['chunk_id']}.{field}", english.get(field, ""), chunk[field],
                "UNREVIEWED ARABIC; source status=" + chunk["verification_status"], chunk["source_url"])

    # Include full source documents too: dates/headings may not have separate chunks.
    docs = [json.loads(line) for line in (ROOT / "data/documents.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_doc = {doc["id"]: doc for doc in docs}
    for doc in docs:
        if doc["language"] == "ar":
            english = by_doc.get(doc["id"].replace("-ar", "-en"), {})
            add("full source document", doc["id"], english.get("text", ""), doc["text"],
                "UNREVIEWED ARABIC; source status=" + doc["verification_status"], doc["source_url"])

    cases = {row["id"]: row for row in quality}
    counterpart = {"case-10": "case-3", "case-11": "case-4"}
    for row in quality:
        if row["language"] == "ar":
            english = cases.get(counterpart.get(row["id"]), {})
            add("real evaluation answer", row["id"] + " question=" + row["question"] + " cited=" + ','.join(row["cited_chunks"]),
                english.get("answer", ""), row["answer"], "UNREVIEWED ARABIC; eval=" + ("PASS" if row["pass"] else "FAIL"))
    demo = (ROOT / "demo.html").read_text(encoding="utf-8")
    for index, match in enumerate(re.finditer(r"'((?:\\.|[^'\\])*)'", demo)):
        text = match[1]
        if re.search(r"[\u0600-\u06ff]", text):
            add("offline demo only", f"demo.html literal {index}", "Original mock text; not a production-model answer", text.replace("\\n", "\n"))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality", type=Path, default=ROOT / "docs/quality-results.json")
    parser.add_argument("--out", type=Path, default=ROOT / "docs/arabic-review.csv")
    args = parser.parse_args()
    rows = build_rows(widget_strings(), json.loads(args.quality.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8 BOM supports spreadsheet applications; quoting preserves Arabic and multiline text.
    with args.out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} review rows to {args.out}")


if __name__ == "__main__":
    main()
