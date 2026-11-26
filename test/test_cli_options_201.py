"""--block-ads is accepted, --env-files is loaded, --length-max/min take seconds (#201)."""

from types import SimpleNamespace

import click
import pytest

import ofscraper.utils.settings as settings
from ofscraper.utils.args.parse.commands.main import program


def _parse(args):
    params, _ = program.main(args=args, standalone_mode=False, prog_name="OF-Scraper")
    return params


def test_block_ads_is_accepted():
    assert _parse(["--block-ads"])["block_ads"] is True
    assert _parse([])["block_ads"] is False


def test_length_filters_take_plain_seconds():
    params = _parse(["--length-max", "90", "--length-min", "5"])
    # whole seconds as ints: the table view splits them into h/m/s inputs
    assert params["length_max"] == 90 and type(params["length_max"]) is int
    assert params["length_min"] == 5


@pytest.mark.parametrize("value", ["1m", "1.5", "nan", "inf", "-1"])
def test_length_filters_reject_anything_but_whole_seconds(value):
    with pytest.raises(click.BadParameter):
        _parse(["--length-max", value])


@pytest.fixture
def loaded(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "load_env_files", lambda files: calls.append(files))
    monkeypatch.setattr(settings.of_env, "get_all_configs", lambda **k: None)
    monkeypatch.setattr(settings, "merged_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(settings, "settings", None)
    return calls


def test_env_files_from_the_command_line_are_loaded(monkeypatch, loaded):
    monkeypatch.setattr(settings, "get_args", lambda *a, **k: SimpleNamespace(env_files=("cli.env",)))
    monkeypatch.setattr(settings.config_data, "get_env_files", lambda *a, **k: ["config.env"])
    settings.setup_settings()
    assert loaded == [["cli.env"]]


def test_config_env_files_are_loaded_without_the_option(monkeypatch, loaded):
    monkeypatch.setattr(settings, "get_args", lambda *a, **k: SimpleNamespace(env_files=()))
    monkeypatch.setattr(settings.config_data, "get_env_files", lambda *a, **k: "a.env, b.env")
    settings.setup_settings()
    assert loaded == [["a.env", "b.env"]]


def test_neg_filter_does_not_grow_on_each_settings_build(monkeypatch):
    from ofscraper.utils.args.main import AutoDotDict

    args = AutoDotDict(_parse(["--block-ads", "--neg-filter", "foo"]))
    args.command = "OF-Scraper"
    monkeypatch.setattr(settings.read_args, "retriveArgs", lambda *a, **k: args)
    first = settings.merged_settings().neg_filter
    second = settings.merged_settings().neg_filter
    assert args.neg_filter == ["foo"]
    assert first == second and len(second) == 2


def test_table_time_field_accepts_decimal_seconds():
    # config.json can hold a decimal length; the table view splits it into h/m/s
    from ofscraper.classes.table.fields.timefield import TimeField

    inputs = [SimpleNamespace(value=None) for _ in range(3)]
    field = object.__new__(TimeField)
    field.query_one = lambda *a: SimpleNamespace(query=lambda *a: inputs)
    field.update_table_max(5400.0)
    # a zero part is left empty so the box shows its placeholder
    assert [i.value for i in inputs] == ["1", "30", ""]
    field.update_table_min(90.7)
    assert [i.value for i in inputs] == ["", "1", "30"]


# --original and truncation_default: false leave a long path as the template
# gives it (#740).

import asyncio

import ofscraper.classes.placeholder as placeholder
from naming_helpers import make_post, naming  # noqa: F401  (fixture)

LONG_CAPTION = " ".join(["word"] * 120)  # 599 characters: over every system's limit


def _long_paths(naming, *options):
    """The path of a long-captioned post's media file and text file."""
    naming("{text}.{ext}", LONG_CAPTION, *options)  # applies the settings
    post = make_post(LONG_CAPTION)
    return [
        asyncio.run(holder.init(create=False)).filepath
        for holder in (
            placeholder.Placeholders(post.all_media[0], "jpg"),
            placeholder.Textholders(post, "txt"),
        )
    ]


def test_original_leaves_a_long_name_whole(naming):
    media, text = _long_paths(naming, "--original")
    assert (media.name, text.name) == (f"{LONG_CAPTION}.jpg", f"{LONG_CAPTION}.txt")


def test_a_long_name_is_shortened_by_default(naming):
    media, text = _long_paths(naming)
    assert len(media.name) < len(LONG_CAPTION) and media.suffix == ".jpg"
    assert len(text.name) < len(LONG_CAPTION) and text.suffix == ".txt"


# A folder longer than Windows' MAX_PATH: shortening it can't work (#737), so
# with --original nothing may try to.
LONG_FOLDER = "{date}/" + "/".join(["d" * 60] * 5)


def _long_paths_on_disk():
    """Whether this system can create a path over 260 characters: on Windows
    only with LongPathsEnabled set."""
    import sys

    if sys.platform != "win32":
        return True
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem"
        ) as key:
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
    except OSError:
        return False


needs_long_paths = pytest.mark.skipif(
    not _long_paths_on_disk(), reason="Windows without LongPathsEnabled can't create these"
)


@pytest.fixture
def on_windows(monkeypatch):
    monkeypatch.setattr(placeholder.paths.platform, "system", lambda: "Windows")


def test_original_leaves_the_folder_of_a_long_path_whole(naming, monkeypatch, on_windows):
    naming("{text}.{ext}", "short", "--original")
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: LONG_FOLDER)
    post = make_post("short")
    media = asyncio.run(placeholder.Placeholders(post.all_media[0], "jpg").init(create=False))
    text = asyncio.run(placeholder.Textholders(post, "txt").init(create=False))
    assert media.trunicated_filedir == media.filepath.parent
    assert text.filedir == text.filepath.parent
    assert len(str(media.filepath)) > 300


@needs_long_paths
def test_original_leaves_a_temp_file_in_a_long_folder_whole(naming, monkeypatch, on_windows):
    naming("{text}.{ext}", "short", "--original")
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: LONG_FOLDER)
    post = make_post("short")
    temp = asyncio.run(
        placeholder.tempFilePlaceholder(post.all_media[0], "pic0.part").init()
    )
    assert temp.tempfilepath.name == "pic0.part"
    assert temp.tempfilepath.parent.is_dir() and len(str(temp.tempfilepath)) > 300


@pytest.mark.parametrize("options", [(), ("--original",)])
def test_a_clashing_name_gets_its_media_id_whole_only_with_original(
    naming, tmp_path, monkeypatch, options
):
    import ofscraper.commands.scraper.actions.utils.paths as action_paths

    naming("{text}.{ext}", "short", *options)
    # Linux's rules, which read the path as this system does, with a 100-byte
    # name limit: the name fits it exactly, so with "_71" added it gets
    # shortened, unless --original
    monkeypatch.setattr(placeholder.paths.platform, "system", lambda: "Linux")
    monkeypatch.setenv("UTF", "utf-8")
    monkeypatch.setenv("LINUX_MAX_FILE_NAME_BYTES", "100")
    target = tmp_path / ("a" * 96 + ".jpg")
    target.write_bytes(b"another file")
    temp = tmp_path / "dl.part"
    temp.write_bytes(b"this download")
    media = SimpleNamespace(id=71, post_id=8, model_id=1, username="u")
    got = action_paths.moveHelper(temp, target, media)
    whole = target.with_name(f"{target.stem}_71.jpg")
    assert (got == whole) == bool(options)
    assert got.suffix == ".jpg" and got.read_bytes() == b"this download"


def _default_settings(naming, monkeypatch):
    """Settings as a run builds them from an empty config.json and no
    options: trunicate is the bool True, as get_truncation gives it."""
    naming("{text}.{ext}", "short")
    assert placeholder.settings.get_settings().trunicate is True
    monkeypatch.setattr(placeholder.paths.platform, "system", lambda: "Linux")


def test_default_settings_shorten_a_long_path(naming, monkeypatch):
    _default_settings(naming, monkeypatch)
    out = placeholder.final_path(f"/data/{'a' * 400}.jpg")
    assert out.suffix == ".jpg" and len(out.name) < 400


@pytest.mark.parametrize("holder", ["Placeholders", "Textholders"])
def test_default_settings_shorten_the_saved_path(naming, monkeypatch, holder):
    # the path a download is saved at reads the flag the same way
    _default_settings(naming, monkeypatch)
    obj = getattr(placeholder, holder).__new__(getattr(placeholder, holder))
    obj._filepath = f"/data/{'a' * 400}.jpg"
    out = obj.trunicated_filepath
    assert out.suffix == ".jpg" and len(out.name) < 400
