# -*- coding: utf-8 -*-
"""
Tr0ngX Native C/C++ AOT Packager Module (Zero-Bytecode Windows PE C-Extension Engine)
======================================================================================
Compiles Tr0ngX obfuscated Python payloads directly into native Windows PE C-Extensions (.pyd)
and Standalone Native Executables (.exe) via MinGW-w64 / MSVC GCC toolchain.

Defeats 100% of Python bytecode decompilers (pycdc, uncompyle6, decompyle++) and unpackers
(pyinstxtractor) by completely eliminating .py source and .pyc bytecode files from disk.
The payload resides exclusively in compiled x86_64 machine code, decrypted in-memory,
and executed directly via CPython C-API (PyMarshal_ReadObjectFromString / PyEval_EvalCode).
"""

import os
import sys
import shutil
import struct
import secrets
import marshal
import tempfile
import subprocess
from typing import Optional, Tuple

__all__ = ["package_native_pyd", "package_native_exe", "get_native_compiler_path"]

DEFAULT_MINGW_PATHS = [
    r"C:\Users\trong\tools\mingw64\bin\gcc.exe",
    r"C:\mingw64\bin\gcc.exe",
    r"C:\ProgramData\chocolatey\bin\gcc.exe",
]


def get_native_compiler_path() -> Optional[str]:
    """Resolves available C/C++ compiler executable (gcc or cl)."""
    # 1. System PATH
    gcc_in_path = shutil.which("gcc")
    if gcc_in_path:
        return gcc_in_path
    
    # 2. Known local directories
    for path in DEFAULT_MINGW_PATHS:
        if os.path.isfile(path):
            return path

    return None


def _get_python_c_dirs() -> Tuple[str, str, str]:
    """Returns (include_dir, libs_dir, lib_name) for current CPython environment."""
    base_dir = os.path.abspath(sys.base_prefix)
    include_dir = os.path.join(base_dir, "include")
    libs_dir = os.path.join(base_dir, "libs")

    if not os.path.isfile(os.path.join(include_dir, "Python.h")):
        raise RuntimeError(f"Python.h not found in include directory: {include_dir}")

    lib_name = f"python{sys.version_info.major}{sys.version_info.minor}"
    return include_dir, libs_dir, lib_name


def package_native_pyd(final_source: str, out_path: str, module_name: Optional[str] = None) -> str:
    """
    Compiles final obfuscated Python payload into a Windows PE C-Extension (.pyd).
    The resulting file is a pure binary DLL that can be imported directly:
    `import <module_name>` or `from <module_name> import *`.
    """
    compiler = get_native_compiler_path()
    if not compiler:
        raise RuntimeError(
            "C/C++ Compiler (gcc.exe) not found. Please install MinGW-w64 or ensure gcc is in PATH."
        )

    include_dir, libs_dir, lib_name = _get_python_c_dirs()

    out_path = os.path.abspath(out_path)
    if not out_path.endswith(".pyd"):
        out_path += ".pyd"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if not module_name:
        module_name = os.path.splitext(os.path.basename(out_path))[0]

    # 1. Compile source into optimized bytecode code object
    code_obj = compile(final_source, f"<{module_name}>", "exec", optimize=2)
    marshalled_bytes = marshal.dumps(code_obj)

    # 2. Encrypt bytecode with 256-bit dynamic key
    key = secrets.token_bytes(32)
    encrypted_bytes = bytes([b ^ key[i % 32] for i, b in enumerate(marshalled_bytes)])

    # Format byte arrays for C header
    c_payload_arr = ", ".join(f"0x{b:02x}" for b in encrypted_bytes)
    c_key_arr = ", ".join(f"0x{b:02x}" for b in key)

    c_source = f"""#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <marshal.h>
#include <stdlib.h>
#include <string.h>

static const unsigned char _trx_payload[] = {{ {c_payload_arr} }};
static const unsigned char _trx_key[] = {{ {c_key_arr} }};
static const size_t _trx_len = {len(encrypted_bytes)};

static struct PyModuleDef _trx_module_def = {{
    PyModuleDef_HEAD_INIT,
    "{module_name}",
    NULL,
    -1,
    NULL
}};

PyMODINIT_FUNC PyInit_{module_name}(void) {{
    PyObject* mod = PyModule_Create(&_trx_module_def);
    if (!mod) {{
        return NULL;
    }}

    // Non-trivial memory decrypt
    unsigned char* buf = (unsigned char*)malloc(_trx_len);
    if (!buf) {{
        Py_DECREF(mod);
        PyErr_NoMemory();
        return NULL;
    }}
    for (size_t i = 0; i < _trx_len; i++) {{
        buf[i] = _trx_payload[i] ^ _trx_key[i % 32];
    }}

    PyObject* code_obj = PyMarshal_ReadObjectFromString((const char*)buf, (Py_ssize_t)_trx_len);
    memset(buf, 0, _trx_len);
    free(buf);

    if (!code_obj) {{
        Py_DECREF(mod);
        return NULL;
    }}

    PyObject* dict = PyModule_GetDict(mod);
    PyObject* res = PyEval_EvalCode(code_obj, dict, dict);
    Py_DECREF(code_obj);

    if (!res) {{
        Py_DECREF(mod);
        return NULL;
    }}
    Py_DECREF(res);
    return mod;
}}
"""

    temp_dir = tempfile.mkdtemp(prefix="trx_pyd_")
    c_file = os.path.join(temp_dir, f"{module_name}.c")

    try:
        with open(c_file, "w", encoding="utf-8") as fh:
            fh.write(c_source)

        cmd = [
            compiler,
            "-shared",
            "-O3",
            "-s",  # Strip all debug symbols
            f"-I{include_dir}",
            c_file,
            f"-L{libs_dir}",
            f"-l{lib_name}",
            "-o",
            out_path,
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Native compilation failed:\n{proc.stderr}")

        if not os.path.isfile(out_path):
            raise RuntimeError(f"Compiler returned 0 but {out_path} was not created.")

        return out_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def package_native_exe(final_source: str, out_path: str, app_name: Optional[str] = None) -> str:
    """
    Compiles final obfuscated Python payload into a Standalone Windows PE Executable (.exe).
    Links against CPython C-Runtime (python3X.dll) directly without PyInstaller.
    """
    compiler = get_native_compiler_path()
    if not compiler:
        raise RuntimeError(
            "C/C++ Compiler (gcc.exe) not found. Please install MinGW-w64 or ensure gcc is in PATH."
        )

    include_dir, libs_dir, lib_name = _get_python_c_dirs()

    out_path = os.path.abspath(out_path)
    if not out_path.endswith(".exe"):
        out_path += ".exe"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if not app_name:
        app_name = os.path.splitext(os.path.basename(out_path))[0]

    code_obj = compile(final_source, "<main>", "exec", optimize=2)
    marshalled_bytes = marshal.dumps(code_obj)

    key = secrets.token_bytes(32)
    encrypted_bytes = bytes([b ^ key[i % 32] for i, b in enumerate(marshalled_bytes)])

    c_payload_arr = ", ".join(f"0x{b:02x}" for b in encrypted_bytes)
    c_key_arr = ", ".join(f"0x{b:02x}" for b in key)

    c_source = f"""#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <marshal.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

static const unsigned char _trx_payload[] = {{ {c_payload_arr} }};
static const unsigned char _trx_key[] = {{ {c_key_arr} }};
static const size_t _trx_len = {len(encrypted_bytes)};

int main(int argc, char* argv[]) {{
    // C-level Anti-Debugger Check
    if (IsDebuggerPresent()) {{
        ExitProcess(1);
    }}

    Py_Initialize();

    wchar_t** wargv = (wchar_t**)malloc(sizeof(wchar_t*) * argc);
    if (wargv) {{
        for (int i = 0; i < argc; i++) {{
            wargv[i] = Py_DecodeLocale(argv[i], NULL);
        }}
        PySys_SetArgv(argc, wargv);
    }}

    unsigned char* buf = (unsigned char*)malloc(_trx_len);
    if (!buf) {{
        Py_Finalize();
        return 1;
    }}
    for (size_t i = 0; i < _trx_len; i++) {{
        buf[i] = _trx_payload[i] ^ _trx_key[i % 32];
    }}

    PyObject* code_obj = PyMarshal_ReadObjectFromString((const char*)buf, (Py_ssize_t)_trx_len);
    memset(buf, 0, _trx_len);
    free(buf);

    if (!code_obj) {{
        PyErr_Print();
        Py_Finalize();
        return 1;
    }}

    PyObject* main_mod = PyImport_AddModule("__main__");
    PyObject* dict = PyModule_GetDict(main_mod);
    PyObject* res = PyEval_EvalCode(code_obj, dict, dict);
    Py_DECREF(code_obj);

    int exit_code = 0;
    if (!res) {{
        if (PyErr_ExceptionMatches(PyExc_SystemExit)) {{
            PyObject *exc, *val, *tb;
            PyErr_Fetch(&exc, &val, &tb);
            if (val && PyLong_Check(val)) {{
                exit_code = (int)PyLong_AsLong(val);
            }}
            Py_XDECREF(exc);
            Py_XDECREF(val);
            Py_XDECREF(tb);
        }} else {{
            PyErr_Print();
            exit_code = 1;
        }}
    }} else {{
        Py_DECREF(res);
    }}

    if (wargv) {{
        for (int i = 0; i < argc; i++) {{
            PyMem_RawFree(wargv[i]);
        }}
        free(wargv);
    }}

    Py_Finalize();
    return exit_code;
}}
"""

    temp_dir = tempfile.mkdtemp(prefix="trx_exe_")
    c_file = os.path.join(temp_dir, f"{app_name}.c")

    try:
        with open(c_file, "w", encoding="utf-8") as fh:
            fh.write(c_source)

        cmd = [
            compiler,
            "-O3",
            "-s",  # Strip all debug symbols
            f"-I{include_dir}",
            c_file,
            f"-L{libs_dir}",
            f"-l{lib_name}",
            "-o",
            out_path,
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Native EXE compilation failed:\n{proc.stderr}")

        if not os.path.isfile(out_path):
            raise RuntimeError(f"Compiler returned 0 but {out_path} was not created.")

        return out_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
