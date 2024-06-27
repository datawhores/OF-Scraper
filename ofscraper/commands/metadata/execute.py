#runs metadata action for specific user used by normal and --userfirst
async def execute_metadata_action_on_user(*args,ele=None, media=None,**kwargs):
    username = ele.name
    model_id = ele.id
    mark_stray = read_args.retriveArgs().mark_stray
    metadata_action = read_args.retriveArgs().metadata
    active=ele.active
    log.warning(
                    f"""
                Perform Meta {metadata_action} with
                Mark Stray: {mark_stray}
                for [bold]{username}[/bold]\n[bold]
                Subscription Active:[/bold] {active}
                """
    )
    await operations.table_init_create(model_id=model_id, username=username)
    progress_utils.update_activity_task(
        description=metadata_activity_str.format(username=username)
    )
    data=await download.download_process(username, model_id, media)
    await  metadata_stray_media(username, model_id, media)
    if args.true:
        return True
    return [data]
