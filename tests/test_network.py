import httpx
import pytest

from github_radar.network import request


def test_retry_then_success():
    calls = []
    waits = []

    def handler(req):
        calls.append(req)
        return httpx.Response(503 if len(calls) == 1 else 200, text="ok")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert request(client, "https://github.com/trending", sleep=waits.append).text == "ok"
    assert len(calls) == 2
    assert waits == [1]


def test_honor_retry_after():
    calls = []
    waits = []

    def handler(req):
        calls.append(req)
        return (
            httpx.Response(429, headers={"Retry-After": "3"})
            if len(calls) == 1
            else httpx.Response(200)
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        request(client, "https://api.github.com/repos/org/repo", sleep=waits.append)
    assert waits == [3]


def test_do_not_retry_permanent_errors():
    waits = []
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            request(client, "https://api.github.com/repos/org/missing", sleep=waits.append)
    assert waits == []


def test_bounded_retry_exhaustion():
    waits = []
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(503))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            request(client, "https://github.com/trending", sleep=waits.append)
    assert waits == [1, 2]


def test_long_retry_after_fails_without_ignoring_server():
    waits = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(429, headers={"Retry-After": "3600"})
        )
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            request(client, "https://api.github.com/repos/org/repo", sleep=waits.append)
    assert waits == []


def test_cross_origin_redirect_drops_custom_credentials():
    seen = []

    def handler(req):
        seen.append(req)
        if req.url.host == "api.github.com":
            return httpx.Response(302, headers={"Location": "https://github.com/elsewhere"})
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="redirect"):
            request(
                client,
                "https://api.github.com/repos/org/repo",
                headers={"Authorization": "Bearer test-token"},
            )
    assert len(seen) == 1
