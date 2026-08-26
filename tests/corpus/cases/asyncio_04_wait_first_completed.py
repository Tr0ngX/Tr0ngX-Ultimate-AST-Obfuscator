import asyncio


async def quick():
    await asyncio.sleep(0.01)
    return "quick"


async def slow():
    await asyncio.sleep(0.75)
    return "slow"


async def main():
    tasks = {
        asyncio.create_task(quick(), name="q"),
        asyncio.create_task(slow(), name="s"),
    }
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    print(sorted(t.get_name() for t in done))
    print([t.result() for t in done])
    print(len(done) == 1 and len(pending) == 1)


asyncio.run(main())
