import argparse
from src.__version__ import  __version__
import sys
def getargs(input=None):
    global args
    if args and input==None:
        return args
    if input==None:
        input=sys.argv[1:]

    parser = argparse.ArgumentParser()

    parser = argparse.ArgumentParser(add_help=False)   
    general=parser.add_argument_group("General",description="General Args")  
    general.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    general.add_argument('-h', '--help', action='help')

                                    
    general.add_argument(
        '-u', '--username', help="select which username to process (name,name2)\nSet to ALL for all users",type=lambda x: list(filter( lambda y:y!="",x.split(",")))
    )
    general.add_argument(
        '-d', '--daemon', help='run script in the background\nSet value to minimum minutes between script runs\nOverdue runs will run as soon as previous run finishes', type=int,default=None
    )
    general.add_argument(
        '-s', '--silent', help = 'mute output', action = 'store_true',default=False
    )
    general.add_argument(
        '-l', '--log', help = 'set log level', type=str.upper,default=None,choices=["OFF","INFO","DEBUG"]
    )
    post=parser.add_argument_group("Post",description="What type of post to scrape")                                      

    post.add_argument("-e","--dupe",action="store_true",default=False,help="Bypass the dupe check and redownload all files")
    post.add_argument(
        '-o', '--posts', help = 'Download content from a models wall',default=None,required=False,type = str.lower,choices=["highlights","all","archived","messages","timeline","pinned","stories","purchased",],action='append'
    )
    post.add_argument("-c","--letter-count",action="store_true",default=False,help="intrepret config 'textlength' as max length by letter")
    post.add_argument("-a","--action",default=None,help="perform like or unlike action on each post",choices=["like","unlike"])
     #Filters for accounts
    filters=parser.add_argument_group("filters",description="Filters out usernames based on selected parameters")
    
    filters.add_argument(
        '-t', '--account-type', help = 'Filter Free or paid accounts',default=None,required=False,type = str.lower,choices=["paid","free"]
    )
    filters.add_argument(
        '-r', '--renewal', help = 'Filter by whether renewal is on or off for account',default=None,required=False,type = str.lower,choices=["active","disabled"]
    )
    filters.add_argument(
        '-ss', '--sub-status', help = 'Filter by whether or not your subscription has expired or not',default=None,required=False,type = str.lower,choices=["active","expired"]
    )
    
    args=parser.parse_args(input)
    return args
args=None
def changeargs(newargs):
    global args
    args=newargs
    

