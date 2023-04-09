import src.utils.download as download
from unittest.mock import patch
from unittest.mock import MagicMock
import platform
import pathlib


def test_windows_trunicate():
    with patch('platform.system', MagicMock(return_value="Windows")):
        assert(platform.system())=="Windows"
        long_path=pathlib.Path("unittestmockprovidesacore/Mockclassremovingtheneedtocreateahostofstubsthroughout/yourtestsuiteAfterperforminganactionyoucanmakeassertionsaboutwhichmethods/attributeswereusedandargumentstheywerecalledwithYoucanalsospecifyreturnvaluesandsetneededattributesinthenormalway.mkv")
        trunicated=download.trunicate(long_path)
        assert(len(str(trunicated)))<=256
        assert(long_path.parent)==trunicated.parent
        assert(long_path.suffix)==trunicated.suffix



def test_windows_trunicate():
    long_path=pathlib.Path("unittestmockprovidesacore/Mockclassremovingtheneedtocreateahostofstubsthroughout/yourtestsuiteAfterperforminganactionyoucanmakeassertionsaboutwhichmethattributeswereusedandargumentstheywerecalledwithYoucanalsospecifyreturnvaluesandsetneededattributesinthenormalway \
                            attributeswereusedandargumentstheywerecalledwithYoucanalsospecifyreturnvaluesandsetneededattributesinthenormalway \
                            attributeswereusedandargumentstheywerecalledwithYoucanalsospecifyreturnvaluesandsetneededattributesinthenormalway \
                            attributeswereusedandargumentstheywerecalledwithYoucanalsospecifyreturnvaluesandsetneededattributesinthenormalway \
                            attributeswereusedandargumentstheywerecalledwithYoucanalsospecifyreturnvaluesandsetneededattributesinthenormalway.mkv")
    trunicated=download.trunicate(long_path)
    assert(len(trunicated.name.encode('utf8')))<=255
    assert(long_path.parent)==trunicated.parent
    assert(long_path.suffix)==trunicated.suffix