import pytest

import ofscraper.classes.of.posts as posts_
from ofscraper.classes.of.media import Media


def _media(post_data, responsetype=None):
    post = posts_.Post(post_data, 1, "model", responsetype=responsetype)
    media = Media({"id": 111}, 0, post)
    media.mpd = "https://cdn/manifest.mpd"
    return media


@pytest.mark.parametrize(
    "post_data,responsetype,kind",
    [
        ({"id": 5, "responseType": "post"}, None, "post"),
        ({"id": 5, "responseType": "message"}, None, "message"),
        ({"id": 5, "responseType": "post", "isArchived": True}, None, "post"),
        ({"id": 5}, "streams", "post"),
        # purchased tab: the raw responseType decides (#49)
        ({"id": 5, "responseType": "post"}, "Paid", "post"),
        ({"id": 5, "responseType": "message"}, "Paid", "message"),
        ({"id": 5}, "Paid", "message"),
    ],
)
def test_license_endpoint(post_data, responsetype, kind):
    url = _media(post_data, responsetype).license
    assert f"/users/media/111/drm/{kind}/5?" in url

