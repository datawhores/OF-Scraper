import ofscraper.prompts.prompts as prompts
import ofscraper.utils.context.exit as exit
import ofscraper.utils.menu as menu


@exit.exit_wrapper
def process_prompts():
    while True:
        if menu.main_menu_action():
            break
        elif prompts.continue_prompt() == "No":
            break
