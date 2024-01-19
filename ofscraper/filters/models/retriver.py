import ofscraper.api.lists as lists
import ofscraper.api.me as me
import ofscraper.api.subscriptions as subscriptions
import ofscraper.classes.models as models
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.console as console
import ofscraper.utils.context.stdout as stdout


def get_models() -> list:
    """
    Get user's subscriptions in form of a list.
    """
    with stdout.lowstdout():
        count = process_me()
        out = []
        active_subscriptions = subscriptions.get_subscriptions(count[0])
        expired_subscriptions = subscriptions.get_subscriptions(
            count[1], account="expired"
        )
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


def get_model(parsed_subscriptions: list) -> tuple:
    """
    Prints user's subscriptions to console and accepts input from user corresponding
    to the model(s) whose content they would like to scrape.
    """
    return prompts.model_selector(parsed_subscriptions)


# check if auth is valid
def process_me():
    my_profile = me.scrape_user()
    name, username = me.parse_user(my_profile)
    subscribe_count = me.parse_subscriber_count()
    me.print_user(name, username)
    return subscribe_count
