
import logging
import re
import arrow
import ofscraper.utils.config as config
import ofscraper.utils.args as args_

args=args_.getargs()
log=logging.getLogger(__package__)
def filterMedia(media):
    media=dupefilter(media)
    media=post_datesorter(media)
    media=posts_type_filter(media)
    media=posts_date_filter(media)
    media=post_timed_filter(media)
    media=post_user_filter(media)
    media=download_type_filter(media)
    media=sort_media(media)
    return media

def sort_media(media):
    return sorted(media,key=lambda x:x.date)

def post_manual_filter():
    None

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
def post_datesorter(output):
    return list(sorted(output,key=lambda x:x.date,reverse=True))



    
def timeline_array_filter(posts):
    out=[]
    undated=list(filter(lambda x:x.get("postedAt")==None,posts))
    dated=list(filter(lambda x:x.get("postedAt")!=None,posts))
    dated=sorted(dated,key=lambda x:arrow.get(x.get("postedAt")))
    if args.before:
        dated=list(filter(lambda x:arrow.get(x.get("postedAt"))<=args.before,dated))
    if args.after:
         dated=list(filter(lambda x:arrow.get(x.get("postedAt"))>=args.after,dated))
    out.extend(undated)
    out.extend(dated)
    return out
def posts_type_filter(media): 
    filtersettings=config.get_filter(config.read_config())
    if isinstance(filtersettings,str):
        filtersettings=filtersettings.split(",")
    if isinstance(filtersettings,list):
        filtersettings=list(map(lambda x:x.lower().replace(" ",""),filtersettings))
        filtersettings=list(filter(lambda x:x!="",filtersettings))
        if len(filtersettings)==0:
            return media
        log.info(f"filtering Media to {','.join(filtersettings)}")
        media =list(filter(lambda x:x.mediatype.lower() in filtersettings,media))
    else:
        log.info("The settings you picked for the filter are not valid\nNot Filtering")
        log.debug(f"[bold]Combined Media Count Filtered:[/bold] {len(media)}")
    return media

def posts_date_filter(media):
    if args.before:
        media=list(filter(lambda x:x.postdate==None or arrow.get(x.postdate)<=args.before,media))
    if args.after:
        media=list(filter(lambda x:x.postdate==None or arrow.get(x.postdate)>=args.after,media))
    return media

def post_timed_filter(media):
    if args.skip_timed:
        return list(filter(lambda x:not x.expires,media))
    return media
def post_user_filter(media):
    userfilter=args.filter
    if not userfilter.islower():
        return list(filter(lambda x:re.search(userfilter,x.text or "")!=None,media))
    else:
        return list(filter(lambda x:re.search(userfilter,x.text or "",re.IGNORECASE)!=None,media))

def download_type_filter(media):
    if args_.getargs().download_type==None:
        return media
    elif args_.getargs().download_type=="protected":
        return list(filter(lambda x:x.mpd!=None,media))  
    elif args_.getargs().download_type=="normal":
        return list(filter(lambda x:x.url!=None,media))