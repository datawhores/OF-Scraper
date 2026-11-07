from rich.console import Console
from ofscraper.utils.markup import escape_text

console = Console()


def authwarning(authFile):
    console.print(
        "[bold yellow]For an example of how your auth file should look see \
            \n [bold deep_sky_blue2]https://cloakedkeys.gitbook.io/ofsc/getting-started/auth#example[/bold deep_sky_blue2][/bold yellow]"
    )
    console.print(
        f"[bold yellow]If you still can't authenticate after editing from script consider manually edit the file at\n[bold deep_sky_blue2]{escape_text(authFile)}[/bold deep_sky_blue2][/bold yellow]"
    )
