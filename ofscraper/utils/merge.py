
import ofscraper.prompts.prompts as prompts
import ofscraper.db.operations_.merge as merge
from rich.console import Console

console = Console()

def merge_runner():
    while True:
        if not prompts.backup_prompt_db():
            console.print("waiting for backup confirmation")
            break
        folder=prompts.folder_prompt_db()
        new_db_folder=prompts.new_db_prompt()
        confirm=prompts.confirm_prompt_db(folder,new_db_folder)
        if confirm is False:
            continue
        elif confirm is None:
            break
        else:
            merge.batch_database_changes(new_db_folder,folder)
            break
    
    