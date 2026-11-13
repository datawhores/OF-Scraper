import ofscraper.utils.config.schema as schema
import ofscraper.utils.of_env.of_env as of_env


def test_getattr_returns_default_for_unknown_key():
    assert of_env.getattr("OFSC_TEST_NOT_A_KEY", "fallback") == "fallback"
    assert of_env.getattr("OFSC_TEST_NOT_A_KEY") is None


def test_getattr_prefers_known_value_over_default():
    assert of_env.getattr("DISCORD_DEFAULT", "fallback") == of_env.getattr(
        "DISCORD_DEFAULT"
    )


def test_config_rewrite_without_discord_key():
    # get_discord passed a default to getattr, which didn't take one, so
    # rebuilding a config that lacks "discord" raised TypeError
    new = schema.get_current_config_schema({"binary_options": {"ffmpeg": ""}})
    assert new["discord"] == of_env.getattr("DISCORD_DEFAULT")
