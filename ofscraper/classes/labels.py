import ofscraper.classes.posts as posts_


class Label:
    def __init__(self, label, model_id, username):
        self._label_id = label.get("id")
        self._name = label.get("name")
        self._type = label.get("type")
        self._posts = list(
            map(
                lambda x: posts_.Post(x, model_id, username, label=self._name),
                label.get("posts"),
            )
        )
        self._model_id = int(model_id)
        self._username = username

    @property
    def model_id(self):
        return self._model_id

    @property
    def username(self):
        return self._username

    @property
    def label_id(self):
        return self._label_id

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type

    @property
    def posts(self):
        return self._posts
