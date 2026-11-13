import arrow
import pytest

from ofscraper.classes.of.models import Model


def _model(status, expires_in_days, renewed=None):
    return Model(
        {
            "id": 1,
            "username": "model",
            "subscribedByData": {
                "status": status,
                "expiredAt": arrow.now().shift(days=expires_in_days).isoformat(),
                "renewedAt": renewed,
            },
        }
    )


@pytest.mark.parametrize(
    "status,days,active",
    [
        # cancelled but paid until a future date is still scraped (#6)
        ("Set to Expire", 20, True),
        (None, 20, True),
        # within the grace window after expiry (EXPIRED_GRACE_DEFAULT is 1 day);
        # exactly -1 races the boundary
        (None, -0.5, True),
        # long expired
        (None, -30, False),
    ],
)
def test_active(status, days, active):
    assert _model(status, days).active is active


def test_renewed_is_active():
    assert _model(None, -30, renewed="2026-01-01T00:00:00+00:00").active is True


def test_no_subscription_data_uses_expire_date():
    future = arrow.now().shift(days=5).isoformat()
    assert Model({"id": 1, "subscribedByExpireDate": future}).active is True
    assert Model({"id": 1}).active is False
