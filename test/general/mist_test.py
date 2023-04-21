from test_constants import *
from src.utils.separate import separate_by_id
def test_seperate():
    data=[]
    media_ids=[]
    for i in range(5000,5100):
        data.append({"id":i})
    for i in range(5000,5100):
        media_ids.append(i)   
    assert(len(separate_by_id(data,media_ids)))==0
    
