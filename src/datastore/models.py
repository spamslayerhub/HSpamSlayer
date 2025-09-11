import enum
from tortoise import fields
from tortoise.models import Model
from tortoise.validators import MaxValueValidator, MinValueValidator
from . import custom_fields

# TODO: some attributes might not be available from reddit, so I need to check what
# needs to be nullable


class Sub(Model):
    id = fields.IntField(primary_key=True)
    name = custom_fields.RedditName(unique=True)
    is_mod = fields.BooleanField()
    description = fields.TextField(null=True)
    permissions = custom_fields.SubPermissions()
    sub_count = fields.IntField(validators=[MinValueValidator(0)])
    is_nsfw = fields.BooleanField()
    is_banned = fields.BooleanField()
    # TODO: not sure the sub id is 5
    sub_id = fields.CharField(max_length=5, unique=True)
    config = fields.TextField(null=True)
    last_updated_at = fields.DatetimeField(auto_now=True)
    added_at = fields.DatetimeField(auto_now_add=True)
    moderators: fields.ManyToManyRelation["User"]


class User(Model):
    id = fields.IntField(primary_key=True)
    name = custom_fields.RedditName(unique=True)
    is_gold = fields.BooleanField()
    is_mod = fields.BooleanField()
    is_suspended = fields.BooleanField()
    has_verified_email = fields.BooleanField()
    comment_karma = fields.IntField()
    link_karma = fields.IntField()
    # TODO: not sure the user id is 5
    user_id = fields.CharField(max_length=5, unique=True)
    created_at = fields.DatetimeField()
    last_updated_at = fields.DatetimeField(auto_now=True)
    added_at = fields.DatetimeField(auto_now_add=True)
    subreddit: fields.ForeignKeyNullableRelation[Sub] = fields.ForeignKeyField(
        "models.Sub", null=True
    )

    moderating: fields.ManyToManyRelation[Sub] = fields.ManyToManyField(
        "models.Sub", related_name="moderators", through="moderating"
    )
    hss_ban: fields.ReverseRelation["Ban"]


class Ban(Model):
    id = fields.IntField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="hss_ban"
    )
    was_automatic = fields.BooleanField()
    reason = fields.CharField(max_length=255)
    duration = custom_fields.RedditDuration()
    mod_scope = fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User", null=True
    )
    reddit_reason = fields.CharField(max_length=100, null=True)
    message = fields.TextField(null=True)
    # will this work? char is normally limited to 255
    note = fields.CharField(max_length=300, null=True)
    banned_at = fields.DatetimeField(auto_now_add=True)


class SubBan(Model):
    id = fields.IntField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField("models.User")
    sub: fields.ForeignKeyRelation[Sub] = fields.ForeignKeyField("models.Sub")
    effective_duration = custom_fields.RedditDuration()
    banned_at = fields.DatetimeField(auto_now_add=True)


class UserSubInfo(Model):
    id = fields.IntField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField("models.User")
    sub: fields.ForeignKeyRelation[Sub] = fields.ForeignKeyField("models.Sub")
    is_flagged = fields.BooleanField()
    strikes = fields.IntField()
    score = fields.IntField()
    sub_activity_score = fields.IntField()
    profile_activity_score = fields.IntField()


class Post(Model):
    id = fields.IntField(primary_key=True)
    author: fields.ForeignKeyRelation[User] = fields.ForeignKeyField("models.User")
    sub: fields.ForeignKeyRelation[Sub] = fields.ForeignKeyField("models.Sub")
    submission_id = fields.CharField(max_length=5, unique=True)
    was_edited = fields.BooleanField()
    is_self = fields.BooleanField()
    is_locked = fields.BooleanField()
    is_nsfw = fields.BooleanField()
    comment_count = fields.IntField(validators=[MinValueValidator(0)])
    permalink = custom_fields.RedditPermaLink(unique=True)
    score = fields.IntField(validators=[MinValueValidator(0)])
    upvote_ratio = fields.FloatField(validators=[MinValueValidator(0)])
    selftext = fields.TextField(null=True)
    is_stickied = fields.BooleanField()
    title = fields.CharField(max_length=300, null=True)
    url = custom_fields.URL(null=True)
    created_at = fields.DatetimeField()


class Comment(Model):
    id = fields.IntField(primary_key=True)
    author: fields.ForeignKeyRelation[User] = fields.ForeignKeyField("models.User")
    sub: fields.ForeignKeyRelation[Sub] = fields.ForeignKeyField("models.Sub")
    post: fields.ForeignKeyRelation[Post] = fields.ForeignKeyField("models.Post")
    body = fields.TextField()
    was_edited = fields.BooleanField()
    comment_id = fields.CharField(max_length=5)
    parent_id = fields.CharField(max_length=5, null=True)
    is_submitter = fields.BooleanField()
    is_stickied = fields.BooleanField()
    permalink = custom_fields.RedditPermaLink(unique=True)
    score = fields.IntField(validators=[MinValueValidator(0)])
    created_at = fields.DatetimeField()


class UserActivity(Model):
    id = fields.IntField(primary_key=True)
    comment = fields.ForeignKeyRelation[Comment] = fields.ForeignKeyField(
        "models.Comment"
    )
    post = fields.ForeignKeyRelation[Post] = fields.ForeignKeyField("models.Post")
    # TODO


class SubList:
    id = fields.IntField(primary_key=True)
    sub: fields.ForeignKeyRelation[Sub] = fields.ForeignKeyField("models.Sub")
    added_at = fields.DatetimeField(auto_now_add=True)


class Blacklist(Model, SubList):
    pass


class Whitelist(Model, SubList):
    pass
