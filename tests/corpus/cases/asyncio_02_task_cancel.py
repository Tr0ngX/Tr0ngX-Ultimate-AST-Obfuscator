import asyncio

log = []


async def worker():
    try:
        await asyncio.sleep(10)
        log.append("completed")
    except asyncio.CancelledError:
        log.append("cancelled")
        raise


async def shield_demo():
    async def protected():
        await asyncio.sleep(0.05)
        return "protected-result"

    result = await asyncio.shield(asyncio.create_task(protected()))
    log.append(result)


async def main():
    task = asyncio.create_task(worker())
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print(log)
    await shield_demo()
    print(log[-1])
    inner = asyncio.create_task(asyncio.sleep(10, "never"))
    outer = asyncio.create_task(asyncio.shield(inner))
    await asyncio.sleep(0.01)
    outer.cancel()
    try:
        await outer
    except asyncio.CancelledError:
        print("outer cancelled, inner still pending:", not inner.done())
    inner.cancel()
    await asyncio.gather(inner, return_exceptions=True)


asyncio.run(main())
