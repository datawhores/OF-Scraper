import logging
from rich.text import Text
from ofscraper.classes.table.utils.names import get_col_names

from textual.widgets import DataTable
from ofscraper.classes.table.utils.lock import mutex
log = logging.getLogger("shared")


class DataTableExtended(DataTable):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._download_cart_toggle=False
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
        if table.ordered_columns_keys[col]!="download_cart":
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
            for key in keys if isinstance(keys, list) else [keys]:
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
        return list(map(lambda x:x.key.value,self.ordered_columns))
    
    @property
    def ordered_row_keys(self):
        return list(map(lambda x:x.key.value,self.ordered_rows))

        



def get_styled(row):
        styled_row = []
        for key in get_col_names():
            if key in ["length","post_date"]:
                styled_row.append(
                    Text(str(row[key]), style="bold deep_sky_blue1")
                )
            elif key =="download_cart":
                styled_row.append(
                    Text(str(row[key]), style="bold light_goldenrod2")
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
                styled_row.append(Text(row[key]), style="bold white")
        return styled_row




    


