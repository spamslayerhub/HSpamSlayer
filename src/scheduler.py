import asyncio
import inspect
import sys
import datetime as dt
from typing import Any, Callable, List, Coroutine

import dataclasses


@dataclasses.dataclass
class ScheduledTask:
    task: asyncio.Task | None
    coro_fn: Callable[..., Coroutine[Any, Any, Any]]
    args: List[Any]
    every: dt.time
    last_ran_at: dt.datetime


class Scheduler:
    def __init__(self) -> None:
        self.tasks: List[ScheduledTask] = []
        self._task: asyncio.Task | None = None
        self._stop = False

    def schedule(
        self,
        coro_fn: Callable[..., Coroutine[Any, Any, Any]],
        every: dt.time,
        args: List[Any] = [],
        last_ran_at: dt.datetime | None = None,
    ):
        # TODO: pretty sure this doesn't cover all cases
        expected_params = 0
        sig = inspect.signature(coro_fn)
        for param in sig.parameters.values():
            if param.default is inspect._empty:
                expected_params += 1

        assert len(args) >= expected_params

        self.tasks.append(
            ScheduledTask(
                task=None,
                coro_fn=coro_fn,
                args=args,
                every=every,
                last_ran_at=last_ran_at if last_ran_at is not None else dt.datetime.min,
            )
        )

    def seconds_to_wait(self, last_ran_at: dt.datetime, every: dt.time) -> float:
        now = (
            dt.datetime.now(last_ran_at.tzinfo)
            if last_ran_at.tzinfo
            else dt.datetime.now()
        )

        time_delta = now - last_ran_at

        return (
            (every.hour * 60 + every.minute) * 60
            + every.second
            + (every.microsecond / 1000000)
        ) - time_delta.total_seconds()

    async def loop(self):
        assert len(self.tasks) != 0

        while True:
            self.tasks.sort(
                key=lambda t: (self.seconds_to_wait(t.last_ran_at, t.every))
            )

            wait = sys.float_info.max
            can_stop = True

            for t in self.tasks:

                t_wait = self.seconds_to_wait(t.last_ran_at, t.every)

                if t.task is None:
                    if t_wait <= 0 and not self._stop:
                        t.task = asyncio.create_task(t.coro_fn(*t.args))
                        t.last_ran_at = dt.datetime.now()
                elif t.task.done():
                    # TODO: handle exceptions
                    # ex = t.task.exception()
                    # if ex is not None:
                    #     print(ex)

                    t.task = None
                else:
                    can_stop = False

                wait = t_wait if t_wait < wait else wait

            if self._stop and can_stop:
                break

            if wait > 0:
                await asyncio.sleep(wait)

    def start(self):
        self._task = asyncio.create_task(self.loop())

    def cancel(self):
        assert self._task is not None
        self._task.cancel()

    async def safe_cancel(self):
        assert self._task is not None
        self._stop = True
        await self._task
