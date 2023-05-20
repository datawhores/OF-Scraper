
import logging
import arrow


log=logging.getLogger(__package__)
def filterMedia(media):
    media=dupefilter(media)
    media=datesorter(media)
    media=posts_type_filter(media)
    return media

def date_filter(media):
    media=media
    print("test")


def dupefilter(media):
    output=[]
    ids=set()
    log.info("Removing duplicate media")
    log.debug(f"[bold]Combined Media Count with dupes[/bold]  {len(media)}")
    for item in media:
        if not item.id or item.id not in ids:
            output.append(item)
            ids.add(item.id)
    log.debug(f"[bold]Combined Media Count without dupes[/bold] {len(output)}")
    return output
def datesorter(output):
    return list(sorted(output,key=lambda x:x.date,reverse=True))

def posts_type_filter(media): 
    if isinstance(filtersettings,str):
        filtersettings=filtersettings.split(",")
    if isinstance(filtersettings,list):
        filtersettings=list(map(lambda x:x.lower().replace(" ",""),filtersettings))
        filtersettings=list(filter(lambda x:x!="",filtersettings))
        if len(filtersettings)==0:
            return media
        log.info(f"filtering Media to {','.join(filtersettings)}")
        output= list(filter(lambda x:x.mediatype.lower() in filtersettings,output))
    else:
        log.info("The settings you picked for the filter are not valid\nNot Filtering")
        log.debug(f"[bold]Combined Media Count Filtered:[/bold] {len(output)}")
    return output
