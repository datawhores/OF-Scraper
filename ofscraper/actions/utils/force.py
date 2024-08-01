from ofscraper.db.operations_.media import (
    download_media_update,
)
async def force_download(ele, username, model_id):
    await download_media_update(
        ele,
        filepath=None,
        model_id=model_id,
        username=username,
        downloaded=True,
    )