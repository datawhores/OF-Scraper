import logging
import time
from typing import Any, Dict, List, Optional, Set

import ofscraper.data.models.utils.retriver as retriver
import ofscraper.filters.models.date as date_
import ofscraper.filters.models.flags as flags
import ofscraper.filters.models.other as other
import ofscraper.filters.models.price as price
import ofscraper.filters.models.sort as sort
import ofscraper.filters.models.subtype as subtype
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.console as console
import ofscraper.utils.env.env as env
import ofscraper.utils.env.env as env
import ofscraper.utils.settings as settings
from ofscraper.utils.context.run_async import run
from ofscraper.data.models.models import Model

log = logging.getLogger("shared")


class ModelManager:
    """
    Manages fetching, filtering, and selecting user models (subscriptions).
    Includes state management for tracking processed models.
    """
    def __init__(self) -> None:
        """Initializes the ModelManager."""
        self._all_subs_dict: Dict[str, Model] = {}
        self._parsed_subs_dict: Dict[str, Model] = {}
        self._seen_users: Set[str] = set()
        self._processed_usernames: Set[str] = set()

    @property
    def num_selected(self) -> int:
        return len(self._parsed_subs_dict)

    def get_model(self, username: str) -> Optional[Model]:
        return self._all_subs_dict.get(username)

    @property
    def all_subs(self) -> List[Model]:
        return list(self._all_subs_dict.values())

    @property
    def parsed_subs(self) -> List[Model]:
        return list(self._parsed_subs_dict.values())
    
    @property
    def num_models(self)->int:
        return len(self.all_subs)
    
    @property
    def num_models_selected(self)->int:
        return len(self.parsed_subs)


    def update_all_subs(self, models: List[Model] | Dict[str, Model]) -> None:
        if isinstance(models, dict):
            self._all_subs_dict.update(models)
        elif isinstance(models, list):
            for ele in models:
                self._all_subs_dict[ele.name] = ele

    def get_selected_models(self, rescan: bool = False, reset: bool = False) -> List[Model]:
        if rescan:
            self._fetch_all_subs()

        should_reset_selection = reset
        if reset and self.parsed_subs:
            prompt_choice = prompts.reset_username_prompt()
            if prompt_choice == "Data":
                should_reset_selection = False
            if prompt_choice in {"Selection", "Data"}:
                self._fetch_all_subs()

        self._load_all_subs_if_needed()
        self._process_parsed_subscriptions(reset=should_reset_selection)
        return self.parsed_subs

    @run
    async def _fetch_all_subs(self, force_refetch: bool = True) -> None:
        if self._all_subs_dict and not force_refetch:
            return
        await self._fetch_all_subs_async()

    def _load_all_subs_if_needed(self) -> None:
        if not self._all_subs_dict:
            self._fetch_all_subs(force_refetch=True)

    async def _fetch_all_subs_async(self) -> None:
        while True:
            models = await retriver.get_models()
            if models:
                self.update_all_subs(models)
                break
            console.get_console().print("[bold red]No accounts found during scan[/bold red]")
            time.sleep(env.getattr("LOG_DISPLAY_TIMEOUT", 0))
            if not prompts.retry_user_scan():
                raise SystemExit("Could not find any accounts on list.")

    def _process_parsed_subscriptions(self, reset: bool = False) -> None:
        args = read_args.retriveArgs()
        if reset:
            args.usernames = None
            write_args.setArgs(args)

        if not args.usernames:
            filtered_sorted_models = self._filter_and_sort_models()
            selected_users = retriver.get_selected_model(filtered_sorted_models)
            self._parsed_subs_dict = {model.name: model for model in selected_users}
            settings.get_settings().usernames = list(self._parsed_subs_dict.keys())
            write_args.setArgs(args)
        elif "ALL" in args.usernames:
            self._parsed_subs_dict = self._filter_and_sort_models()
        else:
            username_set = set(args.usernames)
            self._parsed_subs_dict = {
                name: model for name, model in self._all_subs_dict.items() if name in username_set
            }

    def _filter_and_sort_models(self) -> Dict[str, Model]:
        filtered_models = self._apply_filters()
        sorted_models = sort.sort_models_helper(filtered_models)
        return {model.name: self._all_subs_dict[model.name] for model in sorted_models}
    
    def _apply_filters(self) -> List[Model]:
        models = self.all_subs
        models = subtype.subType(models)
        models = price.pricePaidFreeFilterHelper(models)
        models = flags.promoFilterHelper(models)
        models = date_.dateFilters(models)
        models = other.otherFilters(models)
        return models

    def mark_as_processed(self, username: str) -> None:
        if username in self._parsed_subs_dict:
            self._processed_usernames.add(username)
        else:
            logging.warning(f"Attempted to mark non-selected user '{username}' as processed.")

    def is_processed(self, username: str) -> bool:
        return username in self._processed_usernames

    def reset_processed_status(self) -> None:
        logging.info("Resetting processing status for all users.")
        self._processed_usernames.clear()

    @property
    def processed_dict(self) -> Dict[str, Model]:
        """Returns a dictionary of {username: model} for processed models."""
        return {
            username: self._parsed_subs_dict[username]
            for username in self._processed_usernames
            if username in self._parsed_subs_dict
        }

    @property
    def unprocessed_dict(self) -> Dict[str, Model]:
        """Returns a dictionary of {username: model} for unprocessed models."""
        return {
            username: model
            for username, model in self._parsed_subs_dict.items()
            if username not in self._processed_usernames
        }
