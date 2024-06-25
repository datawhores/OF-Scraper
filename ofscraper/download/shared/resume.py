def get_resume_header(resume_size,total):
    return None if not resume_size or not total else {"Range": f"bytes={resume_size}-{total}"}