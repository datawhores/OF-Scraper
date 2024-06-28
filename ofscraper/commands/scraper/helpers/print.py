import ofscraper.utils.console as console
def print_start():
    console.get_shared_console().print(
        f"[bold green]Version {__version__}[/bold green]"
    )