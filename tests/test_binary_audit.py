# -*- coding: utf-8 -*-
"""
Binary Artifact Audit & Anti-Analysis Verification (Task 3.4)
============================================================
Thoroughly audits the compiled and armored PE binary to verify:
1. Zero-IAT compliance (python312.dll is never in PE Import Table).
2. Zero plaintext Python bytecode (no marshal magic \xa7\r\r\n).
3. Zero sensitive strings (python312.dll, __main__, _auth_decrypt, compute_signature).
4. Stripped Debug Directory & PDB path signatures.
5. Successful execution & functional correctness.
"""

import os
import sys
import tempfile
import subprocess
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import tr0ngx.packagers_native as pn

try:
    import pefile
except ImportError:
    pefile = None


def test_binary_artifact_audit_full():
    test_src = """import sys

def compute_signature():
    base = 0x5452304E4758
    acc = 0
    for i in range(1, 100):
        acc = (acc + i * 37) ^ 0x1337
    return hex((base ^ acc) & 0xFFFFFFFFFFFF)

sig = compute_signature()
print(f"AUDIT_PASS_SIG:{sig}")
sys.exit(0)
"""
    with tempfile.TemporaryDirectory(prefix="trx_audit_") as tmpdir:
        out_exe = os.path.join(tmpdir, "audited_app.exe")
        built_path = pn.package_native_exe(test_src, out_exe, app_name="audited_app", stealth_pe=True,
                                          password="Tr0ngX-Audit-Password!9")
        assert os.path.isfile(built_path)

        with open(built_path, "rb") as f:
            raw_bytes = f.read()

        # 1. Zero-IAT Verification
        if pefile is not None:
            pe = pefile.PE(data=raw_bytes)
            imported_dlls = []
            if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    imported_dlls.append(entry.dll.decode("utf-8", errors="ignore").lower())

            assert "python312.dll" not in imported_dlls, f"Detected python312.dll in Import Table: {imported_dlls}"
            assert "python3.dll" not in imported_dlls, f"Detected python3.dll in Import Table: {imported_dlls}"

            # Debug Directory wiped check
            debug_entry = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DEBUG']]
            assert debug_entry.VirtualAddress == 0, "IMAGE_DIRECTORY_ENTRY_DEBUG VirtualAddress was not wiped"
            assert debug_entry.Size == 0, "IMAGE_DIRECTORY_ENTRY_DEBUG Size was not wiped"

        # 2. Zero-Plaintext Bytecode Check
        # Python 3.12 marshal magic is \xa7\r\r\n
        py312_marshal_magic = b"\xa7\r\r\n"
        assert py312_marshal_magic not in raw_bytes, "Found plaintext Python 3.12 marshal magic in binary!"

        # 3. Sensitive String Anonymization Checks
        forbidden_strings = [
            b"python312.dll",
            b"_auth_decrypt\x00",
            b"compute_signature\x00",
            b"cpython.PyEval_SetTrace",
            b"MinGW-w64 runtime failure:",
            b"Tr0ngX",
            b"t.me/TrongX",
            b"getpass",
            b"argon2id",
        ]
        for s in forbidden_strings:
            assert s not in raw_bytes, f"Found sensitive string in binary: {s}"

        # 4. PDB Signature Check
        assert b"RSDS" not in raw_bytes, "Found RSDS debug signature in binary"

        # 5. Execution Verification (the native loader derives its key from the password)
        env = dict(os.environ)
        env["TR0NGX_PASSWORD"] = "Tr0ngX-Audit-Password!9"
        proc = subprocess.run([built_path], capture_output=True, text=True, timeout=120,
                              env=env, stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        assert "AUDIT_PASS_SIG:0x5452304cafa5" in proc.stdout
