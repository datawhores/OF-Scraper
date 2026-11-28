r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

from InquirerPy.base import Choice
from InquirerPy.separator import Separator

import ofscraper.db.postgres as postgres
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.sites as sites
import ofscraper.utils.of_env.of_env as of_env


def _get_non_property(obj, attr):
    if isinstance(getattr(type(obj), attr, None), property):
        return None
    return getattr(obj, attr, None)


def _peek_current_model_manager(mgr):
    if mgr is None:
        return None
    # Prefer peeking on an already-initialized ProfileManager so rendering
    # the menu never eagerly creates a ProfileManager or ModelManager.
    if hasattr(mgr, "_profile_manager"):
        pm = _get_non_property(mgr, "_profile_manager")
        if pm is None:
            return None
        if hasattr(pm, "peek_model_manager"):
            return pm.peek_model_manager()
        return _get_non_property(pm, "current_model_manager")
    pm = _get_non_property(mgr, "profile_manager")
    if pm is not None:
        if hasattr(pm, "peek_model_manager"):
            return pm.peek_model_manager()
        return _get_non_property(pm, "current_model_manager")
    return _get_non_property(mgr, "current_model_manager")


def _main_menu_status() -> str:
    import ofscraper.managers.manager as manager
    import ofscraper.utils.args.accessors.areas as areas
    import ofscraper.utils.profiles.data as profile_data
    import ofscraper.utils.settings as settings

    dl_areas = sorted(areas.get_download_area() or [])
    if getattr(settings.get_settings(), "scrape_paid", False) and "Paid" not in dl_areas:
        dl_areas.append("Paid")
    like_areas = sorted(areas.get_like_area() or [])

    area_parts = []
    if dl_areas:
        area_parts.append(f"DL: {', '.join(dl_areas)}")
    if like_areas:
        area_parts.append(f"Like: {', '.join(like_areas)}")
    areas_str = " / ".join(area_parts) if area_parts else "Prompt on run"

    mm = _peek_current_model_manager(manager.Manager)
    selected = len(mm.state.get_all_queued_usernames()) if mm is not None else 0
    cli_users = getattr(settings.get_settings(), "usernames", None) or []
    if selected:
        users_str = f"{selected} selected"
    elif any(str(u).upper() == "ALL" for u in cli_users):
        users_str = "ALL from CLI"
    elif cli_users:
        users_str = f"{len(cli_users)} from CLI"
    else:
        users_str = "Prompt on run"

    db_str = f"PostgreSQL ({postgres.describe()})" if postgres.enabled() else "user_data.db"
    return (
        f"(Site: {sites.site_name()} | Profile: {profile_data.get_active_profile()} "
        f"| Areas: {areas_str} | Users: {users_str} | DB: {db_str})"
    )


@promptClasses.top_level
def main_prompt() -> str:
    choices_map = dict(of_env.getattr("mainPromptChoices"))
    main_prompt_choices = list(choices_map)
    main_prompt_choices.insert(1, Separator())
    if "site" not in choices_map.values():
        switch_label = f"Switch Site (Current: {sites.site_name()})"
        choices_map[switch_label] = "site"
        quit_idx = next(
            (i for i, k in enumerate(main_prompt_choices) if choices_map.get(k) == "quit"),
            len(main_prompt_choices),
        )
        main_prompt_choices.insert(quit_idx, switch_label)
    main_prompt_choices.insert(len(main_prompt_choices) - 1, Separator())
    answer = promptClasses.getChecklistSelection(
        message="Main Menu: What would you like to do?",
        choices=[*main_prompt_choices],
        instruction=_main_menu_status(),
    )
    return choices_map[answer]


def switch_site_prompt(target: str | None = None) -> str | None:
    if target is None:
        target = sites.FANSLY if not sites.is_fansly() else sites.ONLYFANS
    target_label = sites.site_name(target)
    return promptClasses.getChecklistSelection(
        message=f"Switch active site from {sites.site_name()} to {target_label}:",
        choices=[
            Choice("session", f"Switch to {target_label} for this session only"),
            Choice("profile", f"Switch to {target_label} and save to profile site.json"),
            Choice(None, "Cancel"),
        ],
        default="session",
    )


def continue_prompt() -> bool:
    if not of_env.getattr("CONTINUE_BOOL"):
        return False
    name = "continue"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Do you want to continue with script",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer[name]
