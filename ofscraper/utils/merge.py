from rich.console import Console

import ofscraper.db.operations_.merge as merge
import ofscraper.prompts.prompts as prompts

console = Console()


def merge_runner():
    while True:
        if not prompts.backup_prompt_db():
            console.print("waiting for backup confirmation")
            break
        folder = prompts.folder_prompt_db()
        new_db_folder = prompts.new_db_prompt()
        confirm = prompts.confirm_prompt_db(folder, new_db_folder)
        if confirm is False:
            continue
        elif confirm is None:
            break
    merge_loop(new_db_folder, folder)


def merge_loop(new_db_folder, folder):
    db_merger = merge.MergeDatabase()
    while True:
        failures = merge.batch_database_changes(new_db_folder, folder)
        # if len(failures)==0:
        #     return
        # for failure in failures:
        #     print("[red]Please read the following selections carfully[/red]")
        #     model_id=prompts.model_id_prompt()
        #     if model_id.isnumeric():
