import argparse
import sys
import re
import arrow
import pathlib
from humanfriendly import parse_size
from ofscraper.__version__ import __version__ 
import ofscraper.constants as constants
args=None
def create_parser(input=None):
    parent_parser=argparse.ArgumentParser(add_help=False)
    general=parent_parser.add_argument_group("Program",description="Program Args")  
    general.add_argument('-v', '--version', action='version', version=__version__ ,default=__version__)
    general.add_argument(
        '-cg', '--config', help="Change location of config folder/file",default=None
    )
    general.add_argument(
        '-r', '--profile', help="Change which profile you want to use\nIf not set then the config file is used\nProfiles are always within the config file parent directory",default=None,type=lambda x:f"{re.sub('_profile','', x)}_profile"
    )
    output=parent_parser.add_argument_group("Logging",description="Arguments for output controls")  

    output.add_argument(
        '-l', '--log', help = 'set log file level', type=str.upper,default="OFF",choices=["OFF","STATS","LOW","NORMAL","DEBUG","TRACE"]
    ),
    output.add_argument(
        '-dc', '--discord', help = 'set discord log level', type=str.upper,default="OFF",choices=["OFF","STATS","LOW","NORMAL","DEBUG","TRACE"]
    )

    output.add_argument(
        '-p', '--output', help = 'set console output log level', type=str.upper,default="NORMAL",choices=["PROMPT","STATS","LOW","NORMAL","DEBUG","TRACE"]
    )
  


    parser = argparse.ArgumentParser(add_help=False,parents=[parent_parser],prog="OF-Scraper")  
    parser.add_argument( '-h', '--help', action='help')
    scraper=parser.add_argument_group("scraper",description="General Arguments for scraper")                                
    scraper.add_argument(
        '-u', '--username', help="select which username to process (name,name2)\nSet to ALL for all users",type=username_helper,action="extend"
    )
    scraper.add_argument(
        '-eu', '--excluded-username', help="select which usernames to exclude  (name,name2)\nThis has preference over --username",type=username_helper,action="extend"
    )
  
    scraper.add_argument(
        '-d', '--daemon', help='run script in the background\nSet value to minimum minutes between script runs\nOverdue runs will run as soon as previous run finishes', type=int,default=None
    )

    scraper.add_argument(
        '-g', '--original', help = 'don\'t truncate long paths', default=False,action="store_true"
    )
    scraper.add_argument("-c","--letter-count",action="store_true",default=False,help="intrepret config 'textlength' as max length by letter")
    scraper.add_argument("-a","--action",default=None,help="perform like or unlike action on each post",choices=["like","unlike"])


    post=parser.add_argument_group("Post",description="What type of post to scrape")                                      

    post.add_argument("-e","--dupe",action="store_true",default=False,help="Bypass the dupe check and redownload all files")
    post.add_argument(
        '-o', '--posts', help = 'Download specified content from a model',default=[],required=False,type = posttype_helper,action='extend'
    )

    post.add_argument(
        '-eo', '--excluded-posts', help = 'Don\'t Download specified content from a model. Has preference over all',default=[],required=False,type = exposttype_helper,action='extend'
    )

    post.add_argument(
        '-ft', '--filter', help = 'Filter post to where the provided regex True\nNote if you include any uppercase characters the search will be case-sensitive',default=".*",required=False,type = str
    )


    post.add_argument(
        '-nf', '--neg-filter', help = 'Filter post by provide regex is False\nNote if you include any uppercase characters the search will be case-sensitive',default=None,required=False,type = str
    )
    post.add_argument(
        '-sp', '--scrape-paid', help = 'scrape the entire paid page for content. This can take a very long time',default=False,required=False,action="store_true"
    )

    post.add_argument(
        '-dt', '--download-type', help = 'Filter to what type of download you want None==Both, protected=Files that need mp4decrpyt',default=None,required=False,type=str.lower,choices=["protected","normal"]
    )

    post.add_argument(
        '-lb', '--label', help = 'Filter by label',default=None,required=False,type=label_helper,action="extend"
    )
    post.add_argument(
        '-be', '--before', help = 'Process post at or before the given date general synax is Month/Day/Year\nWorks for like,unlike, and downloading posts',type=arrow_helper)
    post.add_argument(
        '-af', '--after', help = 'Process post at or after the given date Month/Day/Year\nnWorks for like,unlike, and downloading posts',type=arrow_helper)
    post.add_argument(
        '-mt', '--mediatype', help = 'Filter by media',default=[],required=False,type = mediatype_helper,action='extend')
   
    post.add_argument(
        '-sx', '--size-max', help = 'Filter out files greater then given size supported inputs include int in bytes or human-readable such as 10mb',required=False,type = parse_size)
    post.add_argument(
        '-sm', '--size-min', help = 'Filter out files greater smaller then the given size bytes or human-readable such as 10mb',required=False,type =parse_size)
    
    #mutual exclusive groups
    group1=post.add_mutually_exclusive_group()
    
    group1.add_argument(
        '-mm', '--mass-only', help = 'download mass messages only',default=None,required=False,action="store_const",dest='mass_msg',const=True
    )

    group1.add_argument(
        '-ms', '--mass-skip', help = 'skip mass messages',default=None,required=False,action="store_const",dest='mass_msg',const=False
    )
    group2=post.add_mutually_exclusive_group()
    group2.add_argument("-sk","--skip-timed",default=None,help="skip promotional or temporary post",action="store_const",const=False,dest="timed_only")
    group2.add_argument("-ok","--only-timed",default=None,help="skip promotional or temporary post",action="store_const",const=True,dest="timed_only")

    
     #Filters for accounts
    filters=parser.add_argument_group("filters",description="Filters out usernames based on selected parameters")
    
    filters.add_argument(
        '-at', '--account-type', help = 'Filter Free or paid accounts\npaid and free correspond to your original price, and not the renewal price',default=None,required=False,type = str.lower,choices=["paid","free"]
    )
    filters.add_argument(
        '-rw', '--renewal', help = 'Filter by whether renewal is on or off for account',default=None,required=False,type = str.lower,choices=["active","disabled"]
    )
    filters.add_argument(
        '-ss', '--sub-status', help = 'Filter by whether or not your subscription has expired or not',default=None,required=False,type = str.lower,choices=["active","expired"]
    )

    filters.add_argument(
        '-ul', '--user-list', help = 'Filter by userlist\n Note:  the lists "ofscraper.main,ofscraper.expired,ofscraper.active" are reserved  and should not be the name of any list you have on OF',default=[],required=False,type = lambda x:x.split(","),action='extend'
    )
    
    filters.add_argument(
        '-bl', '--black-list', help = 'Remove all users from selected list\n Note: the list "ofscraper.main,ofscraper.expired,ofscraper.active" are reserved should not be the name of any list you have on OF',default=[],required=False,type = lambda x:x.split(","),action='extend'
    )
    
    
    sort=parser.add_argument_group("sort",description="Options on how to sort list")
    sort.add_argument(
        '-st', '--sort', help = 'What to sort the model list by',default="Name",choices=["name","subscribed","expiring","price"],type=str.lower)
    sort.add_argument(
        '-ds', '--desc', help = 'Sort the model list in descending order',action="store_true",default=False) 
    
    advanced=parser.add_argument_group("Advanced",description="Advanced Args")  
    advanced.add_argument(
        '-uf', '--users-first', help = 'Scrape all users first rather then one at a time. This only effects downloading posts',default=False,required=False,action="store_true"
    )
    advanced.add_argument(
        '-nc', '--no-cache', help = 'disable cache',default=False,required=False,action="store_true"
    )
    advanced.add_argument(
        '-k', '--key-mode', help = 'key mode override',default=None,required=False,choices=constants.KEY_OPTIONS,type=str.lower)
    advanced.add_argument(
        '-dr', '--dynamic-rules', help = 'Dynamic signing',default=None,required=False,choices=["dc","deviint"],type=str.lower)
    advanced.add_argument(
        '-pc', '--part-cleanup', help = 'Cleanup temp .part files\nNote this removes the ability to resume from downloads',default=False,action="store_true")

    advanced.add_argument(
        '-db', '--downloadbars', help = 'show individual download progress bars',default=False,action="store_true")

    advanced.add_argument('-sd', '--downloadsems', help = 'Number of sems or concurrent downloads per thread',default=None,type=int)

    advanced.add_argument('-dp', '--downloadthreads', help = 'Number threads to use minimum will always be 1, Maximmum will never be higher then max availible-1',default=None,type=int)
    
    
    
    subparser=parser.add_subparsers(help="commands",dest="command")
    post_check=subparser.add_parser("post_check",help="Display a generated table of data with information about models post(s)\nCache lasts for 24 hours",parents=[parent_parser])


    post_check.add_argument("-u","--url",
    help = 'Scan posts via url',default=None,required=False,type = check_strhelper,action='extend'
    )


    post_check.add_argument("-f","--file",
    help = 'Scan posts via file\nWith line seperated URL(s)',default=None,required=False,type = check_filehelper
    )
    
    post_check.add_argument(
        '-fo', '--force', help = 'force retrieval of new posts info from API', default=False,action="store_true"
    )

    message_check=subparser.add_parser("msg_check",help="Display a generated table of data with information about models messages\nCache lasts for 24 hours",parents=[parent_parser])
    message_check.add_argument(
        '-fo', '--force', help = 'force retrieval of new messages info from API', default=False,action="store_true"
    )
    message_check.add_argument("-f","--file",
    help = 'Scan messages via file\nWith line seperated URL(s)',default=None,required=False,type = check_filehelper
    )
    

    message_check.add_argument("-u","--url",
    help = 'scan messages via file',type = check_strhelper,action="extend")
 

    paid_check=subparser.add_parser("paid_check",help="Display a generated table of data with information purchashes from model\nCache last for 24 hours",parents=[parent_parser])
    paid_check.add_argument(
        '-fo', '--force', help = 'force retrieval of new purchases info from API', default=False,action="store_true"
    )
    paid_check.add_argument("-f","--file",
    help = 'Scan purchases via file\nWith line seperated usernames(s)',default=None,required=False,type = check_filehelper
    )
    

    paid_check.add_argument("-u","--username",
    help = 'Scan purchases via usernames',type = check_strhelper,action="extend")




    story_check=subparser.add_parser("story_check",help="Parse Stories/Highlights sent from a user\nCache last for 24 hours",parents=[parent_parser])
    story_check.add_argument(
        '-fo', '--force', help = 'force retrieval of new posts info from API', default=False,action="store_true"
    )
    story_check.add_argument("-f","--file",
    help = 'Scan mevia file',default=None,required=False,type = check_filehelper
    )
    

    story_check.add_argument("-u","--username",
    help = 'link to conversation',type = check_strhelper,action="extend")

    manual=subparser.add_parser("manual",help="Manually download content via url or ID",parents=[parent_parser])
    manual.add_argument("-f","--file",
    help = 'Pass links/IDs to download via file',default=None,required=False,type = check_filehelper
    )
    manual.add_argument("-u","--url",
    help = 'pass links to download via url',type = check_strhelper,action="extend")

    return parser
  
    

def getargs(input=None):
    global args
    if args and input==None:
        return args
    if "pytest" in sys.modules and input==None:
        input=[]
    elif input==None:
        input=sys.argv[1:]


    parser=create_parser(input)

    args=parser.parse_args(input)
 

    #fix args
    args.posts=list(set(args.posts or []))
    args.excluded_post=list(set(args.excluded_posts or []))
    args.username=set(args.username or [])
    args.excluded_username=set( args.excluded_username or [])
    args.label=set(args.label) if args.label else args.label
    args.black_list=set(list(map(lambda x:x.lower(),args.black_list)))
    if len(args.user_list)==0:args.user_list={constants.OFSCRAPER_RESERVED_LIST}
    else:args.user_list=set(list(map(lambda x:x.lower(),args.user_list)))

    


    if args.command in set(["post_check","msg_check"])and not (args.url or args.file):
        raise argparse.ArgumentTypeError("error: argument missing --url or --file must be specified )")
    elif args.command in set(["story_check","paid_check"])and not (args.username or args.file):
        raise argparse.ArgumentTypeError("error: argument missing --username or --file must be specified )")
    elif args.command in set(["manual"])and not (args.url or args.file):
        raise argparse.ArgumentTypeError("error: argument missing --url or --file must be specified )")
    return args




def check_strhelper(x):
    temp=None
    if isinstance(x,list):
        temp=x
    elif isinstance(x,str):
        temp=x.split(",")
    return temp

def check_filehelper(x):
    if isinstance(x,str) and pathlib.Path(x).exists():
        with open(x,"r") as _:
           return _.readlines()

   
    
def posttype_helper(x):
    choices=set(["Highlights","All","Archived","Messages","Timeline","Pinned","Stories","Purchased","Profile","Labels","Skip"])
    if isinstance(x,str):
        x=x.split(',')
        x=list(map(lambda x:x.capitalize() ,x))
    if len(list(filter(lambda y: y not in choices,x)))>0:
        raise argparse.ArgumentTypeError("error: argument -o/--posts: invalid choice: (choose from 'highlights', 'all', 'archived', 'messages', 'timeline', 'pinned', 'stories', 'purchased','profile','labels','skip')")
    return x

def exposttype_helper(x):
    choices=set(["Highlights","Archived","Messages","Timeline","Pinned","Stories","Purchased","Profile","Labels"])
    if isinstance(x,str):
        x=x.split(',')
        x=list(map(lambda x:x.capitalize() ,x))
    if len(list(filter(lambda y: y not in choices,x)))>0:
        raise argparse.ArgumentTypeError("error: argument -o/--posts: invalid choice: (choose from 'highlights', 'archived', 'messages', 'timeline', 'pinned', 'stories', 'purchased','profile','labels')")
    return x

def mediatype_helper(x):
    choices=set(["Videos","Audio","Images"])
    if isinstance(x,str):
        x=x.split(',')
        x=list(map(lambda x:x.capitalize() ,x))
    if len(list(filter(lambda y: y not in choices,x)))>0:
        raise argparse.ArgumentTypeError("error: argument -o/--mediatype: invalid choice: (choose from 'images','audio','videos')")
    return x
def changeargs(newargs):
    global args
    args=newargs


def username_helper(x):
    temp=None
    if isinstance(x,list):
        temp=x
    elif isinstance(x,str):
        temp=x.split(",")
    
    return list(map(lambda x: x.lower() if not x=="ALL" else x,temp))
def label_helper(x):
    temp=None
    if isinstance(x,list):
        temp=x
    elif isinstance(x,str):
        temp=x.split(",")
    return list(map(lambda x:x.lower(),temp))

def arrow_helper(x):
    print(x)
    try:
        return arrow.get(x)
    except arrow.parser.ParserError as E:
        try:
            x=re.sub("\\byear\\b","years",x)
            x=re.sub("\\bday\\b","days",x)
            x=re.sub("\\bmonth\\b","months",x)
            x=re.sub("\\bweek\\b","weeks",x)
            print(x)
            arw=arrow.utcnow()
            return arw.dehumanize(x)
        except ValueError as E:
             raise E


