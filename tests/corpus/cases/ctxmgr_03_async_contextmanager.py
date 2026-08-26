import asyncio
from contextlib import asynccontextmanager

trail = []


@asynccontextmanager
async def connect(tag):
    trail.append("open:" + tag)
    try:
        yield tag + "-session"
    finally:
        trail.append("close:" + tag)


async def query(sess):
    trail.append("run:" + sess)
    return 7


async def main():
    n = 0
    async with connect("primary") as sess:
        n = await query(sess)
    try:
        async with connect("backup"):
            raise RuntimeError("query exploded")
    except RuntimeError:
        pass
    print(trail)
    print(n)


asyncio.run(main())
