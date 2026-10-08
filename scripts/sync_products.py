"""Save public EN/AR product descriptions; never embed prices, variants or inventory.
Run: python -m scripts.sync_products. Then re-ingest the approved corpus.
"""
import asyncio
import hashlib
import json
from datetime import datetime, timezone

from app.catalogue import API_BASE, STORE_BASE, list_products, product_detail
from app.config import Settings


async def sync():
    settings = Settings.from_env()
    base = settings.catalogue_base_url or API_BASE
    website = settings.source_base_url or STORE_BASE
    products = await list_products(base_url=base, website=website)
    stamp = datetime.now(timezone.utc).isoformat()
    records, chunks = [], []
    for product in products:
        for language in ("en", "ar"):
            detail = await product_detail(product.slug, language, base_url=base, website=website)
            if language == "ar" and not any("\u0600" <= c <= "\u06ff" for c in detail.description):
                raise ValueError("Missing original Arabic product description")
            document = "product-" + detail.slug + "-" + language
            sections = [(detail.name, detail.description)]
            sections.extend((s.key, s.value) for s in detail.specifications if s.key in {"Details", "التفاصيل"})
            if detail.productCare:
                sections.append(("Product care" if language == "en" else "العناية بالمنتج", detail.productCare))
            text = "\n\n".join(heading + "\n" + body for heading, body in sections)
            record = {"id": document, "slug": detail.slug, "name": detail.name, "language": language,
                      "title": detail.name, "source_url": website.rstrip("/") + "/collection",
                      "content_type": "product_description", "extracted_at": stamp,
                      "verification_status": "source_extracted", "extraction_method": "public_catalogue_api",
                      "source_api": base + "/v1/products/" + detail.slug + "?locale=" + language,
                      "content_hash": hashlib.sha256(text.encode()).hexdigest(), "text": text,
                      "notes": "Descriptive fields only. Original website language; Arabic awaits owner review. Prices, sizes, colours and stock are fetched live."}
            records.append(record)
            for index, (heading, body) in enumerate(sections, 1):
                chunks.append({**record, "chunk_id": document + "-" + str(index),
                               "parent_document_id": document, "heading": heading, "text": heading + "\n" + body})
    path = settings.data_dir / "chunks.jsonl"
    existing = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Only replace records owned by this sync; policy and brand sources are untouched.
    kept = [c for c in existing if c.get("extraction_method") != "public_catalogue_api"]
    path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in kept + chunks), encoding="utf-8")
    (settings.data_dir / "products.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    print(json.dumps({"products": len(products), "language_records": len(records), "new_description_chunks": len(chunks)}))


if __name__ == "__main__":
    asyncio.run(sync())
