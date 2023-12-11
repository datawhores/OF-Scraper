import arrow

import ofscraper.constants as constants

DATE_NOW = arrow.now()
FORMAT = "YYYY-MM-DD"


class Model:
    def __init__(self, model):
        self._model = model

    # All media return from API dict
    @property
    def model(self):
        return self._model

    @property
    def name(self):
        return self._model["username"]

    @property
    def id(self):
        return self._model["id"]

    @property
    def avatar(self):
        return self._model["avatar"]

    @property
    def header(self):
        return self._model["header"]

    @property
    def sub_price(self):
        return self._model.get("currentSubscribePrice", {})

    @property
    def subscribed_data(self):
        if not self._model.get("subscribedByData"):
            return None
        return self._model.get("subscribedByData")

    @property
    def subscribed_expired_date(self):
        return self._model.get("subscribedByExpireDate")

    @property
    def regular_price(self):
        if not self.subscribed_data:
            return self.model.get("subscribePrice")
        return self.subscribed_data.get("regularPrice")

    @property
    def all_claimable_promo(self):
        return sorted(
            list(
                filter(
                    lambda x: x.get("canClaim") is True,
                    self._model.get("promotions") or [],
                )
            ),
            key=lambda x: x["price"],
        )

    @property
    def lowest_promo_claim(self):
        if len(self.all_claimable_promo) == 0:
            return None
        return self.all_claimable_promo[0]["price"]

    @property
    def all_promo(self):
        return sorted(
            self._model.get("promotions") or [],
            key=lambda x: x["price"],
        )

    @property
    def lowest_promo_all(self):
        if len(self.all_promo) == 0:
            return None
        return self.all_promo[0]["price"]

    @property
    def expired(self):
        if not self.subscribed_data:
            return None
        elif not self.subscribed_data.get("expiredAt"):
            return None
        return arrow.get(self.subscribed_data.get("expiredAt")).format(FORMAT)

    @property
    def final_expired(self):
        if not self.expired:
            return 0
        return self.expired

    @property
    def subscribed(self):
        if not self.subscribed_data:
            return None
        elif (
            not self.subscribed_data.get("subscribes")
            or len(self.subscribed_data.get("subscribes")) == 0
        ):
            return None
        return self.subscribed_data.get("subscribes")[0].get("startDate")

    @property
    def final_subscribed(self):
        if self.subscribed:
            return arrow.get(self.subscribed).float_timestamp
        else:
            return 0

    @property
    def renewed(self):
        if not self.subscribed_data:
            return None
        elif not self.subscribed_data.get("renewedAt"):
            return None
        return arrow.get(self.subscribed_data.get("renewedAt")).format(FORMAT)

    @property
    def active(self):
        if not self.subscribed_data or self.subscribed_expired_date:
            return False
        elif self.subscribed_data and self.subscribed_data["status"] == "Set to Expire":
            return True
        return (
            arrow.get(
                (self.subscribed_data or self.subscribed_expired_date).get("expiredAt")
            )
            > DATE_NOW
        )

    @property
    def last_seen(self):
        if not self._model.get("lastSeen"):
            return DATE_NOW.float_timestamp + constants.DAY_SECONDS
        else:
            return arrow.get(self._model["lastSeen"]).float_timestamp

    @property
    def isRealPerformer(self):
        return self._model.get("isRealPerformer")

    @property
    def isRestricted(self):
        return self._model.get("isRestricted")

    @property
    def final_current_price(self):
        if self.sub_price:
            return self.sub_price
        elif self.lowest_promo_claim:
            return self.lowest_promo_claim
        elif self.regular_price:
            return self.regular_price
        else:
            return 0

    @property
    def final_renewal_price(self):
        if self.lowest_promo_claim:
            return self.lowest_promo_claim
        elif self.regular_price:
            return self.regular_price
        else:
            return 0

    @property
    def final_regular_price(self):
        if self.regular_price:
            return self.regular_price
        else:
            return 0

    @property
    def final_promo_price(self):
        if self.lowest_promo_all:
            return self.lowest_promo_all
        elif self.regular_price:
            return self.regular_price
        return 0
