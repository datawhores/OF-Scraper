import ofscraper.utils.settings as settings


def get_allowed_qualities():
    qualities = {"240": 240, "720": 720, "source": 4000}
    # Get the minimum quality *name* (e.g., "240" or "source")
    min_quality_name = settings.get_settings().quality or "source"
    # Get the corresponding *numerical value* (e.g., 240 or 4000)
    min_quality_value = qualities.get(min_quality_name, 0) # Default to 0 if key not found

    # 1. Filter the qualities to get only those >= the minimum value
    #    This creates a list of (name, value) tuples, e.g., [('source', 4000), ('240', 240), ('720', 720)]
    valid_qualities = [
        (name, value) for name, value in qualities.items()
        if value >= min_quality_value
    ]
    # 2. Sort the filtered list based on the value (the second item in the tuple)
    #    e.g., [('240', 240), ('720', 720), ('source', 4000)]
    sorted_qualities = sorted(valid_qualities, key=lambda item: item[1])
    # 3. Extract just the names from the sorted list
    #    e.g., ['240', '720', 'source']
    return [name for name, value in sorted_qualities]