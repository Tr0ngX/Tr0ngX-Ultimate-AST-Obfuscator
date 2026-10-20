# -*- coding: utf-8 -*-
"""
Differential Correctness Tests:
Verifies that Native AOT compilation maintains 100% semantic equivalence with Python reference.
"""

import os
import sys
import tempfile
import subprocess
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tr0ngx.aot_compiler import AOTRegistry, is_aot_candidate
from tr0ngx.packagers_native import package_native_exe


def python_reference_signature() -> str:
    base = 0x5452304E4758
    acc = 0
    for i in range(1, 100):
        acc = (acc + i * 37) ^ 0x1337
    return hex((base ^ acc) & 0xFFFFFFFFFFFF)


def test_python_reference_constant():
    """Confirms oracle reference value."""
    ref = python_reference_signature()
    assert ref == "0x5452304cafa5"


def test_aot_ast_extraction():
    """Confirms that AOT candidate functions are extracted and removed from Python AST."""
    src = """
def compute_signature():
    return 123

print(compute_signature())
"""
    registry = AOTRegistry()
    transformed, funcs = registry.scan_and_extract(src)
    assert "compute_signature" in funcs
    assert "def compute_signature" not in transformed
    assert "print(compute_signature())" in transformed


def test_aot_end_to_end_in_exe():
    """Builds a Native EXE with compute_signature, runs it, and asserts exact match with Python oracle."""
    test_src = """import sys
def compute_signature():
    base = 0x5452304E4758
    acc = 0
    for i in range(1, 100):
        acc = (acc + i * 37) ^ 0x1337
    return hex((base ^ acc) & 0xFFFFFFFFFFFF)

sig = compute_signature()
print(f"TRX_SIGNATURE:{sig}")
sys.exit(0)
"""
    with tempfile.TemporaryDirectory(prefix="trx_aot_test_") as tmpdir:
        out_exe = os.path.join(tmpdir, "test_aot_app.exe")
        built_path = package_native_exe(test_src, out_exe, app_name="test_aot_app", stealth_pe=False,
                                       password="Tr0ngX-AOT-Password!3")
        assert os.path.isfile(built_path)

        env = dict(os.environ)
        env["TR0NGX_PASSWORD"] = "Tr0ngX-AOT-Password!3"
        proc = subprocess.run([built_path], capture_output=True, text=True, timeout=120,
                              env=env, stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        assert f"TRX_SIGNATURE:{python_reference_signature()}" in proc.stdout


def test_aot_bytecode_eradication_proof():
    """Proves that extracted AOT function does NOT leave any Python bytecode in the compiled CodeObject."""
    import marshal
    test_src = """
def compute_signature():
    base = 0x5452304E4758
    acc = 0
    for i in range(1, 100):
        acc = (acc + i * 37) ^ 0x1337
    return hex((base ^ acc) & 0xFFFFFFFFFFFF)

sig = compute_signature()
"""
    registry = AOTRegistry()
    transformed, funcs = registry.scan_and_extract(test_src)
    code_obj = compile(transformed, "<main>", "exec", optimize=2)
    marshalled = marshal.dumps(code_obj)

    # In Python bytecode, function definitions produce a code object constant named 'compute_signature'
    # Check that no code object with that name exists in co_consts
    const_code_names = [c.co_name for c in code_obj.co_consts if hasattr(c, "co_name")]
    assert "compute_signature" not in const_code_names

    # Ensure the function name only exists as a global Name lookup (calling the C function from dict)
    assert "compute_signature" in code_obj.co_names


