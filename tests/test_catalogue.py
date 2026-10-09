"""The adapter uses the public website schema, never saved inventory or guessed fields."""
import json
from pathlib import Path

import pytest

from app import catalogue


def summary():
    return {"id": "41", "slug": "dubai-above-mars", "name": "Dubai Above Mars",
            "price": 1300, "priceAfterVat": 1365, "currency": "AED", "image": "https://example.com/product.png", "inStock": True}


def detail(language="en"):
    return {**summary(), "description": "Original product description" if language == "en" else "وصف المنتج الأصلي",
            "images": [], "variants": [{"colorId": "white", "size": "M", "stock": 5}],
            "colors": [{"id": "white", "label": "White"}], "specifications": [{"key": "Details", "value": "Recycled polyester"}],
            "productCare": "Hand wash"}


async def test_live_schema_price_vat_variants_and_localized_detail(monkeypatch):
    calls = []
    async def fetch(path, **kwargs):
        calls.append(path)
        if "?page=" in path:
            return {"items": [summary()], "page": 1, "totalPages": 1}
        return detail("ar")
    monkeypatch.setattr(catalogue, "fetch_json", fetch)
    result = await catalogue.lookup("Show products", "ar", enabled=True)
    assert result.status is catalogue.CatalogueStatus.OK
    product = result.products[0]
    assert product["price"] == 1300 and product["price_includes_vat"] is True
    assert product["variants"][0]["available"] is True and product["in_stock"] is True
    assert "stock" not in product["variants"][0]
    assert calls[-1].endswith("?locale=ar")
    assert "وصف المنتج الأصلي" in catalogue.live_data_note(result)


async def test_disabled_catalogue_never_calls_network(monkeypatch):
    async def unexpected(*args, **kwargs):
        pytest.fail("network must not be called")
    monkeypatch.setattr(catalogue, "fetch_json", unexpected)
    assert (await catalogue.lookup("products", "en", enabled=False)).status is catalogue.CatalogueStatus.NOT_CONNECTED


@pytest.mark.parametrize("vat_field", ["original", "missing", "changed"])
async def test_customer_prices_never_include_added_vat(monkeypatch, vat_field):
    items = [summary(),
             {**summary(), "id": "35", "slug": "wonders-of-the-world", "name": "Wonders of the World",
              "price": 200, "priceAfterVat": 210},
             {**summary(), "id": "29", "slug": "glitched", "name": "Glitched",
              "price": 200, "priceAfterVat": 210}]
    for item in items:
        if vat_field == "missing":
            del item["priceAfterVat"]
        elif vat_field == "changed":
            item["priceAfterVat"] = "invalid VAT field"

    async def fetch(path, **kwargs):
        if "?page=" in path:
            return {"items": items, "page": 1, "totalPages": 1}
        item = next(item for item in items if f"/{item['slug']}?" in path)
        value = {**detail(), **item}
        if vat_field == "missing":
            del value["priceAfterVat"]
        return value

    monkeypatch.setattr(catalogue, "fetch_json", fetch)
    result = await catalogue.lookup("Show products and prices", "en", enabled=True)
    assert result.status is catalogue.CatalogueStatus.OK
    assert [product["price"] for product in result.products] == [1300, 200, 200]
    assert all(product["price_includes_vat"] is True for product in result.products)
    note = catalogue.live_data_note(result)
    assert "1365" not in json.dumps(result.products) and "210" not in json.dumps(result.products)
    assert "1365" not in note and "210" not in note
    assert "Prices include VAT." in note
    assert "Quote the price exactly as given in the product data." in note
    assert "Never add VAT or any tax on top, and never say VAT is extra." in note


@pytest.mark.parametrize("failure", ["network", "missing_price", "missing_detail_price", "invalid_stock", "wrong_slug", "missing_arabic"])
async def test_bad_or_unavailable_catalogue_never_means_sold_out(monkeypatch, failure):
    async def fetch(path, **kwargs):
        if failure == "network":
            raise TimeoutError("offline")
        if "?page=" in path:
            item = summary()
            if failure == "missing_price": del item["price"]
            if failure == "invalid_stock": item["inStock"] = "true"
            return {"items": [item], "page": 1, "totalPages": 1}
        value = detail()
        if failure == "missing_detail_price": del value["price"]
        if failure == "wrong_slug": value["slug"] = "wrong-product"
        return value
    monkeypatch.setattr(catalogue, "fetch_json", fetch)
    result = await catalogue.lookup("products", "ar", enabled=True)
    assert result.status is catalogue.CatalogueStatus.UNAVAILABLE and result.products == []


async def test_named_product_limits_detail_requests(monkeypatch):
    calls = []
    async def fetch(path, **kwargs):
        calls.append(path)
        if "?page=" in path:
            other = {**summary(), "id": "29", "slug": "glitched", "name": "Glitched"}
            return {"items": [summary(), other], "page": 1, "totalPages": 1}
        return detail()
    monkeypatch.setattr(catalogue, "fetch_json", fetch)
    result = await catalogue.lookup("Price of Dubai Above Mars", "en", enabled=True)
    assert len(result.products) == 1 and len(calls) == 2


async def test_endpoint_allowlist_blocks_other_hosts():
    with pytest.raises(ValueError, match="allowlisted"):
        await catalogue.fetch_json("/v1/products", base_url="https://evil.example")


def test_product_snapshot_contains_descriptions_only():
    path = Path(__file__).resolve().parents[1] / "data" / "products.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 6 and {r["language"] for r in records} == {"en", "ar"}
    assert all(r["text"].strip() for r in records)
    forbidden = {"price", "priceAfterVat", "inStock", "in_stock", "variants", "sizes", "colors", "stock"}
    assert all(not forbidden.intersection(r) for r in records)


async def test_named_arabic_product_filters_localized_cards(monkeypatch):
    async def fetch(path, **kwargs):
        if "?page=" in path:
            return {"items": [summary(), {**summary(), "id": "29", "slug": "glitched", "name": "Glitched"}], "page": 1, "totalPages": 1}
        if "/glitched?" in path:
            return {**detail("ar"), "id": "29", "slug": "glitched", "name": "خلل"}
        return {**detail("ar"), "name": "دبي فوق المريخ"}
    monkeypatch.setattr(catalogue, "fetch_json", fetch)
    result = await catalogue.lookup("كم سعر دبي فوق المريخ؟", "ar", enabled=True)
    assert result.status is catalogue.CatalogueStatus.OK
    assert [p["slug"] for p in result.products] == ["dubai-above-mars"]


@pytest.mark.parametrize('question,index', [
    ('Available sizes for the second product?', 1), ('What sizes for product 2?', 1),
    ('sizes for the 3rd one', 2), ('colours of the first product', 0),
    ('مقاسات المنتج الثاني', 1), ('مقاسات المنتج ٢', 1), ('ألوان المنتج الأخير', 2),
])
def test_product_references_use_saved_card_order(question, index):
    refs = [{'slug': 'dubai', 'name': 'Dubai'}, {'slug': 'wonders', 'name': 'Wonders'}, {'slug': 'glitched', 'name': 'Glitched'}]
    resolved, ambiguous = catalogue.resolve_reference(question, [refs])
    assert not ambiguous and resolved.endswith('Product: ' + refs[index]['slug'])


@pytest.mark.parametrize('question', ['sizes for the fourth product', 'What sizes are available?', 'Is it available?'])
def test_ambiguous_product_references_require_clarification(question):
    refs = [{'slug': 'dubai', 'name': 'Dubai'}, {'slug': 'wonders', 'name': 'Wonders'}]
    assert catalogue.resolve_reference(question, [refs])[1]


def test_single_product_focus_and_explicit_name_priority():
    refs = [{'slug': 'dubai', 'name': 'Dubai'}]
    assert catalogue.resolve_reference('What sizes are available?', [refs])[0].endswith('Product: dubai')
    assert catalogue.resolve_reference('Is it available?', [refs])[0].endswith('Product: dubai')
    assert catalogue.resolve_reference('What sizes does Glitched have?', [refs]) == ('What sizes does Glitched have?', False)
    assert catalogue.resolve_reference('Is Dubai available?', [refs]) == ('Is Dubai available?', False)
    assert catalogue.resolve_reference('sizes for the second product', [])[1]


async def test_removed_referenced_product_does_not_select_another(monkeypatch):
    async def fetch(path, **kwargs):
        assert '?page=' in path
        return {'items': [summary()], 'page': 1, 'totalPages': 1}
    monkeypatch.setattr(catalogue, 'fetch_json', fetch)
    result = await catalogue.lookup('sizes of the second product\nProduct: removed-product', 'en', enabled=True)
    assert result.status is catalogue.CatalogueStatus.OK and not result.products


@pytest.mark.parametrize('quantity,available', [(0, False), (1, True), (50, True)])
async def test_inventory_counts_never_reach_model_or_browser(monkeypatch, quantity, available):
    async def fetch(path, **kwargs):
        if '?page=' in path:
            return {'items': [summary()], 'page': 1, 'totalPages': 1}
        value = detail()
        value['variants'][0]['stock'] = quantity
        return value
    monkeypatch.setattr(catalogue, 'fetch_json', fetch)
    result = await catalogue.lookup('Dubai Above Mars sizes', 'en', enabled=True)
    assert result.status is catalogue.CatalogueStatus.OK
    assert result.products[0]['variants'] == [{'colorId': 'white', 'size': 'M', 'available': available}]
    assert '"stock":' not in json.dumps(result.products)
    assert '"stock":' not in catalogue.live_data_note(result)


@pytest.mark.parametrize('lang', ['en','ar'])
@pytest.mark.parametrize('available', [True,False])
def test_size_summary_uses_only_live_availability_without_counts(lang, available):
    product={'name':'Wonders', 'colors':[{'id':'blue','label':'Blue'}], 'variants':[{'colorId':'blue','size':'M','available':available}]}
    query='What sizes are available for the second product?' if lang=='en' else 'ما المقاسات المتاحة للمنتج الثاني؟'
    answer=catalogue.available_sizes_answer(query,[product],lang)
    assert 'Wonders' in answer and 'stock' not in answer
    if available:
        assert 'Blue' in answer and 'M' in answer
    else:
        assert 'Blue' not in answer and 'M' not in answer


def test_size_advice_and_incomplete_variants_are_not_treated_as_availability():
    assert catalogue.available_sizes_answer('What sizes fit my height?', [], 'en') is None
    assert catalogue.available_sizes_answer('What sizes are available?', [{'variants':[]}], 'en') is None
