"""Tests for the Flask rate-limit decorator in web/rate_limit.py."""

from __future__ import annotations

from unittest.mock import patch

from flask import Flask

from local_deepwiki.web.rate_limit import rate_limit, reset_rate_limits


def _make_app() -> Flask:
    """Create a minimal Flask app with a rate-limited test endpoint."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/test")
    @rate_limit(requests_per_minute=3)
    def test_endpoint():
        return "ok"

    return app


class TestRateLimitDecorator:
    """Tests for the rate_limit() Flask decorator."""

    def setup_method(self):
        reset_rate_limits()

    def teardown_method(self):
        reset_rate_limits()

    def test_returns_normally_under_limit(self):
        """Decorated route returns 200 when under the request limit."""
        app = _make_app()
        with app.test_client() as client:
            for _ in range(3):
                resp = client.get("/test")
                assert resp.status_code == 200
                assert resp.data == b"ok"

    def test_returns_429_when_limit_exceeded(self):
        """Decorated route returns 429 after exceeding requests_per_minute."""
        app = _make_app()
        with app.test_client() as client:
            for _ in range(3):
                client.get("/test")

            resp = client.get("/test")
            assert resp.status_code == 429
            body = resp.get_json()
            assert body["error"] == "Rate limit exceeded"

    def test_old_timestamps_are_evicted(self):
        """Timestamps older than 60 seconds are evicted and do not count."""
        app = _make_app()
        with app.test_client() as client:
            # First three requests happen at t=0
            with patch("local_deepwiki.web.rate_limit.time", return_value=1000.0):
                for _ in range(3):
                    resp = client.get("/test")
                    assert resp.status_code == 200

            # Fourth request at t=0 should be rejected
            with patch("local_deepwiki.web.rate_limit.time", return_value=1000.0):
                resp = client.get("/test")
                assert resp.status_code == 429

            # After 61 seconds the old timestamps are evicted, so requests succeed
            with patch("local_deepwiki.web.rate_limit.time", return_value=1061.0):
                resp = client.get("/test")
                assert resp.status_code == 200

    def test_reset_rate_limits_clears_state(self):
        """reset_rate_limits() clears all accumulated timestamps."""
        app = _make_app()
        with app.test_client() as client:
            # Exhaust the limit
            for _ in range(3):
                client.get("/test")

            resp = client.get("/test")
            assert resp.status_code == 429

            # Reset should allow new requests
            reset_rate_limits()

            resp = client.get("/test")
            assert resp.status_code == 200

    def test_different_ips_tracked_independently(self):
        """Each IP address has its own request counter."""
        app = _make_app()
        with app.test_client() as client:
            # Exhaust the limit for 10.0.0.1
            for _ in range(3):
                resp = client.get(
                    "/test",
                    headers={"X-Forwarded-For": "10.0.0.1"},
                    environ_base={"REMOTE_ADDR": "10.0.0.1"},
                )
                assert resp.status_code == 200

            # 10.0.0.1 should be blocked
            resp = client.get(
                "/test",
                headers={"X-Forwarded-For": "10.0.0.1"},
                environ_base={"REMOTE_ADDR": "10.0.0.1"},
            )
            assert resp.status_code == 429

            # 10.0.0.2 should still be allowed
            resp = client.get(
                "/test",
                headers={"X-Forwarded-For": "10.0.0.2"},
                environ_base={"REMOTE_ADDR": "10.0.0.2"},
            )
            assert resp.status_code == 200
