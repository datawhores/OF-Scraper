from ofscraper.db.operations_.others import get_schema_changes


def get_group_difference(model_id=None, username=None, db_path=None):

    changes = get_schema_changes(model_id=model_id, username=username, db_path=db_path)
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
    return set((groupA + groupB)).difference(set(changes))
