from ofscraper.download.shared.send.message import send_msg
from ofscraper.download.shared.progress.progress import update_total
async def batch_total_change_helper(past_total, new_total):
    if not new_total and not past_total:
        return
    elif not past_total:
        await send_msg((None, 0, new_total))
    elif past_total and new_total - past_total != 0:
        await send_msg((None, 0, new_total - past_total))


async def total_change_helper(past_total, new_total):
    if not new_total and not past_total:
        return
    elif not past_total:
        await update_total(new_total)
    elif past_total and new_total - past_total != 0:
        await update_total(new_total - past_total)