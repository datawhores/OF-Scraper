col_names = (
    "Number",
    "Download_Cart",
    "UserName",
    "Downloaded",
    "Unlocked",
    "Download_Type",
    "other_posts_with_media",
    "Length",
    "Mediatype",
    "Post_Date",
    "Post_Media_Count",
    "Responsetype",
    "Price",
    "Post_ID",
    "Media_ID",
    "Text",
)

input_only_names = ("num_per_page", "page")

PINNED_COLUMNS = ("number", "download_cart")
EXTRA_COLUMNS = {"post_media_count", "responsetype", "price", "post_id", "media_id"}


def get_col_names(show_extra=True):
    for ele in col_names:
        if show_extra or ele.lower() not in EXTRA_COLUMNS:
            yield ele.lower()


def get_input_names():
    for ele in [*col_names, *input_only_names]:
        yield ele.lower()


post_col_names = (
    "Number",
    "Download_Cart",
    "UserName",
    "Unlocked",
    "Total_Cost",
    "Total_Media",
    "New_Media",
    "Photos",
    "New_Photos",
    "Videos",
    "New_Videos",
    "Audios",
    "New_Audios",
    "Video_Length",
    "New_Video_Length",
    "Audio_Length",
    "New_Audio_Length",
    "Cost_Per_Vid_Sec",
    "New_Cost_Per_Vid_Sec",
    "Cost_Per_Photo",
    "New_Cost_Per_Photo",
    "Cost_Per_Audio",
    "New_Cost_Per_Audio",
    "Cost_Per_Audio_Sec",
    "New_Cost_Per_Audio_Sec",
    "Cost_Per_Media",
    "New_Cost_Per_Media",
    "Shared_Bundles",
    "Responsetype",
    "Post_Date",
    "Post_ID",
    "Text",
)

POST_EXTRA_COLUMNS = {
    "audios",
    "new_audios",
    "audio_length",
    "new_audio_length",
    "cost_per_audio",
    "new_cost_per_audio",
    "cost_per_audio_sec",
    "new_cost_per_audio_sec",
    "post_date",
}


def get_post_col_names(show_extra=True):
    for ele in post_col_names:
        if show_extra or ele.lower() not in POST_EXTRA_COLUMNS:
            yield ele.lower()
