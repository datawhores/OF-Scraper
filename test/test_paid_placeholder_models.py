import ofscraper.managers.model as model_manager
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.classes.of.models import Model


def _placeholder():
    return f"{of_env.getattr('DELETED_MODEL_PLACEHOLDER')}_123"


def test_placeholder_models_are_left_out_of_the_scrape_selection(monkeypatch):
    for module, name in [
        (model_manager.subtype, "subType"),
        (model_manager.price, "pricePaidFreeFilterHelper"),
        (model_manager.flags, "promoFilterHelper"),
        (model_manager.date_, "dateFilters"),
        (model_manager.other, "otherFilters"),
    ]:
        monkeypatch.setattr(module, name, lambda models: models)
    manager = model_manager.ModelManager()
    # what --scrape-paid adds for a deleted account, beside a real subscription
    manager._update_all_subs(
        [
            Model({"username": "model", "id": 1, "avatar": None}),
            Model({"username": _placeholder(), "id": _placeholder()}),
        ]
    )

    assert [m.name for m in manager._apply_filters()] == ["model"]
    assert manager.get_model(_placeholder()) is not None  # still there for the paid pass


def test_placeholder_model_has_no_avatar_or_header():
    placeholder = Model({"username": _placeholder(), "id": _placeholder()})
    assert placeholder.avatar is None and placeholder.header is None
