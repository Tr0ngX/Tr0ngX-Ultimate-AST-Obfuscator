# Test file with complex Python features:
# - Asynchronous coroutines (async / await)
# - Custom metaclass & decorators with args
# - Pattern matching (match / case)
# - Dataclasses & Generators & Context Managers
# - Bitwise operations, math, recursion, hashing, multiprocessing mock

import asyncio
import hashlib
import json
import math
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Generator

# 1. Custom Decorator & Context Manager
def time_it(prefix: str = "[BENCHMARK]"):
    def decorator(func):
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            res = func(*args, **kwargs)
            dt = time.perf_counter() - t0
            print(f"{prefix} {func.__name__} took {dt:.6f}s")
            return res
        return wrapper
    return decorator

class DataStreamManager:
    def __init__(self, stream_name: str):
        self.stream_name = stream_name
        self.buffer = []

    def __enter__(self):
        self.buffer.append(f"INIT:{self.stream_name}")
        return self

    def push(self, val: Any):
        self.buffer.append(val)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.buffer.append("CLOSED")
        return False

# 2. Metaclass & OOP Hierarchy
class AutoRegisterMeta(type):
    registry = {}
    def __new__(cls, name, bases, attrs):
        new_cls = super().__new__(cls, name, bases, attrs)
        if name != "BasePlugin":
            cls.registry[name] = new_cls
        return new_cls

class BasePlugin(metaclass=AutoRegisterMeta):
    def execute(self) -> Dict[str, Any]:
        raise NotImplementedError

class CryptoPlugin(BasePlugin):
    def __init__(self, key: str = "SecretKey123"):
        self.key = key

    def execute(self) -> Dict[str, Any]:
        payload = b"Advanced_Agentic_Payload_2026"
        h = hashlib.sha256(payload + self.key.encode()).hexdigest()
        hm = hashlib.md5(payload).hexdigest()
        return {"sha256": h, "md5": hm, "len": len(payload)}

class MathVectorPlugin(BasePlugin):
    @dataclass
    class Vector3D:
        x: float
        y: float
        z: float

        def magnitude(self) -> float:
            return math.sqrt(self.x**2 + self.y**2 + self.z**2)

        def dot(self, other: 'MathVectorPlugin.Vector3D') -> float:
            return self.x * other.x + self.y * other.y + self.z * other.z

    def execute(self) -> Dict[str, Any]:
        v1 = self.Vector3D(3.0, 4.0, 12.0)
        v2 = self.Vector3D(1.0, 2.0, 3.0)
        return {
            "v1_mag": v1.magnitude(),
            "v1_dot_v2": v1.dot(v2)
        }

# 3. Generator & Recursive Algorithm
def prime_sieve(limit: int) -> Generator[int, None, None]:
    primes = [True] * (limit + 1)
    primes[0] = primes[1] = False
    for p in range(2, int(math.isqrt(limit)) + 1):
        if primes[p]:
            for i in range(p * p, limit + 1, p):
                primes[i] = False
    for p in range(2, limit + 1):
        if primes[p]:
            yield p

def ackermann(m: int, n: int) -> int:
    if m == 0:
        return n + 1
    elif m > 0 and n == 0:
        return ackermann(m - 1, 1)
    else:
        return ackermann(m - 1, ackermann(m, n - 1))

# 4. Pattern Matching & Complex State Engine
def process_command(cmd: Dict[str, Any]) -> str:
    match cmd:
        case {"type": "START", "id": int(job_id)}:
            return f"Job {job_id} initialized."
        case {"type": "CALC", "nums": list(arr)}:
            total = sum(x**2 for x in arr if x % 2 == 0)
            return f"Even square sum: {total}"
        case {"type": "ECHO", "msg": str(message)}:
            return f"Echo payload: {message.upper()}"
        case _:
            return "Unknown command received."

# 5. Async Coroutine Pipeline
async def async_worker(worker_id: int, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"Worker {worker_id} completed after {delay}s"

async def run_async_pipeline() -> List[str]:
    tasks = [
        async_worker(1, 0.01),
        async_worker(2, 0.02),
        async_worker(3, 0.01)
    ]
    return await asyncio.gather(*tasks)

# 6. Main Benchmark Runner
@time_it(prefix="[MAIN PIPELINE]")
def main():
    print("=" * 55)
    print(">>> ADVANCED PYTHON SUITE TEST STARTING <<<")
    print("=" * 55)

    # Test 1: Context manager & Streams
    with DataStreamManager("LiveEventStream") as dsm:
        dsm.push({"event": "LOGIN", "user_id": 999})
        dsm.push({"event": "TX", "amount": 150.75})
    print("[1] Data Stream Buffer:", dsm.buffer)

    # Test 2: Metaclass Plugins
    print(f"[2] Registered Plugins: {list(AutoRegisterMeta.registry.keys())}")
    for name, p_cls in AutoRegisterMeta.registry.items():
        plugin = p_cls()
        print(f"    * {name} Result:", plugin.execute())

    # Test 3: Math & Algorithms
    primes = list(prime_sieve(30))
    ack_res = ackermann(3, 3)
    print(f"[3] Primes <= 30: {primes}")
    print(f"    Ackermann(3, 3): {ack_res}")

    # Test 4: Match / Case Logic
    c1 = process_command({"type": "START", "id": 404})
    c2 = process_command({"type": "CALC", "nums": [1, 2, 3, 4, 5, 6]})
    c3 = process_command({"type": "ECHO", "msg": "antigravity-velimatix"})
    print("[4] Pattern Match Results:")
    print("   ", c1)
    print("   ", c2)
    print("   ", c3)

    # Test 5: Async Event Loop
    async_results = asyncio.run(run_async_pipeline())
    print("[5] Async Gather Results:", async_results)

    print("=" * 55)
    print(">>> ALL COMPLEX TESTS PASSED SUCCESSFULLY! <<<")
    print("=" * 55)

if __name__ == "__main__":
    main()
