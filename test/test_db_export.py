import csv
from types import SimpleNamespace

import ofscraper.commands.db as db_command

ROWS = {
    1: [{"media_id": 10, "model_id": 1}, {"media_id": 11, "model_id": 1}],
    2: [{"media_id": 20, "model_id": 2}],
    3: [],
}


class FakeDBManager(db_command.DBManager):
    """The real manager, minus reading a database and printing the table."""

    def get_wanted_media(self):
        self.media = [
            {**row, "posted_at": "2024-01-02", "created_at": "2024-01-01", "size": 100}
            for row in ROWS[self.model_id]
        ]

    def print_dictionary_table(self):
        pass


def test_export_keeps_every_creators_rows(monkeypatch, tmp_path):
    models = [SimpleNamespace(name=f"creator{i}", id=i) for i in (1, 2, 3)]
    model_manager = SimpleNamespace(all_subs=models, sync_models=lambda **kwargs: None)
    monkeypatch.setattr(
        db_command.manager, "Manager", SimpleNamespace(current_model_manager=model_manager)
    )
    monkeypatch.setattr(db_command.actions, "select_areas", lambda: None)
    monkeypatch.setattr(db_command, "DBManager", FakeDBManager)
    monkeypatch.setattr(db_command.time, "sleep", lambda seconds: None)
    export = tmp_path / "out"
    monkeypatch.setattr(db_command.settings, "get_settings", lambda: SimpleNamespace(export=export))

    db_command.db()

    with open(export.with_suffix(".csv"), newline="") as f:
        written = [(int(r["model_id"]), int(r["media_id"]), r["size_human"]) for r in csv.DictReader(f)]
    # before the fix each creator rewrote the file, so only the last one's
    # (here empty) export survived
    assert written == [(1, 10, "100 bytes"), (1, 11, "100 bytes"), (2, 20, "100 bytes")]
