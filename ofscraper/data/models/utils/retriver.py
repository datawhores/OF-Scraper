import logging
import ofscraper.data.api.me as me
import ofscraper.data.api.subscriptions.individual as individual
import ofscraper.data.api.subscriptions.lists as lists
import ofscraper.data.api.subscriptions.subscriptions as subscriptions
import ofscraper.classes.of.models as models
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.console as console
import ofscraper.utils.me as me_util
from ofscraper.utils.live.updater import activity
import ofscraper.utils.settings as settings


async def get_models(all_main_models: bool = False) -> list:
    """
    Get user's subscriptions. Can be forced to fetch all models.
    """
    activity.update_task(description="Getting subscriptions")
    # if the anon flag is on force individual
    if settings.get_settings().anon:
        return await get_via_individual()
    # actions for if anon flag is falses
    count = get_sub_count()
    if all_main_models:
        return await get_via_main_list(count)
    # --- Existing logic for when all_main_models is False ---
    if not bool(settings.get_settings().usernames):
        return await get_via_list(count)
    elif "ALL" in settings.get_settings().usernames:
        return await get_via_list(count)
    elif settings.get_settings().username_search == "indvidual":
        return await get_via_individual()
    elif settings.get_settings().username_search == "list":
        return await get_via_list(count)
    elif (sum(count) // 12) >= len(settings.get_settings().usernames):
        return await get_via_individual()
    else:
        return await get_via_list(count)


async def get_via_main_list(count):
    out = []
    active_subscriptions = await subscriptions.get_all_subscriptions(count[0])
    expired_subscriptions = await subscriptions.get_all_subscriptions(
        count[1], account="expired"
    )
    out.extend(active_subscriptions)
    out.extend(expired_subscriptions)
    models_objects = list(map(lambda x: models.Model(x), out))
    return models_objects


async def get_via_list(count):
    out = []
    active_subscriptions = await subscriptions.get_subscriptions(count[0])
    expired_subscriptions = await subscriptions.get_subscriptions(
        count[1], account="expired"
    )
    console.get_shared_console().print(
        "[yellow]Warning: Numbering on OF site can be iffy\nExample Including deactived accounts in expired\nSee: https://of-scraper.gitbook.io/of-scraper/faq#number-of-users-doesnt-match-account-number[/yellow]"
    )

    other_subscriptions = await lists.get_otherlist()
    out.extend(active_subscriptions)
    out.extend(expired_subscriptions)
    out.extend(other_subscriptions)
    black_list = await lists.get_blacklist()
    out = list(filter(lambda x: x.get("id") not in black_list, out))
    models_objects = list(map(lambda x: models.Model(x), out))
    return models_objects


async def get_via_individual():
    out = await individual.get_subscription()
    console.get_shared_console().print(
        "[yellow]Warning: Numbering on OF site can be iffy\nExample Including deactived accounts in expired\nSee: https://of-scraper.gitbook.io/of-scraper/faq#number-of-users-doesnt-match-account-number[/yellow]"
    )
    models_objects = list(map(lambda x: models.Model(x), out))
    if len(models_objects) == 0:
        logging.getLogger("shared").warning("[bold red]No models were found[/bold red]")
        raise Exception("Provided usernames did not yield any valid models")
    return models_objects


def get_selected_model(parsed_subscriptions: list,existing_models:list) -> tuple:
    """
    Prints user's subscriptions to console and accepts input from user corresponding
    to the model(s) whose content they would like to scrape.
    """
    return prompts.model_selector(parsed_subscriptions,existing_models)


def get_sub_count():
    name, username = me_util.parse_user()
    subscribe_count = me.parse_subscriber_count()
    me_util.print_user(name, username)
    return subscribe_count
