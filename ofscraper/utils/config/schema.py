import ofscraper.utils.config.data as data
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths


def get_current_config_schema(config: dict = None) -> dict:
    if isinstance(config, dict) and config.get("config"):
        config = config["config"]
    new_config = {
        (
            "main_profile" if config is False else of_env.getattr("mainProfile")
        ): data.get_main_profile(config=config),
        "metadata": data.get_metadata(config=config),
        "discord": data.get_discord(config=config),
        "file_options": {
            "save_location": common_paths.get_save_location(config=config),
            "dir_format": data.get_dirformat(config=config),
            "file_format": data.get_fileformat(config=config),
            "textlength": data.get_textlength(config=config),
            "space_replacer": data.get_spacereplacer(config=config),
            "date": data.get_date(config=config),
            "text_type_default": data.get_textType(config=config),
            "truncation_default": data.get_truncation(config=config),
        },
        "download_options": {
            "filter": data.get_filter(config=config),
            "auto_resume": data.get_part_file_clean(config=config),
            "system_free_min": data.get_system_freesize(config=config),
            "max_post_count": data.get_max_post_count(config=config),
        },
        "binary_options": {
            "ffmpeg": data.get_ffmpeg(config=config),
        },
        "cdm_options": {
            "private-key": data.get_private_key(config=config),
            "client-id": data.get_client_id(config=config),
            "key-mode-default": data.get_key_mode(config=config),
        },
        "performance_options": {
            "download_sems": data.get_download_semaphores(config=config),
            "download_limit": data.get_download_limit(config=config),
        },
        "content_filter_options": {
            "block_ads": data.get_block_ads(config=config),
            "file_size_max": data.get_filesize_max(config=config),
            "file_size_min": data.get_filesize_min(config=config),
            "length_max": data.get_max_length(config=config),
            "length_min": data.get_min_length(config=config),
        },
        "advanced_options": {
            "dynamic-mode-default": data.get_dynamic(config=config),
            "downloadbars": data.get_show_downloadprogress(config=config),
            "cache-mode": data.cache_mode_helper(config=config),
            "rotate_logs": data.get_rotate_logs(config=config),
            "sanitize_text": data.get_sanitizeDB(config=config),
            "temp_dir": data.get_TempDir(config=config),
            "remove_hash_match": data.get_hash(config=config),
            "infinite_loop_action_mode": data.get_InfiniteLoop(config=config),
            "enable_auto_after": data.get_enable_after(config=config),
            "default_user_list": data.get_default_userlist(config=config),
            "default_black_list": data.get_default_blacklist(config=config),
            "logs_expire_time": data.get_logs_expire(config=config),
            "ssl_verify": data.get_ssl_verify(config=config),
            "env_files": data.get_env_files(config=config),
        },
        "script_options": {
            "after_action_script": data.get_after_action_script(config=config),
            "post_script": data.get_post_script(config=config),
            "naming_script": data.get_naming_script(config=config),
            "after_download_script": data.get_after_download_script(config=config),
            "skip_download_script": data.get_skip_download_script(config=config),
        },
        "responsetype": {
            "timeline": data.get_timeline_responsetype(config=config),
            "message": data.get_messages_progress_responsetype(config=config),
            "archived": data.get_archived_responsetype(config=config),
            "paid": data.get_paid_responsetype(config=config),
            "stories": data.get_stories_responsetype(config=config),
            "highlights": data.get_highlights_responsetype(config=config),
            "profile": data.get_profile_responsetype(config=config),
            "pinned": data.get_pinned_responsetype(config=config),
            "streams": data.get_streams_responsetype(config=config),
        },
    }
    return new_config


# basic recursion for comparing nested keys
def config_diff(config):
    if config is None:
        return True
    if config.get("config"):
        config = config["config"]
    schema = get_current_config_schema()
    return _config_diff_helper(config, schema)


def _config_diff_helper(config, schema):
    # Check for keys in schema but missing in config
    if set(schema.keys()) - set(config.keys()):
        return True

    # Check for keys in config but missing in schema
    if set(config.keys()) - set(schema.keys()):
        return True

    for key, schema_value in schema.items():
        if key in config:
            config_value = config[key]
            if isinstance(schema_value, dict):
                if not isinstance(config_value, dict):
                    return True
                if _config_diff_helper(config_value, schema_value):
                    return True
            elif schema_value != config_value:  # Simple value comparison
                return True
        # Keys missing from config are already handled above

    return False
