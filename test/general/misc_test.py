from test_constants import *
from src.utils.separate import separate_by_id

def test_seperate(mocker):
    data=[]
    media_ids=[]
    for i in range(5000,5100):
        t=mocker.MagicMock()
        t.id=i
        data.append(t)
    for i in range(5000,5100):
        media_ids.append(i)   
    assert(len(separate_by_id(data,media_ids)))==0
    

def test_seperate2(mocker):
    data=[]
    media_ids=[]
    for i in range(5000,5200):
        t=mocker.MagicMock()
        t.id=i
        data.append(t)
    for i in range(5000,5100):
        media_ids.append(i)   
    assert(len(separate_by_id(data,media_ids)))==100
    
