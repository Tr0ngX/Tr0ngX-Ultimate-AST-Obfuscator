import asyncio
from contextlib import asynccontextmanager

events = []


class AsyncConn:
    def __init__(self, name):
        self.name = name

    async def __aenter__(self):
        events.append(f"open:{self.name}")
        return self

    async def __aexit__(self, et, ev, tb):
        events.append(f"close:{self.name}:{'exc' if et else 'ok'}")
        return False


@asynccontextmanager
async def session(tag):
    events.append(f"begin:{tag}")
    try:
        yield tag
    finally:
        events.append(f"end:{tag}")


async def main():
    async with AsyncConn("db"), session("sess") as s:
        events.append(f"work:{s}")
        async with AsyncConn("cache"):
            await asyncio.sleep(0)
    try:
        async with AsyncConn("failconn"):
            raise ValueError("boom")
    except ValueError as e:
        events.append(f"handled:{e}")
    print(events)


asyncio.run(main())
