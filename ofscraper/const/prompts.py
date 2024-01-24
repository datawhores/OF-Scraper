mainPromptChoices = {
    "Perform Action": 0,
    "Edit auth.json file": 1,
    "Edit config.json file": 2,
    "Edit advanced config.json settings": 3,
    "Edit Profile": 4,
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
    "Change default profile": 0,
    "Edit a profile name": 1,
    "Create a profile": 2,
    "Delete a profile": 3,
    "View profiles": 4,
    "Go to main menu": "main",
    "Quit": "quit",
}
