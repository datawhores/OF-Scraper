r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
import time
import logging
from itertools import chain
import ofscraper.prompts.prompts as prompts
import ofscraper.api.messages as messages
import ofscraper.db.operations as operations
import ofscraper.api.posts as posts_
import ofscraper.utils.args as args_
import ofscraper.api.paid as paid
import ofscraper.api.highlights as highlights
import ofscraper.api.timeline as timeline
import ofscraper.api.profile as profile
import ofscraper.utils.args as args_
import ofscraper.utils.filters as filters
import ofscraper.utils.stdout as stdout
import ofscraper.api.archive as archive
import ofscraper.api.pinned as pinned

log=logging.getLogger(__package__)
args=args_.getargs()
log.debug(args)

def process_messages(model_id,username):
    with stdout.lowstdout():
        messages_ =asyncio.run(messages.get_messages(  model_id)) 
        messages_=list(map(lambda x:posts_.Post(x,model_id,username),messages_))
        log.debug(f"[bold]Messages Media Count with locked[/bold] {sum(map(lambda x:len(x.post_media),messages_))}")
        log.debug("Removing locked messages media")
        for message in messages_:
            operations.write_messages_table(message)
        output=[]
        [ output.extend(message.media) for message in messages_]
        return list(filter(lambda x:isinstance(x,posts_.Media),output))

def process_paid_post(model_id,username):
    with stdout.lowstdout():
        paid_content=asyncio.run(paid.get_paid_posts(username,model_id))
        paid_content=list(map(lambda x:posts_.Post(x,model_id,username,responsetype="paid"),paid_content))
        log.debug(f"[bold]Paid Media Count with locked[/bold] {sum(map(lambda x:len(x.post_media),paid_content))}")
        log.debug("Removing locked paid media")
        for post in paid_content:
            operations.write_post_table(post,model_id,username)
        output=[]
        [output.extend(post.media) for post in paid_content]
        return list(filter(lambda x:isinstance(x,posts_.Media),output))

         

def process_highlights( model_id,username):
    with stdout.lowstdout():
        highlights_, stories = asyncio.run(highlights.get_highlight_post( model_id))
        highlights_, stories=list(map(lambda x:posts_.Post(x,model_id,username,responsetype="highlights"),highlights_)),\
        list(map(lambda x:posts_.Post(x,model_id,username,responsetype="stories"),stories))
        log.debug(f"[bold]Combined Story and Highlight Media count[/bold] {sum(map(lambda x:len(x.post_media), highlights_))+sum(map(lambda x:len(x.post_media), stories))}")
        for post in highlights_:
            operations.write_stories_table(post,model_id,username)
        for post in stories:
            operations.write_stories_table(post,model_id,username)   
        output=[]
        output2=[]
        [ output.extend(highlight.media) for highlight in highlights_]
        [ output2.extend(stories.media) for stories in stories]
        return list(filter(lambda x:isinstance(x,posts_.Media),output)),list(filter(lambda x:isinstance(x,posts_.Media),output2))

        






def process_timeline_posts(model_id,username):
    with stdout.lowstdout():
        timeline_posts = asyncio.run(timeline.get_timeline_post( model_id))
        timeline_posts  =list(map(lambda x:posts_.Post(x,model_id,username,"timeline"), timeline_posts ))
        log.debug(f"[bold]Timeline Media Count with locked[/bold] {sum(map(lambda x:len(x.post_media),timeline_posts))}")
        log.debug("Removing locked timeline media")
        for post in timeline_posts:
            operations.write_post_table(post,model_id,username)
        output=[]
        [output.extend(post.media) for post in  timeline_posts ]
        return list(filter(lambda x:isinstance(x,posts_.Media),output))

def process_archived_posts( model_id,username):
    with stdout.lowstdout():
        archived_posts = asyncio.run(archive.get_archived_post(model_id))
        archived_posts =list(map(lambda x:posts_.Post(x,model_id,username),archived_posts ))
        log.debug(f"[bold]Archived Media Count with locked[/bold] {sum(map(lambda x:len(x.post_media),archived_posts))}")
        log.debug("Removing locked archived media")

        for post in archived_posts:
            operations.write_post_table(post,model_id,username)
        output=[]
        [ output.extend(post.media) for post in archived_posts ]
        return list(filter(lambda x:isinstance(x,posts_.Media),output))




def process_pinned_posts( model_id,username):
    with stdout.lowstdout():
        pinned_posts = asyncio.run(pinned.get_pinned_post( model_id))
        pinned_posts =list(map(lambda x:posts_.Post(x,model_id,username,"pinned"),pinned_posts ))
        log.debug(f"[bold]Pinned Media Count with locked[/bold] {sum(map(lambda x:len(x.post_media),pinned_posts))}")
        log.debug("Removing locked pinned media")
        for post in  pinned_posts:
            operations.write_post_table(post,model_id,username)
        output=[]
        [ output.extend(post.media) for post in pinned_posts ]
        return list(filter(lambda x:isinstance(x,posts_.Media),output))

def process_profile( username) -> list:
    with stdout.lowstdout():
        user_profile = profile.scrape_profile( username)
        urls, info = profile.parse_profile(user_profile)
        profile.print_profile_info(info)       
        output=[]
        for ele in enumerate(urls):
            count=ele[0]
            data=ele[1]
            output.append(posts_.Media({"url":data["url"],"type":data["mediatype"]},count,posts_.Post(data,info[2],username,responsetype="profile")))
        avatars=list(filter(lambda x:x.filename.find('avatar')!=-1,output))
        if len(avatars)>0:
            log.warning(f"Avatar : {avatars[0].url}")
        return output

def process_all_paid():
    with stdout.lowstdout():
        paid_content=asyncio.run(paid.get_all_paid_posts())
        user_dict={}
        post_array=[]
        [user_dict.update({(ele.get("fromUser",None) or ele.get("author",None) or {} ).get("id"):user_dict.get((ele.get("fromUser",None) or ele.get("author",None) or {} ).get("id"),[])+[ele]}) for ele in paid_content]

        for model_id,value in user_dict.items():
            username=profile.scrape_profile(model_id).get("username")
            if username=="modeldeleted":
                username=operations.get_profile_info(model_id,username) or username
            log.info(f"Processing {username}_{model_id}")
            operations.create_tables(model_id,username)
            log.debug(f"Created table for {username}")
            new_posts=list(map(lambda x:posts_.Post(x,model_id,username,responsetype="paid"),value))
            post_array.extend(new_posts)
            [operations.write_post_table(post,model_id,username) for post in new_posts]
            log.debug(f"Added Paid media for {username}_{model_id}")

                     
        log.debug(f"[bold]Paid Media for all models[/bold] {sum(map(lambda x:len(x.media),post_array))}")
        output=[]
        [output.extend(post.media) for post in post_array]
        return output


def select_areas():
    if not args.scrape_paid and len( args.posts or [])==0:
          args.scrape_paid=prompts.scrape_paid_prompt()
    args.posts = list(map(lambda x:x.capitalize(),(args.posts or prompts.areas_prompt())
))

    args_.changeargs(args)
     
def process_areas(ele, model_id) -> list:
    select_areas()
    timeline_posts_dicts  = []
    pinned_post_dict=[]
    archived_posts_dicts  = []
    highlights_dicts  = []
    messages_dicts  = []
    stories_dicts=[]
    purchased_dict=[]
    pinned_post_dict=[]
    profile_dicts=[]


    username=ele['name']
    if "Skip" in args.posts:
        return []
  
    if ('Profile' in args.posts or 'All' in args.posts):
        profile_dicts  = process_profile(username)
    if ('Pinned' in args.posts or 'All' in args.posts):
            pinned_post_dict = process_pinned_posts(model_id,username)
    if ('Timeline' in args.posts or 'All' in args.posts):
            timeline_posts_dicts = process_timeline_posts( model_id,username)
    if ('Archived' in args.posts or 'All' in args.posts):
            archived_posts_dicts = process_archived_posts( model_id,username)
    if 'Messages' in args.posts or 'All' in args.posts:
            messages_dicts = process_messages( model_id,username)
    if "Purchased" in args.posts or "All" in args.posts:
            purchased_dict=process_paid_post(model_id,username)
    if ('Highlights'  in args.posts or 'Stories'  in args.posts or 'All' in args.posts):
            highlights_tuple = process_highlights( model_id,username)  
            if 'Highlights'  in args.posts:
                highlights_dicts=highlights_tuple[0]
            if 'Stories'  in args.posts:
                stories_dicts=highlights_tuple[1]   
            if 'All' in args.posts:
                highlights_dicts=highlights_tuple[0]
                stories_dicts=highlights_tuple[1]               
    return filters.filterMedia(list(chain(*[profile_dicts  , timeline_posts_dicts ,pinned_post_dict,purchased_dict,
            archived_posts_dicts , highlights_dicts , messages_dicts,stories_dicts]))

)

