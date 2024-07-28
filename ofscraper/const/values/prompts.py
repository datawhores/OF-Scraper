mainPromptChoices = {
    "Perform Action(s)": "action",
    "Edit auth.json file": "auth",
    "Edit config.json file": "config",
    "Edit Profile": "profile",
    "Merge Databases": "merge",
    "Quit": "quit",
}

configPromptChoices = {
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


actionPromptChoices = {
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
usernameOrListChoices = {
    "Select from accounts on profile": "select",
    "Enter a username": "enter",
    "Scrape all users that I'm subscribed to": "sub",
}
profilesPromptChoices = {
    "Change default profile": "default",
    "Edit a profile name": "name",
    "Create a profile": "create",
    "Delete a profile": "delete",
    "View profiles": "view",
    "Go to main menu": "main",
    "Quit": "quit",
}


modelPrompt = {
    "Filter model list by subscription properties": "subtype",
    "Filter model list by account activity": "active",
    "Filter model list based on promotion status": "promo",
    "Filter model list based on status of prices": "price",
    "Change sorting of model list": "sort",
    "Change to a different list [May require rescan]": "list",
    "Remove all model list filters": "reset",
    "Go Back to Model Lists": "modelList",
}
