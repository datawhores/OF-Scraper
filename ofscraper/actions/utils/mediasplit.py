import platform
import more_itertools
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system


platform_name = platform.system()


def get_mediasplits(medialist):
    user_count = settings.get_threads()
    final_count = max(min(user_count, system.getcpu_count(), len(medialist) // 20), 1)
    return more_itertools.divide(final_count, medialist)
