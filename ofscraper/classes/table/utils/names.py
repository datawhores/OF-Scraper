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


def get_col_names():
    for ele in col_names:
        yield ele.lower()


def get_input_names():
    for ele in [*col_names, *input_only_names]:
        yield ele.lower()
