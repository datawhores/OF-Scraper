from InquirerPy import prompt
import ofscraper.utils.live.screens as progress_utils


def press_enter_to_continue():
    """
    Pauses the script and waits for the user to press Enter.
    """
    questions = [
        {
            "type": "input",
            "message": "Press enter to continue\n",
            # The name is not strictly necessary for this use case but is good practice
            "name": "continue",
        }
    ]
    with progress_utils.stop_live_screen():
        prompt(questions)
