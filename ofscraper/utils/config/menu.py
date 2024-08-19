import logging

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.config as config_
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.utils.context as config_context
import ofscraper.utils.console as console_

console = console_.get_shared_console()
log = logging.getLogger("shared")


def update_config_helper(updated_config):
    current_config = config_file.open_config()
    config_.update_config_full(current_config, updated_config)
    console.print("`config.json` has been successfully edited.")


def download_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.download_config()
    update_config_helper(updated_config)


def file_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.file_config()
    update_config_helper(updated_config)


def binary_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.binary_config()
    update_config_helper(updated_config)


def cdm_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.cdm_config()
    update_config_helper(updated_config)


def performance_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.performance_config()
    update_config_helper(updated_config)


def general_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.general_config()
    update_config_helper(updated_config)


def advanced_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.advanced_config()
    update_config_helper(updated_config)


def response_type():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.response_type()
    update_config_helper(updated_config)


def content_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.content_config()
    update_config_helper(updated_config)


def script_config():
    with config_context.config_context():
        config_file.open_config()
        updated_config = prompts.script_config()
    update_config_helper(updated_config)
