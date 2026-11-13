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

EXTRA_COLUMNS = {"post_media_count", "responsetype", "price", "post_id", "media_id"}


def get_col_names(show_extra=True):
    for ele in col_names:
        if show_extra or ele.lower() not in EXTRA_COLUMNS:
            yield ele.lower()


def get_input_names():
    for ele in [*col_names, *input_only_names]:
        yield ele.lower()
