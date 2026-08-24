"""
TVM Syntax Parity Stress Tests
==============================
Comprehensive test suite verifying the TVM virtualization engine handles
ALL Python syntax constructs correctly. Each case runs native vs obfuscated
and compares stdout + exit code at multiple VM levels.

Run: python tests/test_vm_syntax_parity.py [-w 1]
"""
import os, sys, subprocess, tempfile, time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

OBF_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tr0ngx_obfuscator.py')
REPO_ROOT = os.path.dirname(OBF_SCRIPT)
TIMEOUT_BUILD = 420
TIMEOUT_RUN = 120

_results = []
_pass_count = 0
_fail_count = 0


def case(name: str, source: str, expected_stdout: str = None, levels=(1, 2)):
    """Register and run a single syntax parity test case."""
    global _pass_count, _fail_count

    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as f:
        f.write(source)
        target = f.name

    for level in levels:
        tag = f'{name}_L{level}'
        out_path = target + f'.L{level}.vm.py'
        try:
            # Build
            cmd = [sys.executable, OBF_SCRIPT, '-i', target, '-o', out_path,
                   '-m', '1', '--vm-obf', 'y', '--vm-level', str(level), '--no-art']
            build = subprocess.run(cmd, capture_output=True, text=True,
                                   encoding='utf-8', errors='replace',
                                   timeout=TIMEOUT_BUILD, cwd=REPO_ROOT)
            if build.returncode != 0:
                _record(tag, False, f'BUILD_FAIL rc={build.returncode}', build.stderr[:200])
                continue
            if not os.path.exists(out_path):
                _record(tag, False, 'NO_OUTPUT', '')
                continue

            # Run obfuscated
            run_obf = subprocess.run([sys.executable, out_path], capture_output=True,
                                     text=True, encoding='utf-8', errors='replace',
                                     timeout=TIMEOUT_RUN)

            # Run native (only once per case, cache result)
            if not hasattr(case, '_native_cache'):
                case._native_cache = {}
            nat_key = id(source)
            if nat_key not in case._native_cache:
                run_nat = subprocess.run([sys.executable, target], capture_output=True,
                                         text=True, encoding='utf-8', errors='replace',
                                         timeout=TIMEOUT_RUN)
                case._native_cache[nat_key] = (run_nat.stdout.strip(), run_nat.returncode)
            exp_out, exp_rc = case._native_cache.pop(nat_key)

            ok = (run_obf.stdout.strip() == exp_out and run_obf.returncode == exp_rc)
            if expected_stdout is not None:
                ok = ok and (expected_stdout in run_obf.stdout)

            detail = ''
            if not ok:
                detail = f'rc={run_obf.returncode} vs {exp_rc}; out={run_obf.stdout.strip()[:80]} vs {exp_out[:80]}'
                if run_obf.stderr:
                    detail += f' err={run_obf.stderr.strip()[-150:]}'

            _record(tag, ok, detail)
        except subprocess.TimeoutExpired:
            _record(tag, False, 'TIMEOUT')
        except Exception as e:
            _record(tag, False, str(e)[:200])
        finally:
            for f in [out_path]:
                if os.path.exists(f):
                    try: os.remove(f)
                    except Exception: pass

    try: os.remove(target)
    except Exception: pass


def _record(tag: str, passed: bool, detail: str, stderr_hint: str = ''):
    global _pass_count, _fail_count
    if passed:
        _pass_count += 1
        print(f'  [PASS] {tag}')
    else:
        _fail_count += 1
        print(f'  [FAIL] {tag} | {detail}')
        if stderr_hint:
            print(f'         stderr: {stderr_hint[:150]}')
    _results.append((tag, passed, detail))


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CASES
# ═══════════════════════════════════════════════════════════════════════════════

def run_all():
    print('=' * 78)
    print(' TVM 5.0 Syntax Parity Stress Test Suite')
    print(' Native vs Obfuscated differential at multiple VM levels')
    print('=' * 78)
    case._native_cache = {}

    # ─── Exception Handling Edge Cases ───────────────────────────────────────
    print('\n--- Exception Handling ---')

    case('exc_try_finally_return', '''
def f():
    try:
        return 42
    finally:
        print("finally runs")
print(f())
''')

    case('exc_reraise_from_cause', '''
def risky(x):
    if x < 0:
        raise ValueError("neg") from IndexError("cause")
    return x
try:
    risky(-1)
except ValueError as e:
    print("caught", e)
    print("cause", type(e.__cause__).__name__)
''')

    case('exc_custom_hierarchy', '''
class AppError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code
class DBError(AppError):
    pass
try:
    raise DBError(504, "timeout")
except AppError as e:
    print(e.code, e.args[0])
''')

    case('exc_bare_raise_nested', '''
def f():
    try:
        try:
            raise KeyError("inner")
        except KeyError:
            raise
    except KeyError as e:
        return str(e)
print(f())
''')

    case('exc_else_clause', '''
for x in range(3):
    try:
        if x == 1: raise ValueError()
        print("ok", x)
    except ValueError:
        print("err", x)
    else:
        print("else", x)
''')

    # ─── Closure & Scoping Stress ────────────────────────────────────────────
    print('\n--- Closures & Scoping ---')

    case('clo_late_binding_shared', '''
def make_pair():
    count = [0]
    def inc():
        count[0] += 1
        return count[0]
    def get():
        return count[0]
    return inc, get
inc, get = make_pair()
inc(); inc(); inc()
print(inc(), get())
''')

    case('clo_nonlocal_mutation', '''
def outer():
    x = 10
    def inner():
        nonlocal x
        x += 5
    inner()
    inner()
    return x
print(outer())
''')

    case('clo_deep_nest_3level', '''
def a():
    va = 1
    def b():
        vb = 2
        def c():
            nonlocal va, vb
            va += 10; vb += 20
            return va + vb
        r = c()
        return r, va, vb
    return b()
print(a())
''')

    case('clo_recursion_inner', '''
def wrap():
    def fact(n):
        if n <= 1: return 1
        return n * fact(n - 1)
    return fact(6)
print(wrap())
''')

    case('clo_global_shadows_local', '''
gv = "global"
def f():
    gv = "local"
    return gv
def g():
    global gv
    return gv
print(f(), g())
''')

    # ─── Generator & Async ───────────────────────────────────────────────────
    print('\n--- Generators & Async ---')

    case('gen_yield_send', '''
def gen():
    x = yield 1
    y = yield (x + 10)
    yield y * 2
g = gen()
print(next(g))
print(g.send(5))
print(g.send(20))
''')

    case('gen_yield_from_chain', '''
def inner():
    yield 1; yield 2; return "done"
def outer():
    r = yield from inner()
    yield r
for v in outer(): print(v)
''')

    case('async_basic_await', '''
import asyncio
async def fetch():
    await asyncio.sleep(0)
    return "data"
async def main():
    r = await fetch()
    print(r)
asyncio.run(main())
''')

    case('async_gather_two', '''
import asyncio
async def task(name, delay):
    await asyncio.sleep(delay)
    return name.upper()
async def main():
    results = await asyncio.gather(task("a", 0.01), task("b", 0.005))
    print(results)
asyncio.run(main())
''')

    # ─── OOP Advanced ────────────────────────────────────────────────────────
    print('\n--- OOP Advanced ---')

    case('oop_metaclass_basic', '''
class Meta(type):
    def __new__(mcs, name, bases, ns):
        cls = super().__new__(mcs, name, bases, ns)
        cls.created_by = "meta"
        return cls
class Foo(metaclass=Meta):
    pass
print(Foo.created_by)
''')

    case('oop_property_full', '''
class Temp:
    def __init__(self): self._c = 0
    @property
    def c(self): return self._c
    @c.setter
    def c(self, v): self._c = max(v, 0)
t = Temp()
t.c = -5
print(t.c)
t.c = 25
print(t.c)
''')

    case('oop_diamond_super', '''
class A:
    def greet(self): return "A"
class B(A):
    def greet(self): return "B<" + super().greet() + ">"
class C(A):
    def greet(self): return "C<" + super().greet() + ">"
class D(B, C):
    def greet(self): return "D<" + super().greet() + ">"
d = D()
print(d.greet())
print([c.__name__ for c in D.__mro__])
''')

    case('oop_classmethod_staticmethod', '''
class Registry:
    _items = []
    @classmethod
    def add(cls, item): cls._items.append(item); return len(cls._items)
    @staticmethod
    def reset(): Registry._items.clear()
Registry.add("x"); Registry.add("y")
print(len(Registry._items))
Registry.reset()
print(len(Registry._items))
''')

    case('oop_init_subclass_setname', '''
class PluginBase:
    subclasses = []
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        cls.subclasses.append(cls.__name__)
class Alpha(PluginBase): pass
class Beta(PluginBase): pass
print(sorted(PluginBase.subclasses))
''')

    # ─── Control Flow Stress ─────────────────────────────────────────────────
    print('\n--- Control Flow ---')

    case('cf_nested_break_continue', '''
result = []
for i in range(4):
    for j in range(4):
        if j == 2: continue
        if i == 3: break
        result.append((i, j))
print(result)
''')

    case('cf_try_in_loop_in_try', '''
log = []
try:
    for i in range(5):
        try:
            if i == 2: raise ValueError(f"v{i}")
            log.append(("ok", i))
        except ValueError as e:
            log.append(("err", str(e)))
            if i >= 3: break
finally:
    log.append(("fin",))
print(log)
''')

    case('cf_match_comprehensive', '''
def classify(val):
    match val:
        case 0:
            return "zero"
        case None | True | False:
            return "singleton"
        case int(n) if n < 0:
            return ("neg", n)
        case float() as f:
            return ("float", round(f, 2))
        case [1, *rest]:
            return ("seq_rest", rest)
        case [a, b]:
            return ("pair", a, b)
        case {"type": "cmd", "val": v, **extra}:
            return ("cmd", v, sorted(extra.keys()))
        case str() as s if s.startswith("~"):
            return ("tilde", s[1:])
        case Point(xx=x):
            return ("point", x)
        case _:
            return "fallback"

class Point:
    __match_args__ = ("x",)
    def __init__(self, xx): self.xx = xx

inputs = [0, None, True, -5, 3.14159, [1,2,3], [9,9],
          {"type":"cmd","val":42,"extra":"e"}, "~/home", Point(77), object()]
for inp in inputs:
    print(classify(inp))
''')

    case('cf_walrus_operator', '''
data = [1, 2, 3, 4, 5]
filtered = [y for x in data if (y := x * 2) > 4]
print(filtered)
if (n := len(data)) > 3:
    print("long", n)
''')

    case('cf_while_else_for_else', '''
i = 0
while i < 5:
    i += 1
    if i == 3: break
else:
    print("while-else ran")
for x in range(3):
    pass
else:
    print("for-else ran")
''')

    # ─── Imports & Module-level ──────────────────────────────────────────────
    print('\n--- Imports ---')

    case('imp_from_submodule', '''
from os.path import join, basename
print(join("/a", "b"), basename("/x/y.txt"))
''')

    case('imp_dotted_as_alias', '''
import collections.abc as cabc
import json.encoder as jenc_mod
from collections import OrderedDict as OD
d = OD([("b", 2), ("a", 1)])
print(isinstance(d, cabc.Mapping), list(d.keys()))
''')

    case('imp_try_except_importerror', '''
try:
    import json
    HAS_JSON = True
except ImportError:
    HAS_JSON = False
try:
    import nonexistent_module_xyz
    HAS_BAD = True
except ImportError:
    HAS_BAD = False
print(HAS_JSON, HAS_BAD)
''')

    # ─── Misc Hard Cases ─────────────────────────────────────────────────────
    print('\n--- Misc Hard Cases ---')

    case('misc_lambda_defaults_shared', '''
def add_item(item, lst=[]):
    lst.append(item)
    return lst
r1 = add_item(1)
r2 = add_item(2)
print(r1 is r2, r1, r2)
''')

    case('misc_chained_comparison', '''
a, b, c, d = 1, 2, 3, 4
print(a < b <= c < d)
print(a > b, b >= c, c != d)
print(a < d > b < c)
''')

    case('misc_star_unpack_deep', '''
a, *b, c = range(10)
(x, y), z = (1, 2), 3
first, *rest = [42]
print(a, b, c)
print(x, y, z)
print(first, rest)
''')

    case('misc_dict_order_update', '''
d = {"b": 2, "a": 1}
d["c"] = 3
d.update({"a": 99})
del d["b"]
d["b"] = 2
print(list(d.items()))
''')

    case('misc_fstring_format_edge', '''
pi = 3.14159265
num = 255
text = "hi"
print(f"{pi:.2f} {num:>8d} {num:08b} {text!r}")
print("{:+.3e}".format(pi))
print("%05.1f|%s" % (pi, text))
''')

    case('misc_decorators_stacked', '''
def trace(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper
def double_result(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs) * 2
    return wrapper
@double_result
@trace
def compute(x):
    return x + 1
print(compute(5))
''')

    # ─── Summary ─────────────────────────────────────────────────────────────
    total = _pass_count + _fail_count
    print('\n' + '=' * 78)
    print(f' SYNTAX PARITY SUMMARY: {_pass_count} PASSED | {_fail_count} FAILED | {total} TOTAL')
    print(f' Pass rate: {_pass_count/total*100:.1f}%' if total else 'No cases')
    print('=' * 78)
    if _fail_count:
        print('\n Failures:')
        for tag, ok, detail in _results:
            if not ok:
                print(f'   {tag}: {detail[:120]}')
    return _fail_count


if __name__ == '__main__':
    sys.exit(min(1, run_all()))
