KEY_OPTIONS = ["cdrm", "manual"]
DYNAMIC_OPTIONS = [
    "digitalcriminals",
    "manual",
    "generic",
    "xagler",
    "rafa",
]
# rules that were removed, and why; a config.json that still names one falls
# back to the default with this reason in the warning
REMOVED_DYNAMIC_RULES = {}
# other names accepted for a dynamic rule, and the rule each one picks
DYNAMIC_ALIASES = {
    "dc": "digitalcriminals",
    "digital": "digitalcriminals",
    "digitals": "digitalcriminals",
    "digitalcriminal": "digitalcriminals",
    # the datawhores rule source was removed (#596); upstream's docs and
    # configs still name it, so it picks digitalcriminals
    "datawhores": "digitalcriminals",
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

# Timeline-style post areas shared across CLI choices, filters, DB writes and refresh
TIMELINE_POST_AREAS = ("Timeline", "Pinned", "Archived", "Streams")
TIMELINE_POST_AREA_SET = frozenset(TIMELINE_POST_AREAS)
TIMELINE_POST_AREA_CHOICES = (
    "All",
    "Archived",
    "Timeline",
    "Pinned",
    "Labels",
    "Streams",
)
