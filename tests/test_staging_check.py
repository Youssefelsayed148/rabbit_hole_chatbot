import httpx
import pytest

from scripts.check_staging import check, check_url


@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "https://example.com/path", "https://example.com?x=1"])
def test_staging_requires_https_origin(url):
    with pytest.raises(ValueError):
        check_url(url)


def test_staging_checker_detects_missing_assets():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)), base_url="https://example.com") as client:
        with pytest.raises(RuntimeError, match="widget reachable"):
            check(client, "https://site.example", "https://denied.example", "public")
