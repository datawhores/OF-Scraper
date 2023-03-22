r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""


def separate_by_id(urls: list, media_ids: list) -> list:
    filtered_urls = []
    for url in urls:
        try:
            if url[2] not in media_ids:
                filtered_urls.append(url)
        except IndexError:
            filtered_urls.append(url)

    return filtered_urls


def separate_database_results_by_id(results: list, media_ids: list) -> list:
    filtered_results = [r for r in results if r[0] not in media_ids]
    return filtered_results
