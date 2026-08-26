import asyncio


async def sleeper(name, seconds):
    await asyncio.sleep(seconds)
    return name


async def main():
    fast = asyncio.create_task(sleeper("fast", 0.01))
    slow = asyncio.create_task(sleeper("slow", 60))
    labels = {id(fast): "F", id(slow): "S"}
    done, pending = await asyncio.wait({fast, slow}, timeout=0.08)
    print(sorted(labels[id(t)] for t in done), sorted(labels[id(t)] for t in pending))
    slow.cancel()
    outcome = await asyncio.gather(fast, slow, return_exceptions=True)
    print([type(o).__name__ for o in outcome])
    try:
        await asyncio.wait_for(sleeper("never", 60), timeout=0.01)
    except asyncio.TimeoutError:
        print("timeout-ok")
    print("end")


asyncio.run(main())
