import asyncio
import dataclasses
import datetime as dt
import sys
from collections.abc import Coroutine
from typing import Any, Callable, ParamSpec, TypeVar

from src.log import get_logger
from src.datastore.models import SchedulerTask

R = TypeVar("R")
P = ParamSpec("P")

LOGGER = get_logger("hss.scheduler")

type CoroFN[R] = Callable[..., Coroutine[Any, Any, R]]
type ErrorHandler[R] = Callable[[BaseException, ScheduledTask[R]], None]


@dataclasses.dataclass
class ScheduledTask[R]:
    task: asyncio.Task[Any] | None
    name: str
    coro_fn: CoroFN[R]
    args: tuple[object, ...]
    kwargs: dict[str, object]
    every: dt.timedelta
    last_ran_at: dt.datetime
    errors: list[BaseException]
    error_handler: ErrorHandler[R] | None


# TODO: add debug logs here
class Scheduler[R]:
    def __init__(self) -> None:
        self.tasks: list[ScheduledTask[R]] = []
        self._task: asyncio.Task[Any] | None = None
        self._stop = False

    async def schedule(
        self,
        coro_fn: Callable[P, Coroutine[Any, Any, R]],
        name: str,
        every: dt.timedelta,
        error_handler: ErrorHandler[R] | None = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> ScheduledTask[R]:

        task_db = await SchedulerTask.get_or_none(name=name)
        if task_db is None:
            task_db = await SchedulerTask.create(name=name, last_ran_at=dt.datetime.min)
            LOGGER.info(f"created scheduler task '{name}'!")

        task = ScheduledTask[R](
            task=None,
            name=name,
            coro_fn=coro_fn,
            args=args,
            kwargs=kwargs,
            every=every,
            last_ran_at=task_db.last_ran_at,
            errors=[],
            error_handler=error_handler,
        )

        self.tasks.append(task)

        LOGGER.debug(
            f"scheduled task '{name}' to run every {every}, last ran at {task_db.last_ran_at}"
        )
        return task

    def seconds_to_wait(self, last_ran_at: dt.datetime, every: dt.timedelta) -> float:
        now = (
            dt.datetime.now(last_ran_at.tzinfo)
            if last_ran_at.tzinfo
            else dt.datetime.now()
        )

        time_delta = now - last_ran_at

        return every.total_seconds() - time_delta.total_seconds()

    type Time2WaitSecs = float
    type CanStop = bool

    def _handle_exception(self, t: ScheduledTask[R], ex: BaseException | None):
        if ex is None:
            return

        LOGGER.error(f"task '{t.name}' has raised an exception: {ex}")
        LOGGER.error(f"task '{t.name}' traceback: {ex.__traceback__}")

        t.errors.append(ex)

        # HACK/NOTE: the way for the handler to make a task stop executing after
        # some given execption would be to set `last_ran_at` to `dt.datetime.max`,
        # this is not ideal, but it works...

        if t.error_handler is not None:
            t.error_handler(ex, t)

    async def _handle_tasks(self) -> tuple[Time2WaitSecs, CanStop]:
        wait = sys.float_info.max
        can_stop = True

        for t in self.tasks:
            t_wait = self.seconds_to_wait(t.last_ran_at, t.every)

            if t.task is None:
                if t_wait <= 0 and not self._stop:
                    t.task = asyncio.create_task(t.coro_fn(*t.args))

                    task_db = await SchedulerTask.get(name=t.name)
                    task_db.last_ran_at = dt.datetime.now()
                    await task_db.save()

                    t.last_ran_at = task_db.last_ran_at

            elif t.task.done():
                ex = t.task.exception()
                self._handle_exception(t, ex)
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

            wait, can_stop = await self._handle_tasks()

            if self._stop and can_stop:
                break

            if wait > 0:
                await asyncio.sleep(wait)

    def start(self):
        self._task = asyncio.create_task(self.loop())

    def cancel(self):
        assert self._task is not None
        _ = self._task.cancel()

    async def safe_cancel(self):
        assert self._task is not None
        self._stop = True
        await self._task
