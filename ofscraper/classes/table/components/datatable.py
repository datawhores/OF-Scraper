import copy

from textual.widgets._data_table import DataTable as DataTable_,ColumnKey,RowKey,CellType
from operator import itemgetter
from typing import Any, Callable
from typing_extensions import Self


class DataTable(DataTable_):
    def __init__(self, *args, **kwargs) -> None:
        self._old_row_locations=None
        self._old_data=None
        self._old_rows=None
        super().__init__(*args, **kwargs)
    def filter(
        self,
        *columns: ColumnKey | str,
        key: Callable[[Any], Any] | None = None,
        compare: Any = None,
    ) -> Self:
        """Filter the rows in the `DataTable` by one or more column keys or a
        key function (or other callable). If both columns and a key function
        are specified, only data from those columns will sent to the key function.

        Args:
            columns: One or more columns to filter by the values in.
            key: A function (or other callable) that returns a key to
                use for fiself.query_one("#post_media_count").filter()lltering purposes.
            reverse: If True, the filter order will be reversed.

        Returns:
            The `DataTable` instance.
        """

        def key_wrapper(row: tuple[RowKey, dict[ColumnKey | str, CellType]]) -> Any:
            _, row_data = row
            if columns:
                result = itemgetter(*columns)(row_data)
            else:
                result = tuple(row_data.values())
            if key is not None:
                return key(result)
            if compare is not None:
                return result == compare
            return result
        items=self._data.items()
        for row in items:
            if not key_wrapper(row):
                self.remove_row(row[0].value)

        
        
    
    def  reset(self,refresh=False):
        self.clear()
        self._row_locations=copy.deepcopy(self._old_row_locations)
        self._data=copy.deepcopy(self._old_data)
        self.rows=copy.deepcopy(self._old_rows)
        self._update_count += 1
        self._new_rows=list(self.rows.keys())
        self._require_update_dimensions = True
        if refresh:
            self.refresh()
    def save_table(self, *args, **kwargs):
        self._old_row_locations=copy.deepcopy(self._row_locations)
        self._old_data=copy.deepcopy(self._data)
        self._old_rows=copy.deepcopy(self.rows)
