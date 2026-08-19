import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
"""
Test 04: Dynamic Reflection, Custom Decorators & Introspection
Tests: Function Synthesis, Parameterized Decorators, Property Descriptors, Dynamic Namespace Manipulation
"""
import functools, types

# 1. Parameterized Retry & Timing Decorator
def retry(times, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for _ in range(times):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_err = e
            raise last_err
        return wrapper
    return decorator

# 2. Dynamic Property Descriptor
class ValidatedRange:
    def __init__(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return getattr(instance, self.private_name, None)

    def __set__(self, instance, value):
        if not (self.min_val <= value <= self.max_val):
            raise ValueError(f"Value {value} out of range [{self.min_val}, {self.max_val}]")
        setattr(instance, self.private_name, value)

class SensorNode:
    temperature = ValidatedRange(-50, 150)
    def __init__(self, temp):
        self.temperature = temp

# 3. Dynamic Code & Function Type Synthesis
def create_dynamic_calculator(op_name, formula_str):
    code_obj = compile(f"def {op_name}(a, b): return {formula_str}", "<dynamic_calc>", "exec")
    scope = {}
    types.FunctionType(code_obj, scope)()
    # extract function from namespace
    for k, v in scope.items():
        if callable(v):
            return v
    # fallback
    exec(code_obj, scope)
    return scope[op_name]

def run_suite():
    print("[TEST 04] Running Dynamic Reflection & Descriptors Suite...")

    # 1. Retry Decorator
    attempt_count = [0]
    @retry(times=3, exceptions=(RuntimeError,))
    def flaky_network_call():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise RuntimeError("Transient Error")
        return "RESPONSE_200"

    res = flaky_network_call()
    assert res == "RESPONSE_200"
    assert attempt_count[0] == 3
    print("  [PASS] Parameterized Decorator Retry Flow Passed")

    # 2. Descriptor Validation
    s = SensorNode(25)
    assert s.temperature == 25
    try:
        s.temperature = 999
        assert False, "Descriptor validation failed to catch out of range"
    except ValueError:
        pass
    print("  [PASS] Property Descriptor Bound Checking Passed")

    # 3. Dynamic Function Synthesis
    mult_add = create_dynamic_calculator("mult_add", "(a * b) + 10")
    assert mult_add(5, 6) == 40
    print("  [PASS] Dynamic Function Synthesis via Runtime Code Type Passed")

    print("[TEST 04] >>> ALL CHECKS PASSED <<<\n")

if __name__ == "__main__":
    run_suite()
