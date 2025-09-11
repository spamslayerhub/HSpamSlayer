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
    # TODO: is it even worth it to make this a M2M? It would require 4
    # read queries just to check if a post was made in a sub the user
    # is a mod in:
    # 1. u = User.get(username)
    # 2. ban = u.hss_ban
    # 3. mod = ban.mod_scope
    # 4. mod.moderating
    #
    # perhaps this is managable with prefetching? or am I just going
    # too into relations/atomicity and should be just focusing on
    # minimizing queries instead?
    #
    # maybe I should keep duplicates? like a list of comma separated
    # subreddit names for a way to check if a user mods a sub without
    # any additional reads. I'm debating how useful having this relation
    # might be...
    moderating: fields.ManyToManyRelation[Sub] = fields.ManyToManyField(
        "models.Sub", related_name="moderators", through="moderating"
    )
    hss_ban: fields.ReverseRelation["Ban"]


class Ban(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyRelation[User] = fields.ForeignKeyField("models.User")
    reason = fields.CharField(max_length=255)
    duration = fields.IntField(
        validators=[MinValueValidator(0), MaxValueValidator(999)],
    )
    mod_scope = fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", null=True
    )
    message = fields.TextField(null=True)
    banned_at = fields.DatetimeField(auto_now_add=True)


# class SubBan(Model):
#     ban =
