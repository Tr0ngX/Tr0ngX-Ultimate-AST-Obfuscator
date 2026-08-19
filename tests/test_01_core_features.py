import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
"""
Test 01: Core Python Features & Advanced Language Constructs
Tests: Metaclasses, AsyncIO, Generators, Decorators, Context Managers, Pattern Matching
"""
import sys, asyncio, threading, time

class MetaRegistry(type):
    registry = {}
    def __new__(cls, name, bases, attrs):
        new_cls = super().__new__(cls, name, bases, attrs)
        if name != "BasePlugin":
            cls.registry[name] = new_cls
        return new_cls

class BasePlugin(metaclass=MetaRegistry):
    def execute(self):
        raise NotImplementedError

class AuthPlugin(BasePlugin):
    def execute(self):
        return "AUTH_SUCCESS"

class StreamPlugin(BasePlugin):
    def execute(self):
        return "STREAM_SUCCESS"

# Async Coroutine Test
async def async_worker(idx, delay):
    await asyncio.sleep(delay)
    return f"WORKER_{idx}_DONE"

async def async_main():
    tasks = [async_worker(i, 0.01) for i in range(1, 4)]
    results = await asyncio.gather(*tasks)
    return results

# Generator / Coroutine Pipeline
def number_pipeline(limit):
    for i in range(limit):
        if i % 2 == 0:
            yield i * i

# Pattern Matching & Destructuring
def process_command(cmd):
    match cmd:
        case {"type": "LOGIN", "user": str(u), "level": int(lvl)} if lvl >= 10:
            return f"ADMIN_{u}"
        case {"type": "LOGIN", "user": str(u)}:
            return f"USER_{u}"
        case ["QUERY", *items]:
            return f"QUERY_LEN_{len(items)}"
        case _:
            return "UNKNOWN"

def run_suite():
    print("[TEST 01] Running Core Features Test Suite...")
    
    # 1. Metaclass verification
    assert "AuthPlugin" in MetaRegistry.registry
    assert "StreamPlugin" in MetaRegistry.registry
    assert AuthPlugin().execute() == "AUTH_SUCCESS"
    assert StreamPlugin().execute() == "STREAM_SUCCESS"
    print("  [PASS] Metaclass Registry Passed")

    # 2. Async verification
    async_res = asyncio.run(async_main())
    assert async_res == ["WORKER_1_DONE", "WORKER_2_DONE", "WORKER_3_DONE"]
    print("  [PASS] AsyncIO Concurrency Passed")

    # 3. Generator Pipeline
    gen_res = list(number_pipeline(10))
    assert gen_res == [0, 4, 16, 36, 64]
    print("  [PASS] Generator Pipeline Passed")

    # 4. Pattern Matching
    assert process_command({"type": "LOGIN", "user": "alice", "level": 15}) == "ADMIN_alice"
    assert process_command({"type": "LOGIN", "user": "bob", "level": 2}) == "USER_bob"
    assert process_command(["QUERY", 1, 2, 3, 4]) == "QUERY_LEN_4"
    print("  [PASS] Structural Pattern Matching Passed")

    print("[TEST 01] >>> ALL CHECKS PASSED <<<\n")

if __name__ == "__main__":
    run_suite()
