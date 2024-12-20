import arrow
import logging
from rich.text import Text

from ofscraper.classes.table.utils.row_names import row_names
from textual.widgets import DataTable
from ofscraper.classes.table.utils.lock import mutex
log = logging.getLogger("shared")


class DataTableExtended(DataTable):
    def __init_(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
    #cart
    def toggle_cart(self):
        for key in self.ordered_row_keys:
            if self.get_row_dict(key)["download_cart"] == "[downloaded]":
                pass
            elif self._download_cart_toggle:
                self.update_cell_at_key(key, "download_cart", "[]")
            elif self.get_row_dict(key)["download_cart"] == "[]":
                self.update_cell_at_key(key, "download_cart", "[added]")
        self._download_cart_toggle=not self._download_cart_toggle
    def change_cart_cell(self, coord):
        row,col=coord
        table=self
        if list(table.ordered_columns_keys)[col]!="download_cart":
            return
        download_cart = table.get_row_dict_at(row)["download_cart"]
        if download_cart == "Not Unlocked":
            pass
        elif download_cart == "[]":
            table.update_cell_at_coord(coord, Text("[added]",style="bold light_goldenrod2"))

        elif download_cart == "[added]":
            table.update_cell_at_coord(coord, Text("[]",style="bold light_goldenrod2"))
        elif download_cart == "[downloaded]" or "[failed]":
            table.update_cell_at_coord(coord, Text("[added]",style="bold light_goldenrod2"))
        self._download_cart_toggle=False
    #cell modification and retrieval
    def get_row_dict_at(self, row_index):
        return {key:value for key,value in zip(self.ordered_columns_keys,map(lambda x:x.plain if isinstance(x,Text) else x,self.get_row_at(row_index)))}
    def get_row_dict(self,row_key):
        return {key:value for key,value in zip(self.ordered_columns_keys,map(lambda x:x.plain if isinstance(x,Text) else x,self.get_row(row_key)))}

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
            for key in key if isinstance(keys, list) else [keys]:
                try:
                    self.update_cell(key,col_key, value)
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)
    def get_matching_rows(self,col_name,col_value):
        order_row_keys=list(self.ordered_row_keys)
        out={}
        for key in order_row_keys:
            row_dict=self.get_row_dict(key)
            if row_dict[col_name] == col_value:
                out[key]=row_dict
        return out
    
    @property
    def ordered_columns_keys(self):
        return map(lambda x:x.key.value,self.ordered_columns)
    
    @property
    def ordered_row_keys(self):
        return map(lambda x:x.key.value,self.ordered_rows)

        


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

