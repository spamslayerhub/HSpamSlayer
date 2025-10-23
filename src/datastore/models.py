import enum
from typing import Final

from tortoise import fields
from tortoise.models import Model
from tortoise.validators import MinValueValidator

from . import custom_fields

# TODO: some attributes might not be available from reddit, so I need to check what
# needs to be nullable


class Sub(Model):
    id: Final = fields.IntField(primary_key=True)
    name: Final = custom_fields.RedditName(unique=True)
    description = fields.TextField(null=True)
    sub_count = fields.IntField(validators=[MinValueValidator(0)])
    is_nsfw = fields.BooleanField()
    is_banned = fields.BooleanField()
    sub_id: Final = custom_fields.RedditID()
    config = fields.TextField(null=True)
    last_updated_at = fields.DatetimeField(auto_now=True)
    added_at: Final = fields.DatetimeField(auto_now_add=True)

    moderators: fields.ManyToManyRelation["User"]
    users_info: fields.ReverseRelation["UserSubInfo"]
    user_bans: fields.ReverseRelation["SubBan"]
    comments: fields.ReverseRelation["Comment"]
    posts: fields.ReverseRelation["Post"]


class Moderating(Model):
    id: Final = fields.IntField(primary_key=True)
    user: Final[fields.ForeignKeyRelation["User"]] = fields.ForeignKeyField(
        "models.User", related_name="moderatings"
    )
    sub: Final[fields.ForeignKeyRelation["Sub"]] = fields.ForeignKeyField(
        "models.Sub", related_name="moderatings"
    )
    permissions = custom_fields.SubPermissions()


class User(Model):
    id: Final = fields.IntField(primary_key=True)
    name: Final = custom_fields.RedditName(unique=True)
    is_gold = fields.BooleanField()
    is_mod = fields.BooleanField()
    is_suspended = fields.BooleanField()
    has_verified_email = fields.BooleanField()
    comment_karma = fields.IntField()
    link_karma = fields.IntField()
    awarder_karma = fields.IntField()
    total_karma = fields.IntField()
    user_id: Final = custom_fields.RedditID()
    created_at: Final = fields.DatetimeField()
    last_updated_at = fields.DatetimeField(auto_now=True)
    added_at: Final = fields.DatetimeField(auto_now_add=True)
    subreddit: fields.ForeignKeyNullableRelation[Sub] = fields.ForeignKeyField(
        "models.Sub",
        related_name=False,
        null=True,
    )

    moderating: fields.ManyToManyRelation[Sub] = fields.ManyToManyField(
        "models.Sub", through="moderating", backward_key="user_id", forward_key="sub_id"
    )
    comments: fields.ReverseRelation["Comment"]
    posts: fields.ReverseRelation["Post"]
    hss_ban: fields.ReverseRelation["Ban"]
    sub_bans: fields.ReverseRelation["SubBan"]
    subs_info: fields.ReverseRelation["UserSubInfo"]


class Ban(Model):
    id: Final = fields.IntField(primary_key=True)
    user: Final[fields.ForeignKeyRelation[User]] = fields.ForeignKeyField(
        "models.User", related_name="hss_ban"
    )
    was_automatic = fields.BooleanField()
    reason: Final = fields.CharField(max_length=255)
    duration = custom_fields.RedditDuration()
    mod_scope: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User", related_name=False, null=True
    )
    reddit_reason = fields.CharField(max_length=100, null=True)
    message = fields.TextField(null=True)
    note = fields.CharField(max_length=300, null=True)
    banned_at: Final = fields.DatetimeField(auto_now_add=True)


class SubBan(Model):
    id: Final = fields.IntField(primary_key=True)
    user: Final[fields.ForeignKeyRelation[User]] = fields.ForeignKeyField(
        "models.User", related_name="sub_bans"
    )
    sub: Final[fields.ForeignKeyRelation[Sub]] = fields.ForeignKeyField(
        "models.Sub", related_name="user_bans"
    )
    effective_duration: Final = custom_fields.RedditDuration()
    banned_at: Final = fields.DatetimeField(auto_now_add=True)


# TODO: make this work like a M2M relation on tortoise
class UserSubInfo(Model):
    id: Final = fields.IntField(primary_key=True)
    user: Final[fields.ForeignKeyRelation[User]] = fields.ForeignKeyField(
        "models.User", related_name="subs_info"
    )
    sub: Final[fields.ForeignKeyRelation[Sub]] = fields.ForeignKeyField(
        "models.Sub", related_name="users_info"
    )
    is_flagged = fields.BooleanField()
    strikes = fields.IntField(validators=[MinValueValidator(0)])
    score = fields.IntField(validators=[MinValueValidator(0)])
    sub_activity_score = fields.IntField(validators=[MinValueValidator(0)])
    profile_activity_score = fields.IntField(validators=[MinValueValidator(0)])


class Post(Model):
    id: Final = fields.IntField(primary_key=True)
    author: Final[fields.ForeignKeyRelation[User]] = fields.ForeignKeyField(
        "models.User", related_name="posts"
    )
    sub: Final[fields.ForeignKeyRelation[Sub]] = fields.ForeignKeyField(
        "models.Sub", related_name="posts"
    )
    submission_id: Final = custom_fields.RedditID()
    was_processed = fields.BooleanField()
    was_edited = fields.BooleanField()
    is_self: Final = fields.BooleanField()
    is_locked = fields.BooleanField()
    is_nsfw = fields.BooleanField()
    is_crosspost: Final = fields.BooleanField()
    crosspost_parent: Final[fields.ForeignKeyNullableRelation["Post"]] = (
        fields.ForeignKeyField("models.Post", related_name=False, null=True)
    )
    comment_count = fields.IntField(validators=[MinValueValidator(0)])
    permalink: Final = custom_fields.RedditPermaLink(unique=True)
    score = fields.IntField(validators=[MinValueValidator(0)])
    upvote_ratio = fields.FloatField(validators=[MinValueValidator(0)])
    selftext = fields.TextField(null=True)
    is_stickied = fields.BooleanField()
    title = fields.CharField(max_length=300, null=True)
    url = custom_fields.URL(null=True)
    created_at: Final = fields.DatetimeField()
    added_at: Final = fields.DatetimeField(auto_now_add=True)

    comments: fields.ReverseRelation["Comment"]


class Comment(Model):
    id: Final = fields.IntField(primary_key=True)
    author: Final[fields.ForeignKeyRelation[User]] = fields.ForeignKeyField(
        "models.User", related_name="comments"
    )
    sub: Final[fields.ForeignKeyRelation[Sub]] = fields.ForeignKeyField(
        "models.Sub", related_name="comments"
    )
    post: Final[fields.ForeignKeyRelation[Post]] = fields.ForeignKeyField(
        "models.Post", related_name="comments"
    )
    body = fields.TextField()
    was_edited = fields.BooleanField()
    was_processed = fields.BooleanField()
    comment_id: Final = custom_fields.RedditID()
    parent_id: Final = custom_fields.RedditID(unique=False)
    is_submitter: Final = fields.BooleanField()
    is_stickied = fields.BooleanField()
    permalink: Final = custom_fields.RedditPermaLink(unique=True)
    score = fields.IntField(validators=[MinValueValidator(0)])
    created_at: Final = fields.DatetimeField()
    added_at: Final = fields.DatetimeField(auto_now_add=True)


class RecordReason(enum.StrEnum):
    SCORE_CHANGE = "score_change"
    STRIKE_CHANGE = "strike_change"
    FLAGGED = "flagged"
    CROSSPOST = "crosspost"
    PATTERN_MATCHED = "pattern_matched"
    REPEATED_POST = "repeated_post"


class UserRecord(Model):
    id: Final = fields.IntField(primary_key=True)
    comment: Final[fields.ForeignKeyNullableRelation[Comment]] = fields.ForeignKeyField(
        "models.Comment", related_name=False, null=True
    )
    post: Final[fields.ForeignKeyNullableRelation[Post]] = fields.ForeignKeyField(
        "models.Post", related_name=False, null=True
    )
    reason: Final = fields.CharEnumField(RecordReason)

    orignal_score: Final = fields.IntField(validators=[MinValueValidator(0)], null=True)
    score_change: Final = fields.IntField(null=True)

    orignal_strikes: Final = fields.IntField(
        validators=[MinValueValidator(0)], null=True
    )
    strikes_change: Final = fields.IntField(null=True)

    pattern: Final = fields.TextField(null=True)

    repeted_post: Final[fields.ForeignKeyNullableRelation[Post]] = (
        fields.ForeignKeyField("models.Post", related_name=False, null=True)
    )

    # TODO


class SubList:
    id: Final = fields.IntField(primary_key=True)
    sub: Final[fields.ForeignKeyRelation[Sub]] = fields.ForeignKeyField(
        "models.Sub", related_name=False
    )
    added_at: Final = fields.DatetimeField(auto_now_add=True)


class Blacklist(Model, SubList):
    pass


class Whitelist(Model, SubList):
    pass
