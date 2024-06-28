import ofscraper.prompts.prompts as prompts


def check_auth_warning(auth):
    if prompts.check_auth_prompt(auth):
        return True
    return False
