
import ofscraper.prompts.prompts as prompts
import ofscraper.db.operations_.merge as merge
from rich.console import Console

console = Console()

def merge_runner():
    if not prompts.backup_prompt():
        console.print("waiting for backup confirmation")
    folder=prompts.folder_prompt()
    new_db_folder=prompts.new_db_prompt()
    merge.batch_database_changes(new_db_folder,folder)
    
    