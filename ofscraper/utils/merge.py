from rich.console import Console

import ofscraper.db.merge as merge
import ofscraper.prompts.prompts as prompts
from ofscraper.utils.context.run_async import run

console = Console()


def merge_runner():
    while True:
        while True:
            if not prompts.backup_prompt_db():
                console.print("waiting for backup confirmation")
                break
            curr_folder = prompts.folder_prompt_db()
            new_db = prompts.new_db_prompt()
            confirm = prompts.confirm_prompt_db(curr_folder, new_db)
            if confirm is False:
                continue
            elif confirm is True:
                break
        completed, skipped = merge_loop(curr_folder, new_db)
        if not prompts.confirm_db_continue(completed, skipped):
            break


@run
async def merge_loop(curr_folder, new_db):
    db_merger = merge.MergeDatabase()
    failures, completed, skipped = await db_merger(curr_folder, new_db)
    for failure in failures:
        if failure["reason"] == "Found model_id was not numeric":
            continue
    return completed, skipped

    # while True:
    #     failures = merge.batch_database_changes(new_db_folder, folder)
    # if len(failures)==0:
    #     return
    # for failure in failures:
    #     print("[red]Please read the following selections carfully[/red]")
    #     model_id=prompts.model_id_prompt()
    #     if model_id.isnumeric():
