import ofscraper.utils.menu as menu
import ofscraper.prompts.prompts as prompts

@exit.exit_wrapper
def process_prompts():
    while True:
        if menu.main_menu_action():
            break
        elif prompts.continue_prompt() == "No":
            break