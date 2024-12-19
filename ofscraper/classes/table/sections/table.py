import arrow
from rich.text import Text

from ofscraper.classes.table.utils.row_names import row_names
from textual.widgets import DataTable


class DataTableExtended(DataTable):
    def __init_(self,*args,**kwargs):
        super().__init__(*args,**kwargs)


class TableRow:
    def __init__(self, table_row):
        self._table_row = table_row
        self._other_styled = None

    def get_styled(self):
        styled_row = [self._table_row["number"]]
        for key in row_names():
            key = key.lower()
            if key in ["length","post_date"]:
                styled_row.append(
                    Text(str(self._table_row[key]), style="bold deep_sky_blue1")
                )
            elif key =="download_cart":
                styled_row.append(
                    Text(str(self._table_row[key]), style="bold light_goldenrod2")
                )
            elif key=="text":
                styled_row.append(
                    Text(str(self._table_row[key]), style="bold dark_sea_green1")
                )
            elif isinstance(self._table_row[key],str):
                styled_row.append(
                    Text(str(self._table_row[key]), style="bold medium_spring_green")
                )
            elif isinstance(self._table_row[key],bool):
                styled_row.append(
                    Text(str(self._table_row[key]), style="bold plum1")
                )
            elif isinstance(self._table_row[key],(int,list)):
                styled_row.append(
                    Text(str(self._table_row[key]), style="bold bright_white")
                )
        
            else:
                styled_row.append(self._table_row[key])
        return styled_row

    def get_val(self, name):
        name = name.lower()
        name = name if name != "number" else "index"
        return self._table_row[name]

    def get_compare_val(self, name):
        if name == "length":
            return self._get_length_val(name)
        if name == "post_date":
            return self._get_post_date_val(name)
        if name == "other_posts_with_media":
            return self._get_list_length(name)
        else:
            return self.get_val(name)

    def _get_post_date_val(self, name):
        return arrow.get(self._table_row[name]).floor("day")

    def _get_length_val(self, name):
        timestr = self._table_row[name]
        if timestr == "N\A" or timestr == "N/A":
            timestr = "0:0:0"
        return arrow.get(timestr, "h:m:s")

    def _get_list_length(self, name):
        return len(self._table_row[name])

    def set_val(self, key, val):
        self._table_row[key.lower()] = val
        self._other_styled = None

