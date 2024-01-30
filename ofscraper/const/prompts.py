mainPromptChoices = {
    "Perform Action": "actiion",
    "Edit auth.json file": "auth",
    "Edit config.json file": "config",
    "Edit Profile": "profile",
    "Quit": "quit",
}

configPromptChoices = {
    "Perform Action": 0,
    "Edit auth.json file": 1,
    "Edit config.json file": 2,
    "Edit advanced config.json settings": 3,
    "Go to main menu": "menu",
    "Quit": "quit",
}


ActionPromptChoices = {
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
    "Select from accounts on profile": 0,
    "Enter a username": 1,
    "Scrape all users that I'm subscribed to": 2,
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
