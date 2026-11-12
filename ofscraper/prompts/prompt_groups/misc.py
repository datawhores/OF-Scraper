from ofscraper.prompts.promptConvert import prompt
import ofscraper.utils.interactive as interactive
import ofscraper.utils.live.screens as progress_utils


def press_enter_to_continue():
    """
    Pauses the script and waits for the user to press Enter.
    """
    interactive.require_console("Press enter to continue")
    with progress_utils.stop_live_screen():
        prompt("Press enter to continue")
