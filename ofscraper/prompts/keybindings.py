fuzzy = {
    "toggle": [
        {"key": ["pagedown"]},
        {"key": ["home"]},
        {"key": ["end"]},
        {"key": ["pageup"]},
        {"key": ["s-right"]},
    ],
    "toggle-all": [{"key": ["c-a"]}],
    "toggle-all-false": [{"key": ["c-d"]}],
    "toggle-all-true": [{"key": ["c-s"]}],
}

select = {
    "answer": [
        {"key": ["s-right"]},
        {"key": ["pagedown"]},
        {"key": ["home"]},
        {"key": ["end"]},
        {"key": ["space"]},
        {"key": ["enter"]},
        {"key": ["pageup", "enter"]},
    ]
}

input = select
file = select
number = select
multiline = {
    "answer": [
        {"key": ["pagedown", "enter"]},
        {"key": ["home", "enter"]},
        {"key": ["end", "enter"]},
        {"key": ["pageup", "enter"]},
        {"key": ["space", "enter"]},
        {"key": ["escape"]},
    ]
}
