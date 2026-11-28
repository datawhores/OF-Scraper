import logging
import re

from rich.text import Text
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from ofscraper.classes.table.utils.lock import mutex
from ofscraper.classes.table.utils.names import get_col_names, get_post_col_names

log = logging.getLogger("shared")


class DataTableExtended(DataTable):
    #cell modification
    def update_cell_at_coord(self, coords, value):
        with mutex:
            value=value if isinstance(value,Text) else Text(value)
            for coord in coords if isinstance(coords, list) else [coords]:
                try:

                    self.update_cell_at(coord, value)
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    def update_cell_at_key(self, keys, col_key,value):
        with mutex:
            value=value if isinstance(value,Text) else Text(value)
            for key in keys if isinstance(keys, list) else [keys]:
                try:
                    self.update_cell(key,col_key, value)
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    # columns a right-click copies from
    COPY_COLUMNS = {"username", "other_posts_with_media"}

    async def _on_click(self, event):
        # a right-click on one of those cells copies it and doesn't select
        # it. Textual runs DataTable's own handler after this one, unless
        # it's prevented
        if event.button == 3 and self._copy_cell(event):
            event.prevent_default()
            event.stop()

    def _copy_cell(self, event):
        meta = event.style.meta
        row, column = meta.get("row", -1), meta.get("column", -1)
        if row < 0 or column < 0 or meta.get("out_of_bounds", False):
            return False
        if self.ordered_columns_keys[column] not in self.COPY_COLUMNS:
            return False
        coordinate = Coordinate(row, column)
        value = self.get_cell_at(coordinate)
        shown = value.plain if isinstance(value, Text) else str(value)
        # a list of post ids is shown as [1, 2]: copy the id under the
        # pointer, or 1, 2 when the click isn't on one
        text = self._clicked_entry(event, coordinate, shown) or (
            shown.strip().strip("[]").strip()
        )
        if not text:
            return False
        self.app.copy_to_clipboard(text)
        self.app.notify(f"Copied {text}", markup=False)
        return True

    def _clicked_entry(self, event, coordinate, shown):
        """The comma-separated entry of a cell's text that was clicked."""
        try:
            start = self._get_cell_region(coordinate).x + self.cell_padding
            index = int(event.x + self.scroll_x) - start
        except Exception:
            return None
        for entry in re.finditer(r"[^\s,\[\]]+", shown):
            if entry.start() <= index < entry.end():
                return entry.group()
        return None

    @property
    def ordered_columns_keys(self):
        return list(map(lambda x:x.key.value,self.ordered_columns))





def get_styled(row, columns=None):
    styled_row = []
    for key in get_col_names() if columns is None else columns:
        if key in ["length","post_date"]:
            styled_row.append(
                Text(str(row[key]), style="bold deep_sky_blue1")
            )
        elif key =="download_cart":
            val = str(row[key])
            if val == "[downloaded]":
                style = "bold green"
            elif val == "[stopped]":
                style = "bold cyan"
            elif val == "[failed]":
                style = "bold red"
            elif val == "[skipped]":
                style = "bold bright_yellow"
            elif val == "[downloading]":
                style = "bold dark_orange"
            else:
                style = "bold light_goldenrod2" # For [], [added], and Not Unlocked

            styled_row.append(
                Text(val, style=style)
            )
        elif key=="text":
            styled_row.append(
                Text(str(row[key]), style="bold dark_sea_green1")
            )
        elif key == "download_type" and row[key] == "unknown" and not row.get("unlocked"):
            # a locked item has no link yet; only the label changes, so the
            # filters and the cart still see "unknown"
            styled_row.append(Text("protected", style="bold medium_spring_green"))
        elif  key=="number":
            styled_row.append(
                Text(str(row[key]), style="bold bright_white")
            )


        elif isinstance(row[key],str):
            styled_row.append(
                Text(str(row[key]), style="bold medium_spring_green")
            )
        elif isinstance(row[key],bool):
            styled_row.append(
                Text(str(row[key]), style="bold plum1")
            )
        elif isinstance(row[key],(int,list)):
            styled_row.append(
                Text(str(row[key]), style="bold bright_white")
            )

        else:
            styled_row.append(Text(str(row[key]), style="bold white"))
    return styled_row







def get_post_styled(row, columns=None):
    styled_row = []
    for key in get_post_col_names() if columns is None else columns:
        val = row.get(key, "")
        if key in ["video_length", "new_video_length", "audio_length", "new_audio_length", "post_date"]:
            styled_row.append(Text(str(val), style="bold deep_sky_blue1"))
        elif key == "download_cart":
            sval = str(val)
            if sval == "[downloaded]":
                style = "bold green"
            elif sval == "[stopped]":
                style = "bold cyan"
            elif sval == "[failed]":
                style = "bold red"
            elif sval == "[skipped]":
                style = "bold bright_yellow"
            elif sval == "[downloading]":
                style = "bold dark_orange"
            else:
                style = "bold light_goldenrod2"
            styled_row.append(Text(sval, style=style))
        elif key.startswith("new_cost_") or key.startswith("cost_per_") or key == "total_cost":
            sval = str(val)
            style = "dim white" if sval in {"N/A", "All Dupes"} else "bold gold1"
            styled_row.append(Text(sval, style=style))
        elif key in {"new_media", "new_photos", "new_videos", "new_audios"}:
            styled_row.append(Text(str(val), style="bold bright_green"))
        elif key == "text":
            styled_row.append(Text(str(val), style="bold dark_sea_green1"))
        elif key == "number":
            styled_row.append(Text(str(val), style="bold bright_white"))
        elif isinstance(val, bool):
            styled_row.append(Text(str(val), style="bold plum1"))
        elif isinstance(val, (int, float, list)):
            styled_row.append(Text(str(val), style="bold bright_white"))
        else:
            styled_row.append(Text(str(val), style="bold medium_spring_green"))
    return styled_row
