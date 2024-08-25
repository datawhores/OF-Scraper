import inspect
import re

import pynumparser
from InquirerPy.base import Choice
from prompt_toolkit.shortcuts import prompt as prompt
from rich.console import Console

import ofscraper.filters.models.sort as sort
import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.promptConvert as promptConvert
import ofscraper.prompts.utils.model_helpers as modelHelpers
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.settings as settings
import  ofscraper.runner.manager as manager


console = Console()


def model_details(prompt_):
    selected = prompt_.content_control.selection["value"]
    console.print(
        inspect.cleandoc(
            f"""
        ========================================================================================================================================

        Name: [bold deep_sky_blue2]{selected.name}[/bold deep_sky_blue2]
        ----------------------------------------------------------------------------------------------------------------------------------------
        ID: [bold deep_sky_blue2]{selected.id}[/bold deep_sky_blue2]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Renewed Date: [bold deep_sky_blue2]{selected.renewed_string}[/bold deep_sky_blue2]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Subscribed Date: [bold deep_sky_blue2]{selected.subscribed_string}[/bold deep_sky_blue2]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Expired Date: [bold deep_sky_blue2]{selected.expired_string}[/bold deep_sky_blue2]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Last Seen: [bold deep_sky_blue2] {selected.last_seen_formatted}[/bold deep_sky_blue2]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Original Sub Price: [bold deep_sky_blue2]{selected.sub_price}[/bold deep_sky_blue2]   [Current Subscription Price]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Original Regular Price: [bold deep_sky_blue2]{selected.regular_price}[/bold deep_sky_blue2]   [Regular Subscription Price Set By Model]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Original Claimable Promo Price: [bold deep_sky_blue2]{selected.lowest_promo_claim}[/bold deep_sky_blue2]   [Lowest Promotional Price Marked as Claimable]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Original Any Promo Price: [bold deep_sky_blue2]{selected.lowest_promo_all}[/bold deep_sky_blue2]   [Lowest of Any Promotional Price]
        =======================================================================================================================================
        
        [italic yellow]Final Prices Detail =>[ https://of-scraper.gitbook.io/of-scraper/batch-scraping-and-bot-actions/model-selection-sorting/price-filtering-sort][/italic yellow]
        ---------------------------------------------------------------------------------------------------------------------------------------
        Final Current Price: [bold deep_sky_blue2]{selected.final_current_price}[/bold deep_sky_blue2]   [Sub Price or Lowest Claimable Promo Price or Regular Price| See Final Price Details]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Final Promo Price: [bold deep_sky_blue2]{selected.final_promo_price}[/bold deep_sky_blue2]   [Lowest Any Promo Price or Regular Price | See Final Price Details]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Final Renewal Price: [bold deep_sky_blue2]{selected.final_renewal_price}[/bold deep_sky_blue2]   [Lowest Claimable Promo or Regular Price | See Final Price Details]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Final Regular Price: [bold deep_sky_blue2]{selected.final_regular_price}[/bold deep_sky_blue2]   [Regular Price | See Final Price Details]
        =======================================================================================================================================  

        PRESS ENTER TO RETURN
        """
        )
    )
    prompt("")
    return prompt_


def price_info(prompt_):
    console.print(
        inspect.cleandoc(
            f"""
========================================================================================================================================

[italic yellow]Final Prices Detail =>[ https://of-scraper.gitbook.io/of-scraper/batch-scraping-and-bot-actions/model-selection-sorting/price-filtering-sort][/italic yellow]

---------------------------------------------------------------------------------------
current_price => [bold deep_sky_blue2]{read_args.retriveArgs().current_price if read_args.retriveArgs().current_price else 'paid and free'}[/bold deep_sky_blue2]
[Sub Price or Lowest Claimable Promo Price or Regular Price| See Final Price Details]
---------------------------------------------------------------------------------------
promo_price => [bold deep_sky_blue2]{read_args.retriveArgs().promo_price if read_args.retriveArgs().promo_price else 'paid and free'}[/bold deep_sky_blue2]
[Lowest Any Promo Price or Regular Price | See Final Price Details]
---------------------------------------------------------------------------------------
regular_price => [bold deep_sky_blue2]{read_args.retriveArgs().regular_price if read_args.retriveArgs().regular_price else 'paid and free'}[/bold deep_sky_blue2]
[Lowest Claimable Promo or Regular Price | See Final Price Details]
---------------------------------------------------------------------------------------
renewal_price => [bold deep_sky_blue2]{read_args.retriveArgs().renewal_price if read_args.retriveArgs().renewal_price else 'paid and free'}[/bold deep_sky_blue2]
[Regular Price | See Final Price Details]
==========================================================================================================================================

PRESS ENTER TO RETURN

    """
        )
    )
    prompt("")
    return prompt_


def sort_info(prompt_):
    console.print(
        inspect.cleandoc(
            f"""
========================================================================================================================================

sorting by =>  [bold deep_sky_blue2]{read_args.retriveArgs().sort}[/bold deep_sky_blue2]
---------------------------------------------------------------------------------------
sorting direction => [bold deep_sky_blue2]{'desc' if read_args.retriveArgs().desc else 'asc'}[/bold deep_sky_blue2]
========================================================================================================================================
PRESS ENTER TO RETURN

    """
        )
    )
    prompt("")
    return prompt_


def model_funct(prompt):
    manager.Manager.model_manager.setfilter()
    with stdout.nostdout():
        choices = _get_choices()
        selectedSet = set(
            map(
                lambda x: re.search("^[0-9]+: ([^ ]+)", x["name"]).group(1),
                prompt.selected_choices or [],
            )
        )
        for model in choices:
            name = re.search("^[0-9]+: ([^ ]+)", model.name).group(1)
            if name in selectedSet:
                model.enabled = True
        prompt.content_control._raw_choices = choices
        prompt.content_control.choices = prompt.content_control._get_choices(
            prompt.content_control._raw_choices, prompt.content_control._default
        )
        prompt.content_control._format_choices()
        return prompt


def model_select_funct(prompt):
    with stdout.nostdout():
        try:
            toggle = promptConvert.getChecklistSelection(
                choices=[
                    Choice(True, "Range Select"),
                    Choice(False, "Range Deselect"),
                ]
            )

            # select new
            choices = _select_helper(prompt, toggle)
            prompt.content_control._raw_choices = choices
            prompt.content_control.choices = prompt.content_control._get_choices(
                prompt.content_control._raw_choices, prompt.content_control._default
            )
            prompt.content_control._format_choices()
            return prompt
        except Exception as E:
            raise E


def _select_helper(prompt, toggle=True):
    try:
        choices = _get_choices()
        selectedSet = set(
            map(
                lambda x: re.search("^[0-9]+: ([^ ]+)", x["name"]).group(1),
                prompt.selected_choices or [],
            )
        )

        changes = set(
            pynumparser.NumberSequence().parse(
                promptConvert.multiline_input_prompt(
                    message="Enter Num Sequences: ",
                    more_instruction="Example Input: '1-2,20-50 => [1,2,20...50] inclusive' ",
                )
            )
        )
        if toggle:
            for count, model in enumerate(choices):
                name = re.search("^[0-9]+: ([^ ]+)", model.name).group(1)
                if name in selectedSet or count + 1 in changes:
                    model.enabled = True
        elif not toggle:
            for count, model in enumerate(choices):
                name = re.search("^[0-9]+: ([^ ]+)", model.name).group(1)
                if name in selectedSet and count + 1 not in changes:
                    model.enabled = True

    except Exception as E:
        raise E
    return choices


def _get_choices():
    models =manager.Manager.model_manager.filterOnly()
    models = sort.sort_models_helper(models)
    return list(
        map(
            lambda x: modelHelpers.model_selectorHelper(x[0], x[1]),
            enumerate(models),
        )
    )


def user_list(model_str):
    model_list = re.split("(,|\n)", model_str)
    model_list = map(lambda x: re.sub("[^a-zA-Z0-9 ]", "", x), model_list)
    model_list = filter(lambda x: len(x) != 0, model_list)
    return model_list


def get_list_details(white=True):
    return (
        f"""
    {prompt_strings.LIST_PROMPT_INFO}
Default User Lists : {config_data.get_default_userlist() or 'No Default List Selected'}
    """
        if white
        else f"""{prompt_strings.LIST_PROMPT_INFO}
Default Black Lists : {config_data.get_default_blacklist() or 'No Default List Selected'}
    """
    )


def get_current_filters(prompt_):
    console.print(
        inspect.cleandoc(
            f"""
========================================================================================================================================

subscription => [bold deep_sky_blue2]{'active' if read_args.retriveArgs().sub_status else 'expired' if read_args.retriveArgs().sub_status is False else 'expired and active'}[/bold deep_sky_blue2]
---------------------------------------------------------------------------------------
renew => [bold deep_sky_blue2]{'renew on' if read_args.retriveArgs().renewal else 'renew off' if read_args.retriveArgs().renewal is False else 'renew on/off'}[/bold deep_sky_blue2]
==========================================================================================================================================

user-list in use=> [bold deep_sky_blue2]{settings.get_userlist() or 'no userlist'}[/bold deep_sky_blue2]
---------------------------------------------------------------------------------------
black-list in use=> [bold deep_sky_blue2]{settings.get_blacklist() or 'no blacklist'}[/bold deep_sky_blue2]
==========================================================================================================================================

promo status => [bold deep_sky_blue2]{'promo on' if read_args.retriveArgs().promo else 'promo off' if read_args.retriveArgs().promo is False else 'promo off/on'}[/bold deep_sky_blue2]
---------------------------------------------------------------------------------------
all promo status => [bold deep_sky_blue2]{'all promo on' if read_args.retriveArgs().all_promo else 'all promo off' if read_args.retriveArgs().all_promo is False else 'all promo off/on'}[/bold deep_sky_blue2]
==========================================================================================================================================

last-seen => [bold deep_sky_blue2]{read_args.retriveArgs().last_seen}[/bold deep_sky_blue2]
---------------------------------------------------------------------------------------
last-seen-before => [bold deep_sky_blue2]{read_args.retriveArgs().last_seen_before}[/bold deep_sky_blue2]
---------------------------------------------------------------------------------------
last-seen-after => [bold deep_sky_blue2]{read_args.retriveArgs().last_seen_after}[/bold deep_sky_blue2]
==========================================================================================================================================

[italic yellow]Final Prices Detail =>[ https://of-scraper.gitbook.io/of-scraper/batch-scraping-and-bot-actions/model-selection-sorting/price-filtering-sort][/italic yellow]

---------------------------------------------------------------------------------------
current_price => [bold deep_sky_blue2]{read_args.retriveArgs().current_price if read_args.retriveArgs().current_price else 'paid and free'}[/bold deep_sky_blue2]
[Sub Price or Lowest Claimable Promo Price or Regular Price| See Final Price Details]
---------------------------------------------------------------------------------------
promo_price => [bold deep_sky_blue2]{read_args.retriveArgs().promo_price if read_args.retriveArgs().promo_price else 'paid and free'}[/bold deep_sky_blue2]
[Lowest Any Promo Price or Regular Price | See Final Price Details]
---------------------------------------------------------------------------------------
regular_price => [bold deep_sky_blue2]{read_args.retriveArgs().regular_price if read_args.retriveArgs().regular_price else 'paid and free'}[/bold deep_sky_blue2]
[Lowest Claimable Promo or Regular Price | See Final Price Details]
---------------------------------------------------------------------------------------
renewal_price => [bold deep_sky_blue2]{read_args.retriveArgs().renewal_price if read_args.retriveArgs().renewal_price else 'paid and free'}[/bold deep_sky_blue2]
[Regular Price | See Final Price Details]
=======================================================================================================================================

sorting by =>  [bold deep_sky_blue2]{read_args.retriveArgs().sort}[/bold deep_sky_blue2]
---------------------------------------------------------------------------------------
sorting direction => [bold deep_sky_blue2]{'desc' if read_args.retriveArgs().desc else 'asc'}[/bold deep_sky_blue2]
=======================================================================================================================================

PRESS ENTER TO RETURN

    """
        )
    )
    prompt("")
    return prompt_
