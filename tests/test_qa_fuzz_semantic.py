"""QA harness: real bytecode-packet fuzzing, semantic differential, reproducibility."""
import os
import sys
import zlib
import hmac
import random
import marshal
import hashlib
import secrets
import shutil
import tempfile
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBFUSCATOR = os.path.join(ROOT, "main.py")
REPORT_PATH = os.path.join(ROOT, "qa_report.txt")

BUILD_TIMEOUT = 240
EXEC_TIMEOUT = 60

try:
    FUZZ_COUNT = max(300, int(os.environ.get("TRX_FUZZ_COUNT", "400")))
except ValueError:
    FUZZ_COUNT = 400
try:
    FUZZ_SEED = int(os.environ.get("TRX_FUZZ_SEED", "1337"))
except ValueError:
    FUZZ_SEED = 1337

PHASE_RESULTS = []
FAILURES = []


class Phase:
    def __init__(self, name):
        self.name = name
        self.cases = 0
        self.passed = 0
        self.failed = 0

    def check(self, cond, ok_msg, fail_msg):
        self.cases += 1
        if cond:
            self.passed += 1
            log("PASS [%s] %s" % (self.name, ok_msg))
            return True
        self.failed += 1
        record_failure(self.name, fail_msg)
        return False

    def finish(self):
        PHASE_RESULTS.append((self.name, self.cases, self.passed, self.failed))


def log(msg):
    print("[QA] " + str(msg), flush=True)
    try:
        with open(REPORT_PATH, "a", encoding="utf-8") as f:
            f.write("[QA] " + str(msg) + "\n")
    except OSError:
        pass


def record_failure(phase, msg):
    FAILURES.append((phase, msg))
    log("FAIL [%s] %s" % (phase, msg))


SCRATCH_DIR = tempfile.mkdtemp(prefix="trx_qa_fuzz_")


def scratch(name):
    return os.path.join(SCRATCH_DIR, name)


def write_source(name, text):
    path = scratch(name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def run_proc(cmd, timeout):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )


def obfuscate(src_path, out_path, extra_flags):
    cmd = [sys.executable, OBFUSCATOR, "-i", src_path, "-o", out_path, "--no-art"]
    cmd.extend(extra_flags)
    return run_proc(cmd, BUILD_TIMEOUT)


def exec_file(path):
    return run_proc([sys.executable, path], EXEC_TIMEOUT)


def tail(text, limit=600):
    text = text or ""
    if len(text) > limit:
        return text[-limit:]
    return text


# ---------------------------------------------------------------------------
# Phase 1: AST node coverage matrix
# ---------------------------------------------------------------------------

AST_RICH_SOURCE = '''
import math

GLOB_ACCUMULATOR = 0

def bump(amount):
    global GLOB_ACCUMULATOR
    GLOB_ACCUMULATOR += amount
    return GLOB_ACCUMULATOR

def outer(x, y=2, *args, **kwargs):
    def inner(v):
        nonlocal_scale = v * 3
        return nonlocal_scale
    total = inner(x) + y + sum(args)
    if kwargs.get("scale"):
        total *= kwargs["scale"]
    return total

def apply_twice(fn, value):
    return fn(fn(value))

square = lambda v: v * v

matrix = [[r * c for c in range(1, 5)] for r in range(1, 5)]
flat = {v for row in matrix for v in row}
lookup = {idx: val % 7 for idx, val in enumerate(range(10, 25))}

class Engine:
    registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Engine.registry[cls.__name__] = cls

    def __init__(self, factor):
        self.factor = factor

    def run(self, value):
        try:
            result = value / self.factor
        except ZeroDivisionError:
            result = -1
        finally:
            bump(1)
        return result

class TurboEngine(Engine):
    def run(self, value):
        base = super().run(value)
        return base if base < 0 else base * 10

def rank(values):
    ranked = sorted(values, reverse=True)
    del ranked[0]
    return ranked[:3]

def main():
    bump(5)
    engine = TurboEngine(factor=2)
    parts = [
        outer(3, 4, 5, 6, scale=2),
        apply_twice(square, 7),
        math.isqrt(int(engine.run(48))),
        len(flat),
        lookup[3],
        len(Engine.registry),
        sum(rank([9, 1, 8, 2, 7, 3])),
    ]
    print("RESULT_AST=%d" % sum(parts))

main()
assert GLOB_ACCUMULATOR > 0
'''


def phase_ast_coverage():
    phase = Phase("AST_COVERAGE")
    log("=== PHASE 1: AST Node Coverage Matrix ===")
    src = write_source("qa_ast_src.py", AST_RICH_SOURCE)
    out = scratch("qa_ast_out.py")
    flags = ["-m", "3", "--hyperion", "y", "--velimatix", "y", "--veli-level", "2"]
    try:
        res = obfuscate(src, out, flags)
        if not phase.check(res.returncode == 0, "obfuscator accepted AST-heavy program (-m 3 --hyperion)",
                           "build failed rc=%s stderr=%s" % (res.returncode, tail(res.stderr))):
            phase.finish()
            return
        with open(out, "r", encoding="utf-8", errors="replace") as f:
            built_source = f.read()
        syntax_err = ""
        try:
            compile(built_source, out, "exec")
            compiled_ok = True
        except SyntaxError as exc:
            compiled_ok = False
            syntax_err = repr(exc)
        phase.check(compiled_ok, "obfuscated output compiles cleanly",
                    "obfuscated output does not compile: %s" % syntax_err)
        native = run_proc([sys.executable, src], EXEC_TIMEOUT)
        obf_exec = exec_file(out)
        phase.check(native.returncode == 0, "native AST program executed",
                    "native program failed rc=%s stderr=%s" % (native.returncode, tail(native.stderr)))
        phase.check(obf_exec.returncode == 0, "obfuscated AST program executed",
                    "obfuscated program failed rc=%s stderr=%s" % (obf_exec.returncode, tail(obf_exec.stderr)))
        phase.check(bool(native.stdout) and native.stdout == obf_exec.stdout,
                    "obfuscated stdout matches native stdout exactly",
                    "stdout mismatch native=%r obfuscated=%r" % (native.stdout[:200], obf_exec.stdout[:200]))
    except subprocess.TimeoutExpired as exc:
        phase.check(False, "", "timeout during AST coverage build/exec: %r" % exc)
    phase.finish()


# ---------------------------------------------------------------------------
# Phase 2: semantic differential suite (native vs obfuscated stdout)
# ---------------------------------------------------------------------------

SEMANTIC_DEFAULT_FLAGS = ["-m", "2", "--vm-obf", "y", "--vm-level", "2", "--moreobf", "y",
                          "--math-opaque", "y", "--dyn-strings", "y", "--velimatix", "y",
                          "--veli-level", "1", "--seed", "4242"]

AST_ONLY_FLAGS = ["-m", "3", "--moreobf", "y", "--math-opaque", "y", "--dyn-strings", "y",
                  "--velimatix", "y", "--veli-level", "2", "--seed", "4242"]

SEMANTIC_PROGRAMS = [
    ("recursion_math", None, '''
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)

def fact(n):
    return 1 if n <= 1 else n * fact(n - 1)

def prime_sum(limit):
    flags = [True] * (limit + 1)
    flags[0] = flags[1] = False
    i = 2
    while i * i <= limit:
        if flags[i]:
            step = i
            start = i * i
            for j in range(start, limit + 1, step):
                flags[j] = False
        i += 1
    total = 0
    idx = 0
    for flag in flags:
        if flag:
            total += idx
        idx += 1
    return total

print("RESULT_FIB=%d" % fib(16))
print("RESULT_FACT=%d" % fact(9))
print("RESULT_PRIMES=%d" % prime_sum(60))
'''),
    ("collections_strings", None, '''
TEXT = "the quick brown fox jumps over the lazy dog the fox"
words = TEXT.split()
freq = {}
for word in words:
    freq[word] = freq.get(word, 0) + 1
top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
print("RESULT_TOP=%s" % "|".join("%s:%d" % kv for kv in top))
unique_letters = {ch for ch in TEXT if ch != " "}
print("RESULT_UNIQUE=%d" % len(unique_letters))
print("RESULT_REVERSE=%s" % TEXT[::-1][:11])
pairs = [(k, v * 2) for k, v in freq.items() if v >= 2]
print("RESULT_PAIRS=%d" % sum(v for _, v in pairs))
'''),
    ("oop_classes", None, '''
class Shape:
    kind = "shape"

    def __init__(self, size):
        self._size = size

    @property
    def area(self):
        raise NotImplementedError

    def describe(self):
        return "%s(%d)" % (self.kind, self.area)


class Square(Shape):
    kind = "square"

    @property
    def area(self):
        return self._size * self._size


class Cube(Square):
    kind = "cube"

    @property
    def area(self):
        return 6 * Square.area.fget(self)

shapes = [Square(3), Square(4), Cube(3)]
print("RESULT_SHAPES=%s" % ",".join(s.describe() for s in shapes))
print("RESULT_TOTAL_AREA=%d" % sum(s.area for s in shapes))
'''),
    ("control_flow_match", AST_ONLY_FLAGS, '''
def classify(value):
    match value:
        case {"op": "add", "args": [int(a), int(b)]}:
            return a + b
        case {"op": "mul", **rest} if len(rest) == 1:
            return list(rest.values())[0]
        case [0, *tail]:
            return sum(tail)
        case str() as text:
            return len(text)
        case _:
            return -1

def risky(op, a, b):
    try:
        if op == "div":
            return a // b
        raise KeyError(op)
    except ZeroDivisionError:
        return "ZERO_DIV"
    except KeyError as err:
        return "MISSING:%s" % err
    finally:
        pass

def make_counter(start):
    state = [start]

    def inc(step=1):
        state[0] += step
        return state[0]

    return inc

counter = make_counter(10)
values = [counter(), counter(5), counter()]
print("RESULT_MATCH=%d,%d,%d,%d,%d" % (
    classify({"op": "add", "args": [20, 22]}),
    classify({"op": "mul", "x": 7}),
    classify([0, 4, 6, 8]),
    classify("hello"),
    classify(3.14),
))
print("RESULT_RISKY=%s|%s|%s" % (risky("div", 84, 6), risky("div", 1, 0), risky("noop", 1, 2)))
print("RESULT_CLOSURE=%s" % "|".join(str(v) for v in values))
'''),
]


def phase_semantic_differential():
    log("=== PHASE 2: Semantic Differential Suite ===")
    for prog_name, flag_override, source in SEMANTIC_PROGRAMS:
        phase = Phase("SEMANTIC:" + prog_name)
        flags = SEMANTIC_DEFAULT_FLAGS if flag_override is None else flag_override
        src = write_source("qa_sem_%s.py" % prog_name, source)
        out = scratch("qa_sem_%s_out.py" % prog_name)
        native = None
        obf_exec = None
        try:
            native = run_proc([sys.executable, src], EXEC_TIMEOUT)
            phase.check(native.returncode == 0 and bool(native.stdout),
                        "native reference ran",
                        "native failed rc=%s stderr=%s" % (native.returncode, tail(native.stderr)))
            res = obfuscate(src, out, flags)
            if not phase.check(res.returncode == 0 and os.path.exists(out),
                               "CLI build succeeded (%s)" % " ".join(flags[:2] + ["..."]),
                               "build failed rc=%s stderr=%s" % (res.returncode, tail(res.stderr))):
                phase.finish()
                continue
            obf_exec = exec_file(out)
            phase.check(obf_exec.returncode == 0,
                        "obfuscated program exited zero",
                        "exec failed rc=%s stderr=%s" % (obf_exec.returncode, tail(obf_exec.stderr)))
            if native.returncode == 0 and obf_exec is not None:
                native_lines = [ln for ln in native.stdout.splitlines() if ln.startswith("RESULT")]
                obf_lines = [ln for ln in (obf_exec.stdout or "").splitlines() if ln.startswith("RESULT")]
                phase.check(native_lines == obf_lines and bool(native_lines),
                            "all RESULT lines identical (%d lines)" % len(native_lines),
                            "output mismatch native=%r obfuscated=%r stderr=%s" %
                            (native_lines, obf_lines, tail(obf_exec.stderr if obf_exec else "")))
                phase.check(native.stdout == obf_exec.stdout,
                            "full stdout byte-identical",
                            "stdout differs beyond RESULT lines: native=%r obfuscated=%r" %
                            (native.stdout[:200], (obf_exec.stdout or "")[:200]))
        except subprocess.TimeoutExpired as exc:
            stage = "build" if native is not None and native.returncode == 0 else "run"
            phase.check(False, "", "timeout during %s: %r" % (stage, exc))
        phase.finish()


# ---------------------------------------------------------------------------
# Phase 3: real mutation fuzzing against the TVM AEAD packet format
# ---------------------------------------------------------------------------

def load_engine_module():
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import tr0ngx_obfuscator
    return tr0ngx_obfuscator


def tvm_keystream(k_enc, nonce, length):
    ks = bytearray()
    counter = 0
    while len(ks) < length:
        ks.extend(hashlib.sha256(k_enc + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    return bytes(ks[:length])


def tvm_decrypt(packet, k_enc, k_mac):
    """Faithful port of the emitted runtime decrypt_packet().

    The production decoder calls os._exit(1) on tampered input; here every
    rejection raises instead so the test process survives hostile packets.
    """
    if len(packet) < 48:
        raise ValueError("packet shorter than 48-byte AEAD header")
    nonce = packet[:16]
    tag = packet[16:48]
    ciphertext = packet[48:]
    expected_tag = hmac.new(k_mac, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("HMAC authentication failed")
    ks = tvm_keystream(k_enc, nonce, len(ciphertext))
    return bytes(c ^ k for c, k in zip(ciphertext, ks))


def vm_decode_packet(packet, k_enc, k_mac):
    """Mirror of the emitted decode_code() + TVMCodeObject init structural probe."""
    raw = zlib.decompress(tvm_decrypt(packet, k_enc, k_mac))
    data = marshal.loads(raw)
    if not isinstance(data, (tuple, list)) or len(data) != 9:
        raise ValueError("malformed TVM code object field count")
    name, arg_names, kwonly_names, vararg_name, kwarg_name, local_names, bytecode, constants, names = data
    if not isinstance(name, str):
        raise ValueError("code object name is not a string")
    if not isinstance(bytecode, (bytes, bytearray)):
        raise ValueError("instruction stream is not bytes")
    if not isinstance(constants, (tuple, list)):
        raise ValueError("constants pool malformed")
    if not isinstance(names, (tuple, list)):
        raise ValueError("names pool malformed")
    for pool in (arg_names, kwonly_names, local_names):
        if not isinstance(pool, (tuple, list)):
            raise ValueError("argument name pool malformed")
    list(constants)
    return data


def _rand_bytes(rng, lo, hi):
    return bytes(rng.randrange(256) for _ in range(rng.randint(lo, hi)))


def mutate_bytecode_packet(packet: bytes, rng) -> bytes:
    """Apply one randomly chosen malformation strategy to a packet."""
    buf = bytearray(packet)
    strategy = rng.randrange(8)
    if strategy == 0:
        pos = rng.randrange(len(buf))
        buf[pos] ^= 1 << rng.randrange(8)
    elif strategy == 1:
        for _ in range(rng.randint(2, 16)):
            pos = rng.randrange(len(buf))
            buf[pos] ^= rng.randrange(1, 256)
    elif strategy == 2:
        cut = rng.randrange(1, max(2, len(buf)))
        buf = buf[:cut]
    elif strategy == 3:
        buf[:0] = _rand_bytes(rng, 1, 96)
    elif strategy == 4:
        buf.extend(_rand_bytes(rng, 1, 96))
    elif strategy == 5:
        start = rng.randrange(len(buf))
        span = rng.randint(1, max(1, len(buf) // 2))
        for i in range(start, min(len(buf), start + span)):
            buf[i] = 0
    elif strategy == 6:
        head_len = rng.randint(1, 8)
        mode = rng.randrange(3)
        for i in range(min(head_len, len(buf))):
            if mode == 0:
                buf[i] ^= rng.randrange(1, 256)
            elif mode == 1:
                buf[i] = rng.randrange(256)
            else:
                buf[i] = 0xFF
    else:
        pattern = _rand_bytes(rng, 2, 12)
        blob = pattern * rng.randint(2, 24)
        pos = rng.randrange(len(buf) + 1)
        buf[pos:pos] = blob
    return bytes(buf)


def mutate_inner_payload(mod, packet, keys, rng):
    """Corrupt the plaintext payload, then re-wrap it with the REAL encryptor.

    The forged tag is valid, so these mutants reach the zlib/marshal/structural
    layers instead of dying at HMAC verification.
    """
    k_enc, k_mac = keys
    plaintext = zlib.decompress(tvm_decrypt(packet, k_enc, k_mac))
    corrupted = mutate_bytecode_packet(plaintext, rng)
    return mod._tvm_aead_encrypt(zlib.compress(corrupted, 9), k_enc, k_mac)


def _encode_instructions(triples):
    buf = bytearray()
    for op, arg in triples:
        buf.append(op & 0xFF)
        buf.append((arg >> 8) & 0xFF)
        buf.append(arg & 0xFF)
    return bytes(buf)


def _default_triples():
    return [(1, 0), (1, 1), (10, 0), (45, 0)]


def build_packet_via_serializer(mod=None):
    mod = mod or load_engine_module()
    ops = mod._TVMOpcodes
    triples = [
        (ops.LOAD_CONST, 0),
        (ops.LOAD_CONST, 1),
        (ops.BINARY_ADD, 0),
        (ops.RETURN_VALUE, 0),
    ]
    code = mod._TVMCodeObject("fuzz_target", ["alpha", "beta"])
    code.instructions = triples
    code.constants = [40, 2]
    code.names = []
    k_enc, k_mac = mod._tvm_derive_runtime_keys(b"FuzzMasterSeedBytes01", b"FuzzRuntimeSalt0012")
    packet = mod._serialize_tvm_code_object(code, {}, k_enc, k_mac)
    vm_decode_packet(packet, k_enc, k_mac)
    return packet, (k_enc, k_mac)


def build_packet_via_raw_aead(mod=None):
    mod = mod or load_engine_module()
    ops = mod._TVMOpcodes
    triples = [
        (ops.LOAD_CONST, 0),
        (ops.LOAD_CONST, 1),
        (ops.BINARY_ADD, 0),
        (ops.RETURN_VALUE, 0),
    ]
    instr = _encode_instructions(triples)
    payload_tuple = ("fuzz_target", ["alpha", "beta"], [], None, None,
                     ["alpha", "beta"], instr, (40, 2), ())
    blob = zlib.compress(marshal.dumps(payload_tuple), 9)
    k_enc, k_mac = mod._tvm_derive_runtime_keys(b"RawAeadFuzzMasterSeed", b"RawAeadFuzzSalt001")
    packet = mod._tvm_aead_encrypt(blob, k_enc, k_mac)
    vm_decode_packet(packet, k_enc, k_mac)
    return packet, (k_enc, k_mac)


def build_synthetic_packet(mod=None):
    k_enc = hashlib.sha256(b"SyntheticAeadEncKeyFuzz").digest()
    k_mac = hashlib.sha256(b"SyntheticAeadMacKeyFuzz").digest()
    instr = _encode_instructions(_default_triples())
    payload_tuple = ("fuzz_target", ["alpha", "beta"], [], None, None,
                     ["alpha", "beta"], instr, (40, 2), ())
    blob = zlib.compress(marshal.dumps(payload_tuple), 9)
    nonce = secrets.token_bytes(16)
    ct = bytes(p ^ k for p, k in zip(blob, tvm_keystream(k_enc, nonce, len(blob))))
    tag = hmac.new(k_mac, nonce + ct, hashlib.sha256).digest()
    packet = nonce + tag + ct
    vm_decode_packet(packet, k_enc, k_mac)
    return packet, (k_enc, k_mac)


def phase_vm_fuzz():
    phase = Phase("VM_FUZZ")
    log("=== PHASE 3: Bytecode Packet Mutation Fuzzing (%d mutants, seed %d) ===" % (FUZZ_COUNT, FUZZ_SEED))
    rng = random.Random(FUZZ_SEED)

    mod = None
    try:
        mod = load_engine_module()
    except Exception as exc:
        record_failure(phase.name, "tr0ngx_obfuscator import failed: %r" % exc)

    builders = []
    if mod is not None:
        builders.append(("serializer", build_packet_via_serializer))
        builders.append(("raw_aead", build_packet_via_raw_aead))
    builders.append(("synthetic_envelope", build_synthetic_packet))

    target = None
    target_route = None
    build_errors = []
    for route, builder in builders:
        try:
            target = builder(mod)
            target_route = route
            break
        except Exception as exc:
            build_errors.append("%s: %r" % (route, exc))
    if target is None:
        phase.check(False, "", "no fuzz target constructible; attempts: %s" % "; ".join(build_errors))
        phase.finish()
        return
    if target_route == "synthetic_envelope" and mod is not None:
        phase.check(False, "",
                    "real TVM builder routes failed, degraded to synthetic envelope: %s" % "; ".join(build_errors))
    log("Fuzz target built via route '%s'" % target_route)

    base_packet, (k_enc, k_mac) = target
    try:
        vm_decode_packet(base_packet, k_enc, k_mac)
        sanity_ok = True
    except Exception as exc:
        sanity_ok = False
        phase.check(False, "", "unmutated target packet failed its own decoder: %r" % exc)
    phase.check(sanity_ok, "baseline packet decodes (roundtrip sanity)", "")
    if not sanity_ok:
        phase.finish()
        return

    counts = {"rejected_cleanly": 0, "decoded": 0, "crashed": 0}
    inner_capable = mod is not None and target_route != "synthetic_envelope"
    for idx in range(FUZZ_COUNT):
        try:
            if inner_capable and idx % 2 == 1:
                mutant = mutate_inner_payload(mod, base_packet, (k_enc, k_mac), rng)
            else:
                mutant = mutate_bytecode_packet(base_packet, rng)
        except Exception as exc:
            counts["crashed"] += 1
            record_failure(phase.name, "mutant generation exploded at #%d: %r" % (idx, exc))
            continue
        try:
            vm_decode_packet(mutant, k_enc, k_mac)
        except Exception:
            counts["rejected_cleanly"] += 1
            continue
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            counts["crashed"] += 1
            record_failure(phase.name, "mutant #%d escaped the validator with %r" % (idx, exc))
            continue
        counts["decoded"] += 1

    total_accounted = sum(counts.values())
    log("Fuzz tally: rejected_cleanly=%d decoded=%d crashed=%d total_expected=%d"
        % (counts["rejected_cleanly"], counts["decoded"], counts["crashed"], FUZZ_COUNT))
    reject_ratio = counts["rejected_cleanly"] / float(FUZZ_COUNT)
    log("Clean rejection ratio: %.4f" % reject_ratio)
    phase.check(counts["crashed"] == 0,
                "zero crashes escaped to the test process",
                "%d mutant case(s) crashed outside clean rejection" % counts["crashed"])
    phase.check(total_accounted == FUZZ_COUNT,
                "every mutant accounted for",
                "tally mismatch: %d accounted vs %d expected" % (total_accounted, FUZZ_COUNT))
    phase.check(counts["rejected_cleanly"] > 0,
                "validator actively rejects hostile input",
                "validator never rejected anything; it accepts everything")
    phase.finish()


# ---------------------------------------------------------------------------
# Phase 4: reproducible and polymorphic builds
# ---------------------------------------------------------------------------

REPRO_SOURCE = '''def compute(limit):
    total = 0
    for i in range(limit):
        total += i * i - i
    return total

print("RESULT=%d" % compute(25))
'''

REPRO_BUILD_FLAGS = ["-m", "2", "--moreobf", "y", "--math-opaque", "y", "--dyn-strings", "y"]
PINNED_ENTROPY_SEED = 20260822


def _sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

PINNED_RUNNER_TEMPLATE = '''import sys
import random
import secrets

sys.path.insert(0, {root!r})

_pinned = random.Random({pinned_seed})

secrets.randbelow = lambda n: _pinned.randrange(n)
secrets.choice = lambda seq: seq[_pinned.randrange(len(seq))]
secrets.token_bytes = lambda n: _pinned.randbytes(n)
secrets.token_hex = lambda n: _pinned.randbytes(n).hex()
secrets.randbits = lambda k: _pinned.getrandbits(k)


class _PinnedSystemRandom:
    def shuffle(self, seq):
        _pinned.shuffle(seq)

    def randrange(self, *args):
        return _pinned.randrange(*args)

    def random(self):
        return _pinned.random()

    def choice(self, seq):
        return seq[_pinned.randrange(len(seq))]

    def getrandbits(self, k):
        return _pinned.getrandbits(k)


secrets.SystemRandom = _PinnedSystemRandom

sys.argv = ["main.py"] + {argv!r}
import tr0ngx_obfuscator

tr0ngx_obfuscator.main()
'''


def run_pinned_build(src_path, out_path, cli_flags):
    """Build inside a fresh interpreter whose secrets-derived entropy is pinned.

    --seed only seeds the stdlib random module; identifier and junk-constant
    generation draws from secrets.* (unseedable CSPRNG), so cross-process
    byte-determinism requires pinning that entropy source explicitly.
    """
    runner = scratch("qa_pinned_runner.py")
    with open(runner, "w", encoding="utf-8") as f:
        f.write(PINNED_RUNNER_TEMPLATE.format(root=ROOT, pinned_seed=PINNED_ENTROPY_SEED,
                                              argv=["-i", src_path, "-o", out_path, "--no-art"] + list(cli_flags)))
    return run_proc([sys.executable, runner], BUILD_TIMEOUT)


def phase_reproducible_build():
    phase = Phase("REPRODUCIBILITY")
    log("=== PHASE 4: Reproducible & Polymorphic Builds (entropy-pinned) ===")
    src = write_source("qa_repro_src.py", REPRO_SOURCE)
    native_stdout = None
    try:
        native = run_proc([sys.executable, src], EXEC_TIMEOUT)
        native_stdout = native.stdout if native.returncode == 0 else None
        phase.check(native_stdout is not None, "native reference executed",
                    "native repro program failed rc=%s" % native.returncode)

        out1 = scratch("qa_repro_out1.py")
        out2 = scratch("qa_repro_out2.py")
        out3 = scratch("qa_repro_out3.py")
        hashes = {}
        outs = {}
        for tag, out, seed in (("a1", out1, "1337"), ("a2", out2, "1337"), ("b", out3, "9999")):
            res = run_pinned_build(src, out, REPRO_BUILD_FLAGS + ["--seed", seed])
            if not phase.check(res.returncode == 0 and os.path.exists(out),
                               "build %s (seed=%s) succeeded" % (tag, seed),
                               "build %s failed rc=%s stderr=%s" % (tag, res.returncode, tail(res.stderr))):
                continue
            hashes[tag] = _sha256_of(out)
            outs[tag] = out

        if len(hashes) == 3:
            phase.check(hashes["a1"] == hashes["a2"],
                        "identical seeds produce identical sha256 under pinned entropy",
                        "same-seed determinism broken: %s vs %s" % (hashes["a1"], hashes["a2"]))
            phase.check(hashes["a1"] != hashes["b"],
                        "different seeds produce different builds",
                        "polymorphism broken: distinct seeds yielded identical hash")
            if hashes["a1"] != hashes["a2"]:
                log("INFO: un-pinned CLI builds also vary because secrets.* entropy is "
                    "not controlled by --seed; see qa_report.txt notes.")
        else:
            phase.check(False, "", "missing builds for hash comparison: %s" % sorted(hashes))

        for tag in sorted(outs):
            ex = exec_file(outs[tag])
            matches_native = (ex.returncode == 0 and native_stdout is not None
                              and ex.stdout == native_stdout)
            phase.check(matches_native,
                        "build %s executes with native-identical stdout" % tag,
                        "build %s exec mismatch rc=%s stdout=%r stderr=%s"
                        % (tag, ex.returncode, (ex.stdout or "")[:120], tail(ex.stderr)))
    except subprocess.TimeoutExpired as exc:
        phase.check(False, "", "timeout during reproducibility phase: %r" % exc)
    phase.finish()


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main():
    if os.path.exists(REPORT_PATH):
        os.remove(REPORT_PATH)
    log("Tr0ngX QA Suite: fuzz / semantic differential / reproducibility")
    log("Repo root: %s" % ROOT)
    log("Fuzz corpus: %d mutants, seed %d" % (FUZZ_COUNT, FUZZ_SEED))
    try:
        phase_ast_coverage()
        phase_semantic_differential()
        phase_vm_fuzz()
        phase_reproducible_build()
    finally:
        shutil.rmtree(SCRATCH_DIR, ignore_errors=True)

    log("")
    header = "%-36s %7s %6s %6s" % ("PHASE", "CASES", "PASS", "FAIL")
    log(header)
    log("-" * len(header))
    total_cases = total_pass = total_fail = 0
    for name, cases, passed, failed in PHASE_RESULTS:
        log("%-36s %7d %6d %6d" % (name, cases, passed, failed))
        total_cases += cases
        total_pass += passed
        total_fail += failed
    log("-" * len(header))
    log("%-36s %7d %6d %6d" % ("TOTAL", total_cases, total_pass, total_fail))
    log("Failure records: %d" % len(FAILURES))
    for phase_name, msg in FAILURES:
        log("  - [%s] %s" % (phase_name, msg.replace("\n", " | ")[:400]))

    if FAILURES:
        log("SUITE RESULT: FAILED")
        return 1
    log("SUITE RESULT: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
