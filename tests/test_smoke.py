"""
Smoke test: imports + basic logic.
Run with: pytest tests/test_smoke.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_config_loads():
    from app.config import settings
    assert settings.chain == "solana"
    assert settings.monthly_cap_usd == 120.0
    assert settings.price_meteo == 0.01
    assert settings.price_fx == 0.02
    assert settings.price_transit == 0.02
    assert settings.price_news == 0.02
    assert settings.price_stocks == 0.05
    assert settings.price_github_stats == 0.02
    assert settings.bulk_pack_size == 10
    assert settings.bulk_pack_price_usd == 0.08
    assert settings.subscription_price_usd == 50.0


def test_price_for_endpoint():
    from app.config import settings
    assert settings.price_for("/api/v1/meteo") == 0.01
    assert settings.price_for("/api/v1/fx") == 0.02
    assert settings.price_for("/api/v1/stocks") == 0.05
    assert settings.price_for("/api/v1/nonexistent") == settings.price_meteo


def test_store_inmemory():
    from app.store import InMemoryStore
    async def run():
        s = InMemoryStore()
        await s.init()
        assert not await s.is_signature_seen("abc")
        await s.mark_signature("abc", ttl=3600)
        assert await s.is_signature_seen("abc")
        await s.add_earning(0.01)
        await s.add_earning(0.02)
        assert abs(await s.get_earnings_30d() - 0.03) < 1e-9
        # Bulk token
        t = await s.create_bulk_token(10, 86400)
        assert t.startswith("bulk_")
        assert await s.bulk_token_remaining(t) == 10
        assert await s.consume_bulk_token(t) is True
        assert await s.bulk_token_remaining(t) == 9
        # Subscription token
        st = await s.create_subscription_token(100, 86400)
        assert st.startswith("sub_")
        assert await s.subscription_token_remaining(st) == 100
        assert await s.consume_subscription_token(st) is True
        assert await s.subscription_token_remaining(st) == 99
        # Cache
        await s.cache_set("k1", {"x": 1}, ttl=3600)
        v = await s.cache_get("k1")
        assert v == {"x": 1}
        await s.close()
    asyncio.run(run())


def test_payment_challenge_shape():
    from app.payment import build_challenge
    c = build_challenge("/api/v1/meteo", 0.01)
    assert c["asset"] == "USDC"
    assert c["chain"] == "solana"
    assert c["amount_usd"] == 0.01
    assert c["amount_atomic"] == 10000


def test_receipt_header():
    from app.payment import make_receipt_header
    import base64, json
    receipt = {"signature": "abc", "amount_usd": 0.01}
    h = make_receipt_header(receipt)
    assert h.startswith("x402 ")
    decoded = base64.b64decode(h[5:]).decode()
    assert json.loads(decoded)["signature"] == "abc"


def test_llm_keypool():
    from app.llm import KeyPool
    async def run():
        pool = KeyPool(["k1", "k2", "k3"], cooldown_seconds=60)
        seen = []
        for _ in range(6):
            k = await pool.next()
            seen.append(k)
        assert seen == ["k1", "k2", "k3", "k1", "k2", "k3"]
        await pool.cool("k1")
        seen2 = []
        for _ in range(3):
            k = await pool.next()
            seen2.append(k)
        assert "k1" not in seen2
    asyncio.run(run())


def test_endpoints_importable():
    from app.endpoints import (
        billing, fx, github_stats, meteo, news, stocks, transit,
    )
    assert hasattr(meteo, "router")
    assert hasattr(fx, "router")
    assert hasattr(transit, "router")
    assert hasattr(news, "router")
    assert hasattr(stocks, "router")
    assert hasattr(github_stats, "router")
    assert hasattr(billing, "router")


def test_main_app():
    from main import app
    assert app.title == "The Factory v3"
    routes = {r.path for r in app.routes}
    assert "/api/v1/meteo" in routes
    assert "/api/v1/fx" in routes
    assert "/api/v1/transit" in routes
    assert "/api/v1/news" in routes
    assert "/api/v1/stocks" in routes
    assert "/api/v1/github-stats" in routes
    assert "/bulk/purchase" in routes
    assert "/subscription/purchase" in routes
    assert "/health" in routes
    assert "/dashboard" in routes
    assert "/stats" in routes


def test_helpers_safe_json():
    from app.endpoints.helpers import safe_json
    assert safe_json('{"a":1}') == {"a": 1}
    assert safe_json('```json\n{"a":1}\n```') == {"a": 1}
    assert safe_json('```\n{"a":1}\n```') == {"a": 1}


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
