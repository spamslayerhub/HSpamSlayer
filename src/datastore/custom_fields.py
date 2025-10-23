import enum
from functools import singledispatchmethod
from typing import overload, override

from tortoise import fields
from tortoise.validators import MaxValueValidator, MinValueValidator, Validator


class RedditDuration(fields.SmallIntField):
    def __init__(self, **kwargs):
        validators: list[Validator] = [MinValueValidator(0), MaxValueValidator(999)]
        vals = kwargs.get("validators")
        if vals is not None:
            assert isinstance(vals, list)
            vals.extend(validators)
        else:
            kwargs["validators"] = validators
        super().__init__(**kwargs)


class RedditName(fields.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=22, **kwargs)

    @override
    def to_db_value(self, value: str, instance) -> str:
        return value.casefold().strip()

    @override
    def to_python_value(self, value: str) -> str:
        return value.casefold().strip()


class RedditPermaLink(fields.CharField):
    def __init__(self, **kwargs):
        # 500 should be enough
        super().__init__(max_length=500, **kwargs)


class RedditID(fields.CharField):
    def __init__(self, **kwargs):
        # this should cover for the possibility of
        # 3 quadrillion posts/comments/users

        kwargs["unique"] = kwargs.get("unique", True)
        super().__init__(max_length=10, **kwargs)


class URL(fields.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=2000, **kwargs)


class Permission(enum.StrEnum):
    ACCESS = "access"
    CHAT_CONFIG = "chat_config"
    CHAT_OPERATOR = "chat_operator"
    CONFIG = "config"
    FLAIR = "flair"
    MAIL = "mail"
    POSTS = "posts"
    WIKI = "wiki"

    @staticmethod
    def all() -> set["Permission"]:
        return set(Permission)

    @staticmethod
    def none() -> set["Permission"]:
        return set()


class SubPermissions(fields.CharField):
    _SEP = ","

    def __init__(self, **kwargs):
        # max_length = len("access,chat_config,chat_operator,config,flair,mail,posts,wiki")
        super().__init__(max_length=61, **kwargs)

    @override
    def to_db_value(self, value: set[Permission], instance) -> str:
        return self._SEP.join([perm.value for perm in value])

    @singledispatchmethod
    def to_py_val(self, value) -> set[Permission]:
        raise NotImplementedError(
            "SubPermissions only supports 'str' and 'Set[Permission]'"
        )

    @to_py_val.register
    def to_python_value_from_str(self, value: str) -> set[Permission]:
        if len(value) == 0:
            return set()
        return set(Permission(perm) for perm in value.split(self._SEP))

    @to_py_val.register
    def to_python_value_from_set_perm(self, value: set[Permission]) -> set[Permission]:
        return value

    @overload
    def to_python_value(self, value: str) -> set[Permission]: ...

    @overload
    def to_python_value(self, value: set[Permission]) -> set[Permission]: ...

    @override
    def to_python_value(self, *args, **kwargs) -> set[Permission]:
        return self.to_py_val(*args, **kwargs)
