"""Chat bubbles must stay short and readable; product cards already show image, price, stock and link."""
from app.pipeline import tidy_answer
from app.prompts import SYSTEM_PROMPT

SCREENSHOT_REPLY = """Here are the available products:
### 1. Danat Al Dunya

* Price: 1300 AED
* Description: A tribute to Dubai, embodying creativity and ambition.
* Available Sizes (White):
  * S
  * M
* Image: ![Danat Al Dunya](https://res.cloudinary.com/x/y.png)
* More Info: [View Product](https://rabbithole.ae/collection)

### 2. Harmony

* Price: Currently unavailable (no price listed)
"""


def test_markdown_dump_becomes_plain_readable_text():
    out = tidy_answer(SCREENSHOT_REPLY, cards_shown=True)
    assert "![" not in out and "](" not in out and "cloudinary" not in out
    assert "###" not in out and "View Product" not in out and "rabbithole.ae/collection" not in out
    assert "**1. Danat Al Dunya**" in out and "**2. Harmony**" in out
    assert "\n  *" not in out and "\n  -" not in out          # nested bullets flattened
    assert "- S\n- M" in out
    assert "Image:" not in out and "More Info" not in out
    assert "\n\n\n" not in out


def test_links_kept_as_text_with_url_when_no_cards():
    out = tidy_answer("See the [refund policy](https://rabbithole.ae/refund) for details.", cards_shown=False)
    assert out == "See the refund policy (https://rabbithole.ae/refund) for details."
    assert tidy_answer("See the [refund policy](https://rabbithole.ae/refund).", cards_shown=True) == "See the refund policy."


def test_plain_answers_and_arabic_are_unchanged():
    plain = "Our refund window is 14 days.\n\n- Items must be unworn.\n- Tags must be attached."
    assert tidy_answer(plain, cards_shown=False) == plain
    ar = "هذه المنتجات المتاحة:\n\n- دانة الدنيا\n- هارموني"
    assert tidy_answer(ar, cards_shown=True) == ar
    assert tidy_answer("Email info@rabbithole.ae for help.", cards_shown=False) == "Email info@rabbithole.ae for help."


def test_never_returns_empty():
    assert tidy_answer("![x](https://a.b/c.png)", cards_shown=True) == "![x](https://a.b/c.png)"


def test_prompt_tells_model_not_to_repeat_product_cards():
    assert "Product cards" in SYSTEM_PROMPT and "no markdown images" in SYSTEM_PROMPT
