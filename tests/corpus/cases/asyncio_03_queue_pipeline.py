import asyncio


async def producer(q):
    for i in range(5):
        await q.put(i * i)
    await q.put(None)


async def consumer(q):
    out = []
    while True:
        item = await q.get()
        if item is None:
            break
        out.append(item)
    print(out)


async def main():
    q = asyncio.Queue(maxsize=3)
    await asyncio.gather(producer(q), consumer(q))


asyncio.run(main())
