import ofscraper.utils.config.custom as custom
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths


def get_current_config_schema(config: dict = None) -> dict:
    new_config = {
        "config": {
            constants.getattr("mainProfile"): data.get_main_profile(config),
            "metadata": data.get_metadata(config),
            "discord": data.get_discord(config),
            "file_options": {
                "save_location": common_paths.get_save_location(config),
                "dir_format": data.get_dirformat(config),
                "file_format": data.get_fileformat(config),
                "textlength": data.get_textlength(config),
                "space-replacer": data.get_spacereplacer(config),
                "date": data.get_date(config),
                "text_type_default": data.get_textType(config),
                "truncation_default": data.get_truncation(config),
            },
            "download_options": {
                "file_size_limit": data.get_filesize_limit(config),
                "file_size_min": data.get_filesize_min(config),
                "filter": data.get_filter(config),
                "auto_resume": data.get_part_file_clean(config),
                "system_free_min": data.get_system_freesize(config),
            },
            "binary_options": {
                "mp4decrypt": data.get_mp4decrypt(config),
                "ffmpeg": data.get_ffmpeg(config),
            },
            "cdm_options": {
                "private-key": data.get_private_key(config),
                "client-id": data.get_client_id(config),
                "key-mode-default": data.get_key_mode(config),
                "keydb_api": data.get_keydb_api(config),
            },
            "performance_options": {
                "download-sems": data.get_download_semaphores(config),
                "threads": data.get_threads(config),
            },
            "advanced_options": {
                "code-execution": data.get_allow_code_execution(config),
                "dynamic-mode-default": data.get_dynamic(config),
                "backend": data.get_backend(config),
                "downloadbars": data.get_show_downloadprogress(config),
                "cache-mode": data.cache_mode_helper(config),
                "appendlog": data.get_appendlog(config),
                "custom_values": custom.get_custom(),
                "sanitize_text": data.get_sanitizeDB(config),
                "temp_dir": data.get_TempDir(config),
                "infinite_loop": data.get_InfiniteLoop(config),
            },
            "responsetype": {
                "timeline": data.get_timeline_responsetype(config),
                "message": data.get_messages_responsetype(config),
                "archived": data.get_archived_responsetype(config),
                "paid": data.get_paid_responsetype(config),
                "stories": data.get_stories_responsetype(config),
                "highlights": data.get_highlights_responsetype(config),
                "profile": data.get_profile_responsetype(config),
                "pinned": data.get_pinned_responsetype(config),
            },
        }
    }
    return new_config


# basic recursion for comparing nested keys
def config_diff(config, schema=None):
    if config == None:
        return True
    schema = schema or get_current_config_schema()["config"]
    diff = set(schema.keys()) - set(config.keys())
    if len(diff) > 0:
        return True
    for key in schema.keys():
        if not isinstance(schema[key], dict):
            continue
        elif not isinstance(config[key], dict):
            return True
        elif config_diff(config[key], schema[key]):
            return True
