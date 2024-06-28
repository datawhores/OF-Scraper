def post_datesorter(output):
    return list(sorted(output, key=lambda x: x.date, reverse=True))
