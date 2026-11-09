r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

import contextlib
import logging
import sqlite3
from collections import defaultdict

import arrow
from rich.console import Console

import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.utils.rebuild as rebuild
import ofscraper.db.utils.columns as db_columns
from ofscraper.db.operations_.profile import get_single_model_via_profile
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")

mediaCreate = """
CREATE TABLE IF NOT EXISTS medias (
    id INTEGER NOT NULL, 
    media_id INTEGER, 
    post_id INTEGER NOT NULL, 
    link VARCHAR, 
    directory VARCHAR, 
    filename VARCHAR, 
    size INTEGER, 
    api_type VARCHAR, 
    media_type VARCHAR, 
    preview INTEGER,
    linked BOOL,
    downloaded BOOL,
    created_at TIMESTAMP, 
    posted_at TIMESTAMP,
    duration VARCHAR,
    unlocked BOOL,
    hash VARCHAR,
    model_id INTEGER,
    skip_permanent BOOL,
    PRIMARY KEY (id),
    UNIQUE (media_id,model_id,post_id)
);"""

# columns a later version added are (name, stand-in when missing): see
# db_columns.select_all
mediaSelectTransition = [
    "media_id",
    "post_id",
    "link",
    "directory",
    "filename",
    "size",
    "api_type",
    "media_type",
    "preview",
    "linked",
    "downloaded",
    "created_at",
    ("unlocked", "NULL"),
    ("model_id", "NULL"),
    ("posted_at", "NULL"),
    ("hash", "NULL"),
    ("duration", "NULL"),
    ("skip_permanent", "NULL"),
]

mediaUpdateAPI = """Update 'medias'
SET
media_id=?,post_id=?,link=?,linked=?,api_type=?,media_type=?,preview=?,created_at=?,posted_at=?,model_id=?,duration=?,unlocked=?
WHERE media_id=(?) and model_id=(?) and post_id=(?);"""


# skip_permanent: 1 when skip_download_script skipped the item for good (it's
# saved as downloaded with no file); every other download write clears it
mediaUpdateDownload = """Update 'medias'
SET
directory=?,filename=?,size=?,downloaded=?,hash=?,skip_permanent=?
WHERE media_id=(?) and model_id=(?);"""


mediaDupeHashesMedia = """
WITH x AS (
    SELECT hash, size
    FROM medias
    WHERE hash IS NOT NULL AND size IS NOT NULL AND media_type = ?
)
SELECT hash
FROM x
GROUP BY hash, size
HAVING COUNT(*) > 1;
"""

mediaDupeHashes = """
WITH x AS (
    SELECT hash, size
    FROM medias
    WHERE hash IS NOT NULL AND size IS NOT NULL
)
SELECT hash
FROM x
GROUP BY hash, size
HAVING COUNT(*) > 1;
"""
mediaDupeFiles = """
SELECT filename
FROM medias
where hash=(?)
"""
mediaInsertAPI = """INSERT INTO 'medias'(
media_id,post_id,link,api_type,
media_type,preview,linked,
created_at,posted_at,model_id,duration,unlocked)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?);"""

mediaInsertTransition = """INSERT INTO 'medias'(
media_id,post_id,link,directory,
filename,size,api_type,
media_type,preview,linked,
downloaded,created_at,posted_at,hash,model_id,duration,unlocked,skip_permanent)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"""

mediaDownloadForce = """
Update 'medias'
SET
unlocked=0
WHERE media_id=(?) and model_id=(?);
"""
mediaDownloadSelect = """
SELECT  
directory,filename,size,
downloaded,hash,skip_permanent
FROM medias where media_id=(?) and model_id=(?)
"""
allIDCheck = """
SELECT media_id FROM medias
"""
allDLIDCheck = """
SELECT media_id FROM medias where downloaded=(1)
"""
allDLModelIDCheck = """
SELECT media_id FROM medias where downloaded=(1) and model_id=(?)
"""
# the same, leaving out permanent skip_download_script skips, which
# --retry-permanent-skips offers to the script again (#354)
allDLIDCheckNoPermanentSkips = """
SELECT media_id FROM medias where downloaded=(1) and skip_permanent IS NOT 1
"""
allDLModelIDCheckNoPermanentSkips = """
SELECT media_id FROM medias where downloaded=(1) and model_id=(?) and skip_permanent IS NOT 1
"""
allPostIDCheck = """
SELECT media_id, post_id FROM medias
"""

allPostIDDLCheck = """
SELECT media_id, post_id FROM medias where downloaded=(1)
"""
# the per-area queries below are filled in by execute_area_media
mediaAreaColumns = [
    "media_id",
    "post_id",
    "link",
    "directory",
    "filename",
    "size",
    "api_type",
    "media_type",
    "preview",
    "linked",
    "downloaded",
    "created_at",
    ("posted_at", "NULL"),
    ("hash", "NULL"),
    ("model_id", "NULL"),
    ("unlocked", "NULL"),
    ("duration", "NULL"),
]
getTimelineMedia = """
SELECT {columns}
FROM medias where LOWER(api_type) in ('timeline','posts','post') {model_filter}
"""
getModelMediaStatus = """
SELECT
media_id,post_id,media_type,downloaded,unlocked
FROM medias where model_id=(?)
"""
getArchivedMedia = """
SELECT {columns}
FROM medias where LOWER(api_type) in ('archived') {model_filter}
"""

getPinnedMedia = """
SELECT {columns}
FROM medias where LOWER(api_type) in ('pinned') {model_filter}
"""

getStoriesMedia = """
SELECT {columns}
FROM medias where LOWER(api_type) in ('stories') {model_filter}
"""
getHighlightsMedia = """
SELECT {columns}
FROM medias where LOWER(api_type) in ('highlights') {model_filter}
"""
getStreamsMedia = """
SELECT {columns}
FROM medias where LOWER(api_type) in ('streams') {model_filter}
"""
getMessagesMedia = """
SELECT {columns}
FROM medias
WHERE LOWER(api_type) IN ('message', 'messages')
{model_filter}
"""
unlockedMediaCheck = """
SELECT media_id, post_id FROM medias WHERE model_id=(?) AND unlocked=(1) AND downloaded=(0)
"""

# Before #326 a file skipped by a size limit was saved as downloaded with no
# file, and its row got the media type "Forced_skippeds" (#319, #352). The
# download columns are written for every post of the media at once, so all
# of its rows were left downloaded with no file.
SIZE_SKIP_LABEL = "Forced_skippeds"
SIZE_SKIP_REPAIR_FLAG = "media_size_skip_repaired"
sizeSkipLabelled = """
SELECT DISTINCT media_id, model_id FROM medias
WHERE media_type = ? AND downloaded = 1 AND media_id IS NOT NULL
"""
# a row with anything recorded about a file is not the bug's
mediaHasFile = """
SELECT 1 FROM medias
WHERE media_id = ? AND model_id IS ?
AND (filename IS NOT NULL OR directory IS NOT NULL OR size IS NOT NULL OR hash IS NOT NULL)
LIMIT 1
"""
# a permanent skip_download_script skip (#351) is saved as downloaded with no
# file on purpose: it counts as a file, so the repair leaves its media alone
mediaHasFileOrPermanentSkip = mediaHasFile.replace(
    "OR hash IS NOT NULL)", "OR hash IS NOT NULL OR skip_permanent = 1)"
)
# un-marks a permanent skip_download_script skip (#354): NULL, as a skip for
# one run leaves the row
permanentSkipUnmark = """
UPDATE medias SET downloaded = NULL, skip_permanent = NULL
WHERE media_id = ? AND model_id IS ? AND skip_permanent = 1
"""
permanentSkipIDs = """
SELECT DISTINCT media_id FROM medias WHERE model_id IS ? AND skip_permanent = 1
"""
# NULL, as a size skip leaves the row now
sizeSkipUnmark = """
UPDATE medias SET downloaded = NULL
WHERE media_id = ? AND model_id IS ? AND downloaded = 1
AND filename IS NULL AND directory IS NULL AND size IS NULL AND hash IS NULL
"""


@wrapper.operation_wrapper_async
def create_media_table(model_id=None, username=None, conn=None, db_path=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(mediaCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def add_column_media_hash(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('medias') WHERE name = 'hash') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)
            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE medias ADD COLUMN hash VARCHAR;")
                # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def add_column_media_unlocked(model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('medias') WHERE name = 'unlocked') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)
            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE medias ADD COLUMN unlocked BOOL;")
                # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def add_column_media_posted_at(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('medias') WHERE name = 'posted_at') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)

            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE medias ADD COLUMN posted_at TIMESTAMP;")
            # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def add_column_media_ID(model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('medias') WHERE name = 'model_id') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)

            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE medias ADD COLUMN model_id INTEGER;")

                # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def add_column_media_skip_permanent(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('medias') WHERE name = 'skip_permanent') THEN 1 ELSE 0 END AS alter_required;"
            )
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE medias ADD COLUMN skip_permanent BOOL;")
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper_async
def add_column_media_duration(model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('medias') WHERE name = 'duration') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)
            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE medias ADD COLUMN duration VARCHAR;")
                # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def get_media_ids(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allIDCheck)
        return [dict(row)["media_id"] for row in cur.fetchall()]


@wrapper.operation_wrapper
def get_media_ids_downloaded(conn=None, without_permanent_skips=False, **kwargs) -> list:
    """without_permanent_skips leaves out the permanent skip_download_script
    skips (#354)."""
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(
            allDLIDCheckNoPermanentSkips if without_permanent_skips else allDLIDCheck
        )
        return set([dict(row)["media_id"] for row in cur.fetchall()])


@run
@wrapper.operation_wrapper_async
def get_media_ids_downloaded_model(model_id=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allDLModelIDCheck, [model_id])
        return set([dict(row)["media_id"] for row in cur.fetchall()])


@wrapper.operation_wrapper
def get_media_post_ids(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allPostIDCheck)
        return [(dict(row)["media_id"], dict(row)["post_id"]) for row in cur.fetchall()]


@wrapper.operation_wrapper
def get_media_post_ids_downloaded(
    model_id=None, username=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allPostIDDLCheck)
        return [(dict(row)["media_id"], dict(row)["post_id"]) for row in cur.fetchall()]


@wrapper.operation_wrapper
def get_dupe_media_hashes(
    model_id=None, username=None, conn=None, mediatype=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        if mediatype:
            cur.execute(mediaDupeHashesMedia, [mediatype])
        else:
            cur.execute(mediaDupeHashes)
        return [dict(row)["hash"] for row in cur.fetchall()]


@wrapper.operation_wrapper
def get_dupe_media_files(
    model_id=None, username=None, conn=None, hash=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(mediaDupeFiles, [hash])
        return [dict(row)["filename"] for row in cur.fetchall()]


@wrapper.operation_wrapper_async
def mark_media_as_downloaded(
    media,
    model_id=None,
    username=None,
    conn=None,
    filepath=None,
    filename=None,
    directory=None,
    downloaded=None,
    hashdata=None,
    size=None,
    skip_permanent=None,
    **kwargs,
):
    with contextlib.closing(conn.cursor()) as curr:
        filename = filename or (filepath.name if filepath is not None else None)
        directory = directory or (filepath.parent if filepath is not None else None)
        update_media_table_via_api_helper(
            media, curr=curr, model_id=model_id, conn=conn
        )
        update_media_table_download_helper(
            media,
            model_id,
            filename=filename,
            directory=directory,
            username=username,
            hashdata=hashdata,
            conn=conn,
            curr=curr,
            downloaded=downloaded,
            size=size,
            skip_permanent=skip_permanent,
        )


@wrapper.operation_wrapper
def write_media_table_via_api_batch(medias, model_id=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as curr:
        insertData = list(
            map(
                lambda media: [
                    media.id,
                    media.post_id,
                    media.link,
                    media.responsetype.capitalize(),
                    media.mediatype.capitalize(),
                    media.preview,
                    media.linked,
                    media.date,
                    media.postdate,
                    model_id,
                    media.duration_string,
                    media.canview,
                ],
                medias,
            )
        )
        curr.executemany(mediaInsertAPI, insertData)
        conn.commit()


@wrapper.operation_wrapper
def update_media_table_via_api_batch(
    medias, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as curr:
        insertData = list(
            map(
                lambda media: [
                    media.id,
                    media.post_id,
                    media.link,
                    media.linked,
                    media.responsetype.capitalize(),
                    media.mediatype.capitalize(),
                    media.preview,
                    media.date,
                    media.postdate,
                    model_id,
                    media.duration_string,
                    media.canview,
                    media.id,
                    model_id,
                    media.post_id,
                ],
                medias,
            )
        )
        curr.executemany(mediaUpdateAPI, insertData)
        conn.commit()


def media_transition_rows(inputData) -> list:
    ordered_keys = [
        "media_id",
        "post_id",
        "link",
        "directory",
        "filename",
        "size",
        "api_type",
        "media_type",
        "preview",
        "linked",
        "downloaded",
        "created_at",
        "posted_at",
        "hash",
        "model_id",
        "duration",
        "unlocked",
    ]
    inputData = _media_cleaup_helper(inputData)
    # optional column: a row read before it existed has no value
    return [
        tuple([data[key] for key in ordered_keys] + [data.get("skip_permanent")])
        for data in inputData
    ]


@wrapper.operation_wrapper_async
def write_media_table_transition(inputData, model_id=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as curr:
        curr.executemany(mediaInsertTransition, media_transition_rows(inputData))
        conn.commit()


@wrapper.operation_wrapper_async
def update_media_table_download_transition(
    inputData, model_id=None, conn=None, **kwargs
):
    download_keys = ["directory", "filename", "size", "downloaded", "hash"]
    with contextlib.closing(conn.cursor()) as curr:
        curr.executemany(
            mediaUpdateDownload,
            [
                [data[key] for key in download_keys]
                + [data.get("skip_permanent")]
                + [data["media_id"], data["model_id"]]
                for data in inputData
            ],
        )
        conn.commit()


@wrapper.operation_wrapper_async
def replace_media_table(inputData, model_id=None, conn=None, **kwargs):
    rebuild.replace_table(
        conn,
        "medias",
        mediaCreate,
        mediaInsertTransition,
        media_transition_rows(inputData),
    )


def _media_cleaup_helper(inputData):
    output_dict = defaultdict(lambda: None)
    for ele in inputData:
        key = (ele["media_id"], ele["post_id"], ele["model_id"])
        if output_dict[key]:
            merged = {}
            past_data = output_dict[key]
            for inner_key in ele.keys():
                merged[inner_key] = ele[inner_key] or past_data[inner_key]
            output_dict[key] = merged
        else:
            output_dict[key] = ele
    return output_dict.values()


def execute_area_media(cur, query, model_id):
    """Run one of the per-area queries (getTimelineMedia and the rest) on a
    medias table that may be older than this version: a missing column gets
    its stand-in (see mediaAreaColumns). A table from before model_id holds
    one creator's media, so it isn't filtered by creator."""
    present = db_columns.table_columns(cur, "medias")
    has_model_id = "model_id" in present
    cur.execute(
        query.format(
            columns=db_columns.select_list(present, mediaAreaColumns),
            model_filter="and model_id=(?)" if has_model_id else "",
        ),
        [model_id] if has_model_id else [],
    )


@wrapper.operation_wrapper_async
def get_all_medias_transition(
    model_id=None, username=None, conn=None, database_model=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(db_columns.select_all(cur, "medias", mediaSelectTransition))
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                row,
                model_id=row.get("model_id") or database_model,
                duration=row.get("duration"),
                unlocked=row.get("unlocked"),
            )
            for row in data
        ]


async def get_all_medias(model_id=None, username=None, database_model=None, **kwargs):
    return await get_all_medias_transition(
        model_id=model_id, username=username, database_model=database_model, **kwargs
    )


@run
@wrapper.operation_wrapper_async
def get_messages_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        execute_area_media(cur, getMessagesMedia, model_id)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                ele,
                posted_at=arrow.get(
                    ele["posted_at"] or ele["created_at"] or 0
                ).float_timestamp,
            )
            for ele in data
        ]


@run
@wrapper.operation_wrapper_async
def get_archived_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        execute_area_media(cur, getArchivedMedia, model_id)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                ele,
                posted_at=arrow.get(
                    ele["posted_at"] or ele["created_at"] or 0
                ).float_timestamp,
            )
            for ele in data
        ]


@run
@wrapper.operation_wrapper_async
def get_pinned_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        execute_area_media(cur, getPinnedMedia, model_id)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                ele,
                posted_at=arrow.get(
                    ele["posted_at"] or ele["created_at"] or 0
                ).float_timestamp,
            )
            for ele in data
        ]


@run
@wrapper.operation_wrapper_async
def get_stories_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        execute_area_media(cur, getStoriesMedia, model_id)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                ele,
                posted_at=arrow.get(
                    ele["posted_at"] or ele["created_at"] or 0
                ).float_timestamp,
            )
            for ele in data
        ]


@run
@wrapper.operation_wrapper_async
def get_highlights_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        execute_area_media(cur, getHighlightsMedia, model_id)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                ele,
                posted_at=arrow.get(
                    ele["posted_at"] or ele["created_at"] or 0
                ).float_timestamp,
            )
            for ele in data
        ]


@run
@wrapper.operation_wrapper_async
def get_streams_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        execute_area_media(cur, getStreamsMedia, model_id)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                ele,
                posted_at=arrow.get(
                    ele["posted_at"] or ele["created_at"] or 0
                ).float_timestamp,
            )
            for ele in data
        ]


@run
@wrapper.operation_wrapper_async
def get_timeline_media(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        execute_area_media(cur, getTimelineMedia, model_id)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(ele, posted_at=arrow.get(ele["posted_at"] or ele["created_at"] or 0))
            for ele in data
        ]


@run
@wrapper.operation_wrapper_async
def get_model_media_status(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(getModelMediaStatus, [model_id])
        return [dict(row) for row in cur.fetchall()]


def update_media_table_via_api_helper(
    media, model_id=None, conn=None, curr=None, **kwargs
) -> list:

    insertData = [
        media.id,
        media.post_id,
        media.link,
        media.linked,
        media.responsetype.capitalize(),
        media.mediatype.capitalize(),
        media.preview,
        media.date,
        media.postdate,
        model_id,
        media.duration_string,
        media.canview,
        media.id,
        model_id,
        media.post_id,
    ]
    curr.execute(mediaUpdateAPI, insertData)
    conn.commit()


def update_media_table_download_helper(
    media,
    model_id,
    filename=None,
    directory=None,
    hashdata=None,
    conn=None,
    downloaded=None,
    curr=None,
    size=None,
    skip_permanent=None,
    **kwargs,
) -> list:
    filename = str(filename) if filename else None
    directory = str(directory) if directory else None
    insertData = [
        directory,
        filename,
        size,
        downloaded,
        hashdata,
        1 if skip_permanent else None,
    ]
    insertData.extend([media.id, model_id])
    curr.execute(mediaUpdateDownload, insertData)
    conn.commit()


@run
@wrapper.operation_wrapper_async
def prev_download_media_data(media, model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as curr:
        prevData = curr.execute(mediaDownloadSelect, (media.id, model_id)).fetchone()
        prevData = dict(prevData) if prevData else None
        return prevData


@wrapper.operation_wrapper
def batch_set_media_downloaded(medias, model_id=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as curr:
        insertData = list(
            map(
                lambda media: [
                    media["media_id"],
                    model_id,
                ],
                medias,
            )
        )
        curr.executemany(mediaDownloadForce, insertData)
        conn.commit()


@run
async def batch_mediainsert(media, **kwargs):
    curr = set(get_media_post_ids(**kwargs) or [])
    mediaDict = {}
    for ele in media:
        mediaDict[(ele.id, ele.post_id)] = ele
    write_media_table_via_api_batch(
        list(filter(lambda x: (x.id, x.post_id) not in curr, mediaDict.values())),
        **kwargs,
    )

    update_media_table_via_api_batch(
        list(filter(lambda x: (x.id, x.post_id) in curr, mediaDict.values())), **kwargs
    )


async def rebuild_media_table(model_id=None, username=None, db_path=None, **kwargs):
    database_model = get_single_model_via_profile(
        model_id=model_id, username=username, db_path=db_path
    )
    data = await get_all_medias_transition(
        model_id=model_id,
        username=username,
        database_model=database_model,
        db_path=db_path,
    )
    await replace_media_table(
        data, model_id=model_id, username=username, db_path=db_path
    )


@wrapper.operation_wrapper_async
def get_unlocked_media_ids(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(unlockedMediaCheck, [model_id])
        return [
            {"media_id": dict(row)["media_id"], "post_id": dict(row)["post_id"]}
            for row in cur.fetchall()
        ]


@wrapper.operation_wrapper_async
def repair_size_skipped_media(
    from_backups=(), model_id=None, username=None, conn=None, **kwargs
) -> int:
    """Un-mark the media the size-skip bug saved as downloaded (#352).

    The media is the one labelled "Forced_skippeds" here, or in a backup
    (`from_backups`: (media_id, model_id) pairs). Only its rows downloaded
    with no file change, and none if any of its rows has a file. Writes the
    repair's flag in the same transaction, so it runs once per database.
    Returns the number of rows un-marked."""
    with contextlib.closing(conn.cursor()) as cur:
        try:
            media = {
                (row["media_id"], row["model_id"])
                for row in cur.execute(sizeSkipLabelled, [SIZE_SKIP_LABEL])
            }
            media.update(pair for pair in from_backups if pair[0] is not None)
            # the column is added before the repair runs; checked anyway, so
            # the repair also works on a table without it
            has_file = (
                mediaHasFileOrPermanentSkip
                if any(
                    col[1] == "skip_permanent"
                    for col in cur.execute("PRAGMA table_info('medias')").fetchall()
                )
                else mediaHasFile
            )
            changed = 0
            for pair in sorted(media, key=str):
                if cur.execute(has_file, pair).fetchone():
                    continue
                changed += cur.execute(sizeSkipUnmark, pair).rowcount
            cur.execute(
                "INSERT OR REPLACE INTO schema_flags (flag_name, flag_value) VALUES (?, ?);",
                [SIZE_SKIP_REPAIR_FLAG, 1],
            )
            conn.commit()
            return changed
        except sqlite3.Error as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper
def get_media_ids_downloaded_model_sync(
    model_id=None, conn=None, without_permanent_skips=False, **kwargs
) -> list:
    """without_permanent_skips leaves out the permanent skip_download_script
    skips (#354)."""
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(
            (
                allDLModelIDCheckNoPermanentSkips
                if without_permanent_skips
                else allDLModelIDCheck
            ),
            [model_id],
        )
        return set([dict(row)["media_id"] for row in cur.fetchall()])


def _has_skip_permanent(cur):
    return any(
        col[1] == "skip_permanent"
        for col in cur.execute("PRAGMA table_info('medias')").fetchall()
    )


@run
@wrapper.operation_wrapper_async
def get_permanent_skip_media_ids(model_id=None, conn=None, **kwargs) -> set:
    """The media ids of the creator's permanent skip_download_script skips
    (#354). Empty for a database from before the column."""
    with contextlib.closing(conn.cursor()) as cur:
        if not _has_skip_permanent(cur):
            return set()
        cur.execute(permanentSkipIDs, [model_id])
        return {row["media_id"] for row in cur.fetchall()}


@wrapper.operation_wrapper_async
def unmark_permanent_skips(media_ids, model_id=None, conn=None, **kwargs) -> int:
    """Un-mark the permanent skip_download_script skips of these media of the
    creator (#354): they're set back to not downloaded, so the next run asks
    the script about them again. Only rows with skip_permanent = 1 change;
    a media's download state is kept on all of its rows (every post it's
    in), as a download writes it. Returns the number of rows changed."""
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # the db command doesn't upgrade the database: one from before the
            # column has no permanent skips
            if not _has_skip_permanent(cur):
                return 0
            changed = 0
            for media_id in sorted(set(media_ids), key=str):
                changed += cur.execute(
                    permanentSkipUnmark, [media_id, model_id]
                ).rowcount
            conn.commit()
            return changed
        except sqlite3.Error as e:
            conn.rollback()
            raise e
