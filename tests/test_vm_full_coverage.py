"""
Test Suite 15: TVM Full-Language Coverage Matrix
Verifies the VM virtualization engine against a broad corpus of Python
constructs - every statement form, expression form, callable shape, class
feature, generator protocol and async pattern in this repo's support surface -
across ALL vm levels (1..4).

For each (case, level): build with --vm-obf y --vm-level N, execute the
obfuscated artifact, and require byte-identical stdout plus exit code 0 when
compared to the native run of the same source.

Env knobs:
  TRX_VM_COV_LEVELS   comma list of vm levels (default "1,2,3,4")
"""
import os
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = [int(x) for x in os.environ.get("TRX_VM_COV_LEVELS", "1,2,3,4").split(",") if x.strip()]
BUILD_TIMEOUT = 300
RUN_TIMEOUT = 90

# ---------------------------------------------------------------------------
# CORPUS: name -> (source, expected_stdout)
# expected_stdout is captured from the native run automatically; the strings
# below exist only as documentation of intent.
# ---------------------------------------------------------------------------

CORPUS = {}

def case(name, src):
    CORPUS[name] = src

# --- expressions -----------------------------------------------------------
case("expr_arith_chain", '''
a, b, c = 7, 3, 2
print(a % b * c ** 2 - -b // c, (a << 1) | (b & 3), ~(a ^ b), divmod(a, b))
''')
case("expr_boolop_shortcircuit", '''
calls = []
def t(v):
    calls.append(v)
    return v
r = t(0) or t('') or t(3) and t(5)
r2 = t(1) and t(2) and t(0)
print(r, r2, calls == [0,'',3,5,1,2,0])
''')
case("expr_ifexp_ternary", '''
x = 10
print('big' if x > 5 else 'small', 'neg' if x < 0 else 'pos' if x > 0 else 'zero')
''')
case("expr_walrus", '''
data = [1, 2, 3, 4]
if (n := len(data)) > 3:
    print('long', n)
print([y for y in data if (y % 2 == 0)])
''')
case("expr_compare_chain", '''
print(1 < 2 <= 2 < 3 != 4, 'abc' < 'abd', 3 in [1,2,3], 5 not in {1:2})
''')

# --- f-strings / formatting -----------------------------------------------
case("fstring_spec_conv", '''
name, v = 'pi', 3.14159
print(f"{name!r:>8} = {v:.2f} ({v*2:+08.3f})")
print(f"{name=}, {v=:.1f}")
''')

# --- statements ------------------------------------------------------------
case("stmt_for_else_break", '''
total = 0
for i in range(10):
    if i == 4:
        break
    total += i
else:
    total = -1
print(total)

found = False
for i in range(3):
    pass
else:
    found = True
print(found)
''')
case("stmt_while_else_continue", '''
i, out = 0, []
while i < 6:
    i += 1
    if i % 2:
        continue
    out.append(i)
else:
    out.append('done')
print(out)
''')
case("stmt_del_assert", '''
d = {'a': 1, 'b': 2}
del d['a']
lst = [1, 2, 3, 4]
del lst[1:3]
assert len(lst) == 2
x = 5
del x
try:
    print(x)
except NameError:
    print('gone')
print(d, lst)
''')
case("stmt_global_nonlocal", '''
G = []
def outer():
    v = 0
    def inner():
        nonlocal v
        v += 5
    inner()
    G.append(v)
outer()
counter = 0
def bump():
    global counter
    counter += 1
bump(); bump(); bump()
print(G, counter)
''')
case("stmt_import_forms", '''
import math
from collections import OrderedDict, defaultdict as dd
import os.path as op
print(math.gcd(12, 18), isinstance(dd(), dict), op.basename('/x/y.txt'))
''')

# --- exceptions ------------------------------------------------------------
case("exc_full", '''
class MyErr(Exception):
    pass

def risky(k):
    if k == 0:
        raise ValueError('zero') from KeyError('cause')
    if k == 1:
        raise MyErr('one')
    return 10 / k

for k in (2, 0, 1):
    try:
        r = risky(k)
    except ValueError as e:
        print('VE', e, isinstance(e.__cause__, KeyError))
    except MyErr as e:
        print('ME', e)
    except Exception as e:
        print('E', type(e).__name__)
    else:
        print('ok', r)
    finally:
        print('fin', k)
''')
case("exc_finally_reraise", '''
def f():
    try:
        try:
            raise RuntimeError('inner')
        finally:
            print('cleanup')
    except RuntimeError as e:
        print('caught', e)
        raise
try:
    f()
except RuntimeError:
    print('recaught')
''')

# --- with / context managers ------------------------------------------------
case("with_sync", '''
class CM:
    def __init__(self, tag):
        self.tag = tag
    def __enter__(self):
        print('enter', self.tag)
        return self
    def __exit__(self, et, ev, tb):
        print('exit', self.tag, et is None)
        return False

with CM('a') as ca, CM('b'):
    print('body', ca.tag)

class Suppress:
    def __enter__(self): return self
    def __exit__(self, et, ev, tb):
        return et is not None and issubclass(et, ZeroDivisionError)

with Suppress():
    print(1 / 0)
print('suppressed')
''')

# --- functions --------------------------------------------------------------
case("fn_args_matrix", '''
def f(a, b=2, *args, c, d=4, **kw):
    return (a, b, args, c, d, sorted(kw.items()))
print(f(1, 9, 7, 8, c=3, z=26, y=25))
g = lambda *a, **k: (len(a), sorted(k))
print(g(1, 2, x=1))
def h(*args, **kwargs):
    return f(*args, **kwargs)
print(h(1, c=3, kw=9))
''')
case("fn_defaults_eval_once", '''
def mk(tag, acc=[]):
    acc.append(tag)
    return tuple(acc)
print(mk('a'))
print(mk('b'))
''')
case("fn_recursion_mutual", '''
def is_even(n):
    return True if n == 0 else is_odd(n - 1)
def is_odd(n):
    return False if n == 0 else is_even(n - 1)
def fib(n):
    return n if n < 2 else fib(n-1) + fib(n-2)
print(is_even(10), is_odd(7), fib(12))
''')
case("fn_closures_cells", '''
def make_adders():
    adders = []
    for i in range(3):
        def adder(x, _i=i):
            return x + _i
        adders.append(adder)
    def counter():
        c = 0
        def inc():
            nonlocal c
            c += 1
            return c
        return [inc(), inc(), inc()]
    return [f(10) for f in adders], counter()

adds, (c1, c2, c3) = make_adders()
print(adds, (c1, c2, c3))
''')
case("fn_decorators", '''
import functools
def trace(fn):
    @functools.wraps(fn)
    def w(*a, **k):
        r = fn(*a, **k)
        return r * 2
    return w
def tag(t):
    def deco(fn):
        def w(*a, **k):
            return (t,) + (fn(*a, **k),)
        return w
    return deco

@trace
@tag('T')
def calc(x):
    return x + 1

print(calc(4), calc.__name__)
''')

# --- classes ----------------------------------------------------------------
case("cls_dunder_protocols", '''
class Vec:
    __slots__ = ('x', 'y')
    def __init__(self, x, y):
        self.x, self.y = x, y
    def __add__(self, o):
        return Vec(self.x + o.x, self.y + o.y)
    def __eq__(self, o):
        return isinstance(o, Vec) and (self.x, self.y) == (o.x, o.y)
    def __len__(self):
        return 2
    def __getitem__(self, i):
        if isinstance(i, slice):
            return (self.x, self.y)[i]
        return (self.x, self.y)[i]
    def __iter__(self):
        yield from (self.x, self.y)
    def __repr__(self):
        return f'Vec({self.x},{self.y})'
    def __hash__(self):
        return hash((self.x, self.y))

v = Vec(1, 2) + Vec(3, 4)
print(repr(v), len(v), v[0], v[1:], list(v), v == Vec(4, 6), {v: 'ok'}[Vec(4, 6)])
''')
case("cls_property_desc_methods", '''
class Temp:
    factor = 2
    def __init__(self, c):
        self._c = c
    @property
    def f(self):
        return self._c * self.factor
    @f.setter
    def f(self, val):
        self._c = val // self.factor
    @classmethod
    def unit(cls):
        return cls(1)
    @staticmethod
    def const():
        return 99

t = Temp.unit()
print(t.f)
t.f = 20
print(t.f, Temp.const(), Temp.factor)
''')
case("cls_inheritance_mro_super", '''
class A:
    def who(self):
        return 'A'
    def greet(self):
        return 'hi ' + self.who()
class B(A):
    def who(self):
        return 'B'
class C(A):
    def who(self):
        return 'C'
class D(B, C):
    def who(self):
        return 'D+' + super().who()

print([k.__name__ for k in D.__mro__], D().greet())
class MetaCheck(type):
    pass
class WithMeta(metaclass=MetaCheck):
    attr = 5
print(isinstance(WithMeta, MetaCheck), WithMeta.attr)
''')
case("cls_getattr_hooks", '''
class Lazy:
    def __init__(self):
        object.__setattr__(self, '_d', {'real': 42})
    def __getattr__(self, k):
        if k.startswith('_'):
            raise AttributeError(k)
        return self._d.get(k, 'missing')
    def __setattr__(self, k, v):
        self._d[k] = v

l = Lazy()
print(l.real, l.nope)
l.extra = 7
print(l.extra)
''')
case("cls_dynamic_type", '''
Point = type('Point', (), {
    '__init__': lambda self, x: setattr(self, 'x', x),
    'double': lambda self: self.x * 2,
})
p = Point(21)
print(p.double())
''')

# --- match-case -------------------------------------------------------------
case("match_matrix", '''
def m(x):
    match x:
        case 0:
            return 'zero'
        case None | True:
            return 'special'
        case int(n) if n < 0:
            return ('neg', n)
        case float() as fl:
            return ('float', round(fl, 1))
        case [1, *rest]:
            return ('seq1', rest)
        case [a, b]:
            return ('pair', a, b)
        case {'op': 'set', 'val': val, **extra}:
            return ('setcmd', val, sorted(extra))
        case str() as s if s.startswith('~'):
            return ('tilde', s[1:])
        case Point(xx=xx):
            return ('point', xx)
        case _:
            return 'other'

class Point:
    __match_args__ = ('y',)
    def __init__(self, xx, y=0):
        self.xx, self.y = xx, y

outs = [m(0), m(None), m(-5), m(2.75), m([1, 2, 3]), m([9, 9]),
        m({'op': 'set', 'val': 3, 'extra1': 'e'}),
        m('~/home'), m(Point(77)), m(object())]
print(outs)
''')

# --- comprehensions / iter tools --------------------------------------------
case("comp_all_kinds", '''
matrix = [[1, 2], [3, 4]]
flat = [x for row in matrix for x in row if x % 2 == 1]
squares = {x * x for x in flat}
lookup = {x: x ** 3 for x in flat}
lazy = sum(x for x in range(10) if x % 3 == 0)
pairs = [(i, j) for i in range(2) for j in range(2) if i != j]
print(flat, squares, lookup, lazy, pairs)
''')
case("iter_builtin_matrix", '''
data = [5, 3, 8, 1]
print(sorted(data, reverse=True), list(reversed(data)),
      list(map(lambda x: x * 2, data)), list(filter(lambda x: x > 2, data)),
      any(x > 7 for x in data), all(x > 0 for x in data),
      max(data), min(data), sum(data, start=0),
      list(enumerate(data[:2])), list(zip(data, data[1:])))
import heapq, itertools
print(list(itertools.islice(itertools.count(10), 3)),
      list(itertools.chain([1], [2, 3])),
      list(heapq.nlargest(2, data)))
''')
case("unpack_everywhere", '''
a, *b, c = [1, 2, 3, 4, 5]
head, *tail = (9,)
merged = [*a_list] if False else None
first, *rest = 'xyz'
def f(p, q, *, r):
    return p + q + r
parts = {'r': 30}
print(a, b, c, head, tail, first, rest, f(10, **{'q': 20}, **parts))
nums = *[1, 2], *['3']
print(nums)
''')

# --- generators --------------------------------------------------------------
case("gen_protocol_send_throw_close", '''
def echo():
    total = 0
    while True:
        x = yield total
        if x is None:
            break
        total += x
    return total

g = echo()
first = next(g)
s1 = g.send(10)
s2 = g.send(32)
try:
    g.send(None)
except StopIteration as si:
    ret = si.value
print(first, s1, s2, ret)

def guarded():
    try:
        yield 1
        yield 2
    finally:
        print('cleanup-run')
gg = guarded()
print(next(gg))
gg.close()

def bomb():
    yield 1
bb = bomb()
next(bb)
try:
    bb.throw(KeyError('k'))
except KeyError as e:
    print('threw', e)
''')
case("gen_yield_from_chain", '''
def leaf(n):
    yield from range(n)
    return n * 100

def mid():
    r = yield from leaf(3)
    yield ('r', r)
    yield from 'ab'

def top():
    yield from mid()
    yield from [99, 98]

print(list(top()))
from itertools import islice
def naturals():
    i = 0
    while True:
        yield i
        i += 1
print(list(islice(naturals(), 5, 10)))
''')

# --- async ------------------------------------------------------------------
case("async_gather_sleep", '''
import asyncio

async def work(tag, t, result):
    await asyncio.sleep(t)
    result.append(tag)
    return tag.upper()

async def main():
    result = []
    r = await asyncio.gather(work('a', 0.01, result), work('b', 0.02, result))
    print('G', r, sorted(result))

asyncio.run(main())
''')
case("async_for_with_gen", '''
import asyncio

async def agen(n):
    for i in range(n):
        await asyncio.sleep(0)
        yield i * 10

class ARange:
    def __init__(self, n):
        self.n = n
    def __aiter__(self):
        self.i = 0
        return self
    async def __anext__(self):
        if self.i >= self.n:
            raise StopAsyncIteration
        self.i += 1
        return self.i

async def main():
    vals = []
    async for v in agen(4):
        vals.append(v)
    total = 0
    async for w in ARange(3):
        total += w
    print('AF', vals, total)

asyncio.run(main())
''')
case("async_context_manager", '''
import asyncio

class ACM:
    async def __aenter__(self):
        print('aenter')
        return 5
    async def __aexit__(self, et, ev, tb):
        print('aexit', et is None)
        return False

async def main():
    async with ACM() as v:
        await asyncio.sleep(0)
        print('body', v)

asyncio.run(main())
''')

# --- stdlib mini-tours -------------------------------------------------------
case("stdlib_collections_re_json", '''
import json, re
from collections import Counter, defaultdict, deque
text = 'a b a c b a'
c = Counter(text.split())
dq = deque([1, 2]); dq.appendleft(0)
dd = defaultdict(list)
for k, v in [('x', 1), ('x', 2)]:
    dd[k].append(v)
m = re.findall(r'\\d+', 'a1b22c333')
obj = {'nums': [1, 2], 'tag': 't'}
print(c.most_common(1), dq, dict(dd), m, json.loads(json.dumps(obj)))
''')
case("stdlib_functools_dataclassish", '''
import functools
@functools.lru_cache(maxsize=None)
def slow(n):
    return n * n
print(slow(4), slow(4), slow.cache_info().currsize)
class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y
    def __eq__(self, o):
        return (self.x, self.y) == (o.x, o.y)
    def __repr__(self):
        return f'P({self.x},{self.y})'
ps = [Point(2, 1), Point(1, 2)]
print(sorted(ps, key=lambda p: (p.x, p.y))[0])
''')

# --- identifier stress --------------------------------------------------------
case("ident_unicode_mix", '''
héllo_wörld = 1
日本語変数 = 2
_ünïcode_3 = héllo_wörld + 日本語変数
def función(_π):
    return _π * _ünïcode_3
print(función(10))
''')
case("ident_shadow_builtins", '''
def process(data, max=3, len_override=None):
    ln = len(data)
    capped = data[:max]
    return ln, capped, len_override
_real_len = len
len = lambda seq: 100
try:
    r = process([1, 2, 3, 4], max=2, len_override=_real_len([1]))
finally:
    pass
len = _real_len
print(r)
''')
case("ident_long_names_zalgo_valid", '''
def _very_long_function_name_created_to_stress_symbol_tables_aaaaaaaaaaaaaaaa(arg_one, arg_two):
    combined = arg_one + arg_two
    return combined
z̲a̷l̶g̡ơ_n̂a̅ḿė = 40
another_extremely_long_but_valid_identifier_name_here = 2
print(_very_long_function_name_created_to_stress_symbol_tables_aaaaaaaaaaaaaaaa(
    z̲a̷l̶g̡ơ_n̂a̅ḿė, another_extremely_long_but_valid_identifier_name_here))
''')

# --- misc semantics ----------------------------------------------------------
case("mutables_scope_defaults_slices", '''
s = 'hello world'
print(s[::-1], s[0:5].upper(), s[-5:].replace('world', 'py'), '%s|%d' % ('x', 7), '{}{:+d}'.format('n', 5))
grid = [[0] * 3 for _ in range(2)]
grid[1][2] = 9
print(grid)
sl = slice(1, None, 2)
print('abcdef'[sl])
bytes_b = b'AB' + bytearray(b'CD')
print(bytes_b, bytes_b.hex(), memoryview(bytes_b)[0])
''')


def run_native(src_path):
    p = subprocess.run([sys.executable, src_path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=RUN_TIMEOUT,
                       cwd=REPO_ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return p.returncode, p.stdout


def main():
    levels = LEVELS
    print("[TEST 15] TVM Full-Language Coverage Matrix")
    print("  corpus=%d cases | levels=%s" % (len(CORPUS), levels))

    tmp_root = tempfile.mkdtemp(prefix="trx_cov_")
    passed = failed = 0
    failures = []

    native_cache = {}
    try:
        for name, src in CORPUS.items():
            src_path = os.path.join(tmp_root, name + ".native.py")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(src)
            rc, out = run_native(src_path)
            if rc != 0:
                print("  [SKIP] %-28s native itself fails (corpus bug)" % name)
                continue
            native_cache[name] = out.strip()

            for lvl in levels:
                out_path = os.path.join(tmp_root, "%s.l%s.py" % (name, lvl))
                cmd = [
                    sys.executable, os.path.join(REPO_ROOT, "main.py"),
                    "-i", src_path, "-o", out_path,
                    "--vm-obf", "y", "--vm-level", str(lvl),
                    "-m", "1", "--force-py", "off", "--no-art",
                ]
                b = subprocess.run(cmd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   timeout=BUILD_TIMEOUT, cwd=REPO_ROOT)
                if b.returncode != 0 or not os.path.exists(out_path):
                    failed += 1
                    msg = "build fail rc=%s %s" % (b.returncode, (b.stderr or "").strip()[-160:])
                    failures.append((name, lvl, msg))
                    print("  [FAIL] %-28s L%d  %s" % (name, lvl, msg))
                    continue
                try:
                    rr = subprocess.run([sys.executable, out_path], capture_output=True,
                                        text=True, encoding="utf-8", errors="replace",
                                        timeout=RUN_TIMEOUT,
                                        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                        cwd=REPO_ROOT)
                except subprocess.TimeoutExpired:
                    failed += 1
                    failures.append((name, lvl, "timeout"))
                    print("  [FAIL] %-28s L%d  TIMEOUT" % (name, lvl))
                    continue
                if rr.returncode == 0 and rr.stdout.strip() == native_cache[name]:
                    passed += 1
                    continue
                failed += 1
                msg = "rc=%s out=%r want=%r err=%s" % (
                    rr.returncode, rr.stdout.strip()[:80],
                    native_cache[name][:80], (rr.stderr or "").strip().splitlines()[-1:])
                failures.append((name, lvl, msg))
                print("  [FAIL] %-28s L%d  %s" % (name, lvl, msg))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print("-" * 70)
    print("[TEST 15] SUMMARY: %d PASSED | %d FAILED  (cases=%d x levels=%s)" %
          (passed, failed, len(CORPUS), levels))
    if failures:
        print("[TEST 15] failing cells:")
        for name, lvl, why in failures[:20]:
            print("   - %s L%s: %s" % (name, lvl, why))
    if failed == 0:
        print("[TEST 15] >>> SUITE GREEN <<<")
        return 0
    print("[TEST 15] >>> SUITE FAILED <<<")
    return 1


if __name__ == "__main__":
    sys.exit(main())
