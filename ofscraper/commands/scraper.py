r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import logging
import os
import platform
import traceback
from contextlib import contextmanager

import ofscraper.actions.process as process_actions
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.read as read_args
import ofscraper.utils.checkers as checkers
import ofscraper.utils.config.data as data
import ofscraper.utils.console as console
import ofscraper.utils.context.exit as exit
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.menu as menu
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.run as run
import ofscraper.utils.system.network as network

log = logging.getLogger("shared")


def process_selected_areas():
    log.debug(f"[bold blue] Running Action Mode [/bold blue]")
    checkers.check_auth()
    checkers.check_config()
    functs = process_actions.add_selected_areas()
    run.run_helper(*functs)
    while True:
        if not data.get_InfiniteLoop() or prompts.continue_prompt() == "No":
            break
        action = prompts.action_prompt()
        if action == "main":
            process_prompts()
            break
        elif action == "quit":
            break
        else:
            menu.get_count() > 0 and menu.reset_menu_helper()
            functs = process_actions.add_selected_areas()
            run.run_helper(*functs)
            menu.update_count()


def daemon_process():
    checkers.check_auth()
    checkers.check_config()
    functs = process_actions.add_selected_areas()
    run.daemon_run_helper(*functs)


@exit.exit_wrapper
def process_prompts():
    while True:
        if menu.main_menu_action():
            break
        elif prompts.continue_prompt() == "No":
            break


def print_start():
    with stdout.lowstdout():
        console.get_shared_console().print(
            f"[bold green]Version {read_args.retriveArgs().version}[/bold green]"
        )


def main():
    try:
        print_start()
        paths.cleanup()
        paths.cleanDB()
        network.check_cdm()

        scrapper()
        paths.cleanup()
        paths.cleanDB()
    except KeyboardInterrupt:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.cleanup()
                paths.cleanDB()
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            raise KeyboardInterrupt
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.cleanup()
                paths.cleanDB()
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E


def scrapper():
    if platform.system() == "Windows":
        os.system("color")
    global selectedusers
    selectedusers = None
    args = read_args.retriveArgs()
    if args.daemon:
        if len(args.action) == 0 and not args.scrape_paid:
            prompts.action_prompt()
        daemon_process()
    elif len(args.action) > 0 or args.scrape_paid:
        process_selected_areas()
    elif len(args.action) == 0:
        process_prompts()
