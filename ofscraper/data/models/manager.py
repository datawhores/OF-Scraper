import logging
from typing import Dict, List, Optional, Set, Union


import ofscraper.data.models.utils.retriver as retriver
import ofscraper.filters.models.date as date_
import ofscraper.filters.models.flags as flags
import ofscraper.filters.models.other as other
import ofscraper.filters.models.price as price
import ofscraper.filters.models.sort as sort
import ofscraper.filters.models.subtype as subtype
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.console as console
from ofscraper.utils.context.run_async import run
from ofscraper.classes.of.models import Model
import ofscraper.utils.settings as settings
from ofscraper.utils.args.mutators.user import resetUserFilters
from ofscraper.data.models.state import StateManager, EActivity, string_to_activity
import ofscraper.utils.of_env.of_env as of_env

log = logging.getLogger("shared")


class ModelManager:
    """
    Manages fetching, filtering, and caching of user Model objects.
    Delegates all processing state to a StateManager instance.
    """

    def __init__(self, state_manager: StateManager = None) -> None:
        """
        Initializes the ModelManager.

        Args:
            state_manager (StateManager): An instance of the StateManager class for tracking processing state.
        """
        self.state: "StateManager" = state_manager or StateManager()
        self._all_subs_dict: Dict[str, "Model"] = {}
        self._last_fetched: Optional[List["Model"]] = None

    @property
    def all_subs(self) -> List["Model"]:
        """Returns a list of all models currently held in the manager."""
        return list(self._all_subs_dict.values())

    @property
    def num_models(self) -> int:
        """Returns the total number of models held."""
        return len(self.all_subs)

    def get_model(self, username: str) -> Optional["Model"]:
        """Gets a model object from the global cache by username."""
        return self._all_subs_dict.get(username)

    def get_models(self, usernames: Set[str]) -> Dict[str, "Model"]:
        """Gets a dictionary of model objects for a given set of usernames."""
        return {
            name: self._all_subs_dict[name]
            for name in usernames
            if name in self._all_subs_dict
        }

    def update_all_subs(self, models: List["Model"] | Dict[str, "Model"]) -> None:
        """Updates the global cache of all fetched models."""
        if isinstance(models, dict):
            self._all_subs_dict.update(models)
        elif isinstance(models, list):
            for ele in models:
                self._all_subs_dict[ele.name] = ele

    def update_selected_subs(self, models: List["Model"] | Dict[str, "Model"]) -> None:
        """Updates the global cache of all fetched models."""
        if isinstance(models, dict):
            self._selected_subs_dict.update(models)
        elif isinstance(models, list):
            for ele in models:
                self._selected_subs_dict[ele.name] = ele

    def select_models(self) -> List["Model"]:
        """Applies filters and prompts user to return a list of selected models."""
        filtered_models = self._filter_and_prompt_for_selection()
        if settings.get_settings().username == "ALL":
            return list(filtered_models.values())
        return retriver.get_selected_model(list(filtered_models.values()))

    @run
    async def add_models(self, usernames: List[str], activity: Union[EActivity, str]) -> List[str]:
        """
        Fetches data for new usernames and adds them to the master list.
        Handles placeholder models by skipping the fetch and creating a dummy object.
        """
        if not isinstance(usernames,list):
            usernames=[usernames]
        # 1. Get placeholder prefix and initial username set
        placeholder_prefix = of_env.getattr("DELETED_MODEL_PLACEHOLDER")
        username_set = set(usernames)

        # 2. Partition usernames into 'to_fetch' and 'placeholders'
        new_usernames_to_fetch = set()
        placeholder_usernames = set()

        for name in username_set:
            # Skip if already in our master list
            if name in self._all_subs_dict:
                continue
            # Check for placeholder prefix, but only if the prefix is set
            if placeholder_prefix and name.startswith(placeholder_prefix):
                placeholder_usernames.add(name)
            else:
                new_usernames_to_fetch.add(name)

        # 3. Fetch real models from the API if needed
        if new_usernames_to_fetch:
            log.info(
                f"Attempting to fetch new model data for: {list(new_usernames_to_fetch)}"
            )
            args = settings.get_args()
            original_usernames = args.usernames or []
            args.usernames=list(new_usernames_to_fetch)
            settings.update_args(args)
            fetched_models = await retriver.get_models()
            if fetched_models:
                self.update_all_subs(fetched_models)
            args.usernames = original_usernames
            settings.update_args(args)
        # 4. Create and add placeholder models without fetching
        if placeholder_usernames:
            log.info(f"Creating placeholder models for: {', '.join(placeholder_usernames)}")
            placeholder_models = [Model({"username": name, "id": name}) for name in placeholder_usernames]
            self.update_all_subs(placeholder_models)

        # 5. Queue all successfully added models for the activity
        # This list includes both fetched and placeholder models
        successfully_added = [name for name in username_set if name in self._all_subs_dict]
        
        if successfully_added:
            # Normalize activity string/enum and queue the usernames
            activity = self._get_activity(activity)
            self.state.queue_for_activity(activity, successfully_added)

        return successfully_added

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
                    new_args.blacklist = [""]  # Clears the blacklist
                elif choice == "rescan":
                    self._fetch_all_subs(force_refetch=True, reset=True)

                # 2. If any action generated new arguments, process the changes
                if new_args:
                    # Use sets to compare lists, safely handling None with 'or []'
                    user_list_changed = set(original_args.userlist or []) != set(
                        new_args.userlist or []
                    )
                    black_list_changed = set(original_args.blacklist or []) != set(
                        new_args.blacklist or []
                    )

                    # Always update the arguments in the settings
                    settings.update_args(new_args)
                    # If a list changed, it requires re-fetching all the models
                    if user_list_changed or black_list_changed:
                        console.get_console().print(
                            "[yellow]Lists changed, re-fetching models from API...[/yellow]"
                        )
                        self._fetch_all_subs(force_refetch=True, reset=True)
                        original_args = new_args
                        new_args = settings.get_args(copy=True)

            except Exception as e:
                console.get_console().print(f"Exception in menu: {e}")
            settings.update_args(new_args)

    def prepare_activity(
        self,
        activity: Union[EActivity, str, List[Union[EActivity, str]]],
        rescan: bool = False,
        reset: bool = False,
    ) -> List["Model"]:
        """
        Prepares one or more activities by fetching data and selecting models as needed,
        then queues them in the StateManager.
        """
        # --- Step 1: Normalize Input ---
        # Convert the flexible input into a clean list of EActivity members.
        activities_to_process = self._get_activities(activity)
        # --- Step 2: Handle Data Fetching ---
        if rescan:
            self._fetch_all_subs(force_refetch=True)
        self._load_all_subs_if_needed()

        # --- Step 3: Determine if a New Selection is Required ---
        # Check if any of the specified activities already have users in their queue.
        existing_queued_users = set()
        for activity in activities_to_process:
            existing_queued_users.update(self.state.get_unprocessed(activity))

        requires_new_selection = reset or not existing_queued_users

        # If reset=True but there's an existing selection, prompt the user.
        if reset and not requires_new_selection:
            prompt_choice = prompts.reset_username_prompt()
            if prompt_choice == "No":
                requires_new_selection = False
            elif prompt_choice in {"Selection", "Selection_Strict"}:
                settings.resetUserSelect()
                if prompt_choice == "Selection":
                    self._fetch_all_subs(force_refetch=True)

        # --- Step 4: Get the Final List of Models ---
        if requires_new_selection:
            # Get a fresh selection from the user.
            log.info("Prompting for a new model selection.")
            final_selection = self.select_models()
        else:
            # Re-use the existing queued users.
            log.info(f"Re-using existing queue of {len(existing_queued_users)} models.")
            final_selection = list(self.get_models(existing_queued_users).values())

        # --- Step 5: Queue the Selection for All Specified Activities ---
        # This is the key part: loop through the list of activities.
        for activity in activities_to_process:
            self.state.queue_for_activity(
                activity, [model.name for model in final_selection]
            )

        return final_selection

    @run
    async def sync_models(
        self, all_main_models: bool = False, all_models: bool = False
    ) -> None:
        """
        Fetches models from the API and updates the internal master list.
        This method is non-interactive and does not use activity queues.

        Args:
            all_main_models (bool): If True, forces fetching of all main subscription models.
            all_models (bool): If True, forces fetching of all subscription models.
        """
        log.info("Synchronizing models...")
        if not all_main_models and not all_models:
            raise Exception("Must pass all_main or all_models")

        # Directly call the retriever function with the provided flags
        fetched_models = await retriver.get_models(
            all_main_models=all_main_models, all_models=all_models
        )

        if fetched_models:
            self.update_all_subs(fetched_models)
            log.info(f"Synchronization complete. Updated {len(fetched_models)} models.")
        else:
            log.info("Synchronization complete. No new models found.")
    # selected models

    def get_all_selected_models(self) -> List["Model"]:
        """
        Gets a list of all unique models currently queued across ALL activities,
        preserving the order of first appearance.
        """
        all_usernames = self.state.get_all_queued_usernames()
        # Get models and re-create the list to ensure the final order matches
        models_dict = self.get_models(set(all_usernames))
        return [models_dict[name] for name in all_usernames if name in models_dict]

    def get_selected_models_activity(self, activity:  Union[EActivity, str]) -> List["Model"]:
        """
        Gets a list of all unique models currently queued across ALL activities,
        preserving the order of first appearance.
        """
        activity = self._get_activity(activity)
        all_usernames = self.state.get_queued_usernames(activity)
        # Get models and re-create the list to ensure the final order matches
        models_dict = self.get_models(set(all_usernames))
        return [models_dict[name] for name in all_usernames if name in models_dict]

    def get_num_all_selected_models(self) -> int:
        # Just call the corresponding method and get its length
        return len(self.get_all_selected_models())
    
    def get_num_selected_models_activity(self, activity: Union[EActivity, str] = None) -> int:
        # Call the corresponding method and get its length
        activity = self._get_activity(activity)
        return len(self.get_selected_models_activity(activity))
    # statemanagement


    def mark_as_processed(self, username: str, activity:  Union[EActivity, str]):
        """Marks a single user as processed for a given activity."""
        activity=self._get_activity(activity)
        if username in self.state._queues[activity]["queued"]:
            self.state._queues[activity]["processed"].add(username)
   
    def get_processed(self, activity:  Union[EActivity, str]) -> Set[str]:
        """Returns the set of users who have been processed for a given activity."""
        activity=self._get_activity(activity)
        return self.state._queues[activity]["processed"]

    def get_unprocessed(self, activity:  Union[EActivity, str]) -> Set[str]:
        """Returns the set of users who are still queued but not yet processed."""
        activity=self._get_activity(activity)
        queued = self.state._queues[activity]["queued"]
        processed = self.state._queues[activity]["processed"]
        return queued - processed

    def reset_processed_status(self, activity: Union[EActivity, str]) -> Set[str]:
        activity=self._get_activity(activity)
        self.state.reset_processed_status(activity)

    def reset_all_processed_status(self) -> Set[str]:
        self.state.reset_all_processed_status()

    def _load_all_subs_if_needed(self) -> None:
        if not self._all_subs_dict:
            self._fetch_all_subs(force_refetch=True)

    def _fetch_all_subs(
        self,
        force_refetch: bool = False,
        reset: bool = False,
        all_main_models: bool = False,
    ) -> None:
        if self._all_subs_dict and not force_refetch and not reset:
            return
        self._last_fetched = None
        if reset:
            self._all_subs_dict = {}

        while True:
            self._fetch_all_subs_async(all_main_models=all_main_models)
            if self._last_fetched:
                self.update_all_subs(self._last_fetched)
                return
            console.get_console().print(
                "[bold red]No accounts found during last scan[/bold red]"
            )
            if not prompts.retry_user_scan():
                break
    
    
    @run
    async def _fetch_all_subs_async(self, all_main_models: bool = False) -> None:
        self._last_fetched = await retriver.get_models(all_main_models=all_main_models)

    def _filter_and_prompt_for_selection(self):
        while True:
            filtered_models = self._apply_filters()
            sorted_models = sort.sort_models_helper(filtered_models)
            if sorted_models:
                return {
                    model.name: self._all_subs_dict[model.name]
                    for model in sorted_models
                }
            console.get_console().print(
                "[bold red]You have filtered the user list to zero.[/bold red]"
            )
            self.setfilter()

    def _apply_filters(self) -> List["Model"]:
        models = self.all_subs
        models = subtype.subType(models)
        models = price.pricePaidFreeFilterHelper(models)
        models = flags.promoFilterHelper(models)
        models = date_.dateFilters(models)
        models = other.otherFilters(models)
        return models

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
            "promo_price_min",
            "promo_price_max",
            "regular_price_min",
            "regular_price_max",
            "current_price_min",
            "current_price_max",
            "renewal_price_min",
            "renewal_price_max",
            # Date Filters
            "last_seen_before",
            "last_seen_after",
            "expired_before",
            "expired_after",
            "subscribed_before",
            "subscribed_after",
            # Sorting
            "sort",
            "desc",
            # User Lists
            "userlist",
            "blacklist",
            # Paid/Free Choice Filters
            "current_price",
            "renewal_price",
            "regular_price",
            "promo_price",
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
            if attr == "desc":
                is_empty = False
            # Special check for userlist/blacklist: treat a list of only empty strings as empty
            if attr in {"blacklist", "userlist"} and isinstance(value, list):
                # any(value) checks if there is at least one non-empty string in the list.
                # If all items are empty strings, any() is False, so we set is_empty to True.
                if not any(value):
                    is_empty = True

            # Only print if the value is not considered empty
            if not is_empty:
                display_name = attr.replace("_", " ").title()
                print(f"{display_name}: {value}")
                found_active_filter = True

        # If no filters were active, print a message
        if not found_active_filter:
            print("No active filters set.")
        print("----------------------------\n")

    def _get_activities(self,activities):
        if not activities:
            return []
        activities_to_process = []
        input_list = activities if isinstance(activities, list) else [activities]
        for item in input_list:
            if isinstance(item, str):
                activities_to_process.append(string_to_activity(item))
            elif isinstance(item, EActivity):
                activities_to_process.append(item)
        return activities_to_process

    def _get_activity(self,activitity):
        if isinstance(activitity, str):
            return string_to_activity(activitity)
        elif isinstance(activitity, EActivity):
            return activitity
