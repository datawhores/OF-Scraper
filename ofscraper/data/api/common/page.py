import logging
import ofscraper.utils.of_env.of_env as of_env

log = logging.getLogger("shared")


def get_min_posts_batch(total_count, api_type):
    """
    Calculates the 'Density vs. Concurrency' sweet spot for API tasks.

    Logic:
    - Density Floor (MIN_PAGE_POST_COUNT): Prevents spawning workers for tiny
      chunks (e.g., don't spawn 50 workers for 50 posts).
    - Concurrency Cap (REASONABLE_MAX_PAGE): Limits the total number of
      concurrent tasks to prevent API rate-limiting or OOM errors.
    """
    # 1. Select the correct cap based on API type
    reasonable_max_key = "REASONABLE_MAX_PAGE"
    if str(api_type).lower() == "messages":
        reasonable_max_key = "REASONABLE_MAX_PAGE_MESSAGES"

    reasonable_max = of_env.getattr(reasonable_max_key)
    min_density_floor = of_env.getattr("MIN_PAGE_POST_COUNT")

    # 2. Perform the Sweet Spot math
    # total_count // reasonable_max calculates how many items each of the 50 workers
    # should take to stay under the concurrency cap.
    calculated_min = total_count // reasonable_max

    # 3. Apply the Density Floor
    # max() ensures that if the account is small, we prioritize worker density
    # over maximizing concurrency.
    final_min = max(calculated_min, min_density_floor)

    log.debug(
        f"[{api_type}] Pagination Density: {final_min} items per task (Total: {total_count})"
    )
    return final_min
