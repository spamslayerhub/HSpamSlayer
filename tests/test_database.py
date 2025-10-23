from tortoise.contrib import test

from src.datastore.models import Ban, Sub, User

# TODO:
# moderators: fields.ManyToManyRelation["User"]
# users_info: fields.ReverseRelation["UserSubInfo"]
# user_bans: fields.ReverseRelation["SubBan"]
# comments: fields.ReverseRelation["Comment"]
# posts: fields.ReverseRelation["Post"]


class TestSub(test.IsolatedTestCase):
    async def test_create_sub(self):
        s = Sub(
            name="test",
            description="test_sub",
            sub_count=10,
            is_nsfw=False,
            is_banned=False,
            sub_id="test1",
            config="",
        )
        await s.save()

        s1 = await Sub.get(name="test")
        self.assertEqual(s, s1)

    @test.expectedFailure
    async def test_create_sub_bad(self):
        await Sub.create(
            name="test",
            description="test_sub",
            sub_count=10,
            is_nsfw=False,
            is_banned=False,
            sub_id="test1",
            config="",
        )

        await Sub.create(
            name="test",
            description="different_sub",
            sub_count=100,
            is_nsfw=False,
            is_banned=False,
            sub_id="test2",
            config="[has_something]",
        )

    @test.expectedFailure
    async def test_get_sub_bad(self):
        await Sub.get(name="test")

    async def test_update_sub(self):
        s_og = Sub(
            name="test",
            description="test_sub",
            sub_count=10,
            is_nsfw=False,
            is_banned=False,
            sub_id="test1",
            config="",
        )

        await s_og.save()

        s_new = await Sub.get(name="test")
        s_new.is_banned = True
        await s_new.save()

        s_current = await Sub.get(name="test")

        self.assertNotEqual(s_og.is_banned, s_current.is_banned)
        self.assertEqual(s_new.is_banned, s_current.is_banned)


# last_updated_at = fields.DatetimeField(auto_now=True)
# added_at: Final = fields.DatetimeField(auto_now_add=True)
# subreddit: fields.ForeignKeyNullableRelation[Sub] = fields.ForeignKeyField(
#     "models.Sub",
#     related_name=False,
#     null=True,
# )
#
# moderating: fields.ManyToManyRelation[Sub] = fields.ManyToManyField(
#     "models.Sub", related_name="moderators", through="moderating"
# )
# comments: fields.ReverseRelation["Comment"]
# posts: fields.ReverseRelation["Post"]
# sub_bans: fields.ReverseRelation["SubBan"]
# subs_info: fields.ReverseRelation["UserSubInfo"]


class TestUser(test.IsolatedTestCase):
    async def test_create_user(self):
        u = User(
            name="test",
            is_gold=False,
            is_mod=False,
            is_suspended=False,
            has_verified_email=True,
            comment_karma=10,
            link_karma=30,
            awarder_karma=0,
            total_karma=40,
            user_id="testid",
            created_at="2025-09-16 09:24",
        )
        await u.save()

        u0 = await User.get(name="test")
        self.assertEqual(u, u0)

    @test.expectedFailure
    async def test_create_user_bad(self):
        _ = await User.create(
            name="test",
            is_gold=False,
            is_mod=False,
            is_suspended=False,
            has_verified_email=True,
            comment_karma=10,
            link_karma=30,
            awarder_karma=0,
            total_karma=40,
            user_id="testid",
            created_at="2025-09-16 09:24",
        )

        _ = await User.create(
            name="test2",
            is_gold=False,
            is_mod=False,
            is_suspended=False,
            has_verified_email=True,
            comment_karma=10,
            link_karma=30,
            awarder_karma=0,
            total_karma=40,
            user_id="testid",  # id is the same
            created_at="2025-09-16 09:24",
        )

    @test.expectedFailure
    async def test_get_user_bad(self):
        _ = await User.get(name="test")

    async def test_update_user(self):
        u_og = User(
            name="test",
            is_gold=False,
            is_mod=False,
            is_suspended=False,
            has_verified_email=True,
            comment_karma=10,
            link_karma=30,
            awarder_karma=0,
            total_karma=40,
            user_id="testid",  # id is the same
            created_at="2025-09-16 09:24",
        )

        await u_og.save()

        u_new = await User.get(name="test")
        u_new.is_suspended = True
        await u_new.save()

        u_current = await User.get(name="test")

        self.assertNotEqual(u_og.is_suspended, u_current.is_suspended)
        self.assertEqual(u_new.is_suspended, u_current.is_suspended)


# id: Final = fields.IntField(primary_key=True)
# user: Final[fields.ForeignKeyRelation[User]] = fields.ForeignKeyField(
#     "models.User", related_name="hss_ban"
# )
# was_automatic = fields.BooleanField()
# reason: Final = fields.CharField(max_length=255)
# duration = custom_fields.RedditDuration()
# mod_scope: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
#     "models.User", related_name=False, null=True
# )
# reddit_reason = fields.CharField(max_length=100, null=True)
# message = fields.TextField(null=True)
# note = fields.CharField(max_length=300, null=True)
# banned_at: Final = fields.DatetimeField(auto_now_add=True)


class TestBan(test.IsolatedTestCase):
    async def test_create_ban(self):
        u = User(
            name="test",
            is_gold=False,
            is_mod=False,
            is_suspended=False,
            has_verified_email=True,
            comment_karma=10,
            link_karma=30,
            awarder_karma=0,
            total_karma=40,
            user_id="testid",
            created_at="2025-09-16 09:24",
        )

        await u.save()

        b = Ban(
            user=u,
            was_automatic=False,
            reason="some reason",
            duration=0,
            mod_scope=None,
            reddit_reason=None,
            message="some message",
            note="some note",
        )

        await b.save()

        ban_from_user = await Ban.get(user__name="test")
        user_from_ban = await User.get(name="test", hss_ban__isnull=False)

        self.assertEqual(u, user_from_ban)
        self.assertEqual(b, ban_from_user)

    @test.expectedFailure
    async def test_get_ban_bad(self):
        _ = await Ban.get(user__name="test")


# TODO: remove this
# these comments are here because for some reason if I delete the
# last line in a buffer neovim will fail an assertion and simply crash
