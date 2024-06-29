import json
import textwrap

import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings


def print_auth_warning(auth=None):
    auth = auth or auth_requests.auth_file.read_auth()
    auth.update({"app-token": constants.getattr("APP_TOKEN")})

    console.get_console().print(
        textwrap.dedent(
            """
        [bold red]This info is only printed to console[/bold red]
        """
        )
    )
    console.get_console().print_json(json.dumps(auth))
    console.get_console().print(f"[bold] Dynamic Rule: {settings.get_dynamic_rules()}")
    console.get_console().print(
        textwrap.dedent(
            """
        ==============================================================
        Double check to make sure the [bold blue]\[x-bc,user-agent][/bold blue] info is correct

        Double check to make sure the [bold blue]\[sess, auth_id][/bold blue] info is correct
                        
        If 2fa is enabled double check that [bold blue]\[auth_uid_][/bold blue] is set and not the same as auth_id

        Double check to make sure [bold blue]dynamic rule[/bold blue] is as desired
        ================================================
        """
        )
    )
