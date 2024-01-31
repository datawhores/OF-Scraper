import functools

from InquirerPy import get_style, inquirer
from InquirerPy.separator import Separator
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.keybindings as keybindings
import ofscraper.prompts.prompt_strings as prompt_strings


def wrapper(funct):
    def inner(*args, **kwargs):
        # setup
        long_message = functools.partial(
            handle_skip_helper,
            kwargs.pop("long_message", None) or get_default_instructions(funct),
        )
        kwargs["long_instruction"] = kwargs.get(
            "long_instruction", prompt_strings.KEY_BOARD
        )
        kwargs["message"] = f"{kwargs.get('message')}" if kwargs.get("message") else ""

        altx_action = kwargs.pop("altx", None) or (lambda prompt: None)
        altd_action = kwargs.pop("altd", None) or (lambda prompt: None)
        altv_action = kwargs.pop("altv", None) or long_message

        action_set = set()

        prompt_ = funct(*args, **kwargs)

        @prompt_.register_kb("alt-x")
        def _handle_alt_x(event):
            action_set.add("altx")
            event.app.exit()

        @prompt_.register_kb("c-b")
        def _handle_alt_x(event):
            action_set.add("altx")
            event.app.exit()

        @prompt_.register_kb("alt-v")
        def _handle_alt_v(event):
            action_set.add("altv")
            event.app.exit()

        @prompt_.register_kb("c-v")
        def _handle_alt_v(event):
            action_set.add("altv")
            event.app.exit()

        @prompt_.register_kb("alt-d")
        def _handle_altd(event):
            action_set.add("alt-d")
            event.app.exit()

        while True:
            out = prompt_.execute()
            prompt_._default = get_default(funct, prompt_)
            if "altx" in action_set:
                prompt_ = altx_action(prompt_)
            elif "altv" in action_set:
                altv_action()
            elif "alt-d" in action_set:
                altd_action(prompt_)
            else:
                break
            action_set = set()

        return out

    return inner


def get_default(funct, prompt):
    if funct.__name__ in {"getChecklistSelection", "getFuzzySelection", "checkbox"}:
        return prompt.selected_choices
    elif funct.__name__ in {"number_type"}:
        return prompt.value
    else:
        return prompt._session.default_buffer.text


def get_default_instructions(funct):
    if funct.__name__ == "getChecklistSelection":
        return prompt_strings.CHECKLISTINSTRUCTIONS
    elif funct.__name__ == "getFuzzySelection":
        return prompt_strings.FUZZY_INSTRUCTION
    elif funct.__name__ == "multiline_input_prompt":
        return prompt_strings.MULTI_LINE
    elif funct.__name__ == "input_prompt":
        return prompt_strings.SINGLE_LINE
    elif funct.__name__ == "number_type":
        return prompt_strings.SINGLE_LINE

    elif funct.__name__ == "checkbox":
        return prompt_strings.FUZZY_INSTRUCTION
    elif funct.__name__ == "checkbox":
        return prompt_strings.FUZZY_INSTRUCTION


@wrapper
def getChecklistSelection(*args, **kwargs):
    prompt = inquirer.select(
        *args, keybindings=keybindings.select, mandatory=False, **kwargs
    )

    @prompt.register_kb("c-d")
    def _handle_toggle_all_false(event):
        for choice in prompt.content_control._filtered_choices:
            raw_choice = prompt.content_control.choices[choice["index"]]
            if isinstance(raw_choice["value"], Separator):
                continue
            raw_choice["enabled"] = False

    return prompt


@wrapper
def getFuzzySelection(*args, **kwargs):
    prompt = inquirer.fuzzy(
        *args,
        marker="\u25c9 ",
        marker_pl="\u25cb ",
        style=get_style(
            {
                "questionmark": "fg:#e5c07b bg:#ffffff",
                "answermark": "#e5c07b",
                "answer": "#61afef",
                "input": "#98c379",
                "question": "",
                "answered_question": "",
                "instruction": "#abb2bf",
                "long_instruction": "#abb2bf",
                "pointer": "#61afef",
                "checkbox": "#98c379",
                "separator": "",
                "skipped": "#5c6370",
                "validator": "",
                "marker": "#e5c07b",
                "fuzzy_prompt": "#c678dd",
                "fuzzy_info": "#abb2bf",
                "fuzzy_border": "#4b5263",
                "fuzzy_match": "#c678dd bold",
                "spinner_pattern": "#e5c07b",
                "spinner_text": "",
            }
        ),
        keybindings=keybindings.fuzzy,
        mandatory=False,
        **kwargs,
    )
    return prompt


@wrapper
def checkbox(*args, **kwargs):
    return inquirer.checkbox(keybindings=keybindings.fuzzy, *args, **kwargs)


@wrapper
def input_prompt(*args, **kwargs):
    prompt = inquirer.text(
        *args, mandatory=False, keybindings=keybindings.input, **kwargs
    )
    return prompt


@wrapper
def multiline_input_prompt(*args, **kwargs):
    prompt = inquirer.text(
        *args, mandatory=False, keybindings=keybindings.multiline, **kwargs
    )

    return prompt


@wrapper
def file_type(*args, **kwargs):
    return inquirer.filepath(*args, keybindings=keybindings.file, **kwargs)


@wrapper
def number_type(*args, **kwargs):
    return inquirer.number(*args, keybindings=keybindings.number, **kwargs)


@wrapper
def confirm_prompt(*args, **kwargs):
    return inquirer.confirm(*args, **kwargs)


def getType(input_type):
    if input_type == "checkbox":
        return checkbox
    elif input_type == "list":
        return getChecklistSelection
    elif input_type == "fuzzy":
        return getFuzzySelection

    elif input_type == "input":
        return input_prompt
    elif input_type == "multiline":
        return multiline_input_prompt
    elif input_type == "confirm":
        return confirm_prompt
    elif input_type == "filepath":
        return file_type
    elif input_type == "number":
        return number_type


def batchConverterHelper(ele, kwargs):
    ele_type = ele.pop("type")
    ele_type = "multiline" if ele.get("multiline") else ele_type
    ele_type = "fuzzy" if ele.get("fuzzy") else ele_type
    name = ele.pop("name")
    kwargs = kwargs or {}
    ele["long_instruction"] = ele.get("long_instruction", "") + kwargs.pop(
        "long_instruction", ""
    )
    return name, getType(ele_type)(**kwargs, **ele)


def batchConverter(*args, **kwargs):
    outDict = {}
    outDict.update(list(map(lambda x: batchConverterHelper(x, kwargs), args)))
    return outDict


def handle_skip_helper(message):
    print(message)
    prompt("")
