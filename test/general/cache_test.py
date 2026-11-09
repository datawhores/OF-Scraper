from diskcache_community import Cache, Disk

planted_calls = []


def planted():
    planted_calls.append(True)
    return {"id": 1, "username": "planted"}


class Planted:
    def __reduce__(self):
        return (planted, ())


def test_planted_pickle_is_a_cache_miss(mocker, tmp_path):
    mocker.patch("sys.argv", ["ofscraper", "--config", str(tmp_path)])
    from ofscraper.data.api import profile
    from ofscraper.utils.cache import cache
    from ofscraper.utils.paths import common as common_paths

    mocker.patch.object(profile, "log")
    mocker.patch.object(cache, "cache", None)
    session = mocker.MagicMock()
    response = session.requests.return_value.__enter__.return_value
    response.status = 200
    response.json.return_value = {"id": 1, "username": "model"}
    with Cache(str(common_paths.getcachepath()), disk=Disk) as other_writer:
        other_writer.set("username_model", Planted())

    assert profile.scrape_profile_helper(session, "model")["username"] == "model"
    assert planted_calls == []
    session.requests.assert_called_once()
    cache.close()
