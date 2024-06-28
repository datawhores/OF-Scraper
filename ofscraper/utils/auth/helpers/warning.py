from rich.console import Console

console = Console()


def authwarning(authFile):
    console.print(
        "[bold yellow]For an example of how your auth file should look see \
            \n [bold deep_sky_blue2]https://of-scraper.gitbook.io/of-scraper/auth#example[/bold deep_sky_blue2][/bold yellow]"
    )
    console.print(
        f"[bold yellow]If you still can't authenticate after editing from script consider manually edit the file at\n[bold deep_sky_blue2]{authFile}[/bold deep_sky_blue2][/bold yellow]"
    )
