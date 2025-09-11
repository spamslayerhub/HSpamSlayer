import enum
from typing import Set

from tortoise import fields


class RedditName(fields.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=22, **kwargs)

    def to_db_value(self, value: str, instance) -> str:
        return value.casefold().strip()

    def to_python_value(self, value: str) -> str:
        return value


class Permission(enum.StrEnum):
    ACCESS = "access"
    CHAT_CONFIG = "chat_config"
    CHAT_OPERATOR = "chat_operator"
    CONFIG = "config"
    FLAIR = "flair"
    MAIL = "mail"
    POSTS = "posts"
    WIKI = "wiki"


class SubPermissions(fields.CharField):
    _SEP = ","

    def __init__(self, **kwargs):
        # max_length = len("access,chat_config,chat_operator,config,flair,mail,posts,wiki")
        super().__init__(max_length=61, **kwargs)

    def to_db_value(self, value: Set[Permission], instance) -> str:
        return self._SEP.join([perm.value for perm in value])

    def to_python_value(self, value: str) -> Set[Permission]:
        if len(value) == 0:
            return set()
        return set(Permission(perm) for perm in value.split(self._SEP))
