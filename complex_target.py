"""
=============================================================================
 TR0NGX ULTIMATE CHALLENGE PAYLOAD - ADVANCED MULTI-PARADIGM SUITE
 Tests: Metaclasses, AsyncIO Pipelines, Decorators, Pattern Matching,
 Custom Stream Ciphers, Graph Solvers, Dynamic Reflection, Matrix Algebra
=============================================================================
"""
import sys
import os
import time
import math
import hashlib
import hmac
import asyncio
import threading
import collections
import heapq
import functools
import types
from dataclasses import dataclass, field
from typing import List, Dict, Any, Generator, Tuple, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# =============================================================================
# 1. DESCRIPTORS, METACLASS & IN-MEMORY REGISTRY
# =============================================================================
class ValidatedField:
    def __init__(self, expected_type, min_val=None, max_val=None):
        self.expected_type = expected_type
        self.min_val = min_val
        self.max_val = max_val
        self._storage_name = None

    def __set_name__(self, owner, name):
        self._storage_name = f"_field_{name}"

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return getattr(instance, self._storage_name, None)

    def __set__(self, instance, value):
        if not isinstance(value, self.expected_type):
            raise TypeError(f"Expected {self.expected_type}, got {type(value)}")
        if self.min_val is not None and value < self.min_val:
            raise ValueError(f"Value {value} < min {self.min_val}")
        if self.max_val is not None and value > self.max_val:
            raise ValueError(f"Value {value} > max {self.max_val}")
        setattr(instance, self._storage_name, value)


class EntityMeta(type):
    _registry: Dict[str, type] = {}

    def __new__(cls, name, bases, attrs):
        # Decorate only standard instance methods with call telemetry
        for k, v in list(attrs.items()):
            if isinstance(v, types.FunctionType) and not k.startswith("__"):
                attrs[k] = cls._wrap_telemetry(k, v)
        new_cls = super().__new__(cls, name, bases, attrs)
        if name != "BaseEntity":
            cls._registry[name] = new_cls
        return new_cls

    @staticmethod
    def _wrap_telemetry(func_name, func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, "_telemetry"):
                self._telemetry = collections.defaultdict(int)
            self._telemetry[func_name] += 1
            return func(self, *args, **kwargs)
        return wrapper


class BaseEntity(metaclass=EntityMeta):
    def get_call_count(self, method_name: str) -> int:
        return getattr(self, "_telemetry", {}).get(method_name, 0)


# =============================================================================
# 2. CUSTOM BITWISE CRYPTO & MATRIX COMPUTATION ENGINE
# =============================================================================
class BitMatrixEngine(BaseEntity):
    power_rating = ValidatedField(int, min_val=1, max_val=1000000)

    def __init__(self, rating: int = 777):
        self.power_rating = rating

    def matrix_multiply(self, size: int) -> int:
        """Matrix multiplication & trace computation"""
        A = [[(i * size + j + 1) for j in range(size)] for i in range(size)]
        B = [[(j * size + i + 1) for j in range(size)] for i in range(size)]
        C = [[sum(A[i][k] * B[k][j] for k in range(size)) for j in range(size)] for i in range(size)]
        trace = sum(C[i][i] for i in range(size))
        return trace

    def custom_stream_cipher(self, message: bytes, key: bytes) -> bytes:
        """Custom Salsa/ChaCha style bit-rotation cipher"""
        def rotl32(v, c):
            return ((v << c) & 0xFFFFFFFF) | (v >> (32 - c))

        state = [
            0x61707865, 0x3320646e, 0x79622d32, 0x6b206574,
            int.from_bytes(key[:4].ljust(4, b'\x00'), 'little'),
            int.from_bytes(key[4:8].ljust(4, b'\x00'), 'little'),
            int.from_bytes(key[8:12].ljust(4, b'\x00'), 'little'),
            int.from_bytes(key[12:16].ljust(4, b'\x00'), 'little'),
        ]

        # 4 Rounds of Quarter-Rounds
        for _ in range(4):
            state[0] = (state[0] + state[4]) & 0xFFFFFFFF
            state[3] ^= state[0]
            state[3] = rotl32(state[3], 16)

            state[2] = (state[2] + state[3]) & 0xFFFFFFFF
            state[1] ^= state[2]
            state[1] = rotl32(state[1], 12)

        keystream = b"".join(x.to_bytes(4, 'little') for x in state)
        # XOR encrypt
        return bytes(m ^ keystream[i % len(keystream)] for i, m in enumerate(message))


# =============================================================================
# 3. GENERATORS, DIJKSTRA GRAPH & TRIE SEARCH
# =============================================================================
class GraphTrieEngine(BaseEntity):
    class TrieNode:
        def __init__(self):
            self.children = {}
            self.is_terminal = False
            self.weight = 0

    def __init__(self):
        self.root = self.TrieNode()

    def insert_token(self, token: str, weight: int):
        curr = self.root
        for char in token:
            if char not in curr.children:
                curr.children[char] = self.TrieNode()
            curr = curr.children[char]
        curr.is_terminal = True
        curr.weight = weight

    def search_token(self, token: str) -> Optional[int]:
        curr = self.root
        for char in token:
            if char not in curr.children:
                return None
            curr = curr.children[char]
        return curr.weight if curr.is_terminal else None

    @staticmethod
    def solve_shortest_path(graph: Dict[str, Dict[str, int]], start: str) -> Dict[str, int]:
        distances = {node: float('inf') for node in graph}
        distances[start] = 0
        pq = [(0, start)]

        while pq:
            curr_dist, curr_node = heapq.heappop(pq)
            if curr_dist > distances[curr_node]:
                continue
            for neighbor, weight in graph[curr_node].items():
                distance = curr_dist + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    heapq.heappush(pq, (distance, neighbor))
        return distances

    @staticmethod
    def prime_generator(limit: int) -> Generator[int, None, None]:
        sieve = [True] * (limit + 1)
        sieve[0] = sieve[1] = False
        for p in range(2, int(math.isqrt(limit)) + 1):
            if sieve[p]:
                for i in range(p * p, limit + 1, p):
                    sieve[i] = False
        for p in range(2, limit + 1):
            if sieve[p]:
                yield p


# =============================================================================
# 4. PATTERN MATCHING & NESTED PIPELINE
# =============================================================================
@dataclass
class Packet:
    sender: str
    action: str
    meta: Dict[str, Any] = field(default_factory=dict)
    payload: Any = None


def route_packet(packet: Packet) -> Tuple[str, Any]:
    match packet:
        case Packet(sender="root", action="EXEC", meta={"auth": True, "level": int(lvl)}) if lvl >= 99:
            return ("SYSTEM_SUPERUSER_EXEC", hash(str(packet.payload)))
        case Packet(sender="admin", action="UPDATE", meta={"auth": True}):
            return ("ADMIN_UPDATE_OK", len(str(packet.payload)))
        case Packet(action="QUERY", payload=[str(first), *rest]):
            return (f"QUERY_{first.upper()}", len(rest))
        case Packet(action="PING"):
            return ("PONG", time.time_ns())
        case _:
            return ("REJECTED", 403)


# =============================================================================
# 5. ASYNC CONCURRENCY, PRODUCER-CONSUMER & REFLECTION
# =============================================================================
async def async_worker_task(task_id: int, channel: asyncio.Queue, results: list):
    while True:
        job = await channel.get()
        if job is None:
            channel.task_done()
            break
        # Compute dynamic hash
        h = hashlib.sha256(f"WORKER_{task_id}_{job}".encode()).hexdigest()
        results.append((task_id, job, h[:8]))
        channel.task_done()


async def run_async_pipeline(items: List[str]) -> List[Tuple[int, str, str]]:
    queue = asyncio.Queue()
    results = []
    num_workers = 3
    workers = [asyncio.create_task(async_worker_task(i, queue, results)) for i in range(num_workers)]

    for it in items:
        await queue.put(it)

    await queue.join()

    # Signal stop
    for _ in range(num_workers):
        await queue.put(None)
    await asyncio.gather(*workers)

    return sorted(results, key=lambda x: x[1])


# =============================================================================
# 6. MAIN VERIFICATION HARNESS
# =============================================================================
def main():
    print("=" * 65)
    print(">>> EXECUTING COMPLEX CHALLENGE TARGET PIPELINE <<<")
    print("=" * 65)

    # 1. Metaclass & Descriptors Check
    assert "BitMatrixEngine" in EntityMeta._registry
    assert "GraphTrieEngine" in EntityMeta._registry
    matrix_eng = BitMatrixEngine(rating=9999)
    assert matrix_eng.power_rating == 9999
    print("  [PASS] 1. Metaclass, Registry & Field Descriptors")

    # 2. Matrix Computation & Cipher
    trace_val = matrix_eng.matrix_multiply(size=4)
    assert trace_val == 1496, f"Trace expected 1496, got {trace_val}"
    
    secret = b"Tr0ngX_Advanced_Agentic_2026"
    key = b"MatrixKey1234567"
    enc = matrix_eng.custom_stream_cipher(secret, key)
    dec = matrix_eng.custom_stream_cipher(enc, key)
    assert dec == secret, "Stream cipher decryption mismatch!"
    assert matrix_eng.get_call_count("matrix_multiply") == 1
    assert matrix_eng.get_call_count("custom_stream_cipher") == 2
    print(f"  [PASS] 2. BitMatrix Engine & Stream Cipher (Trace: {trace_val})")

    # 3. Trie & Dijkstra Graph Solver
    gt_eng = GraphTrieEngine()
    gt_eng.insert_token("ANTIGRAVITY", 100)
    gt_eng.insert_token("VELIMATIX", 200)
    gt_eng.insert_token("TRONGX", 300)
    assert gt_eng.search_token("ANTIGRAVITY") == 100
    assert gt_eng.search_token("TRONGX") == 300
    assert gt_eng.search_token("UNKNOWN") is None

    graph = {
        'A': {'B': 4, 'C': 2},
        'B': {'A': 4, 'C': 1, 'D': 5},
        'C': {'A': 2, 'B': 1, 'D': 8, 'E': 10},
        'D': {'B': 5, 'D': 2, 'E': 2},
        'E': {'C': 10, 'D': 2}
    }
    shortest = gt_eng.solve_shortest_path(graph, 'A')
    assert shortest['A'] == 0
    assert shortest['B'] == 3
    assert shortest['C'] == 2
    assert shortest['D'] == 8
    assert shortest['E'] == 10
    
    primes_under_30 = list(gt_eng.prime_generator(30))
    assert primes_under_30 == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    print(f"  [PASS] 3. Prefix Trie, Dijkstra Graph & Prime Sieve")

    # 4. Structural Pattern Matching
    p1 = Packet(sender="root", action="EXEC", meta={"auth": True, "level": 100}, payload="SystemReboot")
    p2 = Packet(sender="admin", action="UPDATE", meta={"auth": True}, payload={"config": "v2"})
    p3 = Packet(sender="guest", action="QUERY", payload=["users", "active", "today"])
    p4 = Packet(sender="anyone", action="PING")

    r1 = route_packet(p1)
    r2 = route_packet(p2)
    r3 = route_packet(p3)
    r4 = route_packet(p4)

    assert r1[0] == "SYSTEM_SUPERUSER_EXEC"
    assert r2 == ("ADMIN_UPDATE_OK", len(str({"config": "v2"})))
    assert r3 == ("QUERY_USERS", 2)
    assert r4[0] == "PONG"
    print("  [PASS] 4. PEP 634 Structural Pattern Matching & Destructuring")

    # 5. AsyncIO Pipeline
    items = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
    async_results = asyncio.run(run_async_pipeline(items))
    assert len(async_results) == 5
    assert [x[1] for x in async_results] == ["Alpha", "Beta", "Delta", "Epsilon", "Gamma"]
    print("  [PASS] 5. AsyncIO Producer-Consumer Queue & Concurrency")

    print("=" * 65)
    print(">>> ALL TESTS PASSED! PAYLOAD FULLY OPERATIONAL <<<")
    print("=" * 65)


if __name__ == "__main__":
    main()
