from rich.console import Console

import ofscraper.db.merge as merge
import ofscraper.db.postgres as postgres
import ofscraper.prompts.prompts as prompts
from ofscraper.utils.context.run_async import run

console = Console()


def merge_runner():
    # the merge works on user_data.db files, whichever engine is in use.
    # Printed like the screen's other messages, so that it shows at every
    # --output level
    if postgres.enabled():
        console.print(postgres.sqlite_files_notice("Merge Databases"))
    while True:
        while True:
            if not prompts.backup_prompt_db():
                console.print("waiting for backup confirmation")
                return
            curr_folder = prompts.folder_prompt_db()
            new_db = prompts.new_db_prompt()
            confirm = prompts.confirm_prompt_db(curr_folder, new_db)
            if confirm is False:
                continue
            elif confirm is True:
                break
            else:
                return
        completed, skipped, failed = merge_loop(curr_folder, new_db)
        if postgres.enabled() and completed:
            # the file, not its folder: the preview then covers what the
            # migrate command brings in, and no other user_data.db the folder
            # holds. It ends in user_data.db, so no backslash is before the
            # closing quote (on Windows "D:\" reads as D:")
            merged = str(merge.MergeDatabase().get_new_db(new_db))
            console.print("To bring the merged file into PostgreSQL, close the scraper and run:")
            # on one line and as written, so that it can be copied
            console.print(
                f'ofscraper --migrate-sqlite-to-postgres "{merged}"',
                soft_wrap=True,
                markup=False,
                emoji=False,
                highlight=False,
            )
            console.print("To see what it would do first, without writing anything:")
            console.print(
                f'python -m ofscraper.commands.postgres_import "{merged}"',
                soft_wrap=True,
                markup=False,
                emoji=False,
                highlight=False,
            )
        if not prompts.confirm_db_continue(completed, skipped, failed):
            break


@run
async def merge_loop(curr_folder, new_db):
    db_merger = merge.MergeDatabase()
    failed, completed, skipped = await db_merger(curr_folder, new_db)
    return completed, skipped, failed

    # while True:
    #     failures = merge.batch_database_changes(new_db_folder, folder)
    # if len(failures)==0:
    #     return
    # for failure in failures:
    #     print("[red]Please read the following selections carfully[/red]")
    #     model_id=prompts.model_id_prompt()
    #     if model_id.isnumeric():
