"""Ask for a size or a speed in the config menu as a whole number and a unit.

The number prompt only accepts digits (a minus sign is clamped to 0), so
letters and decimals can't be typed; the unit is then picked from a list.
The answer is still saved in bytes (bytes a second for a speed), as before.

Sizes use Bytes / KB / MB / GB, 1024-based like the check table's download
sidebar. Speeds use bits/s / Kbps / Mbps / Gbps, 1000-based, the way
connection speeds are quoted; 8 bits make a byte.
"""

from dataclasses import dataclass

from InquirerPy.base import Choice
from InquirerPy.validator import EmptyInputValidator
from rich.console import Console

import ofscraper.prompts.promptConvert as promptClasses

WHOLE_NUMBERS = "Whole numbers only (0, 1, 2, ...). Enter 0 for no limit."

console = Console()


@dataclass(frozen=True)
class Scale:
    # (list label, short name, how many base units it is), smallest first
    units: tuple
    # base units in a byte: 1 for bytes, 8 for bits
    per_byte: int
    # the unit shown for 0
    zero_unit: int

    def split(self, size):
        """``size`` bytes as (number, unit) in the largest unit it divides
        into exactly, so a saved value is shown unchanged."""
        try:
            base = int(size or 0) * self.per_byte
        except (TypeError, ValueError):
            base = 0
        if base <= 0:
            return 0, self.zero_unit
        for _, _, unit in reversed(self.units):
            if base % unit == 0:
                return base // unit, unit
        return base, 1

    def to_bytes(self, amount, unit):
        return amount * unit // self.per_byte

    def format(self, size):
        number, unit = self.split(size)
        if number == 0:
            return "0"
        short = next(s for _, s, u in self.units if u == unit)
        return f"{number:,} {short}"

    def choices(self):
        return [Choice(unit, label) for label, _, unit in self.units]

    def entered(self, amount, unit):
        """``amount`` in ``unit`` as typed, e.g. "5 bits/s"."""
        short = next(s for _, s, u in self.units if u == unit)
        return f"{amount:,} {short}"


SIZE = Scale(
    units=(
        ("Bytes", "Bytes", 1),
        ("KB  (1,024 bytes)", "KB", 1024),
        ("MB  (1,024 KB)", "MB", 1024**2),
        ("GB  (1,024 MB)", "GB", 1024**3),
    ),
    per_byte=1,
    zero_unit=1024**2,
)

SPEED = Scale(
    units=(
        ("bits/s", "bits/s", 1),
        ("Kbps  (1,000 bits/s)", "Kbps", 1000),
        ("Mbps  (1,000 Kbps)", "Mbps", 1000**2),
        ("Gbps  (1,000 Mbps)", "Gbps", 1000**3),
    ),
    per_byte=8,
    zero_unit=1000**2,
)


def size_error(
    size, maximum, minimum=1, what="This value", scale=SIZE, entered=None
):
    """Why ``size`` bytes isn't allowed, or None. 0 (no limit) always is.

    ``entered`` is the value as typed ("5 bits/s"). A non-zero entry can
    round down to 0 bytes (1 to 7 bits/s), which is too small, not "no
    limit"."""
    shown = entered or scale.format(size)
    if size == 0 and not entered:
        return None
    if size < minimum:
        return (
            f"{what} must be 0 (no limit) or at least {scale.format(minimum)}; "
            f"{shown} is too small to be useful."
        )
    if size > maximum:
        return (
            f"{what} can be at most {scale.format(maximum)}; "
            f"{shown} is too large."
        )
    return None


def ask_size(
    name,
    message,
    instruction,
    current,
    maximum,
    minimum=1,
    what="This value",
    scale=SIZE,
    check=None,
    **prompt_kwargs,
):
    """Ask for the number, then (unless it's 0) the unit, until the value is
    allowed. ``check(size)`` can refuse it with a message. Returns bytes."""
    number, unit = scale.split(current)
    while True:
        amount = promptClasses.batchConverter(
            {
                "type": "number",
                "name": name,
                "message": message,
                "min_allowed": 0,
                "max_allowed": maximum * scale.per_byte,
                "validate": EmptyInputValidator("Enter a whole number, or 0"),
                "option_instruction": f"{instruction.strip()}\n\n{WHOLE_NUMBERS}\n",
                "default": number,
            },
            **prompt_kwargs,
        )[name]
        amount = int(amount or 0)
        entered = None
        if amount == 0:
            size = 0
        else:
            unit = promptClasses.batchConverter(
                {
                    "type": "list",
                    "name": f"{name}_unit",
                    "message": f"{amount:,} in which unit?",
                    "choices": scale.choices(),
                    "default": unit,
                },
                **prompt_kwargs,
            )[f"{name}_unit"]
            size = scale.to_bytes(amount, unit)
            entered = scale.entered(amount, unit)
        error = size_error(size, maximum, minimum, what, scale, entered)
        if error is None and check is not None:
            error = check(size)
        if error is None:
            return size
        console.print(f"[bold red]{error} Enter it again.[/bold red]")
        number = amount
