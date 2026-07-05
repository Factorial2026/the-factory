"""Tests for The Factory client. Run with: pytest tests/"""
import pytest

from the_factory_client import Factory, FactoryError


def test_factory_requires_keypair_or_token():
    """Should raise if neither keypair nor token is provided."""
    with pytest.raises(FactoryError):
        Factory()


def test_factory_with_token_only():
    """Should construct OK with just a token (bulk/subscription mode)."""
    f = Factory(token="bulk_abc123")
    assert f.token == "bulk_abc123"
    assert f.keypair is None
    assert f.wallet_pubkey is None


def test_factory_with_invalid_private_key():
    """Should raise on invalid base58 key."""
    with pytest.raises(FactoryError):
        Factory(private_key_base58="not-a-real-key")


def test_payment_header_with_token():
    """Token-only mode should produce a base64 X-Payment header."""
    f = Factory(token="bulk_test_token")
    h = f._build_payment_header()
    assert "X-Payment" in h
    import base64, json
    decoded = json.loads(base64.b64decode(h["X-Payment"]).decode())
    assert decoded == {"token": "bulk_test_token"}


def test_payment_header_without_token():
    """Single-call mode should produce no header (server returns 402 first)."""
    # We need a valid base58 key here, but we can fake it with a 64-byte string
    import base58
    fake_key = base58.b58encode(b"0" * 64).decode()
    try:
        f = Factory(private_key_base58=fake_key)
        h = f._build_payment_header()
        assert h == {}
    except FactoryError:
        # If the fake key doesn't parse, skip this test
        pytest.skip("Fake key construction not supported by solders version")


def test_balance_with_no_token():
    """balance() with no token returns empty state."""
    import base58
    fake_key = base58.b58encode(b"0" * 64).decode()
    try:
        f = Factory(private_key_base58=fake_key)
        b = f.balance()
        assert b["token"] is None
    except FactoryError:
        pytest.skip("Fake key construction not supported")


if __name__ == "__main__":
    # Allow running without pytest
    import sys
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
