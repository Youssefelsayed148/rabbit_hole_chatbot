"""Language detection and intent routing.

Rules (not an LLM call) decide the things that must be handled deterministically in code:
what needs LIVE commerce data, what needs an authenticated hand-off, and small talk.
Everything else goes to document retrieval.
"""
from __future__ import annotations

import re
from enum import IntFlag


class Intent(IntFlag):
    KNOWLEDGE = 1
    PRODUCT_LIVE = 2
    SHIPPING = 4
    ORDER_ACCOUNT = 8
    SMALLTALK = 16

    @property
    def label(self) -> str:
        names = {self.KNOWLEDGE: "knowledge", self.PRODUCT_LIVE: "product",
                 self.SHIPPING: "shipping", self.ORDER_ACCOUNT: "order", self.SMALLTALK: "smalltalk"}
        return ",".join(name for flag, name in names.items() if self & flag)


_AR = re.compile(r"[؀-ۿݐ-ݿ]")
_LATIN = re.compile(r"[A-Za-z]")


def detect_language(text: str, hint: str | None = None) -> str:
    """'ar' if the message is mostly Arabic script, else 'en'. Falls back to the hint for letter-less text."""
    ar, la = len(_AR.findall(text)), len(_LATIN.findall(text))
    if ar + la == 0:
        return hint if hint in ("ar", "en") else "en"
    return "ar" if ar >= la else "en"


_ORDER = re.compile(
    r"(\b(my|the)\s+order\b|\border\s+(status|number|tracking)\b|\btrack(ing)?\b.*\b(order|package|parcel|shipment)\b"
    r"|\bwhere\s+is\s+my\s+(order|package|parcel)\b|\bcancel\s+(my|the)\s+order\b"
    r"|طلبي|تتبع\s+(طلب|شحنة)|أين\s+طلب|الغاء\s+(ال)?طلب|إلغاء\s+(ال)?طلب)",
    re.I,
)
_SHIPPING = re.compile(
    r"(\bship(ping|ped|s)?\b|\bdeliver(y|ies|ed)?\b|\bcourier\b|شحن|توصيل|التوصيل|الشحن)", re.I
)
_PRODUCT = re.compile(
    r"(\bprice[sd]?\b|\bpricing\b|\bcost(s)?\b|\bhow\s+much\b|\bin\s+stock\b|\bstock\b|\bavailab(le|ility)\b"
    r"|\bsold\s*out\b|\bsizes?\b|\bcolou?rs?\b|\bdiscount|\bpromo|\bsale\b|\bnew\s+arrival|\blatest\b|\bwaitlist\b"
    r"|سعر|أسعار|اسعار|بكم|كم\s+(ثمن|سعر)|متوفر|المخزون|نفد|مقاس|المقاس|لون|الوان|ألوان|خصم|عرض)",
    re.I,
)
_BROWSE = re.compile(
    r"\b(?:show|browse|list|shop|recommend|see|view)\b.{0,60}\b(?:products?|collections?|designs?|swimwear|shorts|trunks)\b"
    r"|\bwhat\s+(?:products|collections|designs)\b|\b(?:catalogue|catalog)\b"
    r"|(?:اعرض|عرض|تصفح|أرني|ارني|رشح).{0,40}(?:المنتجات|منتجات|التشكيلات|المجموعات|التصاميم)"
    r"|ما هي (?:المنتجات|المجموعات|التشكيلات)", re.I,
)
_SMALLTALK = re.compile(
    r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|thanks?|thank\s+you|ok(ay)?|bye|"
    r"مرحبا|مرحباً|أهلا|اهلا|أهلاً|السلام\s+عليكم|صباح\s+الخير|مساء\s+الخير|شكرا|شكراً|تمام|مع\s+السلامة)[\s!.؟?،,]*$",
    re.I,
)

# A bare monetary question about shipping is not a product-price question.
_PRODUCT_DETAIL = re.compile(
    r"\b(product|swimwear|shorts|trunks|sizes?|stock|colou?rs?|sold\s*out|"
    r"discount\w*|promo\w*|sale|latest|waitlist|medium|large|small)\b"
    r"|مقاس|متوفر|المخزون|نفد|لون|ألوان|الوان|خصم|قطعة|منتج", re.I,
)
_SIZE_REQUEST = re.compile(
    r"(?<![\w'’])(?:S|M|L)\b|(?i:\b(?:xxs|xs|xl|xxl|xxxl)\b|"
    r"\b(?:small|medium|large)\b.*\b(?:left|available|stock)\b)"
)


def route(message: str) -> Intent:
    if _SMALLTALK.match(message):
        return Intent.SMALLTALK
    flags = Intent(0)
    if _ORDER.search(message):
        flags |= Intent.ORDER_ACCOUNT
    if _SHIPPING.search(message):
        flags |= Intent.SHIPPING
    product = _PRODUCT.search(message) or _SIZE_REQUEST.search(message) or _BROWSE.search(message)
    if product and (not flags & Intent.SHIPPING or _PRODUCT_DETAIL.search(message) or _SIZE_REQUEST.search(message)):
        flags |= Intent.PRODUCT_LIVE
    return flags or Intent.KNOWLEDGE


SMALLTALK_REPLY = {
    "en": "Welcome to Rabbit Hole. Ask me about the brand, our collection story, exchanges and refunds, or how to reach us.",
    "ar": "أهلاً بك في رابت هول. اسألني عن العلامة، قصة التشكيلة، سياسة الاستبدال والاسترجاع، أو طريقة التواصل معنا.",
}
