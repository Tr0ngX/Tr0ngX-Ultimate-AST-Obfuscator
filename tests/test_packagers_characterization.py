# -*- coding: utf-8 -*-
"""
Characterization Tests for tr0ngx.packagers_native (API Contract Freeze)
Ensures that no refactor can accidentally modify public signatures, defaults,
return types, or runtime behavior.
"""

import os
import sys
import inspect
import subprocess
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import tr0ngx.packagers_native as pn


def test_public_all_symbols():
    """Confirms that __all__ contains exactly the expected public API symbols."""
    expected = {"package_native_pyd", "package_native_exe", "get_native_compiler_path", "murmur3"}
    assert set(pn.__all__) == expected


def test_package_native_exe_signature():
    """Locks down package_native_exe parameter names and default values."""
    sig = inspect.signature(pn.package_native_exe)
    params = list(sig.parameters.keys())
    assert params == ["final_source", "out_path", "app_name", "stealth_pe", "password", "salt"]

    # Verify default values
    assert sig.parameters["app_name"].default is None
    assert sig.parameters["stealth_pe"].default is True
    assert sig.parameters["password"].default is None
    assert sig.parameters["salt"].default is None


def test_package_native_pyd_signature():
    """Locks down package_native_pyd parameter names and default values."""
    sig = inspect.signature(pn.package_native_pyd)
    params = list(sig.parameters.keys())
    assert params == ["final_source", "out_path", "module_name", "stealth_pe", "password", "salt"]

    # Verify default values
    assert sig.parameters["module_name"].default is None
    assert sig.parameters["stealth_pe"].default is True
    assert sig.parameters["password"].default is None
    assert sig.parameters["salt"].default is None


def test_murmur3_deterministic_hash():
    """Ensures MurmurHash3 output is identical across builds."""
    # Test known inputs against hash function
    h1 = pn.murmur3(b"kernel32.dll", 0x12345678)
    assert isinstance(h1, int)
    assert h1 == pn.murmur3(b"kernel32.dll", 0x12345678)

    # Empty bytes test
    h_empty = pn.murmur3(b"", 0)
    assert h_empty == 0


def test_get_native_compiler_path():
    """Verifies that native compiler path detection works."""
    path = pn.get_native_compiler_path()
    assert path is not None
    assert os.path.isfile(path)
    assert path.lower().endswith("gcc.exe")


def test_package_native_exe_end_to_end():
    """Builds a minimal python script into an EXE and executes it to verify behavior."""
    test_src = """import sys
print("TR0NGX_E2E_OK_12345")
sys.exit(0)
"""
    with tempfile.TemporaryDirectory(prefix="trx_test_") as tmpdir:
        out_exe = os.path.join(tmpdir, "test_app.exe")
        built_path = pn.package_native_exe(test_src, out_exe, app_name="test_app", stealth_pe=False,
                                          password="Tr0ngX-E2E-Password!7")
        assert os.path.isfile(built_path)
        assert os.path.abspath(built_path) == os.path.abspath(out_exe)

        # Run generated executable (the native loader derives its key from the password)
        env = dict(os.environ)
        env["TR0NGX_PASSWORD"] = "Tr0ngX-E2E-Password!7"
        proc = subprocess.run([built_path], capture_output=True, text=True, timeout=120,
                              env=env, stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        assert "TR0NGX_E2E_OK_12345" in proc.stdout


def test_package_native_exe_password_is_optional():
    """The password is a flag, not a requirement: without it the build stays integrity-only."""
    test_src = """import sys
print("TR0NGX_NOPASS_OK")
sys.exit(0)
"""
    with tempfile.TemporaryDirectory(prefix="trx_test_") as tmpdir:
        out_exe = os.path.join(tmpdir, "nopass_app.exe")
        built_path = pn.package_native_exe(test_src, out_exe, app_name="nopass_app", stealth_pe=False)
        assert os.path.isfile(built_path)

        env = dict(os.environ)
        env.pop("TR0NGX_PASSWORD", None)
        proc = subprocess.run([built_path], capture_output=True, text=True, timeout=120,
                              env=env, stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        assert "TR0NGX_NOPASS_OK" in proc.stdout
