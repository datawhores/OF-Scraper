import datetime
import time
from collections import defaultdict
from ofscraper.db.operations_.media import get_media_ids_downloaded_model_sync


def _to_seconds(duration) -> float:
    if duration in (None, "", "N/A", "N\\A"):
        return 0.0
    if isinstance(duration, (int, float)):
        return float(duration)
    try:
        parts = str(duration).split(":")
        t = time.strptime(":".join(parts[-3:]), "%H:%M:%S")
        sec = datetime.timedelta(
            hours=t.tm_hour, minutes=t.tm_min, seconds=t.tm_sec
        ).total_seconds()
        if len(parts) > 3:
            sec += int(parts[0]) * 3600
        return float(sec)
    except Exception:
        return 0.0


def _fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0:00:00"
    return str(datetime.timedelta(seconds=int(round(seconds))))


def _fmt_all_cost(price: float, denominator: float, suffix: str = "") -> str:
    if denominator <= 0:
        return "N/A"
    return f"${price / denominator:.2f}{suffix}"


def _fmt_new_cost(
    price: float,
    all_denominator: float,
    new_denominator: float,
    suffix: str = "",
    is_unlocked: bool = False,
) -> str:
    if all_denominator <= 0:
        return "N/A"
    if is_unlocked:
        return "Unlocked"
    if new_denominator <= 0:
        return "All Dupes"
    return f"${price / new_denominator:.2f}{suffix}"


def _sort_new_cost(
    price: float,
    all_denominator: float,
    new_denominator: float,
    is_unlocked: bool = False,
) -> float:
    if all_denominator <= 0:
        return float("inf")
    if is_unlocked:
        return 0.0
    if new_denominator <= 0:
        return float("inf")
    return price / new_denominator


def _viewable(media) -> bool:
    # the media table's "Unlocked" test: OnlyFans' canView for the item, with
    # None (canView: null) read as locked
    return bool(getattr(media, "canview", False))


def build_post_centric_rows(posts: list, username: str, model_id: int, start_index: int = 1) -> list[dict]:
    """Aggregate Post objects into post-centric rows with All vs. New media economics."""
    try:
        downloaded_ids = get_media_ids_downloaded_model_sync(model_id=model_id, username=username) or set()
    except Exception:
        downloaded_ids = set()

    media_to_posts = defaultdict(set)
    unlocked_or_free_ids = set(downloaded_ids)

    for post in posts:
        for m in post.all_media:
            if m.id is None:
                continue
            media_to_posts[m.id].add(post.id)
            if _viewable(m):
                unlocked_or_free_ids.add(m.id)

    rows = []
    for post in posts:
        all_items = post.all_media
        if not all_items:
            continue

        row_num = len(rows) + 1
        price = float(post.price or 0.0)
        # free or bought is not enough: a free post of an expired
        # subscription can't be viewed either
        is_unlocked = all(_viewable(m) for m in all_items)

        # 1. All-Media Metrics
        total_media = len(all_items)
        all_photos = [m for m in all_items if (m.mediatype or "").lower() == "images"]
        all_videos = [m for m in all_items if (m.mediatype or "").lower() == "videos"]
        all_audios = [m for m in all_items if (m.mediatype or "").lower() == "audios"]

        total_photos = len(all_photos)
        total_videos = len(all_videos)
        total_audios = len(all_audios)
        total_vid_sec = sum(
            _to_seconds(getattr(m, "numeric_duration", None) or getattr(m, "duration", None))
            for m in all_videos
        )
        total_aud_sec = sum(
            _to_seconds(getattr(m, "numeric_duration", None) or getattr(m, "duration", None))
            for m in all_audios
        )

        # 2. Deduplicated New-Media Metrics
        owned_pool = downloaded_ids if is_unlocked else unlocked_or_free_ids
        seen_in_post = set()
        new_items = []
        for m in all_items:
            if m.id is None or m.id in seen_in_post:
                continue
            seen_in_post.add(m.id)
            if m.id in owned_pool:
                continue
            new_items.append(m)

        new_media = len(new_items)
        new_photos_list = [m for m in new_items if (m.mediatype or "").lower() == "images"]
        new_videos_list = [m for m in new_items if (m.mediatype or "").lower() == "videos"]
        new_audios_list = [m for m in new_items if (m.mediatype or "").lower() == "audios"]

        new_photos = len(new_photos_list)
        new_videos = len(new_videos_list)
        new_audios = len(new_audios_list)
        new_vid_sec = sum(
            _to_seconds(getattr(m, "numeric_duration", None) or getattr(m, "duration", None))
            for m in new_videos_list
        )
        new_aud_sec = sum(
            _to_seconds(getattr(m, "numeric_duration", None) or getattr(m, "duration", None))
            for m in new_audios_list
        )

        shared_bundles = sum(
            1 for m in new_items if len(media_to_posts.get(m.id, set())) > 1
        )

        present_types = set()
        if all_videos:
            present_types.add("Videos")
        if all_photos:
            present_types.add("Images")
        if all_audios:
            present_types.add("Audios")

        rows.append({
            "index": start_index + len(rows),
            "number": row_num,
            "download_cart": "[]" if is_unlocked else "Not Unlocked",
            "username": username,
            "unlocked": is_unlocked,
            "responsetype": post.responsetype.capitalize(),
            "post_date": post.formatted_date or "Probably Deleted",
            "total_cost": "Free" if price == 0 else f"${price:.2f}",
            "total_media": total_media,
            "new_media": new_media,
            "photos": total_photos,
            "new_photos": new_photos,
            "videos": total_videos,
            "new_videos": new_videos,
            "audios": total_audios,
            "new_audios": new_audios,
            "video_length": _fmt_duration(total_vid_sec),
            "new_video_length": _fmt_duration(new_vid_sec),
            "audio_length": _fmt_duration(total_aud_sec),
            "new_audio_length": _fmt_duration(new_aud_sec),
            "cost_per_vid_sec": _fmt_all_cost(price, total_vid_sec, "/s"),
            "new_cost_per_vid_sec": _fmt_new_cost(price, total_vid_sec, new_vid_sec, "/s", is_unlocked),
            "cost_per_photo": _fmt_all_cost(price, total_photos),
            "new_cost_per_photo": _fmt_new_cost(price, total_photos, new_photos, "", is_unlocked),
            "cost_per_audio": _fmt_all_cost(price, total_audios),
            "new_cost_per_audio": _fmt_new_cost(price, total_audios, new_audios, "", is_unlocked),
            "cost_per_audio_sec": _fmt_all_cost(price, total_aud_sec, "/s"),
            "new_cost_per_audio_sec": _fmt_new_cost(price, total_aud_sec, new_aud_sec, "/s", is_unlocked),
            "cost_per_media": _fmt_all_cost(price, total_media),
            "new_cost_per_media": _fmt_new_cost(price, total_media, new_media, "", is_unlocked),
            "shared_bundles": shared_bundles,
            "post_id": post.id,
            "text": post.db_sanitized_text or "",
            "_mediatypes": present_types,
            "_sort_total_cost": price,
            "_sort_video_length": total_vid_sec,
            "_sort_new_video_length": new_vid_sec,
            "_sort_audio_length": total_aud_sec,
            "_sort_new_audio_length": new_aud_sec,
            "_sort_cost_per_vid_sec": (price / total_vid_sec) if total_vid_sec > 0 else float("inf"),
            "_sort_new_cost_per_vid_sec": _sort_new_cost(price, total_vid_sec, new_vid_sec, is_unlocked),
            "_sort_cost_per_photo": (price / total_photos) if total_photos > 0 else float("inf"),
            "_sort_new_cost_per_photo": _sort_new_cost(price, total_photos, new_photos, is_unlocked),
            "_sort_cost_per_audio": (price / total_audios) if total_audios > 0 else float("inf"),
            "_sort_new_cost_per_audio": _sort_new_cost(price, total_audios, new_audios, is_unlocked),
            "_sort_cost_per_audio_sec": (price / total_aud_sec) if total_aud_sec > 0 else float("inf"),
            "_sort_new_cost_per_audio_sec": _sort_new_cost(price, total_aud_sec, new_aud_sec, is_unlocked),
            "_sort_cost_per_media": (price / total_media) if total_media > 0 else float("inf"),
            "_sort_new_cost_per_media": _sort_new_cost(price, total_media, new_media, is_unlocked),
        })

    return rows
