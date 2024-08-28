import logging
import time

import ofscraper.filters.models.date as date_
import ofscraper.filters.models.flags as flags
import ofscraper.filters.models.other as other
import ofscraper.filters.models.price as price
import ofscraper.filters.models.sort as sort
import ofscraper.filters.models.subtype as subtype
import ofscraper.data.models.utils.retriver as retriver
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.user as user_helper
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.utils.context.run_async import run
import ofscraper.utils.console as console


log = logging.getLogger("shared")

class ModelManager():
    def __init__(self) -> None:
        self._all_subs_dict={}
        self._parsed_subs_dict={}
        self._seen_users=set()


    def get_num_selected(self):
        return len(self.parsed_subs)


    def get_model(self,name):
        return self._all_subs_dict.get(name)
    

    @property
    def all_subs(self):
        return list(self._all_subs_dict.keys())
    @property
    def all_subs_obj(self):
        return list(self._all_subs_dict.values())
    @property
    def all_subs_dict(self):
        return self._all_subs_dict
    @all_subs_dict.setter
    def all_subs_dict(self, value):
        if value and isinstance(value, dict):
            self._all_subs_dict.update(value)
        else:
            [self._all_subs_dict .update({ele.name: ele}) for ele in value]
    @property
    def parsed_subs_dict(self):
        return self._parsed_subs_dict

    @property
    def parsed_subs(self):
        return list(self._parsed_subs_dict.keys())
    @property
    def parsed_subs_obj(self):
        return list(self._parsed_subs_dict.values())

    def getselected_usernames(self,rescan=False, reset=False):
        # username list will be retrived every time resFet==True
        if reset is True and rescan is True:
            self.all_subs_retriver()
            self.parsed_subscriptions_helper(reset=True)
        elif reset is True and self.parsed_subs:
            prompt = prompts.reset_username_prompt()
            if prompt == "Selection":
                self.all_subs_retriver()
                self.parsed_subscriptions_helper(reset=True)
            elif prompt == "Data":
                self.all_subs_retriver()
                self.parsed_subscriptions_helper()
            elif prompt == "Selection_Strict":
                self.parsed_subscriptions_helper(reset=True)
        elif rescan is True:
            self.all_subs_retriver()
            self.parsed_subscriptions_helper()
        else:
            self.all_subs_retriver(refetch=False)
            self.parsed_subscriptions_helper()
        return self.parsed_subs_obj


    @run
    async def set_data_all_subs_dict(self,username):
        args = read_args.retriveArgs()
        oldusernames = args.usernames or set()
        all_usernames = set()
        all_usernames.update([username] if not isinstance(username, list) else username)
        all_usernames.update(oldusernames)

        new_names = [
            username
            for username in all_usernames
            if username not in self._seen_users
            and not self._seen_users.add(username)
            and username not in oldusernames
            and username != constants.getattr("DELETED_MODEL_PLACEHOLDER")
        ]

        args.usernames = new_names
        write_args.setArgs(args)
        await self.all_subs_retriver() if len(new_names) > 0 else None
        args.usernames = set(all_usernames)
        write_args.setArgs(args)


    @run
    async def all_subs_retriver(self,refetch=True):
        if bool(self.all_subs_dict) and not refetch:
            return
        while True:
            data=await retriver.get_models()
            self.all_subs_dict = data
            if len(self.all_subs_dict) > 0:
                break
            elif len(self.all_subs_dict) == 0:
                console.get_console().print("[bold red]No accounts found during scan[/bold red]")
                # give log time to process
                time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT"))
                if not prompts.retry_user_scan():
                    raise Exception("Could not find any accounts on list")
                

    def parsed_subscriptions_helper(self,reset=False):
        args = read_args.retriveArgs()
        if reset is True:
            args.usernames = None
            write_args.setArgs(args)
        if not bool(args.usernames):
            selectedusers = retriver.get_selected_model(self.filterNSort())
            read_args.retriveArgs().usernames = list(map(lambda x: x.name, selectedusers))
            self._parsed_subs_dict = {ele.name:ele for ele in selectedusers}
            write_args.setArgs(args)
        elif "ALL" in args.usernames:
            self._parsed_subs_dict = self.filterNSort()
        elif args.usernames:
            usernameset = set(args.usernames)
            self._parsed_subs_dict= {ele.name: ele for ele in self.all_subs_obj if ele.name in usernameset}


    def setfilter(self):
        global args
        while True:
            choice = prompts.decide_filters_menu()
            if choice == "modelList":
                break
            elif choice == "sort":
                args = prompts.modify_sort_prompt(read_args.retriveArgs())
            elif choice == "subtype":
                args = prompts.modify_subtype_prompt(read_args.retriveArgs())
            elif choice == "promo":
                args = prompts.modify_promo_prompt(read_args.retriveArgs())
            elif choice == "active":
                args = prompts.modify_active_prompt(read_args.retriveArgs())
            elif choice == "price":
                args = prompts.modify_prices_prompt(read_args.retriveArgs())
            elif choice == "reset":
                old_args = read_args.retriveArgs()
                old_blacklist = old_args.black_list
                old_list = old_args.user_list
                args = user_helper.resetUserFilters()
                if not list(sorted(old_blacklist)) == list(
                    sorted(args.black_list)
                ) or not list(sorted(old_list)) == list(sorted(args.user_list)):
                    console.get_console().print("Updating Models")
                    self.all_subs_retriver(rescan=True)
            elif choice == "list":
                old_args = read_args.retriveArgs()
                old_blacklist = old_args.black_list
                old_list = old_args.user_list
                args = prompts.modify_list_prompt(old_args)
                if not list(sorted(old_blacklist)) == list(
                    sorted(args.black_list)
                ) or not list(sorted(old_list)) == list(sorted(args.user_list)):
                    console.get_console().print("Updating Models")
                    self.all_subs_retriver(rescan=True)
            elif choice == "select":
                old_args = read_args.retriveArgs()
                args = prompts.modify_list_prompt(old_args)
            write_args.setArgs(args)


    def filterNSort(self):
        while True:
            # paid/free

            log.debug(f"username count no filters: {len(self.all_subs)}")
            filterusername = self.filterOnly()
            log.debug(f"final username count with all filters: {len(filterusername)}")
            # give log time to process
            time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT"))
            if len(filterusername) != 0:
                
                return {ele.name:self._all_subs_dict[ele.name] for ele in sort.sort_models_helper(filterusername)}
            console.get_console().print(
                f"""[bold red]You have filtered the user list to zero[/bold red]
    Change the filter settings to continue

    Active userlist : {settings.get_userlist() or 'no blacklist'}
    Active blacklist : {settings.get_blacklist() or 'no userlist'}

    Sub Status: {read_args.retriveArgs().sub_status or 'No Filter'}
    Renewal Status: {read_args.retriveArgs().renewal or 'No Filter'}

    Promo Price Filter: {read_args.retriveArgs().promo_price or 'No Filter'}
    Current Price Filter: {read_args.retriveArgs().current_price or 'No Filter'}
    Current Price Filter: {read_args.retriveArgs().current_price or 'No Filter'}
    Renewal Price Filter: {read_args.retriveArgs().renewal_price or 'No Filter'}

    [ALT+D] More Filters

    """
            )

            self.setfilter()


    def filterOnly(self,usernames=None):
        usernames = self.all_subs_obj
        filterusername = subtype.subType(usernames)
        filterusername = price.pricePaidFreeFilterHelper(filterusername)
        filterusername = flags.promoFilterHelper(filterusername)
        filterusername = date_.dateFilters(filterusername)
        filterusername = other.otherFilters(filterusername)
        return filterusername
