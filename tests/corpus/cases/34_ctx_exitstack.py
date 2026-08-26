import asyncio
from contextlib import ExitStack, AsyncExitStack, asynccontextmanager

trace = []


def make_cb(name):
    def cb():
        trace.append(f"cb:{name}")
    return cb


async def acb(name):
    trace.append(f"acb:{name}")


class SyncThing:
    def __init__(self, n):
        self.n = n

    def __enter__(self):
        trace.append(f"in:{self.n}")
        return self.n

    def __exit__(self, *ei):
        trace.append(f"out:{self.n}")
        return False


@asynccontextmanager
async def tagged(tag):
    trace.append(f"acm-in:{tag}")
    try:
        yield tag
    finally:
        trace.append(f"acm-out:{tag}")


with ExitStack() as stack:
    a = stack.enter_context(SyncThing(1))
    b = stack.enter_context(SyncThing(2))
    stack.callback(make_cb("late"))
    stack.enter_context(SyncThing(9))
    trace.append(f"body:{a}-{b}")


async def main():
    async with AsyncExitStack() as astack:
        astack.push_async_callback(acb, "worker")
        async with tagged("ctx") as t:
            trace.append(f"abody:{t}")


asyncio.run(main())
print(trace)
