"""
═══════════════════════════════════════════════════════════════════════════════
 Tr0ngX Extreme Master Benchmark - Multi-Paradigm Complex Python Suite
 Combines: Metaclasses, AsyncIO, Custom Cryptography, Matrix Algebra,
 Advanced Data Structures, Pattern Matching, Dynamic Reflection & AST Invariance
═══════════════════════════════════════════════════════════════════════════════
"""
import sys, os, time, math, hashlib, hmac, asyncio, threading, collections, heapq, functools, types, dataclasses

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 1. METACLASS & COMPONENT REGISTRY
class PluginMeta(type):
    registry = {}
    def __new__(cls, name, bases, attrs):
        new_cls = super().__new__(cls, name, bases, attrs)
        if name != "BaseComponent":
            cls.registry[name] = new_cls
        return new_cls

class BaseComponent(metaclass=PluginMeta):
    def run(self, payload):
        raise NotImplementedError

class SecureCryptoComponent(BaseComponent):
    def run(self, payload: str):
        h1 = hashlib.sha256(payload.encode()).hexdigest()
        h2 = hmac.new(b"TR0NGX_MATRIX_KEY", h1.encode(), hashlib.sha256).hexdigest()
        return {"sha256": h1, "hmac": h2}

class MatrixMathComponent(BaseComponent):
    def run(self, dim: int):
        A = [[(i * dim + j + 1) for j in range(dim)] for i in range(dim)]
        B = [[(j * dim + i + 1) for j in range(dim)] for i in range(dim)]
        C = [[sum(A[i][k] * B[k][j] for k in range(dim)) for j in range(dim)] for i in range(dim)]
        trace = sum(C[i][i] for i in range(dim))
        return {"dim": dim, "trace": trace, "cell_0_0": C[0][0]}

# 2. ADVANCED DATA STRUCTURES: TRIE, LRU CACHE & DIJKSTRA
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class PrefixTrie:
    def __init__(self):
        self.root = TrieNode()
    def insert(self, word):
        curr = self.root
        for ch in word:
            if ch not in curr.children:
                curr.children[ch] = TrieNode()
            curr = curr.children[ch]
        curr.is_end = True
    def search(self, word):
        curr = self.root
        for ch in word:
            if ch not in curr.children:
                return False
            curr = curr.children[ch]
        return curr.is_end

def dijkstra_solver(graph, start_node):
    dist = {n: float('inf') for n in graph}
    dist[start_node] = 0
    pq = [(0, start_node)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, weight in graph[u].items():
            if dist[u] + weight < dist[v]:
                dist[v] = dist[u] + weight
                heapq.heappush(pq, (dist[v], v))
    return dist

# 3. SPN BLOCK CIPHER (SUBSTITUTION-PERMUTATION NETWORK)
SBOX = [0xE, 0x4, 0xD, 0x1, 0x2, 0xF, 0xB, 0x8, 0x3, 0xA, 0x6, 0xC, 0x5, 0x9, 0x0, 0x7]
def spn_sub(val):
    return (SBOX[(val >> 12) & 0xF] << 12) | (SBOX[(val >> 8) & 0xF] << 8) | (SBOX[(val >> 4) & 0xF] << 4) | SBOX[val & 0xF]

def spn_perm(val):
    p = [0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15]
    res = 0
    for i in range(16):
        if (val >> i) & 1:
            res |= (1 << p[i])
    return res

def spn_encrypt(block16: int, subkeys: list[int]) -> int:
    state = block16 ^ subkeys[0]
    for r in range(1, 4):
        state = spn_sub(state)
        state = spn_perm(state)
        state ^= subkeys[r]
    state = spn_sub(state)
    state ^= subkeys[4]
    return state

# 4. PATTERN MATCHING & GENERATOR PIPELINE
def stream_evaluator(stream):
    results = []
    for item in stream:
        match item:
            case {"op": "AUTH", "user": str(u), "token": int(t)} if t > 5000:
                results.append(f"SUPER_USER_{u.upper()}")
            case {"op": "AUTH", "user": str(u)}:
                results.append(f"NORMAL_USER_{u}")
            case {"op": "TX", "amount": float(amt), "fee": float(f)}:
                results.append(f"NET_TX_{amt - f:.2f}")
            case ["COMMAND", cmd_name, *args]:
                results.append(f"EXEC_{cmd_name}_{len(args)}_ARGS")
            case _:
                results.append("FALLBACK_ITEM")
    return results

def prime_stream(limit):
    is_p = [True] * (limit + 1)
    is_p[0] = is_p[1] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_p[i]:
            for j in range(i * i, limit + 1, i):
                is_p[j] = False
    for idx, prime in enumerate(is_p):
        if prime:
            yield idx

# 5. ASYNCIO CONCURRENCY & WORKER GATHER
async def async_node_task(node_id: int, payload_size: int):
    await asyncio.sleep(0.01)
    digest = hashlib.sha256(f"NODE_{node_id}_{payload_size}".encode()).hexdigest()[:12]
    return f"NODE_{node_id}:{digest}"

async def run_async_network():
    tasks = [async_node_task(i, i * 256) for i in range(1, 6)]
    res = await asyncio.gather(*tasks)
    return res

# 6. PROPERTY DESCRIPTOR & DYNAMIC RUNTIME SYNTHESIS
class FloatBoundValidator:
    def __init__(self, min_val: float, max_val: float):
        self.min_val = min_val
        self.max_val = max_val
    def __set_name__(self, owner, name):
        self.attr_name = f"_validated_{name}"
    def __get__(self, instance, owner):
        if instance is None: return self
        return getattr(instance, self.attr_name, self.min_val)
    def __set__(self, instance, value: float):
        if not (self.min_val <= value <= self.max_val):
            raise ValueError(f"Value {value} out of bounds [{self.min_val}, {self.max_val}]")
        setattr(instance, self.attr_name, value)

class ReactorCore:
    efficiency = FloatBoundValidator(0.0, 1.0)
    temperature = FloatBoundValidator(-100.0, 5000.0)
    def __init__(self, eff: float, temp: float):
        self.efficiency = eff
        self.temperature = temp

def compile_dynamic_evaluator(expr_str: str):
    code = compile(f"def dyn_eval(x, y): return {expr_str}", "<dynamic_eval>", "exec")
    scope = {}
    types.FunctionType(code, scope)()
    for k, v in scope.items():
        if callable(v):
            return v
    exec(code, scope)
    return scope["dyn_eval"]

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION SUITE
# ═══════════════════════════════════════════════════════════════
def main():
    t_start = time.perf_counter()
    print("=" * 65)
    print(">>> TR0NGX EXTREME MASTER BENCHMARK STARTING <<<")
    print("=" * 65)

    # 1. Metaclass verification
    assert "SecureCryptoComponent" in PluginMeta.registry
    assert "MatrixMathComponent" in PluginMeta.registry
    crypto_comp = SecureCryptoComponent()
    c_res = crypto_comp.run("TR0NGX_ULTIMATE_MAX_PAYLOAD")
    assert len(c_res["sha256"]) == 64 and len(c_res["hmac"]) == 64
    print(f"[1] Metaclass Component Result: HMAC={c_res['hmac'][:16]}...")

    matrix_comp = MatrixMathComponent()
    m_res = matrix_comp.run(4)
    assert m_res["trace"] == 1496 and m_res["cell_0_0"] == 30
    print(f"[2] Matrix Multiplication Trace (4x4): {m_res['trace']}, cell(0,0): {m_res['cell_0_0']}")

    # 2. Prefix Trie & Dijkstra
    trie = PrefixTrie()
    for w in ["hypervisor", "hyperloop", "hybrid", "obfuscation", "antigravity"]:
        trie.insert(w)
    assert trie.search("hybrid") is True
    assert trie.search("hyb") is False
    print("  * Prefix Trie Verification: SUCCESS")

    graph = {
        'S': {'A': 7, 'B': 2, 'C': 3},
        'A': {'S': 7, 'B': 3, 'D': 4},
        'B': {'S': 2, 'A': 3, 'D': 4, 'H': 1},
        'C': {'S': 3, 'L': 2},
        'D': {'A': 4, 'B': 4, 'F': 5},
        'H': {'B': 1, 'F': 3, 'G': 2},
        'L': {'C': 2, 'I': 4, 'J': 4},
        'I': {'L': 4, 'J': 6, 'K': 4},
        'J': {'L': 4, 'I': 6, 'K': 4},
        'K': {'I': 4, 'J': 4, 'E': 5},
        'F': {'D': 5, 'H': 3, 'E': 3},
        'G': {'H': 2, 'E': 2},
        'E': {'K': 5, 'F': 3, 'G': 2}
    }
    shortest_paths = dijkstra_solver(graph, 'S')
    assert shortest_paths['E'] == 7
    print(f"[3] Graph Dijkstra Shortest Path S->E: {shortest_paths['E']} (Expected: 7)")

    # 3. SPN Block Cipher
    keys = [0x1023, 0x4567, 0x89AB, 0xCDEF, 0x55AA]
    raw_block = 0xBEEF
    enc_block = spn_encrypt(raw_block, keys)
    assert enc_block != raw_block
    print(f"[4] SPN Cipher Block: 0x{raw_block:04X} -> Encrypted: 0x{enc_block:04X}")

    # 4. Pattern Matching & Primes
    event_stream = [
        {"op": "AUTH", "user": "tr0ngx", "token": 9999},
        {"op": "AUTH", "user": "guest"},
        {"op": "TX", "amount": 1050.50, "fee": 12.25},
        ["COMMAND", "DEPLOY_ORCHESTRATOR", "node_1", "node_2", "node_3"],
        {"unrecognized": True}
    ]
    eval_res = stream_evaluator(event_stream)
    assert eval_res[0] == "SUPER_USER_TR0NGX"
    assert eval_res[2] == "NET_TX_1038.25"
    assert eval_res[3] == "EXEC_DEPLOY_ORCHESTRATOR_3_ARGS"
    print(f"[5] Pattern Matching Stream Output: {eval_res[:3]}")

    primes_50 = list(prime_stream(50))
    assert primes_50 == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
    print(f"  * Primes <= 50: {primes_50}")

    # 5. AsyncIO Concurrency
    async_out = asyncio.run(run_async_network())
    assert len(async_out) == 5
    print(f"[6] AsyncIO Multi-Node Concurrency: {async_out[:3]}...")

    # 6. Descriptors & Dynamic Code Synthesis
    reactor = ReactorCore(0.92, 1450.0)
    assert reactor.efficiency == 0.92 and reactor.temperature == 1450.0
    try:
        reactor.efficiency = 1.50
        assert False, "Descriptor validation failed"
    except ValueError:
        pass
    print("  * Property Descriptors Bounds: VERIFIED")

    dyn_fn = compile_dynamic_evaluator("(x ** 3) + (y * 5) - 42")
    assert dyn_fn(4, 10) == (64 + 50 - 42)
    print(f"[7] Runtime Function Type Synthesis: dyn_fn(4, 10) = {dyn_fn(4, 10)}")

    elapsed = time.perf_counter() - t_start
    print("=" * 65)
    print(f">>> ALL EXTREME MASTER BENCHMARK TESTS PASSED (took {elapsed:.4f}s) <<<")
    print("=" * 65)

if __name__ == "__main__":
    main()
