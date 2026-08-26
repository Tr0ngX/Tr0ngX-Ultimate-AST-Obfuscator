import asyncio


async def job(name, delay):
    await asyncio.sleep(delay)
    return name


async def main():
    results = await asyncio.gather(
        job("alpha", 0.03),
        job("beta", 0.01),
        job("gamma", 0.02),
    )
    print(results)
    fast = asyncio.create_task(job("fast", 0.005))
    slow = asyncio.create_task(job("slow", 0.05))
    done, pending = await asyncio.wait({fast, slow})
    label = {id(fast): "fast", id(slow): "slow"}
    print(sorted(label[id(t)] for t in done), sorted(label[id(t)] for t in pending))


asyncio.run(main())
print("loop-closed")
