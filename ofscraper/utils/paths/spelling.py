"""How a disk spells a path: whether it tells the case of letters apart, and
which name in a folder is a recorded name spelt otherwise. Shared by
rename_to_format and verify, which each say how two spellings compare
(their key): verify only finds a file, so any Unicode form will do; a
rename mustn't take two different files for one."""

import os
from collections import defaultdict


class Spellings:
    """Per-run caches: which folders don't tell case apart, and each
    folder's names by key. Each folder is read once."""

    def __init__(self):
        self._folds = {}
        self._folders = {}

    def folds_case(self, folder):
        """The disk doesn't tell case apart here: tried on the nearest
        folder whose name has letters."""
        if folder not in self._folds:
            name, parent = os.path.basename(folder), os.path.dirname(folder)
            if parent == folder:
                self._folds[folder] = False
            elif name.swapcase() != name and os.path.lexists(folder):
                other = os.path.join(parent, name.swapcase())
                try:
                    self._folds[folder] = os.path.samefile(folder, other)
                except OSError:
                    self._folds[folder] = False
            else:
                self._folds[folder] = self.folds_case(parent)
        return self._folds[folder]

    def key(self, path):
        """`path` as this disk tells paths apart: os.path.normcase, and lower
        case where the disk doesn't tell case apart (macOS's, whose normcase
        keeps case)."""
        path = os.path.normcase(path)
        return path.lower() if self.folds_case(os.path.dirname(path)) else path

    def find(self, path):
        """The path the file is at, or None when no name in its folder, or
        more than one, is its name spelt otherwise."""
        folder = os.path.dirname(path)
        if folder not in self._folders:
            names = defaultdict(list)
            try:
                for name in os.listdir(folder):
                    names[self.key(os.path.join(folder, name))].append(os.path.join(folder, name))
            except OSError:
                pass
            self._folders[folder] = names
        found = self._folders[folder].get(self.key(path), [])
        return found[0] if len(found) == 1 else None
