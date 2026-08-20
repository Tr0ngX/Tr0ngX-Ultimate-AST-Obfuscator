import sys, os, asyncio, collections, functools, math, time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

"""
Test 10: Master Complex Real-World Challenge Suite
Covers:
1. Metaclass Attribute Registry & Custom __prepare__
2. Descriptors Protocol (__set_name__, __get__, __set__, __delete__)
3. Diamond Multiple Inheritance & Cooperative super() MRO
4. AsyncIO Pipeline: Async Generators, Queue, Producer-Consumer & Context Manager
5. Bidirectional Coroutines (send, throw, yield from)
6. Recursive Descent Arithmetic & Boolean Expression Parser
7. Finite Field GF(2^8) Arithmetic & Rijndael S-Box Inversion
8. Montgomery Multiplication & Miller-Rabin Primality Testing
9. Structural Pattern Matching with Guards, Class & Sequence Patterns
10. Deep Closures with nonlocal, Currying & Decorator Stacking
"""

# ═══════════════════════════════════════════════════════════════
# 1. METACLASS ATTRIBUTE REGISTRY WITH CUSTOM __prepare__
# ═══════════════════════════════════════════════════════════════
class OrderedMeta(type):
    @classmethod
    def __prepare__(metacls, name, bases, **kwargs):
        return collections.OrderedDict()

    def __new__(metacls, name, bases, namespace, **kwargs):
        fields = [k for k, v in namespace.items() if not k.startswith("__") and not callable(v)]
        namespace["_field_order"] = fields
        cls = super().__new__(metacls, name, bases, dict(namespace))
        return cls

class SchemaModel(metaclass=OrderedMeta):
    id: int = 1
    username: str = "alice"
    email: str = "alice@example.com"
    is_active: bool = True

    def get_fields(self):
        return self._field_order

# ═══════════════════════════════════════════════════════════════
# 2. DESCRIPTORS PROTOCOL
# ═══════════════════════════════════════════════════════════════
class ValidatedNumber:
    def __init__(self, min_val=0, max_val=1000):
        self.min_val = min_val
        self.max_val = max_val

    def __set_name__(self, owner, name):
        self.storage_name = f"_{name}"

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return getattr(instance, self.storage_name, self.min_val)

    def __set__(self, instance, value):
        if not isinstance(value, (int, float)):
            raise TypeError(f"Value must be a number, got {type(value).__name__}")
        if not (self.min_val <= value <= self.max_val):
            raise ValueError(f"Value {value} out of bounds [{self.min_val}, {self.max_val}]")
        setattr(instance, self.storage_name, value)

class BankAccount:
    balance = ValidatedNumber(min_val=0, max_val=1000000)
    risk_score = ValidatedNumber(min_val=0, max_val=100)

    def __init__(self, initial_balance, score):
        self.balance = initial_balance
        self.risk_score = score

# ═══════════════════════════════════════════════════════════════
# 3. DIAMOND MULTIPLE INHERITANCE & COOPERATIVE super()
# ═══════════════════════════════════════════════════════════════
class BaseNode:
    def __init__(self, name, **kwargs):
        self.name = name
        self.trace = [f"BaseNode({name})"]
        super().__init__(**kwargs)

    def process(self, data):
        return [f"Base:{data}"]

class EncryptionNode(BaseNode):
    def __init__(self, key=42, **kwargs):
        super().__init__(**kwargs)
        self.key = key
        self.trace.append(f"EncryptionNode(key={key})")

    def process(self, data):
        parent_res = super().process(data)
        return parent_res + [f"Encrypted:{data ^ self.key}"]

class CompressionNode(BaseNode):
    def __init__(self, level=9, **kwargs):
        super().__init__(**kwargs)
        self.level = level
        self.trace.append(f"CompressionNode(lvl={level})")

    def process(self, data):
        parent_res = super().process(data)
        return parent_res + [f"Compressed:L{self.level}({data})"]

class PipelineNode(EncryptionNode, CompressionNode):
    def __init__(self, name="pipeline_root", key=1337, level=6):
        super().__init__(name=name, key=key, level=level)
        self.trace.append("PipelineNode(Ready)")

    def process(self, data):
        return super().process(data)

# ═══════════════════════════════════════════════════════════════
# 4. ASYNCIO PIPELINE & QUEUES & CONTEXT MANAGERS
# ═══════════════════════════════════════════════════════════════
class AsyncAuditSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.events = []

    async def __aenter__(self):
        self.events.append(f"OPEN_{self.session_id}")
        await asyncio.sleep(0.001)
        return self

    async def record(self, event):
        self.events.append(event)
        await asyncio.sleep(0.001)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.events.append(f"CLOSE_{self.session_id}")
        await asyncio.sleep(0.001)
        return False

async def async_num_generator(limit):
    for i in range(1, limit + 1):
        await asyncio.sleep(0.001)
        yield i * i

async def async_producer_consumer_test():
    queue = asyncio.Queue(maxsize=5)
    consumed = []

    async def producer():
        async for val in async_num_generator(5):
            await queue.put(val)
        await queue.put(None)

    async def consumer():
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            consumed.append(item + 10)
            queue.task_done()

    async with AsyncAuditSession("AUDIT_01") as session:
        await asyncio.gather(producer(), consumer())
        await session.record(f"TOTAL_CONSUMED_{len(consumed)}")

    return consumed, session.events

# ═══════════════════════════════════════════════════════════════
# 5. BIDIRECTIONAL COROUTINE WITH send, throw, yield from
# ═══════════════════════════════════════════════════════════════
class ResetSignal(Exception):
    pass

def sub_accumulator():
    total = 0
    while True:
        try:
            val = yield total
            if val is None:
                break
            total += val
        except ResetSignal:
            total = 0

def master_dispatcher():
    while True:
        res = yield from sub_accumulator()
        yield f"FINAL:{res}"

# ═══════════════════════════════════════════════════════════════
# 6. RECURSIVE DESCENT EXPRESSION PARSER
# ═══════════════════════════════════════════════════════════════
class Parser:
    def __init__(self, text, env=None):
        self.tokens = self.tokenize(text)
        self.pos = 0
        self.env = env or {}

    def tokenize(self, s):
        toks = []
        i = 0
        while i < len(s):
            if s[i].isspace():
                i += 1
            elif s[i] in "+-*/()":
                toks.append(s[i])
                i += 1
            elif s[i].isdigit():
                j = i
                while j < len(s) and s[j].isdigit():
                    j += 1
                toks.append(int(s[i:j]))
                i = j
            elif s[i].isalpha():
                j = i
                while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                    j += 1
                toks.append(s[i:j])
                i = j
            else:
                i += 1
        return toks

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self):
        t = self.peek()
        self.pos += 1
        return t

    def parse(self):
        return self.expr()

    def expr(self):
        res = self.term()
        while self.peek() in ("+", "-"):
            op = self.consume()
            right = self.term()
            res = (res + right) if op == "+" else (res - right)
        return res

    def term(self):
        res = self.factor()
        while self.peek() in ("*", "/"):
            op = self.consume()
            right = self.factor()
            res = (res * right) if op == "*" else (res // right)
        return res

    def factor(self):
        t = self.consume()
        if isinstance(t, int):
            return t
        elif isinstance(t, str) and t.isalnum() and t not in ("+", "-", "*", "/", "(", ")"):
            return self.env.get(t, 0)
        elif t == "(":
            res = self.expr()
            assert self.consume() == ")"
            return res
        raise ValueError(f"Unexpected token: {t}")

# ═══════════════════════════════════════════════════════════════
# 7. FINITE FIELD GF(2^8) & S-BOX GENERATION
# ═══════════════════════════════════════════════════════════════
def gf28_mult(a, b, poly=0x11B):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi_bit_set = a & 0x80
        a = (a << 1) & 0xFF
        if hi_bit_set:
            a ^= (poly & 0xFF)
        b >>= 1
    return p

def gf28_inv(a, poly=0x11B):
    if a == 0:
        return 0
    # By Fermat's Little Theorem in GF(2^8), a^(-1) = a^(254)
    res = 1
    base = a
    exp = 254
    while exp > 0:
        if exp & 1:
            res = gf28_mult(res, base, poly)
        base = gf28_mult(base, base, poly)
        exp >>= 1
    return res

# ═══════════════════════════════════════════════════════════════
# 8. MONTGOMERY MULTIPLICATION & MILLER-RABIN PRIMALITY TEST
# ═══════════════════════════════════════════════════════════════
def egcd(a, b):
    if a == 0:
        return (b, 0, 1)
    g, y, x = egcd(b % a, a)
    return (g, x - (b // a) * y, y)

def modinv(a, m):
    g, x, _ = egcd(a, m)
    if g != 1:
        raise ValueError("No inverse")
    return x % m

def montgomery_mult(a, b, N, R, R_inv, N_prime):
    # Montgomery multiplication: (a * b * R_inv) mod N
    T = a * b
    m = ((T & (R - 1)) * N_prime) & (R - 1)
    t = (T + m * N) // R
    if t >= N:
        t -= N
    return t

def miller_rabin(n, witnesses=(2, 3, 5, 7, 11, 13, 17)):
    if n < 2:
        return False
    if n in (2, 3, 5, 7):
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False

    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1

    for a in witnesses:
        if a >= n:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        composite = True
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                composite = False
                break
        if composite:
            return False
    return True

# ═══════════════════════════════════════════════════════════════
# 9. STRUCTURAL PATTERN MATCHING WITH GUARDS (PEP 634)
# ═══════════════════════════════════════════════════════════════
def dispatch_command(cmd_dict):
    match cmd_dict:
        case {"type": "TRANSFER", "amount": amt, "recipient": r} if amt > 1000:
            return f"HIGH_VALUE_TRANSFER_TO_{r}_{amt}"
        case {"type": "TRANSFER", "amount": amt, "recipient": r}:
            return f"STANDARD_TRANSFER_TO_{r}_{amt}"
        case {"type": "QUERY", "keys": [first, *rest]}:
            return f"QUERY_FIRST_{first}_REST_{len(rest)}"
        case {"type": "AUTH", "user": {"id": uid, "role": "admin"}}:
            return f"ADMIN_AUTH_{uid}"
        case _:
            return "UNKNOWN_COMMAND"

# ═══════════════════════════════════════════════════════════════
# 10. CLOSURES WITH NONLOCAL & DECORATOR CHAINS
# ═══════════════════════════════════════════════════════════════
def memoize_audit(func):
    cache = {}
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    wrapper.cache = cache
    return wrapper

def make_counter(start=0, step=1):
    count = start
    history = []
    def increment(delta=None):
        nonlocal count
        d = step if delta is None else delta
        count += d
        history.append(count)
        return count
    def get_history():
        return list(history)
    return increment, get_history

# ═══════════════════════════════════════════════════════════════
# MAIN TEST SUITE RUNNER
# ═══════════════════════════════════════════════════════════════
def run_all_checks():
    print("[TEST 10] Running Master Complex Real-World Challenge Suite...")

    # Check 1: Metaclass Attribute Registry
    m = SchemaModel()
    assert m.get_fields() == ["id", "username", "email", "is_active"]
    print("  [PASS] Metaclass __prepare__ Attribute Registry")

    # Check 2: Descriptors
    acc = BankAccount(500, 25)
    assert acc.balance == 500
    assert acc.risk_score == 25
    acc.balance = 2500
    assert acc.balance == 2500
    try:
        acc.balance = -10
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("  [PASS] Descriptor Protocol Validation")

    # Check 3: Diamond Multiple Inheritance
    pipe = PipelineNode(name="secure_pipe", key=0xAA, level=5)
    res = pipe.process(0x55)
    assert "BaseNode(secure_pipe)" in pipe.trace
    assert "PipelineNode(Ready)" in pipe.trace
    assert res == ["Base:85", "Compressed:L5(85)", "Encrypted:255"]
    print("  [PASS] Diamond Multiple Inheritance & Cooperative MRO")

    # Check 4: AsyncIO Pipeline & Queues
    consumed, audit_events = asyncio.run(async_producer_consumer_test())
    assert consumed == [11, 14, 19, 26, 35]  # [1^2+10, 2^2+10, 3^2+10, 4^2+10, 5^2+10]
    assert audit_events[0] == "OPEN_AUDIT_01"
    assert audit_events[-1] == "CLOSE_AUDIT_01"
    print("  [PASS] AsyncIO Queue Producer-Consumer & Context Manager")

    # Check 5: Bidirectional Coroutine
    acc_coro = sub_accumulator()
    next(acc_coro)
    assert acc_coro.send(10) == 10
    assert acc_coro.send(25) == 35
    acc_coro.throw(ResetSignal)
    assert acc_coro.send(5) == 5
    print("  [PASS] Coroutine Bidirectional Flow (send, throw)")

    # Check 6: Recursive Expression Parser
    p = Parser("10 + 2 * (alpha - 3) + 12 / beta", env={"alpha": 8, "beta": 4})
    # 10 + 2 * (8 - 3) + 12 / 4 = 10 + 2*5 + 3 = 10 + 10 + 3 = 23
    assert p.parse() == 23
    print("  [PASS] Recursive Descent Expression Parser & AST Evaluation")

    # Check 7: Finite Field GF(2^8)
    assert gf28_mult(0x57, 0x83) == 0xC1
    inv_57 = gf28_inv(0x57)
    assert gf28_mult(0x57, inv_57) == 1
    print("  [PASS] Finite Field GF(2^8) Arithmetic & Inversion")

    # Check 8: Montgomery Multiplication & Miller-Rabin
    N = 10007  # Prime
    R = 16384  # 2^14 > N
    R_inv = modinv(R, N)
    N_prime = (-modinv(N, R)) % R
    # Test (345 * 678) mod N
    a_R = (345 * R) % N
    b_R = (678 * R) % N
    c_R = montgomery_mult(a_R, b_R, N, R, R_inv, N_prime)
    c = montgomery_mult(c_R, 1, N, R, R_inv, N_prime)
    assert c == (345 * 678) % N
    assert miller_rabin(10007) is True
    assert miller_rabin(10011) is False
    assert miller_rabin(104729) is True
    print("  [PASS] Montgomery Multiplication & Miller-Rabin Primality")

    # Check 9: Structural Pattern Matching
    c1 = dispatch_command({"type": "TRANSFER", "amount": 5000, "recipient": "Bob"})
    assert c1 == "HIGH_VALUE_TRANSFER_TO_Bob_5000"
    c2 = dispatch_command({"type": "QUERY", "keys": ["name", "age", "role"]})
    assert c2 == "QUERY_FIRST_name_REST_2"
    c3 = dispatch_command({"type": "AUTH", "user": {"id": 99, "role": "admin"}})
    assert c3 == "ADMIN_AUTH_99"
    print("  [PASS] Structural Pattern Matching (PEP 634)")

    # Check 10: Closures & Nonlocal & Walrus Operator
    inc, get_hist = make_counter(start=100, step=5)
    assert inc() == 105
    assert inc(10) == 115
    assert inc() == 120
    assert get_hist() == [105, 115, 120]

    # Walrus in comprehension
    squares_gt_50 = [y for x in range(1, 15) if (y := x * x) > 50 and y < 150]
    assert squares_gt_50 == [64, 81, 100, 121, 144]
    print("  [PASS] Closures, Nonlocal State & Walrus Comprehensions")

    print("[TEST 10] >>> ALL CHECKS PASSED <<<\n")

if __name__ == "__main__":
    run_all_checks()
