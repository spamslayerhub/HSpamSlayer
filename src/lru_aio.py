import asyncio
import datetime as dt
import functools
from collections.abc import Coroutine
from enum import Enum
from typing import (
    Any,
    Callable,
    Hashable,
    NamedTuple,
    ParamSpec,
    Protocol,
    TypeVar,
    cast,
)

R = TypeVar("R")
P = ParamSpec("P")


class CacheInfo(NamedTuple):
    hits: int
    misses: int
    maxsize: int
    cursize: int


# CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])


# https://github.com/python/typing/issues/236#issuecomment-227180301
class Sentinel(Enum):
    token = 0


# This class ( AsyncLruCache ) is based on a modified version of LruCache from ring.
# Changes:
# - uses `datetime` and `timedelta` instead of time for expire time
# - `touch` doesn't change the `expired_time` for a link
# - `SENTINEL` value is based on an Enum for type hints
# - changed methods to be class bound
# - changed some variable names
#
# Original source:
# - <https://github.com/youknowone/ring>
# - <https://github.com/youknowone/ring/blob/7fbd8b8836e68b53b9c0231a751d719bdc78a527/ring/func/lru_cache.py#L15>
#
# Copyright (c) 2016, Jeong YunWon <jeong+ring@youknowone.org>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


SENTINEL = Sentinel.token  # unique object used to signal cache misses
PREV, NEXT, KEY, RESULT, EXPIRE = 0, 1, 2, 3, 4  # names for the link fields
FULL, HITS, MISSES = 0, 1, 2  # names for stat


class AsyncLruCache[R]:
    """Created by breaking down functools.lru_cache from CPython 3.7.0."""

    def __init__(self, max_size: int, expire: dt.timedelta | None):
        self.max_size = max_size
        self.expire = expire
        self.cache = {}
        self.cache_get = self.cache.get  # bound method to lookup a key or return None
        self.cache_len = self.cache.__len__  # get cache size without calling len()
        # NOTE: this isn't thread safe, will need an async reentrant
        # lock if that every comes into play
        self.lock = asyncio.Lock()

        self.root = []  # root of the circular doubly linked list
        # initialize by pointing to self
        self.root[:] = [self.root, self.root, None, None, None]
        self.stat = [False, 0, 0]

    def _expiration_time(self):
        if self.expire is None:
            return self.expire
        return dt.datetime.now(dt.timezone.utc) + self.expire

    async def get(self, key: Hashable) -> R | Sentinel:
        now = dt.datetime.now(dt.timezone.utc)
        async with self.lock:
            link = self.cache_get(key)
            if link is not None and (link[EXPIRE] is None or now < link[EXPIRE]):
                root = self.root
                # Move the link to the front of the circular queue
                link_prev, link_next, _, result, _ = link
                link_prev[NEXT] = link_next
                link_next[PREV] = link_prev
                last = root[PREV]
                last[NEXT] = root[PREV] = link
                link[PREV] = last
                link[NEXT] = root
                self.stat[HITS] += 1
                return result
            else:
                self.stat[MISSES] += 1
                if link is not None:
                    self._delete(key)
        return SENTINEL

    def _delete(self, key: Hashable):
        oldresult = self.root[RESULT]  # noqa
        # delete from the linked list
        link = self.cache[key]
        link_prev, link_next, _, _, _ = link
        link_prev[NEXT] = link_next
        link_next[PREV] = link_prev

        # delete from the cache
        del self.cache[key]
        self.stat[FULL] = False

    async def delete(self, key: Hashable):
        async with self.lock:
            self._delete(key)

    async def set(self, key: Hashable, result: R):
        expired_time = self._expiration_time()
        if self.max_size == 0:
            return
        async with self.lock:
            link = self.cache_get(key)
            if link is not None:
                # Update link to store the new result
                link[RESULT] = result
                link[EXPIRE] = expired_time
            elif self.stat[FULL]:
                # Use the old root to store the new key and result.
                oldroot = self.root
                oldroot[KEY] = key
                oldroot[RESULT] = result
                oldroot[EXPIRE] = expired_time
                # Empty the oldest link and make it the new root.
                # Keep a reference to the old key and old result to
                # prevent their ref counts from going to zero during the
                # update. That will prevent potentially arbitrary object
                # clean-up code (i.e. __del__) from running while we're
                # still adjusting the links.
                root = self.root = oldroot[NEXT]
                oldkey = root[KEY]
                oldresult = root[RESULT]  # noqa
                root[KEY] = root[RESULT] = None
                # Now update the cache dictionary.
                del self.cache[oldkey]
                # Save the potentially reentrant cache[key] assignment
                # for last, after the root and links have been put in
                # a consistent state.
                self.cache[key] = oldroot
            else:
                root = self.root
                # Put result in a new link at the front of the queue.
                last = root[PREV]
                link = [last, root, key, result, expired_time]
                last[NEXT] = root[PREV] = self.cache[key] = link
                # Use the cache_len bound method instead of the len() function
                # which could potentially be wrapped in an lru_cache itself.
                if self.max_size > 0:
                    self.stat[FULL] = self.cache_len() >= self.max_size

    async def info(self) -> CacheInfo:
        """Report cache statistics"""
        async with self.lock:
            return CacheInfo(
                self.stat[HITS], self.stat[MISSES], self.max_size, self.cache_len()
            )

    async def clear(self):
        """Clear the cache and cache statistics"""
        async with self.lock:
            self.cache.clear()
            root = self.root
            root[:] = [root, root, None, None, None]
            self.stat[:] = False, 0, 0

    async def has(self, key: Hashable):
        async with self.lock:
            return key in self.cache

    async def touch(self, key: Hashable):
        async with self.lock:
            root = self.root
            link = self.cache_get(key)
            if link is None:
                raise KeyError
            # Move the link to the front of the circular queue
            link_prev, link_next, _, _, _ = link
            link_prev[NEXT] = link_next
            link_next[PREV] = link_prev
            last = root[PREV]
            last[NEXT] = root[PREV] = link
            link[PREV] = last
            link[NEXT] = root
            # return result


class CachedAsyncFn(Protocol[P, R]):
    cache: AsyncLruCache[R]

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...
    def key(self, *args: P.args, **kwargs: P.kwargs) -> Hashable: ...
    async def clear(self): ...
    async def info(self) -> CacheInfo: ...
    async def get(self, *args: P.args, **kwargs: P.kwargs) -> R: ...
    async def set(self, value: R, *args: P.args, **kwargs: P.kwargs): ...
    async def delete(self, *args: P.args, **kwargs: P.kwargs): ...
    async def update(self, *args: P.args, **kwargs: P.kwargs): ...
    async def has(self, *args: P.args, **kwargs: P.kwargs) -> bool: ...

    async def touch(self, *args: P.args, **kwargs: P.kwargs):
        """
        raises `KeyError`
        """
        ...


# TODO/XXX: this has an unholy amount of nesting that NEEDS to go,
# however it is very hard to factor things out here without adding
# unnecessary complexity.
# + these type hints are kinda hard to read
def lru_aio(
    max_size: int, expire: dt.timedelta | None = None
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], CachedAsyncFn[P, R]]:
    def user_function(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> CachedAsyncFn[P, R]:
        def make_key(args, kwargs):
            return functools._make_key(args, kwargs, False)

        cache = AsyncLruCache[R](max_size, expire)
        # NOTE: all of this pending logic is here to avoid the following race
        # condition:
        # task 1: cache.get() -> SENTINEL : starts computing func()
        # task 2: cache.get() -> SENTINEL : also starts computing func()
        #
        # the reason for not simply locking though the entire scope of `wrapper`
        # is to avoid dead-locks in the case of recursive calls, given that `cache`
        # doesn't use an RLock
        pending: dict[Hashable, asyncio.Future[R]] = {}
        pending_lock = asyncio.Lock()

        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = make_key(args, kwargs)
            cached = await cache.get(key)

            if cached is not SENTINEL:
                return cached

            fut: asyncio.Future[R] | None = None

            async with pending_lock:
                pending_fut = pending.get(key)
                if pending_fut is None:
                    fut = asyncio.Future()
                    pending[key] = fut

            if pending_fut is not None:
                return await pending_fut

            assert fut is not None

            try:
                result = await func(*args, **kwargs)
                await cache.set(key, result)
                fut.set_result(result)
                return result
            except Exception as e:
                fut.set_exception(e)
                raise e
            finally:
                async with pending_lock:
                    if key in pending and pending[key] is fut:
                        del pending[key]

        wrapper = cast(CachedAsyncFn[P, R], wrapper)
        wrapper.cache = cache
        wrapper.key = lambda *args, **kwargs: make_key(args, kwargs)

        async def clear():
            await cache.clear()

        wrapper.clear = clear

        async def info():
            return await cache.info()

        wrapper.info = info

        # lol
        wrapper.get = wrapper

        async def set(value: R, *args: P.args, **kwargs: P.kwargs):
            await cache.set(make_key(args, kwargs), value)

        wrapper.set = set

        async def delete(*args: P.args, **kwargs: P.kwargs):
            await cache.delete(make_key(args, kwargs))

        wrapper.delete = delete

        async def update(*args: P.args, **kwargs: P.kwargs):
            key = make_key(args, kwargs)

            fut: asyncio.Future[R] | None = None

            async with pending_lock:
                pending_fut = pending.get(key)
                if pending_fut is None:
                    fut = asyncio.Future()
                    pending[key] = fut

            if pending_fut is not None:
                result = await pending_fut
                await cache.set(key, result)
                return

            assert fut is not None

            try:
                result = await func(*args, **kwargs)
                await cache.set(key, result)
                fut.set_result(result)
            except Exception as e:
                fut.set_exception(e)
                raise e
            finally:
                async with pending_lock:
                    if key in pending and pending[key] is fut:
                        del pending[key]

        wrapper.update = update

        async def has(*args: P.args, **kwargs: P.kwargs):
            return await cache.has(make_key(args, kwargs))

        wrapper.has = has

        async def touch(*args: P.args, **kwargs: P.kwargs):
            await cache.touch(make_key(args, kwargs))

        wrapper.touch = touch

        _ = functools.update_wrapper(wrapper, func)
        return wrapper

    return user_function
