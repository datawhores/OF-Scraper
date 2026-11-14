"""Choosing and reading Fansly video streams.

A Fansly video offers up to three deliveries:
- direct: an MP4 file (``locationId`` 1), the media's own or one of its
  ``video/*`` variants. Fansly caps the media's own at 720 on the short side.
- HLS: a ``application/vnd.apple.mpegurl`` variant (``locationId`` 102).
- DASH: a ``application/dash+xml`` variant (``locationId`` 103).

The largest rendition wins; on a tie direct beats HLS, which beats DASH.
"""

import json
import os
import re
import statistics
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urljoin, urlparse

DIRECT, HLS, DASH = "direct", "hls", "dash"
_RANK = {DIRECT: 0, HLS: 1, DASH: 2}
HLS_MIME = "application/vnd.apple.mpegurl"
DASH_MIME = "application/dash+xml"
_LOCATION_IDS = {DIRECT: "1", HLS: "102", DASH: "103"}
_SIGNED = ("Policy", "Key-Pair-Id", "Signature")


class StreamError(Exception):
    """A stream that can't be downloaded; the message says why."""


class EmptyMasterPlaylist(StreamError):
    pass


class ProtectedStream(StreamError):
    pass


@dataclass
class Candidate:
    kind: str
    url: str
    width: int = 0
    height: int = 0
    cookies: dict = field(default_factory=dict)
    variant_id: str = None

    @property
    def area(self) -> int:
        return int(self.width or 0) * int(self.height or 0)

    @property
    def is_stream(self) -> bool:
        return self.kind in (HLS, DASH)


def _meta(obj) -> dict:
    raw = obj.get("metadata")
    if isinstance(raw, dict):
        return raw
    try:
        out = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


def cloudfront_cookies(location: dict) -> dict:
    """CloudFront cookies for a location: its ``metadata``, else its URL query."""
    meta = location.get("metadata")
    source = meta if isinstance(meta, dict) else {}
    if not all(source.get(k) for k in _SIGNED):
        source = dict(parse_qsl(urlparse(location.get("location") or "").query))
    return {f"CloudFront-{k}": source[k] for k in _SIGNED if source.get(k)}


def _location(obj, kind):
    for loc in obj.get("locations") or []:
        if str(loc.get("locationId")) == _LOCATION_IDS[kind] and loc.get("location"):
            return loc
    return None


def _size(obj) -> tuple:
    """Largest rendition size: ``metadata.variants`` if listed, else width/height."""
    best = (int(obj.get("width") or 0), int(obj.get("height") or 0))
    for r in _meta(obj).get("variants") or []:
        try:
            w, h = int(r.get("w") or 0), int(r.get("h") or 0)
        except (TypeError, ValueError, AttributeError):
            continue
        if w * h > best[0] * best[1]:
            best = (w, h)
    return best


def candidates(media: dict) -> list:
    """Downloadable deliveries of a raw Fansly Media object.

    A direct file is a ``locationId`` 1 MP4: the media's own, or a ``video/*``
    variant's (ready-made copies at other sizes; some videos have only
    these). Image variants are thumbnails and never count.
    """
    out = []
    if not media:
        return out

    def add(obj, kind):
        loc = _location(obj, kind)
        if not loc:
            return
        w, h = _size(obj) if kind != DIRECT else (obj.get("width"), obj.get("height"))
        out.append(Candidate(kind, loc["location"], int(w or 0), int(h or 0),
                             cloudfront_cookies(loc), str(obj.get("id") or "") or None))

    if (media.get("mimetype") or "").lower().startswith("video/"):
        add(media, DIRECT)
    for v in media.get("variants") or []:
        mime = (v.get("mimetype") or "").lower()
        if mime.startswith("video/"):
            add(v, DIRECT)
        elif mime == HLS_MIME:
            add(v, HLS)
        elif mime == DASH_MIME:
            add(v, DASH)
    return out


def select_best(media: dict):
    """Best candidate, or None when the media has nothing downloadable."""
    found = candidates(media)
    if not found:
        return None
    return max(found, key=lambda c: (c.area, -_RANK[c.kind]))


def has_direct(media) -> bool:
    """True when the media has a direct MP4 file the normal downloader can fetch."""
    return any(c.kind == DIRECT for c in candidates(media))


def raw_media(ele):
    """The raw Fansly Media object a scraped item carries, or None."""
    try:
        fansly = (ele.media or {}).get("fansly")
    except AttributeError:
        return None
    return fansly.get("media") if isinstance(fansly, dict) else None


def uses_stream(ele) -> bool:
    """True only for a Fansly item, on a Fansly run, whose best delivery is HLS or DASH."""
    raw = raw_media(ele)
    if not raw:
        return False
    from ofscraper import sites

    if not sites.is_fansly():
        return False
    best = select_best(raw)
    return bool(best and best.is_stream)


# URL schemes a stream, rendition or audio playlist may use. Tests add "http"
# for their local server; nothing else should change this.
ALLOWED_SCHEMES = ("https",)


def check_url(url: str) -> str:
    """``url`` if its scheme is allowed, else StreamError."""
    scheme = urlparse(url or "").scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise StreamError(f"stream URL scheme {scheme or 'none'!r} is not allowed")
    return url


def protocol_whitelist() -> str:
    """ffmpeg protocols for the allowed schemes: no file, pipe or other local reads."""
    protocols = list(ALLOWED_SCHEMES)
    if "https" in protocols:
        protocols.append("tls")
    return ",".join(protocols + ["tcp", "crypto"])


class MissingAudio(StreamError):
    pass


_ATTR = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', re.I)
_RES = re.compile(r"(\d+)x(\d+)", re.I)


def _attrs(line: str) -> dict:
    body = line.split(":", 1)[1] if ":" in line else ""
    return {k.upper(): v.strip('"') for k, v in _ATTR.findall(body)}


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def master_renditions(text: str, base_url: str) -> list:
    """(width, height, bandwidth, absolute url, audio group or None) for each
    rendition in a master playlist."""
    out = []
    lines = [line.strip() for line in (text or "").splitlines()]
    for i, line in enumerate(lines):
        if not line.upper().startswith("#EXT-X-STREAM-INF"):
            continue
        uri = next((x for x in lines[i + 1:] if x and not x.startswith("#")), None)
        if not uri:
            continue
        attrs = _attrs(line)
        res = _RES.fullmatch(attrs.get("RESOLUTION", ""))
        w, h = (int(res.group(1)), int(res.group(2))) if res else (0, 0)
        out.append((w, h, _int(attrs.get("BANDWIDTH")), urljoin(base_url, uri),
                    attrs.get("AUDIO") or None))
    return out


def _audio_url(text: str, base_url: str, group: str):
    """Audio playlist URL for an ``AUDIO`` group, or None when the audio is in
    the rendition itself (an ``#EXT-X-MEDIA`` without ``URI``, RFC 8216
    4.3.4.2.1). A group the playlist doesn't list is MissingAudio."""
    if not group:
        return None
    media = [
        a for a in (_attrs(line) for line in (text or "").splitlines()
                    if line.strip().upper().startswith("#EXT-X-MEDIA:"))
        if a.get("TYPE", "").upper() == "AUDIO" and a.get("GROUP-ID") == group
    ]
    if not media:
        raise MissingAudio(
            f"the chosen rendition names audio group {group!r}, which the playlist doesn't list"
        )
    pick = next((a for a in media if a.get("DEFAULT", "").upper() == "YES"), media[0])
    return urljoin(base_url, pick["URI"]) if pick.get("URI") else None


def best_rendition(text: str, base_url: str) -> tuple:
    """(video url, audio url or None) of the largest rendition. A plain media
    playlist is used as it is."""
    renditions = master_renditions(text, base_url)
    if renditions:
        w, h, bw, url, group = max(renditions, key=lambda r: (r[0] * r[1], r[2]))
        return url, _audio_url(text, base_url, group)
    if "#EXTINF" in (text or ""):
        return base_url, None
    raise EmptyMasterPlaylist("HLS master playlist lists no renditions; nothing to download")


def best_rendition_url(text: str, base_url: str) -> str:
    """URL of the largest rendition. A plain media playlist is used as it is."""
    return best_rendition(text, base_url)[0]


def expected_duration(media):
    """The video's length in seconds from Fansly's metadata, or None."""
    for obj in [media or {}] + list((media or {}).get("variants") or []):
        try:
            seconds = float(_meta(obj).get("duration") or 0)
        except (TypeError, ValueError):
            seconds = 0
        if seconds > 0:
            return seconds
    return None


# ffmpeg's HLS and DASH readers skip a segment they can't read (a 404, or a
# connection that stops part-way) and still exit 0, leaving a hole in the
# timestamps. A hole is a step between packets longer than both GAP_MIN and
# three normal steps; a clean stream, even one with a variable frame rate, has
# none. The copy must also cover the metadata length within
# max(SHORT_MIN, SHORT_SHARE of it), which catches a lost first or last segment.
GAP_MIN = 0.5
SHORT_MIN = 1.0
SHORT_SHARE = 0.005


def timeline(times) -> tuple:
    """(seconds covered, seconds missing in holes) for one stream's packet times."""
    ts = sorted(times)
    if len(ts) < 2:
        return 0.0, 0.0
    steps = [b - a for a, b in zip(ts, ts[1:])]
    step = statistics.median(steps)
    limit = max(GAP_MIN, 3 * step)
    missing = sum(d - step for d in steps if d > limit)
    return ts[-1] - ts[0] + step - missing, missing


def incomplete_reason(video_times, audio_times=None, expected=None):
    """Why a stream copy is incomplete, or None when it looks whole.

    ``expected`` is the metadata length; without it only holes are found.
    """
    tracks = [(name, times) for name, times in (("video", video_times), ("audio", audio_times))
              if times and len(times) >= 2]
    if not tracks:
        return "the copy has no video or audio"
    for name, times in tracks:
        missing = timeline(times)[1]
        if missing:
            return f"{missing:.1f}s of {name} is missing (a segment was skipped)"
    covered = timeline(tracks[0][1])[0]
    if expected and covered < expected - max(SHORT_MIN, SHORT_SHARE * expected):
        return f"the copy covers {covered:.1f}s, but the video is {expected:.1f}s"
    return None


class UnexpectedPlaylist(StreamError):
    """A media playlist the parallel downloader doesn't handle; ffmpeg fetches it instead."""


@dataclass
class LocalPlaylist:
    """A media playlist rewritten to point at local files.

    ``files`` is (url, local name) for every file to fetch, in playlist order,
    init segments included. ``text`` is the playlist with each URI replaced by
    its local name, for ffmpeg to read once the files are on disk.
    """

    text: str
    files: list


# extensions ffmpeg's HLS reader accepts for a segment by default
_SEGMENT_EXTS = (".ts", ".m4s", ".mp4", ".m4v", ".m4a", ".aac", ".mp3")
# tags that would change what the bytes are or where they come from
_REFUSED_TAGS = ("#EXT-X-BYTERANGE", "#EXT-X-STREAM-INF", "#EXT-X-I-FRAME-STREAM-INF",
                 "#EXT-X-MEDIA:", "#EXT-X-PART", "#EXT-X-PRELOAD-HINT", "#EXT-X-SKIP",
                 "#EXT-X-SESSION-KEY")


def _local_name(prefix, index, url, fmp4):
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    if ext not in _SEGMENT_EXTS:
        ext = ".m4s" if fmp4 else ".ts"
    return f"{prefix}{index:05d}{ext}"


def _checked(url):
    try:
        return check_url(url)
    except StreamError as e:
        raise UnexpectedPlaylist(str(e)) from e


def local_playlist(text: str, base_url: str, prefix: str) -> LocalPlaylist:
    """Plan a parallel download of a media playlist, or UnexpectedPlaylist.

    Only a complete (``#EXT-X-ENDLIST``), unencrypted playlist of whole files
    is planned: no byte ranges, keys other than NONE, partial segments or
    nested playlists. Init segments (``#EXT-X-MAP``) are fetched like segments.
    """
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != "#EXTM3U":
        raise UnexpectedPlaylist("the media playlist doesn't start with #EXTM3U")
    out, files, maps = [], [], {}
    ended = False
    for raw in lines:
        line = raw.strip()
        upper = line.upper()
        if not line:
            continue
        if upper.startswith(_REFUSED_TAGS):
            raise UnexpectedPlaylist(f"the media playlist has {line.split(':', 1)[0]}")
        if upper.startswith("#EXT-X-KEY"):
            method = _attrs(line).get("METHOD", "").upper()
            if method != "NONE":
                raise UnexpectedPlaylist(f"the media playlist is encrypted ({method or 'unknown'})")
            out.append(line)
        elif upper.startswith("#EXT-X-MAP"):
            attrs = _attrs(line)
            if not attrs.get("URI") or "BYTERANGE" in attrs:
                raise UnexpectedPlaylist("the media playlist has an init segment it can't fetch")
            url = _checked(urljoin(base_url, attrs["URI"]))
            if url not in maps:
                maps[url] = _local_name(f"{prefix}init", len(maps), url, True)
                files.append((url, maps[url]))
            out.append(f'#EXT-X-MAP:URI="{maps[url]}"')
        elif line.startswith("#"):
            if "URI=" in upper:
                raise UnexpectedPlaylist(f"the media playlist has {line.split(':', 1)[0]}")
            ended = ended or upper.startswith("#EXT-X-ENDLIST")
            out.append(line)
        else:
            url = _checked(urljoin(base_url, line))
            segments = len(files) - len(maps)
            name = _local_name(prefix, segments, url, bool(maps))
            files.append((url, name))
            out.append(name)
    if len(files) == len(maps):
        raise UnexpectedPlaylist("the media playlist lists no segments")
    if not ended:
        raise UnexpectedPlaylist("the media playlist has no #EXT-X-ENDLIST (live or incomplete)")
    return LocalPlaylist("\n".join(out) + "\n", files)


def local_join_command(ffmpeg, playlist, out_path, audio_playlist=None) -> list:
    """ffmpeg copy of local playlists (see ``local_playlist``) into one MP4,
    with the same output options as ``ffmpeg_command``. Only local files may
    be read."""
    opts = ["-protocol_whitelist", "file"]
    cmd = [str(ffmpeg), "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]
    cmd += opts + ["-i", str(playlist)]
    if audio_playlist:
        cmd += opts + ["-i", str(audio_playlist), "-map", "0:v", "-map", "1:a"]
    cmd += ["-c", "copy", "-f", "mp4", str(out_path)]
    return cmd


_PROTECTION = re.compile(r"<\s*(?:[\w-]+:)?ContentProtection\b")


def dash_is_protected(mpd_text: str) -> bool:
    return bool(_PROTECTION.search(mpd_text or ""))


def _one_line(value) -> str:
    # a line break in a value would start a new header in ffmpeg's requests
    return re.sub(r"[\r\n]", "", str(value))


def ffmpeg_command(ffmpeg, url, out_path, headers: dict, cookies: dict,
                   audio_url=None, rw_timeout=None) -> list:
    """ffmpeg stream copy of an HLS/DASH URL into one MP4.

    ``headers`` and ``cookies`` go on every HTTP request ffmpeg makes,
    playlist/manifest and segments alike. ``audio_url`` is a separate audio
    playlist, added as a second input and mapped next to the video.
    ``rw_timeout`` (seconds) ends the run when a connection stops sending.
    """
    headers = {_one_line(k): _one_line(v) for k, v in (headers or {}).items()}
    user_agent = headers.pop("User-Agent", None) or headers.pop("user-agent", None)
    lines = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    if cookies:
        lines += "Cookie: " + "; ".join(
            f"{_one_line(k)}={_one_line(v)}" for k, v in cookies.items()
        ) + "\r\n"
    # input options apply to the next -i only, so each input gets them all
    opts = ["-protocol_whitelist", protocol_whitelist()]
    if rw_timeout:
        opts += ["-rw_timeout", str(int(float(rw_timeout) * 1_000_000))]
    if user_agent:
        opts += ["-user_agent", user_agent]
    if lines:
        opts += ["-headers", lines]
    cmd = [str(ffmpeg), "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]
    cmd += opts + ["-i", url]
    if audio_url:
        cmd += opts + ["-i", audio_url, "-map", "0:v", "-map", "1:a"]
    cmd += ["-c", "copy", "-f", "mp4", str(out_path)]
    return cmd
