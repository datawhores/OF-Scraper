"""Posts that still have media to download, for scans that stop early.

A repeat scan may stop paging once a page holds nothing new, but only if no
post with media left to download is further down. Label scans and the Fansly
timeline and message scans read the same set from here.
"""

import ofscraper.utils.const as const
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,
    get_model_media_status,
)
from ofscraper.db.operations_.posts import get_deleted_post_ids


async def get_posts_missing_media(model_id, username):
    """
    Post ids that still have media to download, filtered the same way as the
    timeline's get_after: not downloaded, not deleted, not locked, and of a
    media type this run downloads.
    """
    rows = await get_model_media_status(model_id=model_id, username=username)
    if not rows:
        return set()
    downloaded = await get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )
    deleted = await get_deleted_post_ids(model_id=model_id, username=username)
    active_media = settings.get_settings().mediatypes or ["Videos", "Audios", "Images"]
    active_mapped = {const.MEDIA_ALIASES.get(m.lower(), m.lower()) for m in active_media}
    return {
        str(x.get("post_id"))
        for x in rows
        if x.get("downloaded") != 1
        and x.get("media_id") not in downloaded
        and x.get("post_id") not in deleted
        and x.get("unlocked") != 0
        and const.MEDIA_ALIASES.get(
            str(x.get("media_type", "")).lower(), str(x.get("media_type", "")).lower()
        )
        in active_mapped
    }
