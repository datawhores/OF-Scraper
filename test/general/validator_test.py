from ofscraper.prompts.prompt_functions import emptyListValidator,jsonValidator,namevalitator,dirformatvalidator \
,dateplaceholdervalidator,fileformatvalidator,metadatavalidator
from test.test_constants import *
from prompt_toolkit.validation import ValidationError, Validator
import pytest
from prompt_toolkit.document import Document
from InquirerPy.validator import EmptyInputValidator
from unittest.mock import patch,MagicMock




def test_emptyinput_error():
    document=Document()
    document._text = ""
    with pytest.raises(ValidationError):
        EmptyInputValidator().validate(document)
def test_emptyinput_noerror():
    """
    Assert your python code raises no exception.    
    """
    document=Document()
    document._text = "t"
    try:
        EmptyInputValidator().validate(document)
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"

def test_empty_list_error():
    document=Document()
    document._text = []
    with pytest.raises(ValidationError):
        emptyListValidator().validate(document)

def test_empty_list_noerror():
    """
    Assert your python code raises no exception.    
    """
    document=Document()
    document._text = ["t"]
    try:
        emptyListValidator().validate(document)
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"


def test_jsonvalidator_error():
    document=Document()
    document._text = INVALID_JSON
    with pytest.raises(ValidationError):
        jsonValidator().validate(document)


def test_json_noerror():
    """
    Assert your python code raises no exception.    
    """
    document=Document()
    document._text = VALID_JSON
    try:
        jsonValidator().validate(document)
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"

def test_namevalidator_error():
    document=Document()
    document._text = INVALID_NAME
    with pytest.raises(ValidationError):
        namevalitator().validate(document)

def test_namevalidator_noerror():
    """
    Assert your python code raises no exception.    
    """
    document=Document()
    document._text = VALID_NAME
    try:
        namevalitator().validate(document)
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"
def test_dirformat_invalidplaceholder():
    document=Document()
    document._text = DIR_FORMAT_INVALID
    with pytest.raises(ValidationError):
        dirformatvalidator().validate(document)


def test_dirformat_invalidpathwin():
    document=Document()
    document._text = INVALID_WINDOWS
    with patch('platform.system', MagicMock(return_value="Windows")):
        with pytest.raises(ValidationError):
            dirformatvalidator().validate(document)

def test_dirformat_invalidpathlinux():
    document=Document()
    document._text = INVALID_LINUX
    with pytest.raises(ValidationError):
        dirformatvalidator().validate(document)
def test_dirformat_invalidpathmac():
    document=Document()
    document._text = INVALID_LINUX
    with patch('platform.system', MagicMock(return_value="Darwin")):
        with pytest.raises(ValidationError):
            dirformatvalidator().validate(document)


def test_dirformatallvalidkeys():
    document=Document()
    document._text = DIR_FORMAT_ALLVALID
    try:
        dirformatvalidator().validate(document)
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"

def test_dirformatallvalidkeyWthinvalid():
    document=Document()
    document._text = DIR_FORMAT_ALLWTHINVALID
    with pytest.raises(ValidationError):
        dirformatvalidator().validate(document)      

###
# Date formatting is very flexiable
###
def test_dateinvalidformat():
    document=Document()
    document._text = DATE_INVALID
    with pytest.raises(ValidationError):
        dateplaceholdervalidator().validate(document)      


def test_datevalidformat():
    document=Document()
    document._text = DATE_VALID
    try:
        dateplaceholdervalidator().validate(document)     
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"


def test_datesillyvalidformat():
    document=Document()
    document._text = DATE_SILLY
    try:
        dateplaceholdervalidator().validate(document)     
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"



def test_fileformatallvalidkeys():
    document=Document()
    document._text = FILEFORMAT_VALID_ALL
    
    try:
        fileformatvalidator().validate(document)
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"

def test_fileformatallvalidkeyWthinvalid():
    document=Document()
    document._text = FILEFORMAT_ALLVALIDWTHINVALID
    with pytest.raises(ValidationError):
        fileformatvalidator().validate(document)   
def test_fileformat_invalidfilenamewin():
    document=Document()
    document._text = INVALID_WINDOWS
    with patch('platform.system', MagicMock(return_value="Windows")):
        with pytest.raises(ValidationError):
            fileformatvalidator().validate(document)

def test_fileformat_invalidfilenamelinux():
    document=Document()
    document._text = INVALID_LINUX
    with pytest.raises(ValidationError):
        fileformatvalidator().validate(document)
def test_fileformat_invalidfilenamemac():
    document=Document()
    document._text = INVALID_LINUX
    with patch('platform.system', MagicMock(return_value="Darwin")):
        with pytest.raises(ValidationError):
            fileformatvalidator().validate(document)



def test_metaformat_invalidplaceholder():
    document=Document()
    document._text = METADATA_INVALID
    with pytest.raises(ValidationError):
        metadatavalidator().validate(document)


def test_metaformat_invalidpathwin():
    document=Document()
    document._text = INVALID_WINDOWS
    with patch('platform.system', MagicMock(return_value="Windows")):
        with pytest.raises(ValidationError):
            metadatavalidator().validate(document)

def test_metaformat_invalidpathlinux():
    document=Document()
    document._text = INVALID_LINUX
    with pytest.raises(ValidationError):
        metadatavalidator().validate(document)
def test_dirformat_invalidpathmac():
    document=Document()
    document._text = INVALID_LINUX
    with patch('platform.system', MagicMock(return_value="Darwin")):
        with pytest.raises(ValidationError):
            metadatavalidator().validate(document)


def test_metaformatallvalidkeys():
    document=Document()

    document._text = METADATA_ALLVALID
    try:
        metadatavalidator().validate(document)
    except ValidationError as exc:
        assert False, f"'{document._text} {exc}"

def test_metaformatallvalidkeyWthinvalid():
    document=Document()
    document._text = METADATA_ALLWTHINVALID
    with pytest.raises(ValidationError):
        metadatavalidator().validate(document)      