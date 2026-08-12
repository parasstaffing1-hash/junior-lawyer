from app.services.security.rate_limit import FixedWindowCounter


def test_allows_up_to_the_limit_then_refuses() -> None:
    counter = FixedWindowCounter()
    key = ("1.2.3.4", "auth")

    for _ in range(3):
        allowed, _ = counter.hit(key, limit=3, window=60)
        assert allowed

    allowed, retry_after = counter.hit(key, limit=3, window=60)
    assert not allowed
    assert retry_after >= 1


def test_limits_are_tracked_per_key() -> None:
    counter = FixedWindowCounter()
    assert counter.hit(("1.1.1.1", "auth"), limit=1, window=60)[0]
    assert not counter.hit(("1.1.1.1", "auth"), limit=1, window=60)[0]
    # A different caller, and the same caller on a different budget, are unaffected.
    assert counter.hit(("2.2.2.2", "auth"), limit=1, window=60)[0]
    assert counter.hit(("1.1.1.1", "general"), limit=1, window=60)[0]


def test_window_expiry_frees_the_budget() -> None:
    counter = FixedWindowCounter()
    key = ("1.2.3.4", "general")
    assert counter.hit(key, limit=1, window=60)[0]
    assert not counter.hit(key, limit=1, window=60)[0]
    # A zero-length window means every earlier hit is already expired.
    assert counter.hit(key, limit=1, window=0)[0]
