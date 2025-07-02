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
import ofscraper.utils.console as console
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.utils.context.run_async import run
from ofscraper.data.models.models import Model
import ofscraper.utils.settings as settings
from ofscraper.utils.args.mutators.user import resetUserFilters

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
        self._last_fetched=None
        

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
    def num_models(self) -> int:
        return len(self.all_subs)

    @property
    def num_models_selected(self) -> int:
        return len(self.parsed_subs)

    def update_all_subs(self, models: List[Model] | Dict[str, Model]) -> None:
        if isinstance(models, dict):
            self._all_subs_dict.update(models)
        elif isinstance(models, list):
            for ele in models:
                self._all_subs_dict[ele.name] = ele

    def update_parsed_subs(self, models: List[Model] | Dict[str, Model]) -> None:
        if isinstance(models, dict):
            self._parsed_subs_dict.update(models)
        elif isinstance(models, list):
            for ele in models:
                self._parsed_subs_dict[ele.name] = ele

    def update_subs(self, models: List[Model] | Dict[str, Model]):
        self.update_all_subs(models)
        self.update_parsed_subs(models)

    def add_model(self, usernames: str | List[str]) -> None:
        # This wrapper ensures the async method is run and waited for.
        run(self._add_model_async(usernames))()

    async def _add_model_async(self, usernames: str | List[str]) -> None:
        if isinstance(usernames, str):
            username_set = {usernames}
        else:
            username_set = set(usernames)

        new_usernames_to_fetch = {
            name for name in username_set if name not in self._all_subs_dict
        }

        if new_usernames_to_fetch:
            log.info(
                f"Attempting to fetch new model data for: {', '.join(new_usernames_to_fetch)}"
            )
            args = settings.get_args()
            original_usernames = args.usernames or []
            args.usernames = list(new_usernames_to_fetch)
            settings.update_args(args)
            fetched_models = await retriver.get_models()
            if fetched_models:
                self.update_subs(fetched_models)
            args.usernames = original_usernames
            settings.update_args(args)
            for name in new_usernames_to_fetch:
                if name not in self._all_subs_dict:
                    log.warning(f"Failed to fetch and add model: {name}")

        args = settings.get_args()
        current_arg_usernames = set(args.usernames or [])
        verified_usernames = {
            name for name in username_set if name in self._all_subs_dict
        }
        if not verified_usernames:
            log.warning(
                f"Could not add any of the provided usernames: {', '.join(username_set)}"
            )
            return

        current_arg_usernames.update(verified_usernames)
        args.usernames = list(current_arg_usernames)
        settings.update_args(args)
        log.info(
            f"Usernames for processing now include: {', '.join(verified_usernames)}"
        )

    def get_selected_models(
        self, rescan: bool = False, reset: bool = False
    ) -> List[Model]:
        #rescan + reset being true might lead to double scan
        if rescan:
            self._fetch_all_subs()
        should_reset_selection = reset
        if reset and self.parsed_subs:
            prompt_choice = prompts.reset_username_prompt()
            if prompt_choice == "No":
                should_reset_selection = False
            #reset username to force rescan
            if prompt_choice in {"Selection","Selection_Strict"}:
                settings.resetUserSelect()
            if prompt_choice=="Selection":
                  self._fetch_all_subs(force_refetch=True)
        #should not scan if fetch_all_subs called above previously
        self._load_all_subs_if_needed()
        self._process_parsed_subscriptions(reset=should_reset_selection)

        return self.parsed_subs
    

    def setfilter(self):
        while True:
            self._print_filter_settings()
            choice = prompts.decide_filters_menu()
            try:
                # --- Place this dictionary outside your main loop for efficiency ---
                prompt_actions = {
                    "sort": prompts.modify_sort_prompt,
                    "subtype": prompts.modify_subtype_prompt,
                    "promo": prompts.modify_promo_prompt,
                    "active": prompts.modify_active_prompt,
                    "price": prompts.modify_prices_prompt,
                    "list": prompts.modify_list_prompt,
                }

                if choice == "model_list":
                    break

                # Get a copy of the arguments before any modifications
                original_args = settings.get_args()
                new_args = settings.get_args(copy=True)

                # 1. Determine the new arguments based on the user's choice
                if choice in prompt_actions:
                    new_args = prompt_actions[choice](new_args)
                elif choice == "reset_filters":
                    new_args = resetUserFilters()
                elif choice == "reset_list":
                    new_args.userlist = ["main"]
                    new_args.blacklist = [""] # Clears the blacklist
                elif choice == "rescan":
                    self._fetch_all_subs(force_refetch=True, reset=True)

                # 2. If any action generated new arguments, process the changes
                if new_args:
                    # Use sets to compare lists, safely handling None with 'or []'
                    user_list_changed = set(original_args.userlist or []) != set(new_args.userlist or [])
                    black_list_changed = set(original_args.blacklist or []) != set(new_args.blacklist or [])

                    # Always update the arguments in the settings
                    settings.update_args(new_args)
                    # If a list changed, it requires re-fetching all the models
                    if user_list_changed or black_list_changed:
                        console.get_console().print("[yellow]Lists changed, re-fetching models from API...[/yellow]")
                        self._fetch_all_subs(force_refetch=True, reset=True)
                        original_args=new_args
                        new_args=settings.get_args(copy=True)

            except Exception as e:
                console.get_console().print(f"Exception in menu: {e}")
            settings.update_args(new_args)
            

    def _print_filter_settings(self):
        """
        Retrieves and prints all active filter settings.

        This function iterates through a predefined list of filter attributes,
        checks if they have a non-None value in the settings, and prints
        each active filter in a readable format.
        """
        # Get the settings object once to avoid repeated calls
        s = settings.get_settings()

        # A list of all attribute names corresponding to the filter options
        filter_attributes = [
        # Price Range Filters
        "promo_price_min", "promo_price_max",
        "regular_price_min", "regular_price_max",
        "current_price_min", "current_price_max",
        "renewal_price_min", "renewal_price_max",
        # Date Filters
        "last_seen_before", "last_seen_after",
        "expired_before", "expired_after",
        "subscribed_before", "subscribed_after",
        # Sorting
        "sort", "desc",
        # User Lists
        "userlist", "blacklist",
        # Paid/Free Choice Filters
        "current_price", "renewal_price", "regular_price", "promo_price",
        # Flag-based Filters
        "last_seen",
        "free_trial",
        "promo",
        "all_promo",
        "sub_status",
        "renewal",
    ]

        print("\n--- Active Filter Settings ---")
        
        # A flag to check if any filters were printed
        found_active_filter = False

        # Loop through each attribute name
        for attr in filter_attributes:
            # Use getattr() to get the value of the attribute from the settings object
            value = getattr(s, attr, None)

           # --- Start of Improved Logic ---
            is_empty = not value  # This is False for None, "", [], False
            if attr=="desc":
                is_empty=False
            # Special check for userlist/blacklist: treat a list of only empty strings as empty
            if attr in {"blacklist", "userlist"} and isinstance(value, list):
                # any(value) checks if there is at least one non-empty string in the list.
                # If all items are empty strings, any() is False, so we set is_empty to True.
                if not any(value):
                    is_empty = True

            # Only print if the value is not considered empty
            if not is_empty:
                display_name = attr.replace('_', ' ').title()
                print(f"{display_name}: {value}")
                found_active_filter = True

        # If no filters were active, print a message
        if not found_active_filter:
            print("No active filters set.")
        
        print("----------------------------\n")    
    
    
    def _fetch_all_subs(self, force_refetch: bool = False,reset:bool=False) -> None:
        if self._all_subs_dict and not force_refetch and not reset:
            return
        #reset last fetched
        self._last_fetched=None
        if reset:
            self._all_subs_dict={}
        while True:
        # Use run to execute the async fetching logic and block until it's done
            self._fetch_all_subs_async()
            if self._last_fetched:
                self.update_all_subs(self._last_fetched)
                return
            console.get_console().print(
                f"[bold red]No accounts found during last scan[/bold red]\nNumber of Models Stored: {self.num_models}"

            )
            # Use synchronous sleep and prompts
            time.sleep(of_env.getattr("LOG_DISPLAY_TIMEOUT"))
            if self.num_models>0 and not prompts.retry_user_scan():
                return
            elif self.num_models==0 and not prompts.retry_user_scan(no_models=True):
                quit()

    def _load_all_subs_if_needed(self) -> None:
        if not self._all_subs_dict:
            self._fetch_all_subs(force_refetch=True)
    @run
    async def _fetch_all_subs_async(self) -> None:
        self._last_fetched = await retriver.get_models()
            
    def _filter_and_prompt_for_selection(self):
        while True:
            filtered_models = self._apply_filters()
            sorted_models = sort.sort_models_helper(filtered_models)       
            if sorted_models:
                return {model.name: self._all_subs_dict[model.name] for model in sorted_models}

            console.get_console().print(
                "[bold red]You have filtered the user list to zero.[/bold red]\n"
                "Change the filter settings to continue."
            )
            self.setfilter()
    
    def _process_parsed_subscriptions(self, reset: bool = False) -> None:
        args = settings.get_args()
        if reset:
            args.usernames = None
            settings.update_args(args)

        if not args.usernames:
            filtered_sorted_models = self._filter_and_prompt_for_selection()
            selected_users = retriver.get_selected_model(list(filtered_sorted_models.values()))
            self._parsed_subs_dict = {model.name: model for model in selected_users}
            args.usernames = list(self._parsed_subs_dict.keys())
            settings.update_args(args)
        elif "ALL" in args.usernames:
            self._parsed_subs_dict = self._filter_and_prompt_for_selection()
        else:
            username_set = set(args.usernames)
            all_filtered_and_sorted = self._filter_and_prompt_for_selection()
            self._parsed_subs_dict = {
                name: model
                for name, model in all_filtered_and_sorted.items()
                if name in username_set
            }

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
            logging.warning(
                f"Attempted to mark non-selected user '{username}' as processed."
            )

    def is_processed(self, username: str) -> bool:
        return username in self._processed_usernames

    def reset_processed_status(self) -> None:
        logging.info("Resetting processing status for all users.")
        self._processed_usernames.clear()

    @property
    def processed_dict(self) -> Dict[str, Model]:
        return {
            username: self._parsed_subs_dict[username]
            for username in self._processed_usernames
            if username in self._parsed_subs_dict
        }

    @property
    def unprocessed_dict(self) -> Dict[str, Model]:
        return {
            username: model
            for username, model in self._parsed_subs_dict.items()
            if username not in self._processed_usernames
        }