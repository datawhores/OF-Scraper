import asyncio
import os
import pathlib
import time
import platform
import traceback
import random
import threading
import logging
import logging.handlers
from rich.live import Live
import more_itertools
import aioprocessing
import psutil
import ofscraper.utils.config as config_
import ofscraper.utils.paths as paths
import ofscraper.constants as constants
import ofscraper.utils.logger as logger
import ofscraper.utils.console as console
import ofscraper.utils.stdout as stdout
import ofscraper.utils.config as config_
import ofscraper.utils.args as args_
import ofscraper.utils.exit as exit
import ofscraper.classes.placeholder as placeholder
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.system as system
from ofscraper.utils.run_async import run
import ofscraper.utils.manager as manager_
from ofscraper.download.common import addGlobalDir,get_medialog,setDirectoriesDate,\
reset_globals,convert_num_bytes,setupProgressBar,subProcessVariableInit
from ofscraper.download.main_downloadbatch import main_download
from ofscraper.download.alt_downloadbatch import alt_download
import ofscraper.download.common as common


from aioprocessing import AioPipe
platform_name=platform.system()

 

def process_dicts(username,model_id,filtered_medialist):
    log=logging.getLogger("shared")
    common.log=log
    try:
        reset_globals()
        random.shuffle(filtered_medialist)
        manager=manager_.get_manager()
        mediasplits=get_mediasplits(filtered_medialist)
        num_proc=len(mediasplits)
        split_val=min(4,num_proc)
        log.debug(f"Number of process {num_proc}")
        connect_tuples=[AioPipe() for _ in range(num_proc)]
        shared=list(more_itertools.chunked([i for i in range(num_proc)],split_val))
        #shared with other process + main
        logqueues_=[ manager.Queue() for _ in range(len(shared))]
        #other logger queuesprocesses
        otherqueues_=[manager.Queue()  for _ in range(len(shared))]
        #shared cache


        
        #start stdout/main queues consumers
        log_threads=[logger.start_stdout_logthread(input_=logqueues_[i],name=f"ofscraper_{model_id}_{i+1}",count=len(shared[i])) for i in range(len(shared))]

        processes=[ aioprocessing.AioProcess(target=process_dict_starter, args=(username,model_id,mediasplits[i],logqueues_[i//split_val],otherqueues_[i//split_val],connect_tuples[i][1],args_.getargs())) for i in range(num_proc)]
        [process.start() for process in processes]
        progress_group,overall_progress,job_progress=setupProgressBar(multi=True)


       
   
        
        task1 = overall_progress.add_task(common.desc.format(p_count=common.photo_count, v_count=common.video_count,a_count=common.audio_count, 
        skipped=common.skipped,mediacount=len(filtered_medialist), sumcount=common.video_count+common.audio_count+
        common.photo_count+common.skipped,forced_skipped=common.forced_skipped,data=common.data,total=common.total_data), total=len(filtered_medialist),visible=True)
        
         #for reading completed downloads
        queue_threads=[threading.Thread(target=queue_process,args=(connect_tuples[i][0],overall_progress,job_progress,task1,len(filtered_medialist)),daemon=True) for i in range(num_proc)]
        [thread.start() for thread in queue_threads]    
        with stdout.lowstdout():
            with Live(progress_group, refresh_per_second=constants.refreshScreen,console=console.get_shared_console()):
                log.debug(f"Initial Queue Threads: {queue_threads}")
                log.debug(f"Number of initial Queue Threads: {len(queue_threads)}")
                while True: 
                    newqueue_threads=list(filter(lambda x:x.is_alive(),queue_threads))
                    if len(newqueue_threads)!=len(queue_threads):
                        log.debug(f"Remaining Queue Threads: {newqueue_threads}")
                        log.debug(f"Number of Queue Threads: {len(newqueue_threads)}")
                    if len(queue_threads)==0:break
                    queue_threads=newqueue_threads
                    for thread in queue_threads:
                        thread.join(timeout=.1)
                    time.sleep(.5)  
                log.debug(f"Intial Log Threads: {log_threads}")
                log.debug(f"Number of intial Log Threads: {len(log_threads)}")               
                while True: 
                    new_logthreads=list(filter(lambda x:x.is_alive(),log_threads))
                    if len(new_logthreads)!=len(log_threads):
                        log.debug(f"Remaining Log Threads: {new_logthreads}")
                        log.debug(f"Number of Log Threads: {len(new_logthreads)}")
                    if len(new_logthreads)==0:break
                    log_threads=new_logthreads
                    for thread in log_threads:
                        thread.join(timeout=.1)                            
                    time.sleep(.5)       
        log.debug(f"Initial Processes: {processes}")
        log.debug(f"Initial Number of Processes: {len(processes)}")        
        while True:
            new_proceess=list(filter(lambda x:x.is_alive(),processes))
            if len(new_proceess)!=len(processes):
                log.debug(f"Remaining Processes: {new_proceess}")
                log.debug(f"Number of Processes: {len(new_proceess)}")
            if len(new_proceess)==0:break
            processes=new_proceess
            for process in processes:
                process.join(timeout=15)      
                if process.is_alive():process.terminate()              
            time.sleep(.5)
        overall_progress.remove_task(task1)
        progress_group.renderables[1].height=0
        setDirectoriesDate()  
    except KeyboardInterrupt as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    [process.terminate() for process in processes] 
                    manager.shutdown()
                    raise KeyboardInterrupt
            except KeyboardInterrupt:
                    with exit.DelayedKeyboardInterrupt():
                        raise E
            except:
                with exit.DelayedKeyboardInterrupt():
                    raise E
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                [process.terminate() for process in processes]
                manager.shutdown()
                raise E
        except KeyboardInterrupt:
                with exit.DelayedKeyboardInterrupt():
                    raise E
        except Exception:
            with exit.DelayedKeyboardInterrupt():
                raise E
    log.error(f'[bold]{username}[/bold] ({common.photo_count+common.audio_count+common.video_count} \
downloads total [{common.video_count} videos, {common.audio_count} audios, {common.photo_count} photos], \
{common.forced_skipped} skipped, {common.skipped} failed)' )
    return common.photo_count,common.video_count,common.audio_count,common.forced_skipped,common.skipped


def queue_process(pipe_,overall_progress,job_progress,task1,total):
    count=0
    downloadprogress=config_.get_show_downloadprogress(config_.read_config()) or args_.getargs().downloadbars
        #shared globals
  
    while True:
        if count==1 or overall_progress.tasks[task1].total==overall_progress.tasks[task1].completed:
            break
        results = pipe_.recv()
        if not isinstance(results,list):
            results=[results]

        for result in results:
            if result is None:
                count=count+1
                continue 
            if isinstance(result,dict) and not downloadprogress:
                continue
            if isinstance(result,set):
                addGlobalDir(result)
                continue
            if isinstance(result,dict):
                job_progress_helper(job_progress,result)
                continue
            media_type, num_bytes_downloaded,total_size = result
            with common.count_lock:
                common.total_bytes_downloaded=common.total_bytes_downloaded+num_bytes_downloaded
                common.total_bytes=common.total_bytes+total_size
                
                data = convert_num_bytes(common.total_bytes_downloaded)
                total_data=convert_num_bytes(common.total_bytes)
                if media_type == 'images':
                    common.photo_count += 1 

                elif media_type == 'videos':
                    common.video_count += 1
                elif media_type == 'audios':
                    common.audio_count += 1
                elif media_type == 'skipped':
                    common.skipped += 1
                elif media_type =='forced_skipped':
                    common.forced_skipped+=1
                overall_progress.update(task1,description=common.desc.format(
                        p_count=common.photo_count, v_count=common.video_count, a_count=common.audio_count,skipped=common.skipped,forced_skipped=common.forced_skipped, 
                        data=data,total=total_data,mediacount=total, sumcount=common.video_count+common.audio_count+common.photo_count+common.skipped+common.forced_skipped), 
                        refresh=True, completed=common.video_count+common.audio_count+common.photo_count+common.skipped+common.forced_skipped)     


def get_mediasplits(medialist):
    user_count=config_.get_threads(config_.read_config() or args_.getargs().downloadthreads)
    final_count=min(user_count,system.getcpu_count(), len(medialist)//5)
    if final_count==0:final_count=1
    return more_itertools.divide(final_count, medialist   )
def process_dict_starter(username,model_id,ele,p_logqueue_,p_otherqueue_,pipe_,argsCopy):
    subProcessVariableInit(argsCopy,pipe_,logger.get_shared_logger(main_=p_logqueue_,other_=p_otherqueue_,name=f"shared_{os.getpid()}"))
    setpriority()
    plat=platform.system()
    if plat=="Linux":import uvloop;asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    try:
        process_dicts_split(username,model_id,ele)
    except KeyboardInterrupt as E:
        with exit.DelayedKeyboardInterrupt():
            try:
                p_otherqueue_.put("None")
                p_logqueue_.put("None")
                pipe_.send(None)
                raise E
            except Exception as E:
                raise E
def job_progress_helper(job_progress,result):
    funct={
      "add_task"  :job_progress.add_task,
      "update":job_progress.update,
      "remove_task":job_progress.remove_task
     }.get(result.pop("type"))
    if funct:
        try: 
            with common.chunk_lock:
                funct(*result.pop("args"),**result)
        except Exception as E:
            logging.getLogger("shared").debug(E)
def setpriority():
    os_used = platform.system() 
    process = psutil.Process(os.getpid())  # Set highest priority for the python script for the CPU
    if os_used == "Windows":  # Windows (either 32-bit or 64-bit)
        process.ionice(psutil.IOPRIO_NORMAL)
        process.nice(psutil.NORMAL_PRIORITY_CLASS)

    elif os_used == "Linux":  # linux
        process.ionice(psutil.IOPRIO_CLASS_BE)
        process.nice(5) 
    else:  # MAC OS X or other
        process.nice(10) 

@run
async def process_dicts_split(username, model_id, medialist):
    common.log.debug(f"{pid_log_helper()} start inner thread for other loggers")  
    #set variables based on parent process
    #start consumer for other
    other_thread=logger.start_other_thread(input_=common.log.handlers[1].queue,name=str(os.getpid()),count=1)
    medialist=list(medialist)
    # This need to be here: https://stackoverflow.com/questions/73599594/asyncio-works-in-python-3-10-but-not-in-python-3-8

    common.log.debug(f"{pid_log_helper()} starting process")
    common.log.debug(f"{pid_log_helper()} process mediasplit from total {len(medialist)}")
 
    aws=[]
   

    async with sessionbuilder.sessionBuilder() as c:
        i=0
        for ele in medialist:
            aws.append(asyncio.create_task(download(c,ele ,model_id, username)))

        for coro in asyncio.as_completed(aws):
                try:
                    pack = await coro
                    common.log.debug(f"unpack {pack} count {len(pack)}")
                    media_type, num_bytes_downloaded=pack
                    await common.pipe.coro_send(  (media_type, num_bytes_downloaded,0))
                except Exception as e:
                    common.log.traceback(e)
                    common.log.traceback(traceback.format_exc())
                    media_type = "skipped"
                    num_bytes_downloaded = 0
                    await common.pipe.coro_send(  (media_type, num_bytes_downloaded,0))

            
    common.log.debug(f"{pid_log_helper()} download process thread closing")
    #send message directly
    await asyncio.get_event_loop().run_in_executor(common.cache_thread,common.cache.close)
    common.cache_thread.shutdown()
    common.log.handlers[0].queue.put("None")
    common.log.handlers[1].queue.put("None")
    if other_thread:other_thread.join()
    await common.pipe.coro_send(common.localDirSet)
    await common.pipe.coro_send(None)
   
 

def pid_log_helper():
    return f"PID: {os.getpid()}"  


async def download(c,ele,model_id,username):
    # reduce number of logs
    async with common.maxfile_sem:
        templog_=logger.get_shared_logger(name=str(ele.id),main_=aioprocessing.Queue(),other_=aioprocessing.Queue())
        common.innerlog.set(templog_)
        try:
                with paths.set_directory(placeholder.Placeholders().getmediadir(ele,username,model_id)):
                    if ele.url:
                        return await main_download(c,ele,pathlib.Path(".").absolute(),username,model_id)
                    elif ele.mpd:
                        return await alt_download(c,ele,pathlib.Path(".").absolute(),username,model_id)
        except Exception as e:
            common.innerlog.get().debug(f"{get_medialog(ele)} exception {e}")   
            common.innerlog.get().debug(f"{get_medialog(ele)} exception {traceback.format_exc()}")   
            # we can put into seperate otherqueue_
            return "skipped",0
        finally:
            common.log.handlers[1].queue.put(list(common.innerlog.get().handlers[1].queue.queue))
            common.log.handlers[0].queue.put(list(common.innerlog.get().handlers[0].queue.queue))


