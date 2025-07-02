def load_prompts_config():
    """
    Loads configuration dictionaries for various interactive prompts within the application.
    These are typically static UI choices and are best managed as internal Python constants.

    Returns:
        A dictionary containing all loaded prompt choice dictionaries.
    """
    config = {}

    # --- Main Prompt Choices ---
    config["mainPromptChoices"] = {
        "Perform Action(s)": "action",
        "Edit auth.json file": "auth",
        "Edit config.json file": "config",
        "Edit Profile": "profile",
        "Merge Databases": "merge",
        "Quit": "quit",
    }

    # --- Config Prompt Choices ---
    config["configPromptChoices"] = {
        "General Options": "general",
        "File Options": "file",
        "Download Options": "download",
        "Binary Options": "binary",
        "Script Options": "script",
        "CDM Options": "cdm",
        "Performance Options": "performance",
        "Content Options": "content",
        "Response Type": "response",
        "Advanced Options": "advanced",
        "Go to main menu": "main",
        "Quit": "quit",
    }

    # --- Action Prompt Choices ---
    config["actionPromptChoices"] = {
        "Download content from a user": {"download"},
        "Like a selection of a user's posts": {"like"},
        "Unlike a selection of a user's posts": {"unlike"},
        "Download content from a user + Like a selection of a user's posts": {
            "like",
            "download",
        },
        "Download content from a user + Unlike a selection of a user's posts": {
            "unlike",
            "download",
        },
        "Go to main menu": "main",
        "Quit": "quit",
    }

    # --- Username or List Choices ---
    config["usernameOrListChoices"] = {
        "Select from accounts on profile": "select",
        "Enter a username": "enter",
        "Scrape all users that I'm subscribed to": "sub",
    }

    # --- Profiles Prompt Choices ---
    config["profilesPromptChoices"] = {
        "Change default profile": "default",
        "Edit a profile name": "name",
        "Create a profile": "create",
        "Delete a profile": "delete",
        "View profiles": "view",
        "Go to main menu": "main",
        "Quit": "quit",
    }

    # --- Model Prompt Choices ---
    config["modelPrompt"] = {
        "Filter model list by subscription properties": "subtype",
        "Filter model list by account activity": "active",
        "Filter model list based on promotion status": "promo",
        "Filter model list based on status of prices": "price",
        "Change sorting of model list": "sort",
        "Change to a different userlist/blacklist [May require rescan]": "list",
        "Reset all filters": "reset_filters",
        "Clear blacklist and switch to the 'main' userlist [May require rescan]": "reset_list",
        "Rescan userlist": "rescan",
        "Go Back to model lists": "model_list",
    }

    return config
