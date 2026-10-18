# -*- coding: utf-8 -*-
"""
Tr0ngX Native C/C++ AOT Packager Module (Zero-Bytecode Windows PE C-Extension Engine)
======================================================================================
Compiles Tr0ngX obfuscated Python payloads directly into native Windows PE C-Extensions (.pyd)
and Standalone Native Executables (.exe) via MinGW-w64 / MSVC GCC toolchain.

Equipped with Impenetrable Anti-Reverse Engineering & Decompiler Crashers:
1. Hex-Rays F5 & Ghidra Sleigh Decompiler Crashers (Giant RSP Frame Bomb, Flow Overlaps).
2. Dynamic API Hiding (PEB InMemoryOrderModuleList + MurmurHash3 resolver, zero plaintext IAT).
3. Vectored Exception Handler (VEH) State-Machine Trap Dispatcher (ud2 trap).
4. Silent Key Poison Matrix (dr0-dr7 hardware breakpoints & PEB checks degrade key to garbage).
5. Post-Compilation Binary PE Armorer (section scramble, debug directory & watermark stripping).
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

from .pe_armorer import armor_pe_binary

__all__ = ["package_native_pyd", "package_native_exe", "get_native_compiler_path", "murmur3"]

DEFAULT_MINGW_PATHS = [
    r"C:\Users\trong\tools\mingw64\bin\gcc.exe",
    r"C:\mingw64\bin\gcc.exe",
    r"C:\ProgramData\chocolatey\bin\gcc.exe",
]


def murmur3(key: bytes, seed: int = 0) -> int:
    """32-bit MurmurHash3 matching C implementation for compile-time API hashing."""
    h = seed & 0xFFFFFFFF
    c1, c2 = 0xcc9e2d51, 0x1b873593
    nblocks = len(key) // 4
    for i in range(nblocks):
        k = int.from_bytes(key[i * 4:(i + 1) * 4], "little")
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF
        h = (h * 5 + 0xe6546b64) & 0xFFFFFFFF
    tail = key[nblocks * 4:]
    k1 = 0
    if len(tail) == 3:
        k1 ^= tail[2] << 16
    if len(tail) >= 2:
        k1 ^= tail[1] << 8
    if len(tail) >= 1:
        k1 ^= tail[0]
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h ^= k1
    h ^= len(key)
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    h = (h * 0x85ebca6b) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) & 0xFFFFFFFF
    h = (h * 0xc2b2ae35) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return h


def get_native_compiler_path() -> Optional[str]:
    """Resolves available C/C++ compiler executable (gcc or cl)."""
    gcc_in_path = shutil.which("gcc")
    if gcc_in_path:
        return gcc_in_path
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


def package_native_pyd(final_source: str, out_path: str, module_name: Optional[str] = None, stealth_pe: bool = True) -> str:
    """
    Compiles final obfuscated Python payload into a Windows PE C-Extension (.pyd).
    The resulting file is a pure binary DLL that can be imported directly:
    `import <module_name>` or `from <module_name> import *`.
    """
    compiler = get_native_compiler_path()
    if not compiler:
        raise RuntimeError("C/C++ Compiler (gcc.exe) not found. Please install MinGW-w64 or ensure gcc is in PATH.")

    include_dir, libs_dir, lib_name = _get_python_c_dirs()

    out_path = os.path.abspath(out_path)
    if not out_path.endswith(".pyd"):
        out_path += ".pyd"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if not module_name:
        module_name = os.path.splitext(os.path.basename(out_path))[0]

    code_obj = compile(final_source, f"<{module_name}>", "exec", optimize=2)
    marshalled_bytes = marshal.dumps(code_obj)

    key = secrets.token_bytes(32)
    encrypted_bytes = bytes([b ^ key[i % 32] for i, b in enumerate(marshalled_bytes)])

    c_payload_arr = ", ".join(f"0x{b:02x}" for b in encrypted_bytes)
    c_key_arr = ", ".join(f"0x{b:02x}" for b in key)

    traps_code = ""
    if stealth_pe:
        traps_code = """
    // Hex-Rays & Ghidra Decompiler Crash Traps
    __asm__ volatile (
        "push %%rax\\n\\t"
        "xor %%eax, %%eax\\n\\t"
        "jz 1f\\n\\t"
        ".byte 0x48, 0x89, 0x8C, 0x24, 0xEF, 0xBE, 0xAD, 0xDE\\n\\t"
        "1:\\n\\t"
        "pop %%rax\\n\\t"
        ::: "rax", "memory"
    );
    __asm__ volatile (
        ".byte 0xEB, 0x03\\n\\t"
        ".byte 0xE8, 0x5A, 0x3F\\n\\t"
        ::: "memory"
    );
"""

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
{traps_code}
    PyObject* mod = PyModule_Create(&_trx_module_def);
    if (!mod) {{
        return NULL;
    }}

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
            "-s",
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

        if stealth_pe:
            armor_pe_binary(out_path)

        return out_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def package_native_exe(final_source: str, out_path: str, app_name: Optional[str] = None, stealth_pe: bool = True) -> str:
    """
    Compiles final obfuscated Python payload into a Standalone Windows PE Executable (.exe).
    Links against CPython C-Runtime (python3X.dll) directly without PyInstaller.

    When stealth_pe=True:
    - Hex-Rays F5 & Ghidra Decompiler Crashers (Stack offset bomb, flow overlaps).
    - Dynamic PEB EAT Walker & MurmurHash3 API Resolution (Zero plaintext imports for sensitive APIs).
    - Vectored Exception Handler (VEH) State-Machine Dispatcher (ud2 trap).
    - Silent Poison Matrix: Hardware Breakpoints (DR0-DR3, DR7) and PEB checks silently corrupt the key.
    - Post-compilation PE Armorer strips debug dirs and scrambles section names.
    """
    compiler = get_native_compiler_path()
    if not compiler:
        raise RuntimeError("C/C++ Compiler (gcc.exe) not found. Please install MinGW-w64 or ensure gcc is in PATH.")

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

    murmur_seed = secrets.randbits(32)
    k32_hash = murmur3(b"kernel32.dll", murmur_seed)
    ntdll_hash = murmur3(b"ntdll.dll", murmur_seed)
    va_hash = murmur3(b"VirtualAlloc", murmur_seed)
    vp_hash = murmur3(b"VirtualProtect", murmur_seed)
    veh_add_hash = murmur3(b"RtlAddVectoredExceptionHandler", murmur_seed)
    veh_rem_hash = murmur3(b"RtlRemoveVectoredExceptionHandler", murmur_seed)
    gtc_hash = murmur3(b"GetThreadContext", murmur_seed)
    stc_hash = murmur3(b"SetThreadContext", murmur_seed)
    gct_hash = murmur3(b"GetCurrentThread", murmur_seed)

    c_source = f"""#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <marshal.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <windows.h>
#include <winternl.h>

static const unsigned char _trx_payload[] = {{ {c_payload_arr} }};
static const unsigned char _trx_key[] = {{ {c_key_arr} }};
static const size_t _trx_len = {len(encrypted_bytes)};
static const uint32_t _TRX_SEED = 0x{murmur_seed:08X}U;
static const uint32_t _HASH_K32 = 0x{k32_hash:08X}U;
static const uint32_t _HASH_NTDLL = 0x{ntdll_hash:08X}U;
static const uint32_t _HASH_VA  = 0x{va_hash:08X}U;
static const uint32_t _HASH_VP  = 0x{vp_hash:08X}U;
static const uint32_t _HASH_VEH_ADD = 0x{veh_add_hash:08X}U;
static const uint32_t _HASH_VEH_REM = 0x{veh_rem_hash:08X}U;
static const uint32_t _HASH_GTC = 0x{gtc_hash:08X}U;
static const uint32_t _HASH_STC = 0x{stc_hash:08X}U;
static const uint32_t _HASH_GCT = 0x{gct_hash:08X}U;

// Global silent poison accumulator
static volatile uint32_t _trx_poison_accum = 0;
static volatile int _trx_veh_hit = 0;

// MurmurHash3 (32-bit) in-memory API hashing
static inline uint32_t _trx_murmur3(const char* key, size_t len, uint32_t seed) {{
    uint32_t h = seed;
    const uint32_t c1 = 0xcc9e2d51;
    const uint32_t c2 = 0x1b873593;
    const size_t nblocks = len / 4;
    const uint32_t* blocks = (const uint32_t*)(key);
    for (size_t i = 0; i < nblocks; i++) {{
        uint32_t k = blocks[i];
        k *= c1;
        k = (k << 15) | (k >> 17);
        k *= c2;
        h ^= k;
        h = (h << 13) | (h >> 19);
        h = h * 5 + 0xe6546b64;
    }}
    const uint8_t* tail = (const uint8_t*)(key + nblocks * 4);
    uint32_t k1 = 0;
    switch (len & 3) {{
        case 3: k1 ^= tail[2] << 16;
        case 2: k1 ^= tail[1] << 8;
        case 1: k1 ^= tail[0];
                k1 *= c1;
                k1 = (k1 << 15) | (k1 >> 17);
                k1 *= c2;
                h ^= k1;
    }};
    h ^= (uint32_t)len;
    h ^= h >> 16;
    h *= 0x85ebca6b;
    h ^= h >> 13;
    h *= 0xc2b2ae35;
    h ^= h >> 16;
    return h;
}}

// In-Memory Module Traversal
typedef struct _TRX_LDR_ENTRY {{
    LIST_ENTRY InLoadOrderLinks;
    LIST_ENTRY InMemoryOrderLinks;
    LIST_ENTRY InInitializationOrderLinks;
    PVOID DllBase;
    PVOID EntryPoint;
    ULONG SizeOfImage;
    UNICODE_STRING FullDllName;
    UNICODE_STRING BaseDllName;
}} TRX_LDR_ENTRY;

static HMODULE _trx_get_module_by_hash(uint32_t name_hash, uint32_t seed) {{
    PPEB pPeb = (PPEB)__readgsqword(0x60);
    PPEB_LDR_DATA pLdr = pPeb->Ldr;
    PLIST_ENTRY pHead = &pLdr->InMemoryOrderModuleList;
    PLIST_ENTRY pCurr = pHead->Flink;

    while (pCurr != pHead) {{
        TRX_LDR_ENTRY* entry = CONTAINING_RECORD(pCurr, TRX_LDR_ENTRY, InMemoryOrderLinks);
        if (entry->BaseDllName.Buffer) {{
            char name_buf[256];
            int i = 0;
            for (; i < entry->BaseDllName.Length / sizeof(wchar_t) && i < 255; i++) {{
                wchar_t c = entry->BaseDllName.Buffer[i];
                if (c >= 'A' && c <= 'Z') c += ('a' - 'A');
                name_buf[i] = (char)c;
            }}
            name_buf[i] = '\\0';
            if (_trx_murmur3(name_buf, i, seed) == name_hash) {{
                return (HMODULE)entry->DllBase;
            }}
        }}
        pCurr = pCurr->Flink;
    }}
    return NULL;
}}

static FARPROC _trx_get_proc_by_hash(HMODULE hMod, uint32_t func_hash, uint32_t seed) {{
    if (!hMod) return NULL;
    unsigned char* base = (unsigned char*)hMod;
    PIMAGE_DOS_HEADER dos = (PIMAGE_DOS_HEADER)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return NULL;
    PIMAGE_NT_HEADERS nt = (PIMAGE_NT_HEADERS)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return NULL;

    DWORD exp_rva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress;
    if (!exp_rva) return NULL;
    PIMAGE_EXPORT_DIRECTORY exp = (PIMAGE_EXPORT_DIRECTORY)(base + exp_rva);

    DWORD* names = (DWORD*)(base + exp->AddressOfNames);
    WORD* ordinals = (WORD*)(base + exp->AddressOfNameOrdinals);
    DWORD* funcs = (DWORD*)(base + exp->AddressOfFunctions);

    for (DWORD i = 0; i < exp->NumberOfNames; i++) {{
        const char* name = (const char*)(base + names[i]);
        if (_trx_murmur3(name, strlen(name), seed) == func_hash) {{
            return (FARPROC)(base + funcs[ordinals[i]]);
        }}
    }}
    return NULL;
}}

// VEH Trap Handler: Intercepts illegal instructions (ud2) and resumes
LONG WINAPI _trx_veh_handler(PEXCEPTION_POINTERS pExc) {{
    if (pExc->ExceptionRecord->ExceptionCode == EXCEPTION_ILLEGAL_INSTRUCTION) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0x0F && rip[1] == 0x0B) {{
            _trx_veh_hit = 1;
            pExc->ContextRecord->Rip += 2; // Skip past ud2
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }}
    return EXCEPTION_CONTINUE_SEARCH;
}}

static inline void _trx_anti_analysis_check() {{
    PPEB pPeb = (PPEB)__readgsqword(0x60);
    DWORD nt_global_flag = *(DWORD*)((unsigned char*)pPeb + 0xBC);
    if (pPeb->BeingDebugged || (nt_global_flag & 0x70)) {{
        // Silent poison: accumulate delta instead of immediate crash
        _trx_poison_accum += 0x9E3779B9;
    }}

    HMODULE hK32 = _trx_get_module_by_hash(_HASH_K32, _TRX_SEED);
    if (hK32) {{
        typedef HANDLE (WINAPI *pfn_gct)(VOID);
        typedef BOOL (WINAPI *pfn_gtc)(HANDLE, LPCONTEXT);
        typedef BOOL (WINAPI *pfn_stc)(HANDLE, const CONTEXT*);

        pfn_gct fn_gct = (pfn_gct)_trx_get_proc_by_hash(hK32, _HASH_GCT, _TRX_SEED);
        pfn_gtc fn_gtc = (pfn_gtc)_trx_get_proc_by_hash(hK32, _HASH_GTC, _TRX_SEED);
        pfn_stc fn_stc = (pfn_stc)_trx_get_proc_by_hash(hK32, _HASH_STC, _TRX_SEED);

        if (fn_gct && fn_gtc) {{
            CONTEXT ctx;
            memset(&ctx, 0, sizeof(ctx));
            ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
            HANDLE hThread = fn_gct();
            if (fn_gtc(hThread, &ctx)) {{
                if (ctx.Dr0 != 0 || ctx.Dr1 != 0 || ctx.Dr2 != 0 || ctx.Dr3 != 0 || (ctx.Dr7 & 0xFF) != 0) {{
                    // Hardware breakpoint detected!
                    _trx_poison_accum += 0xDEAD1337;
                    // Scrub hardware breakpoints
                    ctx.Dr0 = 0; ctx.Dr1 = 0; ctx.Dr2 = 0; ctx.Dr3 = 0;
                    ctx.Dr6 = 0; ctx.Dr7 = 0;
                    if (fn_stc) {{
                        fn_stc(hThread, &ctx);
                    }}
                }}
            }}
        }}
    }}
}}

static inline void _trx_decompiler_crash_traps() {{
    // Trap 1: Giant RSP stack offset (Hex-Rays Microcode OOM / positive SP failure)
    __asm__ volatile (
        "push %%rax\\n\\t"
        "xor %%eax, %%eax\\n\\t"
        "jz 1f\\n\\t"
        ".byte 0x48, 0x89, 0x8C, 0x24, 0xEF, 0xBE, 0xAD, 0xDE\\n\\t"
        "1:\\n\\t"
        "pop %%rax\\n\\t"
        ::: "rax", "memory"
    );

    // Trap 2: Flow overlap using jmp short over fake CALL opcode
    __asm__ volatile (
        ".byte 0xEB, 0x03\\n\\t"
        ".byte 0xE8, 0x5A, 0x3F\\n\\t"
        ::: "memory"
    );

    // Trap 3: Opaque Carry flag condition
    __asm__ volatile (
        "stc\\n\\t"
        "jc 2f\\n\\t"
        ".byte 0x48, 0x83, 0xEC, 0x7F\\n\\t"
        "2:\\n\\t"
        ::: "memory"
    );
}}

int main(int argc, char* argv[]) {{
    _trx_decompiler_crash_traps();
    _trx_anti_analysis_check();

    // Register VEH Handler dynamically via ntdll.dll
    HMODULE hNt = _trx_get_module_by_hash(_HASH_NTDLL, _TRX_SEED);
    PVOID hVeh = NULL;
    typedef PVOID (WINAPI *pfn_add_veh)(ULONG, PVECTORED_EXCEPTION_HANDLER);
    typedef ULONG (WINAPI *pfn_rem_veh)(PVOID);
    pfn_add_veh fn_add_veh = NULL;
    pfn_rem_veh fn_rem_veh = NULL;
    if (hNt) {{
        fn_add_veh = (pfn_add_veh)_trx_get_proc_by_hash(hNt, _HASH_VEH_ADD, _TRX_SEED);
        fn_rem_veh = (pfn_rem_veh)_trx_get_proc_by_hash(hNt, _HASH_VEH_REM, _TRX_SEED);
        if (fn_add_veh) {{
            hVeh = fn_add_veh(1, _trx_veh_handler);
        }}
    }}

    // Trigger intentional ud2 trap only if VEH was registered
    if (hVeh) {{
        __asm__ volatile (".byte 0x0F, 0x0B\\n\\t" ::: "memory");
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

    // Decrypt with Silent Poison feedback
    for (size_t i = 0; i < _trx_len; i++) {{
        uint8_t p_byte = (uint8_t)(_trx_poison_accum >> ((i % 4) * 8));
        buf[i] = _trx_payload[i] ^ _trx_key[i % 32] ^ p_byte;
    }}

    PyObject* code_obj = PyMarshal_ReadObjectFromString((const char*)buf, (Py_ssize_t)_trx_len);
    memset(buf, 0, _trx_len);
    free(buf);

    if (!code_obj) {{
        // If poisoned by debugger/hook, marshal read fails or decrypts to garbage
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

    if (hVeh && fn_rem_veh) {{
        fn_rem_veh(hVeh);
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
            "-s",
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

        if stealth_pe:
            armor_pe_binary(out_path)

        return out_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
