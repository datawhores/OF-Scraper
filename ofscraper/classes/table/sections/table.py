import logging
from rich.text import Text
from ofscraper.classes.table.utils.names import get_col_names

from textual.widgets import DataTable
from ofscraper.classes.table.utils.lock import mutex
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


    


