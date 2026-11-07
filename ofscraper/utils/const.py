KEY_OPTIONS = ["cdrm", "manual"]
DYNAMIC_OPTIONS = [
    "digitalcriminals",
    "manual",
    "generic",
    "datawhores",
    "xagler",
    "rafa",
]
# other names accepted for a dynamic rule, and the rule each one picks
DYNAMIC_ALIASES = {
    "dc": "digitalcriminals",
    "digital": "digitalcriminals",
    "digitals": "digitalcriminals",
    "digitalcriminal": "digitalcriminals",
}
# the name the config menu lists and saves for a rule, when it isn't the
# rule's own name; "digital" is also the default in a new config.json
DYNAMIC_MENU_NAMES = {
    "digitalcriminals": "digital",
}

MEDIA_ALIASES = {
    "photo": "images",
    "photos": "images",
    "image": "images",
    "images": "images",
    "audio": "audios",
    "audios": "audios",
    "video": "videos",
    "videos": "videos",
    "gif": "videos",
    "gifs": "videos",
}