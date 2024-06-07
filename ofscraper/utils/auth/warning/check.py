import ofscraper.prompts.prompts as prompts
def check_auth_warning():
    if prompts.check_auth_prompt():
        return True
    return False