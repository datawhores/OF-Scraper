import ofscraper.commands.scraper.actions.download as download_action
import ofscraper.commands.scraper.actions.like as like_action
import ofscraper.utils.args.accessors.read as read_args


async def execute_user_action(posts=None, like_posts=None, ele=None, media=None):
    actions = read_args.retriveArgs().action
    username = ele.name
    model_id = ele.id
    out = []
    for action in actions:
        if action == "download":
            out.append(
                await download_action.downloader(
                    ele=ele,
                    posts=posts,
                    media=media,
                    model_id=model_id,
                    username=username,
                )
            )
        elif action == "like":
            out.append(
                like_action.process_like(
                    ele=ele,
                    posts=like_posts,
                    media=media,
                    model_id=model_id,
                    username=username,
                )
            )
        elif action == "unlike":
            out.append(
                like_action.process_unlike(
                    ele=ele,
                    posts=like_posts,
                    media=media,
                    model_id=model_id,
                    username=username,
                )
            )
    return out
