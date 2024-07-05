import pathlib

import ofscraper.utils.settings as settings


def get_resume_header(resume_size, total):
    return (
        None
        if not resume_size or not total
        else {"Range": f"bytes={resume_size}-{total}"}
    )


def get_resume_size(tempholderObj, mediatype=None):
    if not settings.get_auto_resume(mediatype=mediatype):
        pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
        return 0
    return (
        0
        if not pathlib.Path(tempholderObj.tempfilepath).exists()
        else pathlib.Path(tempholderObj.tempfilepath).absolute().stat().st_size
    )

def resume_cleaner(resume_size,total,path):
    if not resume_size:
        return 0
    elif resume_size > total:
        pathlib.Path(path).unlink(missing_ok=True)
        return 0
    return resume_size