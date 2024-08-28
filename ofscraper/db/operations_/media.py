r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
              >>>>>>> main
45
                                                                        
"""

import contextlib
import logging
import sqlite3
from collections import defaultdict

import arrow
from rich.console import Console

import ofscraper.db.operations_.wrapper as wrapper
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
	PRIMARY KEY (id), 
	UNIQUE (media_id,model_id,post_id)
);"""
mediaSelectTransition = """
SELECT  media_id,post_id,link,directory,filename,size,api_type,
media_type,preview,linked,downloaded,created_at,unlocked,
CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('medias') WHERE name = 'model_id')
            THEN model_id
            ELSE NULL
END AS model_id,
CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('medias') WHERE name = 'posted_at')
            THEN posted_at
            ELSE NULL
END AS posted_at,
        CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('medias') WHERE name = 'hash')
            THEN hash
            ELSE NULL
       END AS hash,
        CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('medias') WHERE name = 'duration')
            THEN duration
            ELSE NULL
       END AS duration
FROM medias;
"""
mediaDrop = """
drop table medias;
"""
mediaUpdateAPI = """Update 'medias'
SET
media_id=?,post_id=?,linked=?,api_type=?,media_type=?,preview=?,created_at=?,posted_at=?,model_id=?,duration=?,unlocked=?
WHERE media_id=(?) and model_id=(?) and post_id=(?);"""
mediaUpdateDownload = """Update 'medias'
SET
directory=?,filename=?,size=?,downloaded=?,hash=?
WHERE media_id=(?) and model_id=(?);"""


mediaDupeHashesMedia = """
WITH x AS (
    SELECT hash, size
    FROM medias
    WHERE hash IS NOT NULL AND size is not null and  WHERE hash IS NOT NULL AND size IS NOT NULL AND (media_type = ?)
)
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
    WHERE hash IS NOT NULL AND size is not null and  WHERE hash IS NOT NULL AND size IS NOT NULL
)
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
media_type,preview,link,
downloaded,created_at,posted_at,hash,model_id,duration,unlocked)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"""

mediaDownloadForce = """
Update 'medias'
SET
unlocked=0
WHERE media_id=(?) and model_id=(?);
"""
mediaDownloadSelect = """
SELECT  
directory,filename,size,
downloaded,hash
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
allPostIDCheck = """
SELECT media_id, post_id FROM medias
"""

allPostIDDLCheck = """
SELECT media_id, post_id FROM medias where downloaded=(1) or unlocked=(1)
"""
getTimelineMedia = """
SELECT
media_id,post_id,link,directory
filename,size,api_type,media_type,
preview,linked,downloaded,created_at,posted_at,hash,model_id,unlocked,duration
FROM medias where LOWER(api_type) in ('timeline','posts','post') and model_id=(?)
"""
getArchivedMedia = """
SELECT
media_id,post_id,link,directory
filename,size,api_type,media_type,
preview,linked,downloaded,created_at,posted_at,hash,model_id,unlocked,duration
FROM medias where LOWER(api_type) in ('archived') and model_id=(?)
"""

getPinnedMedia = """
SELECT
media_id,post_id,link,directory
filename,size,api_type,media_type,
preview,linked,downloaded,created_at,posted_at,hash,model_id,unlocked,duration
FROM medias where LOWER(api_type) in ('pinned') and model_id=(?)
"""

getStoriesMedia = """
SELECT
media_id,post_id,link,directory
filename,size,api_type,media_type,
preview,linked,downloaded,created_at,posted_at,hash,model_id,unlocke,duration
FROM medias where LOWER(api_type) in ('stories') and model_id=(?)
"""
getHighlightsMedia = """
SELECT
media_id,post_id,link,directory
filename,size,api_type,media_type,
preview,linked,downloaded,created_at,posted_at,hash,model_id,unlocked,duration
FROM medias where LOWER(api_type) in ('highlights') and model_id=(?)
"""
getStreamsMedia = """
SELECT
media_id,post_id,link,directory
filename,size,api_type,media_type,
preview,linked,downloaded,created_at,posted_at,hash,model_id,unlocked,duration
FROM medias where LOWER(api_type) in ('streams') and model_id=(?)
"""
getMessagesMedia = """
SELECT 
media_id, post_id, link, directory,
filename, size, api_type, media_type,
preview, linked, downloaded, created_at, posted_at, hash, model_id, unlocked,duration
FROM medias
WHERE LOWER(api_type) IN ('message', 'messages') -- Use IN for multiple values
AND model_id = ?;  -- Prepared statement placeholder
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
def get_media_ids_downloaded(conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allDLIDCheck)
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
def download_media_update(
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
        )


@wrapper.operation_wrapper
def write_media_table_via_api_batch(medias, model_id=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as curr:
        insertData = list(
            map(
                lambda media: [
                    media.id,
                    media.postid,
                    media.url or media.mpd,
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
                    media.postid,
                    media.url or media.mpd,
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
                    media.postid,
                ],
                medias,
            )
        )
        curr.executemany(mediaUpdateAPI, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def write_media_table_transition(inputData, model_id=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as curr:
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
        insertData = [tuple([data[key] for key in ordered_keys]) for data in inputData]
        curr.executemany(mediaInsertTransition, insertData)
        conn.commit()


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


@wrapper.operation_wrapper_async
def get_all_medias_transition(
    model_id=None, username=None, conn=None, database_model=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(mediaSelectTransition)
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
async def get_all_medias( model_id=None, username=None, database_model=None, **kwargs):
    return await get_all_medias_transition(model_id=model_id, username=username, database_model=database_model, **kwargs)
    


@wrapper.operation_wrapper_async
def drop_media_table(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(mediaDrop)
        conn.commit()


@run
@wrapper.operation_wrapper_async
def get_messages_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(getMessagesMedia, [model_id])
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
        cur.execute(getArchivedMedia, [model_id])
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
        cur.execute(getPinnedMedia, [model_id])
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
        cur.execute(getStoriesMedia, [model_id])
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
        cur.execute(getHighlightsMedia, [model_id])
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
        cur.execute(getStreamsMedia, [model_id])
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
        cur.execute(getTimelineMedia, [model_id])
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(ele, posted_at=arrow.get(ele["posted_at"] or ele["created_at"] or 0))
            for ele in data
        ]


def update_media_table_via_api_helper(
    media, model_id=None, conn=None, curr=None, **kwargs
) -> list:

    insertData = [
        media.id,
        media.postid,
        media.url or media.mpd,
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
        media.postid,
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
        mediaDict[(ele.id, ele.postid)] = ele
    write_media_table_via_api_batch(
        list(filter(lambda x: (x.id, x.postid) not in curr, mediaDict.values())),
        **kwargs,
    )

    update_media_table_via_api_batch(
        list(filter(lambda x: (x.id, x.postid) in curr, mediaDict.values())), **kwargs
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
    await drop_media_table(model_id=model_id, username=username, db_path=db_path)
    await create_media_table(model_id=model_id, username=username, db_path=db_path)
    await write_media_table_transition(
        data, model_id=model_id, username=username, db_path=db_path
    )
