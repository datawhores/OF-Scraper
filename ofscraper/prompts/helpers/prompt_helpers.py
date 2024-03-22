import inspect
import re

from prompt_toolkit.shortcuts import prompt as prompt
from rich.console import Console

import ofscraper.models.selector as userselector
import ofscraper.prompts.helpers.model_helpers as modelHelpers
import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.settings as settings

console = Console()


def model_details(prompt_):
    selected = prompt_.content_control.selection["value"]
    console.print(
        inspect.cleandoc(
            f"""
        ========================================================================================================================================

        Name: [bold blue]{selected.name}[/bold blue]
        ----------------------------------------------------------------------------------------------------------------------------------------
        ID: [bold blue]{selected.id}[/bold blue]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Renewed Date: [bold blue]{selected.renewed_string}[/bold blue]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Subscribed Date: [bold blue]{selected.subscribed_string}[/bold blue]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Expired Date: [bold blue]{selected.expired_string}[/bold blue]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Last Seen: [bold blue] {selected.last_seen_formatted}[/bold blue]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Original Sub Price: [bold blue]{selected.sub_price}[/bold blue]   [Current Subscription Price]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Original Regular Price: [bold blue]{selected.regular_price}[/bold blue]   [Regular Subscription Price Set By Model]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Original Claimable Promo Price: [bold blue]{selected.lowest_promo_claim}[/bold blue]   [Lowest Promotional Price Marked as Claimable]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Original Any Promo Price: [bold blue]{selected.lowest_promo_all}[/bold blue]   [Lowest of Any Promotional Price]
        =======================================================================================================================================
        
        [italic yellow]Final Prices Detail =>[ https://of-scraper.gitbook.io/of-scraper/batch-scraping-and-bot-actions/model-selection-sorting/price-filtering-sort][/italic yellow]
        ---------------------------------------------------------------------------------------------------------------------------------------
        Final Current Price: [bold blue]{selected.final_current_price}[/bold blue]   [Sub Price or Lowest Claimable Promo Price or Regular Price| See Final Price Details]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Final Promo Price: [bold blue]{selected.final_promo_price}[/bold blue]   [Lowest Any Promo Price or Regular Price | See Final Price Details]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Final Renewal Price: [bold blue]{selected.final_renewal_price}[/bold blue]   [Lowest Claimable Promo or Regular Price | See Final Price Details]
        ----------------------------------------------------------------------------------------------------------------------------------------
        Final Regular Price: [bold blue]{selected.final_regular_price}[/bold blue]   [Regular Price | See Final Price Details]
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
current_price => [bold blue]{read_args.retriveArgs().current_price if read_args.retriveArgs().current_price else 'paid and free'}[/bold blue]
[Sub Price or Lowest Claimable Promo Price or Regular Price| See Final Price Details]
---------------------------------------------------------------------------------------
promo_price => [bold blue]{read_args.retriveArgs().promo_price if read_args.retriveArgs().promo_price else 'paid and free'}[/bold blue]
[Lowest Any Promo Price or Regular Price | See Final Price Details]
---------------------------------------------------------------------------------------
regular_price => [bold blue]{read_args.retriveArgs().regular_price if read_args.retriveArgs().regular_price else 'paid and free'}[/bold blue]
[Lowest Claimable Promo or Regular Price | See Final Price Details]
---------------------------------------------------------------------------------------
renewal_price => [bold blue]{read_args.retriveArgs().renewal_price if read_args.retriveArgs().renewal_price else 'paid and free'}[/bold blue]
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

sorting by =>  [bold blue]{read_args.retriveArgs().sort}[/bold blue]
---------------------------------------------------------------------------------------
sorting direction => [bold blue]{'desc' if read_args.retriveArgs().desc else 'asc'}[/bold blue]
========================================================================================================================================
PRESS ENTER TO RETURN

    """
        )
    )
    prompt("")
    return prompt_


def model_funct(prompt):
    userselector.setfilter()
    with stdout.nostdout():
        models = userselector.filterOnly()
        choices = list(
            map(
                lambda x: modelHelpers.model_selectorHelper(x[0], x[1]),
                enumerate(models),
            )
        )
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

subscription => [bold blue]{'active' if read_args.retriveArgs().sub_status else 'expired' if read_args.retriveArgs().sub_status==False else 'expired and active'}[/bold blue]
---------------------------------------------------------------------------------------
renew => [bold blue]{'renew on' if read_args.retriveArgs().renewal else 'renew off' if read_args.retriveArgs().renewal==False else 'renew on/off'}[/bold blue]
==========================================================================================================================================

user-list in use=> [bold blue]{settings.get_userlist() or 'no userlist'}[/bold blue]
---------------------------------------------------------------------------------------
black-list in use=> [bold blue]{settings.get_blacklist() or 'no blacklist'}[/bold blue]
==========================================================================================================================================

promo status => [bold blue]{'promo on' if read_args.retriveArgs().promo else 'promo off' if read_args.retriveArgs().promo==False else 'promo off/on'}[/bold blue]
---------------------------------------------------------------------------------------
all promo status => [bold blue]{'all promo on' if read_args.retriveArgs().all_promo else 'all promo off' if read_args.retriveArgs().all_promo==False else 'all promo off/on'}[/bold blue]
==========================================================================================================================================

last-seen => [bold blue]{read_args.retriveArgs().last_seen}[/bold blue]
---------------------------------------------------------------------------------------
last-seen-before => [bold blue]{read_args.retriveArgs().last_seen_before}[/bold blue]
---------------------------------------------------------------------------------------
last-seen-after => [bold blue]{read_args.retriveArgs().last_seen_after}[/bold blue]
==========================================================================================================================================

[italic yellow]Final Prices Detail =>[ https://of-scraper.gitbook.io/of-scraper/batch-scraping-and-bot-actions/model-selection-sorting/price-filtering-sort][/italic yellow]

---------------------------------------------------------------------------------------
current_price => [bold blue]{read_args.retriveArgs().current_price if read_args.retriveArgs().current_price else 'paid and free'}[/bold blue]
[Sub Price or Lowest Claimable Promo Price or Regular Price| See Final Price Details]
---------------------------------------------------------------------------------------
promo_price => [bold blue]{read_args.retriveArgs().promo_price if read_args.retriveArgs().promo_price else 'paid and free'}[/bold blue]
[Lowest Any Promo Price or Regular Price | See Final Price Details]
---------------------------------------------------------------------------------------
regular_price => [bold blue]{read_args.retriveArgs().regular_price if read_args.retriveArgs().regular_price else 'paid and free'}[/bold blue]
[Lowest Claimable Promo or Regular Price | See Final Price Details]
---------------------------------------------------------------------------------------
renewal_price => [bold blue]{read_args.retriveArgs().renewal_price if read_args.retriveArgs().renewal_price else 'paid and free'}[/bold blue]
[Regular Price | See Final Price Details]
=======================================================================================================================================

sorting by =>  [bold blue]{read_args.retriveArgs().sort}[/bold blue]
---------------------------------------------------------------------------------------
sorting direction => [bold blue]{'desc' if read_args.retriveArgs().desc else 'asc'}[/bold blue]
=======================================================================================================================================

PRESS ENTER TO RETURN

    """
        )
    )
    prompt("")
    return prompt_
