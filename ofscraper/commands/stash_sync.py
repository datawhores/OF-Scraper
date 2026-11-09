"""Copy downloaded media's OnlyFans and Fansly details into Stash; preview unless --apply.

Reads model databases (user_data.db) offline and talks only to Stash's GraphQL
API. Each downloaded file is looked up in Stash by path; empty fields are filled
in and the creator, studio and tags are added. Fansly posts and messages also
get a gallery each. Nothing set in Stash is overwritten or removed, so running
it again changes nothing.
"""

import argparse
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from contextlib import closing
from pathlib import Path

from ofscraper.sites.fansly.constants import ORIGIN as FANSLY_ORIGIN
from ofscraper.sites.fansly.normalize import hashtags

DEFAULT_URL = "http://localhost:9999/graphql"
ONLYFANS, FANSLY = "onlyfans", "fansly"
# per site: default studio and tag prefix, and the studio's and a creator's links
SITES = {
    ONLYFANS: {
        "label": "OnlyFans",  # disambiguation for a performer whose name Stash would refuse
        "studio": "OnlyFans",
        "tag_prefix": "OnlyFans ",
        "studio_url": "https://onlyfans.com",
        "creator_url": "https://onlyfans.com/{}",
    },
    FANSLY: {
        "label": "Fansly",
        "studio": "Fansly",
        "tag_prefix": "Fansly ",
        "studio_url": FANSLY_ORIGIN,
        "creator_url": FANSLY_ORIGIN + "/{}",
    },
}
# @username in a Fansly caption; not part of an e-mail address
MENTION_RE = re.compile(r"(?<![\w.@])@([A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?)")
# Tables holding a post's text, in order of preference
TEXT_TABLES = ("posts", "messages", "stories", "others", "products")
# OnlyFans media types Stash indexes, and the query that finds them
KINDS = {"Videos": "scene", "Images": "image"}


class StashError(Exception):
    pass


class StashClient:
    def __init__(self, url=DEFAULT_URL, api_key=None, timeout=60):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

    def call(self, query, variables=None, retries=5, wait=1.0):
        # Stash's database is briefly locked while it scans or generates
        # previews; those errors pass, so retry them
        for attempt in range(retries + 1):
            try:
                return self._call(query, variables)
            except StashError as e:
                if "database is locked" not in str(e) or attempt == retries:
                    raise
                time.sleep(wait * (attempt + 1))

    def _call(self, query, variables=None):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["ApiKey"] = self.api_key
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        request = urllib.request.Request(self.url, body, headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as e:
            raise StashError(f"{self.url}: HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
        except urllib.error.URLError as e:
            raise StashError(f"can't reach Stash at {self.url}: {e.reason}") from e
        if data.get("errors"):
            raise StashError("; ".join(err.get("message", str(err)) for err in data["errors"]))
        return data["data"]


# --- reading model databases ---------------------------------------------


def find_databases(paths):
    """Expand directories (e.g. a profile's .data) into their user_data.db files."""
    found = []
    for p in map(Path, paths):
        if p.is_dir():
            found.extend(sorted(p.rglob("user_data.db")))
        elif p.is_file():
            found.append(p)
        else:
            raise FileNotFoundError(p)
    return found


def clean_text(text):
    """OnlyFans captions are HTML; return plain text with line breaks kept."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def make_title(text, limit=100):
    first = next((line for line in text.splitlines() if line.strip()), "")
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def connect(database):
    uri = Path(database).resolve().as_uri()
    return sqlite3.connect(f"{uri}?mode=ro", uri=True)


def site_of(database):
    """The site a database belongs to: Fansly databases carry a site flag."""
    with closing(connect(database)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_flags'").fetchone():
            return "onlyfans"
        row = conn.execute("SELECT flag_value FROM schema_flags WHERE flag_name = 'site'").fetchone()
    return str(row[0]).lower() if row and row[0] else "onlyfans"


def read_model(database, site=ONLYFANS):
    """Return the model's username and its downloaded media, grouped by file path."""
    with closing(connect(database)) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        username = None
        if "profiles" in tables:
            row = conn.execute("SELECT username FROM profiles ORDER BY id DESC LIMIT 1").fetchone()
            username = row[0] if row else None

        # a bought message is saved in posts too, under the message's ID
        message_ids = (
            {str(r[0]) for r in conn.execute("SELECT post_id FROM messages")} if "messages" in tables else set()
        )
        texts = {}
        for table in reversed(TEXT_TABLES):  # earlier tables win
            if table in tables:
                for post_id, text in conn.execute(f"SELECT post_id, text FROM {table}"):
                    if text or str(post_id) not in texts:
                        texts[str(post_id)] = (table, text)

        media_columns = columns(conn, "medias")
        date_col = "posted_at" if "posted_at" in media_columns else "created_at"
        preview_col = "preview" if "preview" in media_columns else "0"
        rows = conn.execute(
            f"SELECT media_id, post_id, directory, filename, api_type, media_type, "
            f"COALESCE({date_col}, created_at), {preview_col} FROM medias "
            "WHERE downloaded = 1 AND filename IS NOT NULL AND filename != ''"
        ).fetchall()

    files = {}
    for media_id, post_id, directory, filename, api_type, media_type, posted, preview in rows:
        path = os.path.join(directory or "", filename)
        entry = files.setdefault(
            path,
            {"path": path, "media_type": media_type, "api_types": set(), "posts": [],
             "media_ids": {}, "sources": {}, "preview": False},
        )
        if api_type:
            entry["api_types"].add(api_type)
        post_id = str(post_id) if post_id is not None else None
        entry["posts"].append((posted or "", post_id))
        entry["media_ids"].setdefault(post_id, str(media_id) if media_id is not None else None)
        if api_type:
            entry["sources"].setdefault(post_id, set()).add(api_type)
        entry["preview"] = entry["preview"] or bool(preview)

    for entry in files.values():
        if site == FANSLY:
            entry["meta"] = describe_fansly(entry, texts, username)
            entry["galleries"] = fansly_galleries(entry, texts, username)
        else:
            entry["meta"] = describe(entry, texts, username, message_ids)
    return username, list(files.values())


def describe(entry, texts, username, message_ids=frozenset()):
    """The Stash fields this file should have, from its earliest post with text."""
    posts = sorted(entry["posts"])
    posted, post_id = posts[0]
    table, text = None, ""
    for _, pid in posts:
        table, raw = texts.get(pid, (None, None))
        if raw:
            post_id, text = pid, clean_text(raw)
            break
    # Profile pictures and headers store a hash where the post ID would be
    code = post_id if post_id and post_id.isdigit() else None
    meta = {"code": code, "details": text or None, "title": make_title(text) or None}
    if re.match(r"\d{4}-\d{2}-\d{2}", posted or ""):
        meta["date"] = posted[:10]
    # A bought message has no public page, and a purchase alone can't be told
    # apart from one, so neither gets a link
    is_post = post_id not in message_ids and not bought_only(entry, post_id)
    if table == "posts" and is_post and username and code:
        meta["url"] = f"https://onlyfans.com/{post_id}/{username}"
    return meta


def plain_text(text):
    """Fansly captions are plain text; trim each line."""
    return "\n".join(line.strip() for line in (text or "").splitlines()).strip()


def mentions(text, username=None):
    """@usernames in a caption, in order, without repeats or the creator."""
    out = []
    seen = {(username or "").lower()}
    for name in MENTION_RE.findall(text or ""):
        if name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def bought_only(entry, post_id):
    """Whether this file was recorded under this ID only as a purchase.

    Purchases are saved in the posts table, with responsetype Paid; on
    Fansly their ID is the bought item's own, and on OnlyFans a bought
    message keeps the message's ID. Neither is a post with a page.
    """
    return entry["sources"].get(post_id) == {"Paid"}


def fansly_post_meta(post_id, posted, texts, username, bought=False):
    """Fields shared by a Fansly file and its post's gallery."""
    table, raw = texts.get(post_id, (None, None))
    text = plain_text(raw)
    meta = {"details": text or None, "title": make_title(text) or None}
    if re.match(r"\d{4}-\d{2}-\d{2}", posted or ""):
        meta["date"] = posted[:10]
    # A message's page needs its conversation id, which the database doesn't keep
    if table == "posts" and not bought and post_id and post_id.isdigit():
        meta["url"] = f"{FANSLY_ORIGIN}/post/{post_id}"
    meta["hashtags"] = hashtags(raw)
    meta["mentions"] = mentions(raw, username)
    return meta


def describe_fansly(entry, texts, username):
    """A Fansly file's fields, from its earliest post with text; the code is the media ID."""
    posts = sorted(entry["posts"])
    posted, post_id = posts[0]
    for when, pid in posts:
        if texts.get(pid, (None, None))[1]:
            posted, post_id = when, pid
            break
    meta = fansly_post_meta(post_id, posted, texts, username, bought_only(entry, post_id))
    meta["code"] = entry["media_ids"].get(post_id)
    return meta


def fansly_galleries(entry, texts, username):
    """One gallery per Fansly post or message holding this file, keyed by its ID.

    Purchases aren't posts (their "post ID" is the item's own ID), so they get none.
    """
    out = {}
    for posted, post_id in sorted(entry["posts"]):
        table = texts.get(post_id, (None, None))[0]
        if table not in ("posts", "messages") or post_id in out or bought_only(entry, post_id):
            continue
        meta = fansly_post_meta(post_id, posted, texts, username)
        meta["code"] = post_id
        meta["title"] = meta["title"] or f"Fansly {table[:-1]} {post_id}"
        meta["sources"] = sorted(entry["sources"].get(post_id, ()))
        out[post_id] = meta
    return out


# --- Stash -------------------------------------------------------------------

FIELDS = "id title details date code urls organized studio { id } performers { id } tags { id } galleries { id }"
GALLERY_FIELDS = "id title details date code urls organized studio { id } performers { id } tags { id }"
FIND_GALLERY = (
    "query($code: String!) { findGalleries(gallery_filter: {code: {value: $code, modifier: EQUALS}}, "
    f"filter: {{per_page: -1}}) {{ galleries {{ {GALLERY_FIELDS} }} }} }}"
)
FIND = {
    "scene": f"query($path: String!) {{ findScenes(scene_filter: {{path: {{value: $path, modifier: EQUALS}}}}, filter: {{per_page: -1}}) {{ scenes {{ {FIELDS} files {{ path }} }} }} }}",
    "image": f"query($path: String!) {{ findImages(image_filter: {{path: {{value: $path, modifier: EQUALS}}}}, filter: {{per_page: -1}}) {{ images {{ {FIELDS} visual_files {{ ... on ImageFile {{ path }} ... on VideoFile {{ path }} }} }} }} }}",
}
UPDATE = {
    "scene": "mutation($input: SceneUpdateInput!) { sceneUpdate(input: $input) { id } }",
    "image": "mutation($input: ImageUpdateInput!) { imageUpdate(input: $input) { id } }",
    "gallery": "mutation($input: GalleryUpdateInput!) { galleryUpdate(input: $input) { id } }",
}
CREATE_GALLERY = "mutation($input: GalleryCreateInput!) { galleryCreate(input: $input) { id } }"


def find_gallery(client, code, url=None):
    """The Fansly gallery with this code (a post or message ID), in any studio, or None.

    The user may move a gallery to another studio, or run with another
    --studio, so the studio isn't checked. A gallery is only taken if it has
    no links or a fansly.com one, so one from another site with the same code
    is left alone. One with this post's link is preferred.
    """

    def fansly_or_unlinked(gallery):
        hosts = [urllib.parse.urlsplit(u or "").hostname or "" for u in gallery.get("urls") or []]
        return not hosts or any(h == "fansly.com" or h.endswith(".fansly.com") for h in hosts)

    found = [
        g for g in client.call(FIND_GALLERY, {"code": code})["findGalleries"]["galleries"]
        if g.get("code") == code and fansly_or_unlinked(g)
    ]
    return next((g for g in found if url and url in (g.get("urls") or [])), found[0] if found else None)


def find_item(client, kind, path):
    data = client.call(FIND[kind], {"path": path})
    items = data["findScenes"]["scenes"] if kind == "scene" else data["findImages"]["images"]
    for item in items:
        files = item.get("files") or item.get("visual_files") or []
        if any(f.get("path") == path for f in files):
            return item
    return None


def find_or_create(client, entity, name, apply, extra=None, disambiguation=None):
    """Return the ID of the studio, tag or performer with this exact name.

    In preview mode a missing one isn't created and None is returned.
    disambiguation is given to a new performer whose name Stash would
    otherwise refuse (see below).
    """
    plural = {"studio": "Studios", "tag": "Tags", "performer": "Performers"}[entity]
    alias_field = "alias_list" if entity == "performer" else "aliases"

    def lookup(field):
        query = (
            f"query($name: String!) {{ find{plural}({entity}_filter: {{{field}: {{value: $name, modifier: EQUALS}}}}) "
            f"{{ {plural.lower()} {{ id name {alias_field} }} }} }}"
        )
        return client.call(query, {"name": name})[f"find{plural}"][plural.lower()]

    # Stash names are unique ignoring case (and a tag's aliases count too), so
    # an existing one in another case or under an alias is the one to use;
    # creating it would be refused
    key = name.lower()
    found = lookup("name")
    for match in found:
        if match["name"] == name:
            return match["id"]
    for match in found:
        if (match.get("name") or "").lower() == key:
            return match["id"]
    aliased = lookup("aliases")
    for match in aliased:
        if key in [(a or "").lower() for a in match.get(alias_field) or []]:
            return match["id"]
    # Stash's EQUALS is SQL LIKE, so "_" and "%" in a name match any character,
    # and it checks a new performer's or studio's name that way: "pal_one" is
    # refused while "Pal One" exists. A performer can be told apart with a
    # disambiguation, and is then found again by its exact name; a studio can't,
    # so that's an error in preview too.
    if entity == "studio" and (found or aliased):
        clash = ", ".join(repr(m["name"]) for m in found + aliased)
        raise StashError(
            f"Stash won't create the studio {name!r}: it reads '_' and '%' in a name as wildcards, "
            f"so the name clashes with {clash}. Use another --studio, or that studio's name."
        )
    if not apply:
        return None
    extra = dict(extra or {})
    if entity == "performer" and found and disambiguation:
        extra["disambiguation"] = disambiguation
    kind = entity[0].upper() + entity[1:]
    mutation = f"mutation($input: {kind}CreateInput!) {{ {entity}Create(input: $input) {{ id }} }}"
    return client.call(mutation, {"input": {"name": name, **extra}})[f"{entity}Create"]["id"]


def plan(item, meta, performer_ids, studio_id, tag_ids, organized=False, gallery_ids=()):
    """Changes to make to a Stash item: empty fields filled, IDs added.

    An ID of None (not created yet in preview mode) still counts as a change.
    """
    changes = {}
    for field in ("title", "details", "date", "code"):
        if meta.get(field) and not item.get(field):
            changes[field] = meta[field]
    urls = item.get("urls") or []
    if meta.get("url") and meta["url"] not in urls:
        changes["urls"] = urls + [meta["url"]]
    if not item.get("studio"):
        changes["studio_id"] = studio_id
    for field, key, ids in (("performers", "performer_ids", performer_ids), ("tags", "tag_ids", tag_ids),
                            ("galleries", "gallery_ids", gallery_ids)):
        have = [x["id"] for x in item.get(field) or []]
        new = [x for x in dict.fromkeys(ids) if x not in have]
        if new:
            changes[key] = have + new
    if organized and not item.get("organized"):
        changes["organized"] = True
    return changes


def is_windows_path(path):
    """A drive (C:) or UNC (\\\\server\\share) path, on any OS."""
    return bool(re.match(r"[A-Za-z]:", path)) or path[:2] in ("\\\\", "//", "\\/", "/\\")


def windows_key(path):
    # Windows paths ignore case, and either slash separates folders
    return path.replace("/", "\\").lower()


def map_path(path, mappings):
    # Either separator ends the prefix, whatever the OS: the database may hold
    # Windows paths while this runs elsewhere, e.g. beside Stash in Docker
    for local, remote in mappings:
        prefix = local.rstrip("\\/")
        head, rest = path[: len(prefix)], path[len(prefix):]
        if is_windows_path(prefix):
            same = windows_key(head) == windows_key(prefix)
        else:
            same = head == prefix
        if same and (rest == "" or rest[0] in "\\/"):
            mapped = remote.rstrip("\\/") + rest
            return mapped.replace("\\", "/") if "/" in remote and "\\" not in remote else mapped
    return path


def scan(client, paths, timeout=3600, poll=2.0):
    """Ask Stash to scan the folders and wait for the job to finish."""
    job = client.call(
        "mutation($input: ScanMetadataInput!) { metadataScan(input: $input) }", {"input": {"paths": paths}}
    )["metadataScan"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.call("query($id: ID!) { findJob(input: {id: $id}) { status error } }", {"id": job})["findJob"]
        # A finished job can drop out of the queue before it's polled
        if status is None or status["status"] == "FINISHED":
            return
        if status["status"] in ("FAILED", "CANCELLED"):
            raise StashError(f"Stash scan {status['status'].lower()}: {status.get('error') or ''}".strip())
        time.sleep(poll)
    raise StashError(f"Stash scan didn't finish within {timeout}s")


def sync(
    databases,
    client,
    apply=False,
    studio=None,
    tag_prefix=None,
    tags=True,
    organized=False,
    mappings=(),
    do_scan=False,
    sample=10,
):
    """Sync every database; studio and tag_prefix, when given, apply to every site."""
    models = []
    skipped = []
    for database in find_databases(databases):
        site = site_of(database)
        if site not in SITES:
            skipped.append({"database": str(database), "skipped": f"{site} database; this site isn't supported"})
            continue
        username, files = read_model(database, site)
        models.append((database, site, username, files))

    studios = {}
    if studio is not None:
        # A --studio Stash would refuse stops the run before anything in Stash
        # is scanned, created or changed; this only reads
        found = find_or_create(client, "studio", studio, False)
        if found is not None:
            studios[studio.lower()] = found

    if do_scan and apply:
        folders = sorted(
            {map_path(os.path.commonpath([os.path.dirname(f["path"]) for f in files]), mappings) for _, _, _, files in models if files}
        )
        if folders:
            scan(client, folders)

    # The studio, performers, tags and galleries are looked up (and created)
    # only once a file is found, so a run that matches nothing leaves Stash unchanged
    tag_cache = {}
    performers = {}
    galleries = {}

    # caches are keyed ignoring case, as Stash's names are
    # One --studio for several sites belongs to none of them, so it gets no site link
    mixed = studio is not None and len({site for _, site, _, _ in models}) > 1

    def studio_id(site):
        name = studio or SITES[site]["studio"]
        if name.lower() not in studios:
            extra = {} if mixed else {"urls": [SITES[site]["studio_url"]]}
            studios[name.lower()] = find_or_create(client, "studio", name, apply, extra)
        return studios[name.lower()]

    def tag_id(tag):
        if tag_cache.get(tag.lower()) is None:
            tag_cache[tag.lower()] = find_or_create(client, "tag", tag, apply)
        return tag_cache[tag.lower()]

    def performer_id(site, name):
        if performers.get(name.lower()) is None:
            performers[name.lower()] = find_or_create(
                client, "performer", name, apply, {"urls": [SITES[site]["creator_url"].format(name)]},
                SITES[site]["label"],
            )
        return performers[name.lower()]

    def fansly_tags(meta, sources, prefix, preview=False):
        if not tags:
            return []
        names = [f"{prefix}{source}" for source in sorted(sources)]
        if preview:
            names.append(f"{prefix}Preview")
        return [tag_id(name) for name in names + meta["hashtags"]]

    def gallery_id(site, prefix, creator_id, meta, counts):
        """Find, fill in or create the gallery for one post or message."""
        key = (site, meta["code"])
        if key in galleries:
            return galleries[key]
        sid = studio_id(site)
        people = [creator_id] + [performer_id(site, m) for m in meta["mentions"]]
        tag_ids = fansly_tags(meta, meta["sources"], prefix)
        existing = find_gallery(client, meta["code"], meta.get("url"))
        if existing:
            changes = plan(existing, meta, people, sid, tag_ids, organized)
            if changes:
                counts["galleries_updated" if apply else "galleries_to_update"] += 1
                if apply:
                    client.call(UPDATE["gallery"], {"input": {"id": existing["id"], **changes}})
            else:
                counts["galleries_up_to_date"] += 1
            galleries[key] = existing["id"]
            return existing["id"]
        counts["galleries_created" if apply else "galleries_to_create"] += 1
        if not apply:
            galleries[key] = None
            return None
        new = {"title": meta["title"], "code": meta["code"], "studio_id": sid, "performer_ids": people}
        for field in ("details", "date"):
            if meta.get(field):
                new[field] = meta[field]
        if meta.get("url"):
            new["urls"] = [meta["url"]]
        if tag_ids:
            new["tag_ids"] = list(dict.fromkeys(tag_ids))
        if organized:
            new["organized"] = True
        galleries[key] = client.call(CREATE_GALLERY, {"input": new})["galleryCreate"]["id"]
        return galleries[key]

    report = {"apply": apply, "models": [], "totals": defaultdict(int)}
    for database, site, username, files in models:
        name = username or Path(database).parent.name
        extra = {"urls": [SITES[site]["creator_url"].format(username)]} if username else {}
        prefix = SITES[site]["tag_prefix"] if tag_prefix is None else tag_prefix
        creator_id = None
        performer_checked = False
        counts = defaultdict(int)
        not_found = []
        for entry in files:
            kind = KINDS.get(entry["media_type"])
            if kind is None:
                counts["unsupported_type"] += 1
                continue
            stash_path = map_path(entry["path"], mappings)
            item = find_item(client, kind, stash_path)
            if item is None:
                counts["not_in_stash"] += 1
                if len(not_found) < sample:
                    not_found.append(stash_path)
                continue
            if not performer_checked:
                creator_id = find_or_create(client, "performer", name, apply, extra, SITES[site]["label"])
                performer_checked = True
            if site == FANSLY:
                meta = entry["meta"]
                people = [creator_id] + [performer_id(site, m) for m in meta["mentions"]]
                tag_ids = fansly_tags(meta, entry["api_types"], prefix, entry["preview"])
                gallery_ids = [gallery_id(site, prefix, creator_id, g, counts) for g in entry["galleries"].values()]
            else:
                people = [creator_id]
                tag_ids = [tag_id(f"{prefix}{api_type}") for api_type in sorted(entry["api_types"])] if tags else []
                gallery_ids = []
            changes = plan(item, entry["meta"], people, studio_id(site), tag_ids, organized, gallery_ids)
            if not changes:
                counts["up_to_date"] += 1
                continue
            counts["updated" if apply else "to_update"] += 1
            if apply:
                client.call(UPDATE[kind], {"input": {"id": item["id"], **changes}})
        if not performer_checked:
            creator_id = find_or_create(client, "performer", name, False)
        model = {
            "database": str(database),
            "performer": name,
            "performer_exists": creator_id is not None,
            "files": len(files),
            **counts,
        }
        if not_found:
            model["not_in_stash_sample"] = not_found
        if counts.get("not_in_stash") and not performer_checked:
            model["hint"] = (
                "None of these files are in Stash. Scan the folders in Stash (or use --scan), "
                "and if Stash sees them under another path, e.g. in Docker, add --path-map LOCAL=STASH."
            )
        report["models"].append(model)
        for key, value in counts.items():
            report["totals"][key] += value
        report["totals"]["files"] += len(files)
    report["models"].extend(skipped)
    if skipped:
        report["totals"]["skipped_databases"] = len(skipped)
    report["totals"] = dict(report["totals"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="user_data.db files, or folders to search for them (e.g. <profile>/.data)")
    parser.add_argument("--apply", action="store_true", help="write to Stash; without it, only report")
    parser.add_argument("--url", default=os.environ.get("STASH_URL", DEFAULT_URL), help=f"Stash GraphQL URL (default {DEFAULT_URL}, or $STASH_URL)")
    parser.add_argument("--api-key", default=os.environ.get("STASH_API_KEY"), help="Stash API key, if Stash has a password (default $STASH_API_KEY)")
    parser.add_argument("--studio", help="studio to set for every site (default OnlyFans, or Fansly for Fansly databases)")
    parser.add_argument("--tag-prefix", help="prefix for the source tags for every site, e.g. 'OnlyFans Paid' (default 'OnlyFans ', or 'Fansly ' for Fansly databases)")
    parser.add_argument("--no-tags", action="store_true", help="don't add tags (source tags, and for Fansly the preview tag and hashtags)")
    parser.add_argument("--organized", action="store_true", help="also mark items as organized")
    parser.add_argument("--path-map", action="append", default=[], metavar="LOCAL=STASH", help="rewrite a path prefix when Stash sees the files elsewhere (e.g. in Docker); repeatable")
    parser.add_argument("--scan", action="store_true", help="with --apply, have Stash scan the download folders first and wait for it")
    args = parser.parse_args(argv)

    mappings = []
    for item in args.path_map:
        if "=" not in item:
            parser.error(f"--path-map needs LOCAL=STASH, got {item!r}")
        mappings.append(tuple(item.split("=", 1)))

    try:
        report = sync(
            args.paths,
            StashClient(args.url, args.api_key),
            apply=args.apply,
            studio=args.studio,
            tag_prefix=args.tag_prefix,
            tags=not args.no_tags,
            organized=args.organized,
            mappings=mappings,
            do_scan=args.scan,
        )
    except (StashError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
