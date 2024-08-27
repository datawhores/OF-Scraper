import functools
import inspect

from InquirerPy import get_style, inquirer
from InquirerPy.separator import Separator
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.keybindings as keybindings
import ofscraper.prompts.prompt_strings as prompt_strings
from ofscraper.utils.live.empty import prompt_live
from  ofscraper.utils.live.clear import clear



def wrapper(prompt_funct):
    def inner(*args, **kwargs):
        # setup
        long_message = functools.partial(
            handle_skip_helper,
            kwargs.pop("long_message", None)
            or get_default_instructions(prompt_funct),
        )
        funct = kwargs.pop("call", None)
        kwargs["long_instruction"] = "\n".join(
            list(
                filter(
                    lambda x: len(x) > 0,
                    [
                        inspect.cleandoc(
                            f"{kwargs.pop('option_instruction', '')}".upper()
                        ),
                        inspect.cleandoc(
                            f"{kwargs.get('long_instruction', prompt_strings.KEY_BOARD)}".upper()
                        ),
                        inspect.cleandoc(
                            f"{kwargs.pop('more_instruction', '') or kwargs.pop('more_instructions', '')}".upper()
                        ),
                    ],
                )
            )
        )
        kwargs["message"] = (
            f"{kwargs.get('message')}" if kwargs.get("message") else ""
        )

        altv_action = kwargs.pop("altv", None) or long_message
        altx_action = kwargs.pop("altx", None)
        altd_action = kwargs.pop("altd", None)
        additional_keys = kwargs.pop("additional_keys", {})
        action = [None]
        with prompt_live():

            prompt_ = prompt_funct(*args, **kwargs)

            register_keys(prompt_, altx_action, altd_action, additional_keys, action)

            while True:
                    funct() if funct else None
                    clear()
                    out = prompt_.execute()
                    prompt_._default = get_default(prompt_funct, prompt_)
                    select = action[0]
                    action[0] = None
                    if select == "altx":
                        prompt_ = altx_action(prompt_)
                    elif select == "altv":
                        altv_action()
                    elif select == "altd":
                        altd_action(prompt_)
                    elif additional_keys.get(select):
                        prompt_ = additional_keys.get(select)(prompt_)
                    else:
                        break

        return out

    return inner


def register_keys(prompt_, altx_action, altd_action, additional_keys, action):
    for key in (additional_keys).keys():
        extra_key_helper(prompt_, key, action)

    if altx_action:

        @prompt_.register_kb("alt-x")
        def _handle_alt_x(event):
            action[0] = "altx"
            event.app.exit()

        @prompt_.register_kb("c-b")
        def _handle_alt_x(event):
            action[0] = "altx"
            event.app.exit()

    if altd_action:

        @prompt_.register_kb("alt-d")
        def _handle_altd(event):
            action[0] = "altd"
            event.app.exit()

    @prompt_.register_kb("alt-v")
    def _handle_alt_v(event):
        action[0] = "altv"
        event.app.exit()

    @prompt_.register_kb("c-v")
    def _handle_alt_v(event):
        action[0] = "altv"
        event.app.exit()


def extra_key_helper(prompt_, key, action):
    @prompt_.register_kb(key.lower())
    def _handle_alt(event):
        action[0] = key
        event.app.exit()


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
    return name, getType(ele_type)(**kwargs, **ele)


def batchConverter(*args, **kwargs):
    outDict = {}
    outDict.update(list(map(lambda x: batchConverterHelper(x, kwargs), args)))
    return outDict


def handle_skip_helper(message):
    print(message)
    prompt("")
