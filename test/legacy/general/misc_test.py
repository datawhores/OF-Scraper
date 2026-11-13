from pytest_check import check

import ofscraper.utils.args2.args as args_
from ofscraper.const.test_constants import *
from ofscraper.utils.separate import separate_by_id


def test_seperate(mocker):
    data = []
    media_ids = []
    for i in range(5000, 5100):
        t = mocker.MagicMock()
        t.id = i
        data.append(t)
    for i in range(5000, 5100):
        media_ids.append(i)
    assert (len(separate_by_id(data, media_ids))) == 0


def test_seperate2(mocker):
    data = []
    media_ids = []
    for i in range(5000, 5200):
        t = mocker.MagicMock()
        t.id = i
        data.append(t)
    for i in range(5000, 5100):
        media_ids.append(i)
    assert (len(separate_by_id(data, media_ids))) == 100


def test_args(mocker):
    args = args_.getargs([])
    assert (args) == args_.getargs()


def test_args_change(mocker):
    args = args_.getargs([])
    args.renewal = "test"
    args_.changeargs(args)
    for key in vars(args).keys():
        with check:
            assert (vars(args)[key]) == vars(args_.getargs())[key]
