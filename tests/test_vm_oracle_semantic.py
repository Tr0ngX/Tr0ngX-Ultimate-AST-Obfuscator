"""
Tr0ngX Ultimate Obfuscator - TVM 2.0 Semantic Oracle & Verification Suite
File: tests/test_vm_oracle_semantic.py

Single-threaded test oracle harness verifying 100% semantic invariance between
native Python execution and Tr0ngX Virtual Machine (_vm_obfuscate).
Covers 31 comprehensive semantic test cases across core language constructs.
"""

import os
import sys
import time
import subprocess
import tempfile
from typing import Dict, Tuple, Any, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tr0ngx.vm import _vm_obfuscate

# ═══════════════════════════════════════════════════════════════════════════
# 31 SEMANTIC TEST CASES
# ═══════════════════════════════════════════════════════════════════════════

SEMANTIC_TEST_CASES: Dict[str, Dict[str, Any]] = {
    "01_loops_break": {
        "title": "Loops: Break in for-loop & for-else",
        "code": """
res = []
for i in range(10):
    if i == 5:
        break
    res.append(i)
else:
    res.append(999)

for j in range(3):
    res.append(j * 10)
else:
    res.append(888)

print("loops_break:", res)
"""
    },

    "02_loops_cont": {
        "title": "Loops: Continue in for-loop",
        "code": """
res = []
for i in range(10):
    if i % 2 == 0:
        continue
    res.append(i)
print("loops_cont:", res)
"""
    },

    "03_while_loop": {
        "title": "While loop: Break, continue, conditions & while-else",
        "code": """
i = 0
res = []
while i < 10:
    i += 1
    if i == 3:
        continue
    if i == 7:
        break
    res.append(i)
else:
    res.append(999)

w = 0
while w < 3:
    w += 1
    res.append(w * 100)
else:
    res.append(777)

print("while_loop:", res)
"""
    },

    "04_fstring_format_spec_float": {
        "title": "F-String format spec: Float precision f'{x:.2f}'",
        "code": """
x = 3.1415926535
val = 123.456789
print(f"fstring_float: {x:.2f} | {val:.4f} | {x:10.2f}")
"""
    },

    "05_fstring_format_spec_int": {
        "title": "F-String format spec: Integer padding f'{x:05d}'",
        "code": """
x = 42
y = 7
print(f"fstring_int: {x:05d} | {y:03d} | {x:>6d}")
"""
    },

    "06_try_except_finally": {
        "title": "Exception handling: try / except / finally execution flow",
        "code": """
log = []
def run_flow(trigger):
    try:
        log.append("try_start")
        if trigger:
            raise ValueError("flow_error")
        log.append("try_end")
    except ValueError as e:
        log.append(f"caught_{e}")
    finally:
        log.append("finally_executed")

run_flow(False)
run_flow(True)
print("try_except_finally:", log)
"""
    },

    "07_try_except_multi_tuple": {
        "title": "Exception handling: try ... except (A, B) as e multi-catch",
        "code": """
log = []
exceptions_to_test = [ValueError("err_val"), TypeError("err_type"), KeyError("err_key")]
for exc in exceptions_to_test:
    try:
        raise exc
    except (ValueError, TypeError) as e:
        log.append(f"caught_multi_{type(e).__name__}_{e}")
    except Exception as e:
        log.append(f"caught_generic_{type(e).__name__}")
print("try_except_multi:", log)
"""
    },

    "08_global_nonlocal": {
        "title": "Scope modifiers: global and nonlocal variable mutation",
        "code": """
g_counter = 100

def outer():
    global g_counter
    g_counter += 50
    n_val = 10

    def inner():
        nonlocal n_val
        n_val += 5
        global g_counter
        g_counter += 20
        return n_val

    r1 = inner()
    r2 = inner()
    return r1, r2, n_val

res1, res2, final_n = outer()
print("global_nonlocal:", g_counter, res1, res2, final_n)
"""
    },

    "09_lambda_default_arg": {
        "title": "Lambdas: Default arguments and varargs",
        "code": """
f1 = lambda x, y=10, z=20: x + y + z
f2 = lambda a, *args, multiplier=2: sum(args, a) * multiplier
print("lambda_default:", f1(1), f1(1, 2), f1(1, 2, 3), f2(5, 1, 2, 3), f2(5, 1, 2, multiplier=3))
"""
    },

    "10_aug_assign_attribute": {
        "title": "Augmented assignment: Attribute mutation c.x += 5",
        "code": """
class Accumulator:
    def __init__(self, start):
        self.total = start
        self.history = [start]

acc = Accumulator(10)
acc.total += 5
acc.total *= 2
acc.total -= 4
acc.total //= 3
acc.history += [acc.total]
print("aug_assign_attr:", acc.total, acc.history)
"""
    },

    "11_aug_assign_subscript": {
        "title": "Augmented assignment: Subscript mutation l[0] += 10 & d['k'] += 5",
        "code": """
l = [10, 20, 30]
l[0] += 10
l[1] *= 2
l[2] -= 5
d = {"count": 100, "scores": [1, 2]}
d["count"] += 50
d["scores"] += [3, 4]
print("aug_assign_subscript:", l, d["count"], d["scores"])
"""
    },

    "12_nested_loop": {
        "title": "Control flow: Multi-tier nested loops (2-3 levels) with break/continue",
        "code": """
res = []
for i in range(3):
    for j in range(3):
        for k in range(3):
            if k == 2:
                break
            if j == 1:
                continue
            res.append((i, j, k))
print("nested_loop:", res)
"""
    },

    "13_set_operations": {
        "title": "Set operations: Set literals and binary operators &, |, -, ^",
        "code": """
a = {1, 2, 3, 4, 5}
b = {3, 4, 5, 6, 7}
inter = a & b
union = a | b
diff = a - b
sym_diff = a ^ b
print("set_ops:", sorted(list(inter)), sorted(list(union)), sorted(list(diff)), sorted(list(sym_diff)))
"""
    },

    "14_chained_comparison": {
        "title": "Comparisons: Chained comparisons 1 < x < 10 with short-circuiting",
        "code": """
x = 5
c1 = 1 < x < 10
c2 = 1 < x < 4
c3 = 10 >= x > 2 == 2
c4 = 10 > x > 100 > (lambda: 1/0)()
print("chained_cmp:", c1, c2, c3, c4)
"""
    },

    "15_arithmetic_bitwise_ops": {
        "title": "Operators: Full spectrum arithmetic & bitwise operations",
        "code": """
a = 29
b = 6
add = a + b
sub = a - b
mul = a * b
div = a / b
fdiv = a // b
mod = a % b
power = b ** 3
band = a & b
bor = a | b
bxor = a ^ b
lsh = b << 2
rsh = a >> 1
neg = -a
inv = ~b
not_val = not (a == b)
print("arith_bitwise:", add, sub, mul, round(div, 4), fdiv, mod, power, band, bor, bxor, lsh, rsh, neg, inv, not_val)
"""
    },

    "16_nested_functions_closures": {
        "title": "Scoping & Closures: Deeply nested closures and environment capture",
        "code": """
def make_multiplier(factor):
    def multiplier(val):
        def deep_multiplier(extra):
            return (val + extra) * factor
        return deep_multiplier
    return multiplier

m3 = make_multiplier(3)
m3_10 = m3(10)
print("closures:", m3_10(5), make_multiplier(2)(8)(5))
"""
    },

    "17_comprehensions": {
        "title": "Comprehensions: List, Dict, and Set comprehensions with filters",
        "code": """
lc = [x * 2 for x in range(10) if x % 2 == 0]
dc = {k: k**2 for k in range(6) if k % 2 != 0}
sc = {x % 4 for x in range(12)}
print("comprehensions:", lc, sorted(dc.items()), sorted(list(sc)))
"""
    },

    "18_context_managers": {
        "title": "Context Managers: Nested with-statements and __enter__/__exit__ protocol",
        "code": """
class TraceCM:
    def __init__(self, tag, log_target):
        self.tag = tag
        self.log_target = log_target

    def __enter__(self):
        self.log_target.append(f"enter_{self.tag}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.log_target.append(f"exit_{self.tag}")
        return False

log = []
with TraceCM("outer", log) as cm1:
    log.append("inside_outer")
    with TraceCM("inner", log) as cm2:
        log.append("inside_inner")

print("context_managers:", log)
"""
    },

    "19_generators_yield_from": {
        "title": "Generators: Generator functions, yield, and yield from delegation",
        "code": """
def child_gen():
    yield 100
    yield 200

def parent_gen():
    yield 1
    yield from child_gen()
    yield 2
    yield from [300, 400]
    yield 3

gen = parent_gen()
print("generators:", list(gen))
"""
    },

    "20_class_inheritance_super": {
        "title": "OOP: Class inheritance, method overriding, and super() delegation",
        "code": """
class Animal:
    def __init__(self, name):
        self.name = name

    def sound(self):
        return "Generic"

    def describe(self):
        return f"Animal:{self.name}:{self.sound()}"

class Dog(Animal):
    def __init__(self, name, breed):
        super().__init__(name)
        self.breed = breed

    def sound(self):
        return "Bark"

    def describe(self):
        return super().describe() + f":{self.breed}"

d = Dog("Rex", "Shepherd")
print("inheritance_super:", d.describe())
"""
    },

    "21_walrus_operator": {
        "title": "Expressions: Assignment expression (walrus operator :=)",
        "code": """
items = [1, 2, 3, 4, 5, 6, 7]
collected = []
if (n := len(items)) > 5:
    collected.append(f"len_{n}")

while (last := items.pop()) > 4:
    collected.append(f"popped_{last}")

print("walrus:", collected, items)
"""
    },

    "22_del_statement": {
        "title": "Statements: del statement on dict keys, list indices, and attributes",
        "code": """
d = {"a": 1, "b": 2, "c": 3}
del d["b"]

l = [10, 20, 30, 40]
del l[1]

class Container:
    def __init__(self):
        self.val = 999

c = Container()
del c.val

print("del_stmt:", sorted(d.items()), l, hasattr(c, "val"))
"""
    },

    "23_assert_statement": {
        "title": "Assertions: assert condition and custom failure message",
        "code": """
log = []
try:
    assert 2 + 2 == 4, "math holds"
    log.append("assert_1_passed")
    assert 2 + 2 == 5, "math failed intentionally"
    log.append("unreachable")
except AssertionError as e:
    log.append(f"caught_assertion: {e}")

print("assert_statement:", log)
"""
    },

    "24_match_case_pattern_matching": {
        "title": "Pattern Matching: match-case statement with literal, sequence & mapping patterns",
        "code": """
def evaluate_cmd(cmd):
    match cmd:
        case 0:
            return "zero"
        case [x, y] if x > y:
            return f"pair_desc_{x}_{y}"
        case {"type": "LOGIN", "user": u}:
            return f"user_{u}"
        case _:
            return "fallback"

print("match_case:", evaluate_cmd(0), evaluate_cmd([10, 3]), evaluate_cmd({"type": "LOGIN", "user": "alice"}), evaluate_cmd("unknown"))
"""
    },

    "25_tuple_unpacking_assignments": {
        "title": "Unpacking: Multi-target and nested tuple/list unpacking",
        "code": """
a, b, c = 10, 20, 30
(x, (y, z)) = (100, (200, 300))
[first, *middle, last] = [1, 2, 3, 4, 5]
print("tuple_unpacking:", a, b, c, x, y, z, first, middle, last)
"""
    },

    "26_variable_keyword_args": {
        "title": "Function arguments: *args, **kwargs packing and unpacking",
        "code": """
def format_signature(req, opt=10, *args, **kwargs):
    return (req, opt, args, sorted(kwargs.items()))

res1 = format_signature(1, 2, 3, 4, a=100, b=200)
positional = (5, 6, 7)
keywords = {"x": 10, "y": 20}
res2 = format_signature(*positional, **keywords)
print("var_kwargs:", res1, res2)
"""
    },

    "27_recursive_functions": {
        "title": "Recursion: Recursive factorial, fibonacci, and tree sum",
        "code": """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

def fibonacci(n):
    if n <= 0:
        return 0
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n - 2)

tree = [1, [2, [3, 4], 5], [6, 7]]
def sum_nested(lst):
    total = 0
    for item in lst:
        if isinstance(item, list):
            total += sum_nested(item)
        else:
            total += item
    return total

print("recursive:", factorial(6), fibonacci(8), sum_nested(tree))
"""
    },

    "28_string_methods_slicing": {
        "title": "Strings: Slicing, transformations, formatting, and methods",
        "code": """
s = "  Tr0ngX TVM Obfuscator 2026  "
stripped = s.strip()
upper = stripped.upper()
words = stripped.split()
rev = stripped[::-1]
sliced = stripped[7:18]
replaced = stripped.replace("2026", "V3")
joined = "-".join(words)
print("string_methods:", upper, words, rev, sliced, replaced, joined)
"""
    },

    "29_bool_logic_ternary": {
        "title": "Boolean logic: Short-circuiting and conditional ternary expressions",
        "code": """
a = 15
b = 30
t1 = "a_larger" if a > b else "b_larger_or_equal"
t2 = "valid" if (a < b and (a != 0 or b != 0)) else "invalid"
t3 = False or (a == 15 and b == 30)
t4 = True and (a == 99 or b == 30)
print("bool_ternary:", t1, t2, t3, t4)
"""
    },

    "30_dictionary_unpacking_updates": {
        "title": "Dictionaries: Unpacking **dict in literals, update(), and item access",
        "code": """
d1 = {"a": 1, "b": 2}
d2 = {"b": 20, "c": 30}
merged = {**d1, **d2, "d": 40}
d1.update({"e": 50, "b": 99})
print("dict_unpacking:", sorted(merged.items()), sorted(d1.items()))
"""
    },

    "31_custom_exceptions_reraise": {
        "title": "Custom Exceptions: User-defined exception classes, parameters, and bare raise",
        "code": """
class CustomAppError(Exception):
    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code

log = []
try:
    try:
        raise CustomAppError("Database query timed out", 504)
    except CustomAppError as err:
        log.append(f"caught_inner_code_{err.error_code}_{str(err)}")
        raise
except CustomAppError as re_err:
    log.append(f"caught_outer_code_{re_err.error_code}")
except Exception:
    log.append("unexpected_fallback")

print("custom_exceptions:", log)
"""
    }
}


# ═══════════════════════════════════════════════════════════════════════════
# ORACLE RUNNER & VERIFICATION ENGINE (SINGLE-THREADED ONLY)
# ═══════════════════════════════════════════════════════════════════════════

class TestResult:
    def __init__(self, key: str, title: str):
        self.key = key
        self.title = title
        self.passed = False
        self.native_stdout = ""
        self.native_stderr = ""
        self.native_code = 0
        self.obf_stdout = ""
        self.obf_stderr = ""
        self.obf_code = 0
        self.duration = 0.0
        self.error_stage: Optional[str] = None
        self.error_message: Optional[str] = None


def run_code_in_subprocess(code_str: str, timeout_sec: float = 5.0) -> Tuple[int, str, str]:
    """
    Executes a Python code string cleanly in an isolated single-threaded subprocess.
    """
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as tf:
        tf.write(code_str)
        temp_file_path = tf.name

    try:
        cmd = [sys.executable, temp_file_path]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Execution timed out (Deadlock / Infinite loop detected)"
    except Exception as e:
        return -2, "", f"Subprocess invocation error: {str(e)}"
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


def evaluate_test_case(key: str, data: Dict[str, Any], seed: int = 42) -> TestResult:
    """
    Runs differential oracle comparison between native Python and TVM obfuscation.
    Strict single-threaded execution.
    """
    result = TestResult(key, data["title"])
    source_code = data["code"].strip()
    t_start = time.perf_counter()

    # Step 1: Run native reference execution
    n_code, n_out, n_err = run_code_in_subprocess(source_code)
    result.native_code = n_code
    result.native_stdout = n_out
    result.native_stderr = n_err

    if n_code != 0:
        result.error_stage = "NATIVE_EXEC_FAIL"
        result.error_message = f"Native code failed with exit code {n_code}: {n_err}"
        result.duration = time.perf_counter() - t_start
        return result

    # Step 2: Obfuscate via TVM
    try:
        obf_code = _vm_obfuscate(source_code, seed=seed, vm_level=1)
    except Exception as e:
        result.error_stage = "OBFUSCATION_COMPILATION_FAIL"
        result.error_message = f"TVM Compiler Exception: {str(e)}"
        result.duration = time.perf_counter() - t_start
        return result

    # Step 3: Run obfuscated execution
    o_code, o_out, o_err = run_code_in_subprocess(obf_code)
    result.obf_code = o_code
    result.obf_stdout = o_out
    result.obf_stderr = o_err
    result.duration = time.perf_counter() - t_start

    # Step 4: Semantic Differential Equivalence Check
    if o_code != n_code:
        result.error_stage = "RETURN_CODE_MISMATCH"
        result.error_message = f"Expected exit code {n_code}, got {o_code}. Stderr: {o_err[:150]}"
        return result

    if o_out != n_out:
        result.error_stage = "STDOUT_MISMATCH"
        result.error_message = f"Expected '{n_out[:100]}', got '{o_out[:100]}'"
        return result

    result.passed = True
    return result


def run_all_oracle_tests(verbose: bool = False) -> List[TestResult]:
    """
    Runs all 31 test cases sequentially in single-threaded mode.
    """
    results: List[TestResult] = []
    total = len(SEMANTIC_TEST_CASES)

    print("=" * 80)
    print(" Tr0ngX Virtual Machine (TVM 2.0) - Semantic Differential Oracle Test Runner")
    print(" Execution Mode: STRICT SINGLE-THREADED (Deterministic)")
    print(f" Total Test Cases: {total}")
    print("=" * 80)

    for idx, (key, data) in enumerate(SEMANTIC_TEST_CASES.items(), start=1):
        res = evaluate_test_case(key, data)
        results.append(res)

        status_tag = "[PASS]" if res.passed else "[FAIL]"
        print(f" {idx:02d}/{total:02d} {status_tag} {key:<32} | {res.title:<40} ({res.duration*1000:6.1f} ms)")
        if not res.passed and verbose:
            print(f"       Reason : {res.error_stage} -> {res.error_message}")
            if res.obf_stderr:
                first_line_err = res.obf_stderr.splitlines()[-1] if res.obf_stderr.splitlines() else res.obf_stderr
                print(f"       Stderr : {first_line_err}")

    return results


def print_summary_report(results: List[TestResult]) -> None:
    """
    Prints a detailed, structured summary report with metrics and failure breakdown.
    """
    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = total - passed_count
    pass_pct = (passed_count / total) * 100.0 if total > 0 else 0.0

    print("\n" + "=" * 80)
    print(" SEMANTIC ORACLE SUMMARY REPORT")
    print("=" * 80)
    print(f" Total Tests Executed : {total}")
    print(f" Passed               : {passed_count} ({pass_pct:.1f}%)")
    print(f" Failed               : {failed_count} ({100.0 - pass_pct:.1f}%)")
    print("=" * 80)

    # Detailed Table
    print(f"{'#':<3} | {'Test ID':<30} | {'Status':<6} | {'Duration':<10} | {'Failure Reason / Stage'}")
    print("-" * 80)
    for idx, r in enumerate(results, start=1):
        status = "PASS" if r.passed else "FAIL"
        reason = "" if r.passed else f"[{r.error_stage}] {r.error_message or ''}"
        dur_str = f"{r.duration*1000:.1f} ms"
        print(f"{idx:<3} | {r.key:<30} | {status:<6} | {dur_str:<10} | {reason[:35]}")
    print("-" * 80)

    if failed_count > 0:
        print("\n [!] Detailed Failure Breakdown for Subagent Remediation:")
        for r in results:
            if not r.passed:
                print(f"\n  • Test: {r.key} ({r.title})")
                print(f"    Stage   : {r.error_stage}")
                print(f"    Expected: {r.native_stdout}")
                print(f"    Actual  : {r.obf_stdout}")
                if r.obf_stderr:
                    print(f"    Stderr  : {r.obf_stderr[:300]}")
    print("=" * 80)


if __name__ == "__main__":
    is_verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test_results = run_all_oracle_tests(verbose=is_verbose)
    print_summary_report(test_results)
    
    # Exit with code 0 if all passed, else 1
    sys.exit(0 if all(r.passed for r in test_results) else 1)
