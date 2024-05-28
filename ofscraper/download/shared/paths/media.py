def content_type_missing(ele):
    if ele.mediatype.lower() == "videos":
        return "mp4"
    elif ele.mediatype.lower() == "images":
        return "jpg"
    elif ele.mediatype.lower() == "audios":
        return "mp3"


def add_path(pathObj, ele):
    ele.media["final_path"] = str(pathObj.trunicated_filepath)
