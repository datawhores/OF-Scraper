import ofscraper.api.me as me
import ofscraper.api.subscriptions.individual as individual
import ofscraper.api.subscriptions.lists as lists
import ofscraper.api.subscriptions.subscriptions as subscriptions
import ofscraper.classes.models as models
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.me as me_util


def get_models(main=False) -> list:
    """
    Get user's subscriptions in form of a list.
    """
    with stdout.lowstdout():
        count = get_sub_count()
        if not bool(read_args.retriveArgs().username):
            return get_via_list(count)
        elif "ALL" in read_args.retriveArgs().username:
            return get_via_list(count)
        elif read_args.retriveArgs().individual:
            return get_via_individual()
        elif read_args.retriveArgs().list:
            return get_via_list(count)
        elif (sum(count) // 10) > len(read_args.retriveArgs().username):
            return get_via_individual()
        else:
            return get_via_list(count)


def get_via_list(count):
    out = []
    active_subscriptions = subscriptions.get_subscriptions(count[0])
    expired_subscriptions = subscriptions.get_subscriptions(count[1], account="expired")
    console.get_shared_console().print(
        "[yellow]Warning: Numbering on OF site can be iffy\nExample Including deactived accounts in expired\nSee: https://of-scraper.gitbook.io/of-scraper/faq#number-of-users-doesnt-match-account-number[/yellow]"
    )

    other_subscriptions = lists.get_otherlist()
    out.extend(active_subscriptions)
    out.extend(expired_subscriptions)
    out.extend(other_subscriptions)
    black_list = lists.get_blacklist()
    out = list(filter(lambda x: x.get("id") not in black_list, out))
    models_objects = list(map(lambda x: models.Model(x), out))
    return models_objects


def get_main_list(count):
    out = []
    active_subscriptions = subscriptions.get_subscriptions(count[0], forced=True)
    expired_subscriptions = subscriptions.get_subscriptions(
        count[1], account="expired", forced=True
    )
    out.extend(active_subscriptions)
    out.extend(expired_subscriptions)
    return out


def get_via_individual():
    out = individual.get_subscription()
    console.get_shared_console().print(
        "[yellow]Warning: Numbering on OF site can be iffy\nExample Including deactived accounts in expired\nSee: https://of-scraper.gitbook.io/of-scraper/faq#number-of-users-doesnt-match-account-number[/yellow]"
    )
    models_objects = list(map(lambda x: models.Model(x), out))
    if len(models_objects) == 0:
        raise Exception("Provided usernames with did not yield any valid models")
    return models_objects


def get_selected_model(parsed_subscriptions: list) -> tuple:
    """
    Prints user's subscriptions to console and accepts input from user corresponding
    to the model(s) whose content they would like to scrape.
    """
    return prompts.model_selector(parsed_subscriptions)


# check if auth is valid
def get_sub_count():
    my_profile = me.scrape_user()
    name, username = me_util.parse_user(my_profile)
    subscribe_count = me.parse_subscriber_count()
    me_util.print_user(name, username)
    return subscribe_count
