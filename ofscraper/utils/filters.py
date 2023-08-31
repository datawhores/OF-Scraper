
import logging
import re
import arrow
import ofscraper.utils.config as config
import ofscraper.utils.args as args_

log=logging.getLogger("shared")
def filterMedia(media):
    logformater="{} data: {} id: {} postid: {}"
    []
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 1-> all media no filter:",x.media,x.id,x.postid),media))))
    log.debug(f"filter 1-> all media no filter count: {len(media)}")
    media=dupefilter(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 2-> all media dupe filter: ",x.media,x.id,x.postid),media))))

    log.debug(f"filter 2-> all media dupe filter count: {len(media)}")
    media=post_datesorter(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 3-> all media datesort: ",x.media,x.id,x.postid),media))))
    log.debug(f"filter 3-> all media datesort count: {len(media)}")
    media=posts_type_filter(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 4-> all media post media type filter: ",x.media,x.id,x.postid),media))))

    log.debug(f"filter 4-> all media post media type filter count: {len(media)}")
    media=posts_date_filter(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 5-> all media post date filter: ",x.media,x.id,x.postid),media))))
    log.debug(f"filter 5-> all media post date filter: {len(media)}")
    media=post_timed_filter(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 6->  all media post timed post filter: ",x.media,x.id,x.postid),media))))
    log.debug(f"filter 6->  all media post timed post filter count: {len(media)}")
    media=post_user_filter(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 7-> all media post text filter: ",x.media,x.id,x.postid),media))))
    log.debug(f"filter 7->  all media post text filter count: {len(media)}")
    media=download_type_filter(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 8->  all download type filter: ",x.media,x.id,x.postid),media))))
    log.debug(f"filter 8->  all media download type filter count: {len(media)}")

    media=mass_msg_filter(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 9->  mass message filter: ",x.media,x.id,x.postid),media))))
    log.debug(f"filter 9->  all media mass message filter count: {len(media)}")
   
    media=sort_media(media)
    log.trace("\n\n\n".join(list(map(lambda x: logformater.format("filter 10-> final media  from retrived post: ",x.media,x.id,x.postid),media))))
    log.debug(f"filter 10->  final media count from retrived post: {len(media)}")
    return media

def sort_media(media):
    return sorted(media,key=lambda x:x.date)

def post_manual_filter():
    None

def dupefilter(media):
    output=[]
    ids=set()
    log.info("Removing duplicate media")
    for item in media:
        if not item.id or item.id not in ids:
            output.append(item)
            ids.add(item.id)
    return output
def post_datesorter(output):
    return list(sorted(output,key=lambda x:x.date,reverse=True))



    
def timeline_array_filter(posts):
    out=[]
    undated=list(filter(lambda x:x.get("postedAt")==None,posts))
    dated=list(filter(lambda x:x.get("postedAt")!=None,posts))
    dated=sorted(dated,key=lambda x:arrow.get(x.get("postedAt")))
    if args_.getargs().before:
        dated=list(filter(lambda x:arrow.get(x.get("postedAt"))<=args_.getargs().before,dated))
    if args_.getargs().after:
         dated=list(filter(lambda x:arrow.get(x.get("postedAt"))>=args_.getargs().after,dated))
    out.extend(undated)
    out.extend(dated)
    return out
def posts_type_filter(media): 
    filtersettings=args_.getargs().mediatype or config.get_filter(config.read_config())
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
    if args_.getargs().before:
        media=list(filter(lambda x:x.postdate==None or arrow.get(x.postdate)<=args_.getargs().before,media))
    if args_.getargs().after:
        media=list(filter(lambda x:x.postdate==None or arrow.get(x.postdate)>=args_.getargs().after,media))
    return media

def post_timed_filter(media):
    if args_.getargs().timed_only==False:
        return list(filter(lambda x:not x.expires,media))
    elif args_.getargs().timed_only==True:
        return list(filter(lambda x:x.expires,media))
    return media
def post_user_filter(media):
    userfilter=args_.getargs().filter
    if not userfilter.islower():
        return list(filter(lambda x:re.search(userfilter,x.text or "")!=None,media))
    else:
        return list(filter(lambda x:re.search(userfilter,x.text or "",re.IGNORECASE)!=None,media))

def anti_post_user_filter(media):
    userfilter=args_.getargs().neg_filter
    if not userfilter.islower():
        return list(filter(lambda x:re.search(userfilter,x.text or "")==None,media)) if userfilter else media
    else:
        return list(filter(lambda x:re.search(userfilter,x.text or "",re.IGNORECASE)==None,media)) if userfilter else media



def download_type_filter(media):
    if args_.getargs().download_type==None:
        return media
    elif args_.getargs().download_type=="protected":
        return list(filter(lambda x:x.mpd!=None,media))  
    elif args_.getargs().download_type=="normal":
        return list(filter(lambda x:x.url!=None,media))


def mass_msg_filter(media):
    if args_.getargs().mass_msg==None:
        return media
    elif args_.getargs().mass_msg==True:
        return list((filter(lambda x:x.mass==True,media)))
    elif args_.getargs().mass_msg==False:
        return list((filter(lambda x:x.mass==False,media)))