import asyncio
import sys
import datetime as dt
from typing import Any, Dict, TypeVar, ParamSpec, Callable, List, Coroutine

import dataclasses


R = TypeVar("R")
P = ParamSpec("P")


@dataclasses.dataclass
class ScheduledTask[R]:
    task: asyncio.Task | None
    coro_fn: Callable[..., Coroutine[Any, Any, R]]
    args: tuple[object, ...]
    kwargs: Dict[str, object]
    every: dt.timedelta
    last_ran_at: dt.datetime


# TODO: this needs a db table to keep the last time every task was ran
class Scheduler:
    def __init__(self) -> None:
        self.tasks: List[ScheduledTask] = []
        self._task: asyncio.Task | None = None
        self._stop = False

    def schedule(
        self,
        coro_fn: Callable[P, Coroutine[Any, Any, R]],
        every: dt.timedelta,
        last_ran_at: dt.datetime | None = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ):

        self.tasks.append(
            ScheduledTask[R](
                task=None,
                coro_fn=coro_fn,
                args=args,
                kwargs=kwargs,
                every=every,
                last_ran_at=last_ran_at if last_ran_at is not None else dt.datetime.min,
            )
        )

    def seconds_to_wait(self, last_ran_at: dt.datetime, every: dt.timedelta) -> float:
        now = (
            dt.datetime.now(last_ran_at.tzinfo)
            if last_ran_at.tzinfo
            else dt.datetime.now()
        )

        time_delta = now - last_ran_at

        return every.total_seconds() - time_delta.total_seconds()

    def _handle_tasks(self) -> tuple[float, bool]:
        """
        returns (wait, can_stop)
        """
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

        return (wait, can_stop)

    async def loop(self):
        assert len(self.tasks) != 0

        while True:
            self.tasks.sort(
                key=lambda t: (self.seconds_to_wait(t.last_ran_at, t.every))
            )

            wait, can_stop = self._handle_tasks()

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
