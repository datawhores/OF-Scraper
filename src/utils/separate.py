r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""


def separate_by_id(data: list, media_ids: list) -> list:
    return list(filter(lambda x:x.get("id") not in media_ids,data))
    
  


def separate_database_results_by_id(results: list, media_ids: list) -> list:
    filtered_results = [r for r in results if r[0] not in media_ids]
    return filtered_results
