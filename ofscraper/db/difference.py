from ofscraper.db.operations_.others import get_schema_changes


groupA = [
    "media_hash",
    "media_model_id",
    "posts_model_id",
    "posts_pinned",
    "products_model_id",
    "other_model_id",
    "stories_model_id",
    "messages_model_id",
    "labels_model_id",
    "media_posted_at",
    "media_unlocked",
    "media_duration",
    "posts_stream",
    "posts_opened",
    "posts_is_deleted",
    "messages_is_deleted",
    "posts_purchase_type",
    "posts_mentions",
    "messages_group_id",
    "media_skip_permanent",
    "profiles_seen_at",
]

groupB = [
    "profile_username_constraint_modified",
    "stories_model_id_constraint_added",
    "labels_model_id_constraint_added",
    "posts_model_id_constraint_added",
    "others_model_id_constraint_added",
    "products_model_id_constraint_added",
    "messages_model_id_constraint_added",
    "media_post_id_constraint_added",
    "media_bool_changes",
]

# one-time data repairs, run after the schema changes
groupC = [
    "media_size_skip_repaired",
]

# every upgrade step this build knows. A SQLite file records the ones it has
# had; PostgreSQL's tables are made with all of them done
ALL_FLAGS = frozenset(groupA + groupB + groupC)


def get_group_difference(model_id=None, username=None, db_path=None):
    changes = get_schema_changes(model_id=model_id, username=username, db_path=db_path)
    return set(ALL_FLAGS).difference(set(changes))
