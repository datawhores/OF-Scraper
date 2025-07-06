import logging
from typing import Dict, List, Set
from enum import Enum, auto




log = logging.getLogger("shared")



class EActivity(Enum):
    """Defines all possible processing activities."""

    # A top-level activity
    SCRAPE_PAID = auto()

    # A nested enum for a group of related sub-activities
    class ScrapeActivity(Enum):
        LIKE = auto()
        UNLIKE = auto()
        DOWNLOAD = auto()

def _get_all_enum_members(enum_class):
    """
    Recursively finds all members in an enum, including nested enums.
    """
    for member in enum_class:
        # Check if the member's value is another Enum class
        if isinstance(member.value, type) and issubclass(member.value, Enum):
            # If so, recursively yield from it
            yield from _get_all_enum_members(member.value)
        else:
            # Otherwise, it's a regular member
            yield member
class StateManager:
    """
    Manages the processing state for different activities.
    This class tracks what is in an activity's queue and what has been completed.
    """

    def __init__(self):
        """Initializes the manager with all defined activities."""
        # Create a flat list of all enum members
        all_activities = list(_get_all_enum_members(EActivity))
    
        # Use the flat list to build the queues dictionary
        self._queues: Dict[EActivity, Dict[str, Set[str]]] = {
            activity: {"queued": [], "processed": set()} for activity in all_activities
        }
    def set_queue(self, activity: EActivity, usernames: List[str]):
        """
        Sets the entire queue for a given activity, preserving order.
        This resets any previous progress for that activity.
        """
        # Directly assign the list to preserve its order
        self._queues[activity]["queued"] = list(usernames)
        self._queues[activity]["processed"] = set() # Reset progress
        log.info(f"Queued {len(usernames)} users for the {activity.name} activity in their original order.")
    def add_to_queue(self, activity: EActivity, usernames: List[str]):
        """
        Adds new, unique usernames to an existing activity queue, preserving order.
        Does not reset progress.
        """
        # Get the existing queue and a set of its users for fast lookups
        current_queue = self._queues[activity]["queued"]
        existing_users = set(current_queue)
        
        added_count = 0
        for user in usernames:
            if user not in existing_users:
                current_queue.append(user)
                existing_users.add(user)
                added_count += 1
                
        if added_count > 0:
            log.info(f"Added {added_count} new, unique users to the {activity.name} queue.")

    def get_unprocessed(self, activity: EActivity) -> List[str]:
        """
        Returns an ordered list of users who are still queued but not yet processed.
        """
        queued = self._queues[activity]["queued"]
        processed = self._queues[activity]["processed"]
        # Return a new list preserving the original order
        return [user for user in queued if user not in processed]

    def get_all_queued_usernames(self) -> List[str]:
        """
        Returns a single list of all unique usernames currently in any activity queue,
        preserving the order of first appearance.
        """
        all_usernames_ordered = []
        seen = set()
        for activity in self._queues:
            for username in self._queues[activity]["queued"]:
                if username not in seen:
                    all_usernames_ordered.append(username)
                    seen.add(username)
        return all_usernames_ordered

    
    def get_queued_usernames(self, activity: EActivity = None) -> List[str]:
        """
        Returns an ordered list of unique usernames for a given activity.
        If no activity is provided, it returns a combined list of all users
        queue
        """
        all_usernames_ordered = []
        seen = set()

        # The new default logic
        if activity is None:
            # Loop through all nested ScrapeActivity members
            for sub_activity in EActivity.ScrapeActivity:
                for username in self._queues[sub_activity]["queued"]:
                    if username not in seen:
                        all_usernames_ordered.append(username)
                        seen.add(username)
        # The existing logic for a specific activity
        elif activity in self._queues:
            # This just returns the original list, already ordered and unique
            return self._queues[activity]["queued"]

        return all_usernames_ordered
    
    def mark_as_processed(self, username: str, activity: EActivity):
        """Marks a single user as processed for a given activity."""
        if username in self._queues[activity]["queued"]:
            self._queues[activity]["processed"].add(username)

    def get_processed(self, activity: EActivity) -> Set[str]:
        """Returns the set of users who have been processed for a given activity."""
        return self._queues[activity]["processed"]

    def reset_processed_status(self, activity: EActivity) -> None:
        """
        Resets the processed status for a single activity.
        All users in the queue for this activity will be marked as unprocessed.
        """
        if activity in self._queues:
            self._queues[activity]["processed"].clear()
            log.info(f"Processed status for {activity.name} has been reset.")

    def reset_all_processed_status(self) -> None:
        """
        Resets the processed status for ALL activities.
        """
        for activity in self._queues:
            self._queues[activity]["processed"].clear()
        log.info("Processed status for all activities has been reset.")

# The map remains the same
ACTIVITY_MAP = {
    "scrape_paid": EActivity.SCRAPE_PAID,
    "like": EActivity.ScrapeActivity.value.LIKE,
    "unlike": EActivity.ScrapeActivity.value.UNLIKE,
    "download": EActivity.ScrapeActivity.value.DOWNLOAD
}

def string_to_activity(s: str) -> EActivity:
    """
    Converts a single string to an EActivity enum member.

    Raises:
        ValueError: If the string is not a valid activity.
    """
    activity = ACTIVITY_MAP.get(s.lower())
    if not activity:
        raise ValueError(f"'{s}' is not a valid activity. Options are: {list(ACTIVITY_MAP.keys())}")
    return activity
