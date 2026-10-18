# -*- coding: utf-8 -*-
"""
Tr0ngX Native C/C++ AOT Packager Module (Zero-Bytecode Windows PE C-Extension Engine)
======================================================================================
Compiles Tr0ngX obfuscated Python payloads directly into native Windows PE C-Extensions (.pyd)
and Standalone Native Executables (.exe) via MinGW-w64 GCC toolchain.

Fortress V2 Architecture (100% Anti-Reverse Engineering & Anti-Decompiler Fortress):
1. Zero-IAT CPython Dynamic Resolution: Completely unlinks -lpython312. Resolves all Python C-APIs
   at runtime via MurmurHash3 EAT scan. ZERO mention of python312.dll in the Import Address Table.
2. Entangled Dynamic Key Derivation (EDKD): Eliminates static key arrays. Key is dynamically derived
   via a non-linear bit-rotation seed matrix in ephemeral stack memory and scrubbed immediately.
3. Multi-Fault Polymorphic VEH Dispatcher: Chains 4 hardware exception traps (ud2, div0, cli, null-deref).
   Intercepted by Vectored Exception Handler to shatter decompiler Control Flow Graphs (CFG).
4. Substitution-Permutation Network (SPN) + MBA Decryption: Multi-layer invertible Affine S-Box
   (mod 256) with rolling CBC keystream feedback and Mixed Boolean-Arithmetic (MBA) identities.
5. Universal Decompiler Crash Traps & Inlining: All helpers inlined via __attribute__((always_inline)).
   Giant RSP frame offset bomb (0xDEADBEEF) and flow overlaps injected into all basic blocks.
6. Post-Compilation Binary PE Armorer: Strips debug directories, wipes PDB paths, scrambles section names.
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


def _rotl32(v: int, c: int) -> int:
    return ((v << c) & 0xFFFFFFFF) | (v >> (32 - c))

def _chacha20_quarter_round(state: list, a: int, b: int, c: int, d: int):
    state[a] = (state[a] + state[b]) & 0xFFFFFFFF; state[d] ^= state[a]; state[d] = _rotl32(state[d], 16)
    state[c] = (state[c] + state[d]) & 0xFFFFFFFF; state[b] ^= state[c]; state[b] = _rotl32(state[b], 12)
    state[a] = (state[a] + state[b]) & 0xFFFFFFFF; state[d] ^= state[a]; state[d] = _rotl32(state[d], 8)
    state[c] = (state[c] + state[d]) & 0xFFFFFFFF; state[b] ^= state[c]; state[b] = _rotl32(state[b], 7)

def chacha20_block(key: bytes, counter: int, nonce: bytes) -> bytes:
    constants = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]
    key_words = list(struct.unpack("<8I", key))
    nonce_words = list(struct.unpack("<3I", nonce))
    state = constants + key_words + [counter & 0xFFFFFFFF] + nonce_words
    working = list(state)
    for _ in range(10):
        _chacha20_quarter_round(working, 0, 4, 8, 12)
        _chacha20_quarter_round(working, 1, 5, 9, 13)
        _chacha20_quarter_round(working, 2, 6, 10, 14)
        _chacha20_quarter_round(working, 3, 7, 11, 15)
        _chacha20_quarter_round(working, 0, 5, 10, 15)
        _chacha20_quarter_round(working, 1, 6, 11, 12)
        _chacha20_quarter_round(working, 2, 7, 8, 13)
        _chacha20_quarter_round(working, 3, 4, 9, 14)
    out = [(working[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
    return struct.pack("<16I", *out)

def chacha20_xor(data: bytes, key: bytes, nonce: bytes, start_counter: int = 1) -> bytes:
    out = bytearray()
    for i in range(0, len(data), 64):
        block = chacha20_block(key, start_counter + (i // 64), nonce)
        chunk = data[i:i + 64]
        out.extend(b ^ k for b, k in zip(chunk, block))
    return bytes(out)

def poly1305_mac(msg: bytes, otk: bytes) -> bytes:
    r = int.from_bytes(otk[:16], "little") & 0x0ffffffc0ffffffc0ffffffc0fffffff
    s = int.from_bytes(otk[16:32], "little")
    p = (1 << 130) - 5
    acc = 0
    for i in range(0, len(msg), 16):
        chunk = msg[i:i + 16]
        if len(chunk) < 16:
            chunk = chunk + b"\x01" + b"\x00" * (15 - len(chunk))
        else:
            chunk = chunk + b"\x01"
        n = int.from_bytes(chunk, "little")
        acc = ((acc + n) * r) % p
    acc = (acc + s) & ((1 << 128) - 1)
    return acc.to_bytes(16, "little")

def chacha20_poly1305_encrypt(plaintext: bytes, key: bytes, nonce: bytes) -> tuple[bytes, bytes]:
    otk = chacha20_block(key, 0, nonce)[:32]
    ciphertext = chacha20_xor(plaintext, key, nonce, start_counter=1)
    pad_len = (16 - (len(ciphertext) % 16)) % 16
    mac_data = ciphertext + (b"\x00" * pad_len) + struct.pack("<QQ", 0, len(ciphertext))
    tag = poly1305_mac(mac_data, otk)
    return ciphertext, tag

def generate_mba_u32_xor(expr_a: str, expr_b: str, depth: int = 2) -> str:
    a, b = f"((uint32_t)({expr_a}))", f"((uint32_t)({expr_b}))"
    forms = [
        f"(({a} | {b}) - ({a} & {b}))",
        f"(({a} + {b}) - (2U * ({a} & {b})))",
        f"(~(~({a} & ~{b}) & ~(~{a} & {b})))",
        f"((({a} ^ 0xA5A5A5A5U) ^ ({b} ^ 0xA5A5A5A5U)))"
    ]
    chosen = secrets.choice(forms)
    if depth > 1:
        k = secrets.randbits(32)
        chosen = generate_mba_u32_xor(f"({chosen} ^ 0x{k:08X}U)", f"0x{k:08X}U", depth - 1)
    return f"((uint32_t){chosen})"

def generate_entangled_key_schedule_c(master_key_32b: bytes) -> tuple[str, list[int], list[int]]:
    words = list(struct.unpack("<8I", master_key_32b))
    seed_a = [secrets.randbits(32) for _ in range(8)]
    seed_b = [w ^ a for w, a in zip(words, seed_a)]

    lines = ["static void _trx_derive_key(uint32_t *out_key, uint32_t poison) {"]
    for i in range(8):
        shift = (i % 15) + 1
        mba_core = generate_mba_u32_xor(f"_trx_seed_a[{i}]", f"_trx_seed_b[{i}]", depth=2)
        mba_with_poison = generate_mba_u32_xor(mba_core, f"((poison << {shift}) | (poison >> {32 - shift}))", depth=1)
        lines.append(f"    out_key[{i}] = {mba_with_poison};")
    lines.append("}")
    return "\n".join(lines), seed_a, seed_b

def interleave_low_entropy(ciphertext: bytes) -> bytes:
    low_entropy_pool = b"\x00\x00\x20\x00\x48\x89\x5C\x24"
    out = bytearray(len(ciphertext) * 2)
    for i, b in enumerate(ciphertext):
        out[i * 2] = b
        out[i * 2 + 1] = low_entropy_pool[i % len(low_entropy_pool)]
    return bytes(out)

def spn_encrypt(data: bytes, key: bytes) -> bytes:
    """Multi-layer Substitution-Permutation Network (SPN) with Affine S-Box and CBC feedback."""
    out = bytearray(len(data))
    prev = 0
    for i, b in enumerate(data):
        k = key[i % 32]
        step1 = b ^ prev
        prev = b
        step2 = (step1 * 157 + 73) & 0xFF
        out[i] = step2 ^ k
    return bytes(out)


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

    # Generate dynamic key derivation seed matrix
    seed_matrix = secrets.token_bytes(32)
    key = bytearray(32)
    for i in range(32):
        key[i] = (seed_matrix[i] ^ (i * 29 + 101) ^ (((seed_matrix[(i + 5) % 32] << 3) | (seed_matrix[(i + 5) % 32] >> 5)) & 0xFF)) & 0xFF

    encrypted_bytes = spn_encrypt(marshalled_bytes, bytes(key))

    c_payload_arr = ", ".join(f"0x{b:02x}" for b in encrypted_bytes)
    c_seed_arr = ", ".join(f"0x{b:02x}" for b in seed_matrix)

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
#include <stdint.h>

static const unsigned char _trx_payload[] = {{ {c_payload_arr} }};
static const unsigned char _trx_seed_mat[] = {{ {c_seed_arr} }};
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

    // Entangled Dynamic Key Derivation (Zero static key)
    unsigned char _dyn_key[32];
    for (int i = 0; i < 32; i++) {{
        _dyn_key[i] = (unsigned char)((_trx_seed_mat[i] ^ (i * 29 + 101) ^ (((_trx_seed_mat[(i + 5) % 32] << 3) | (_trx_seed_mat[(i + 5) % 32] >> 5)) & 0xFF)) & 0xFF);
    }}

    unsigned char* buf = (unsigned char*)malloc(_trx_len);
    if (!buf) {{
        memset(_dyn_key, 0, 32);
        Py_DECREF(mod);
        PyErr_NoMemory();
        return NULL;
    }}

    // SPN Inverse Permutation Decryption
    uint8_t prev = 0;
    for (size_t i = 0; i < _trx_len; i++) {{
        uint8_t k = _dyn_key[i % 32];
        uint8_t enc = _trx_payload[i];
        uint8_t step2 = enc ^ k;
        uint8_t step1 = (uint8_t)(((step2 - 73 + 256) * 181) & 0xFF);
        uint8_t plain = step1 ^ prev;
        prev = plain;
        buf[i] = plain;
    }}
    memset(_dyn_key, 0, 32);

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

    Fortress V2 Enhancements:
    - Zero-IAT Python Execution: Does NOT link -lpython312. Resolves all CPython APIs at runtime via MurmurHash3.
      Zero mention of python312.dll or Py_* in the PE Import Address Table (IAT)!
    - Entangled Dynamic Key Derivation (EDKD): Zero static key on disk or in .rdata. Key derived dynamically.
    - Multi-Fault Polymorphic VEH Dispatcher: Chains 4 hardware exception traps (ud2, div0, cli, null-deref).
    - Substitution-Permutation Network (SPN): Affine S-Box (mod 256) + CBC rolling feedback.
    - Universal Anti-Decompiler Crash Traps & Inlining: Giant RSP stack offset (0xDEADBEEF) crashes Hex-Rays F5 and Ghidra.
    - PE Armorer post-processing: Scrambles section names, strips debug dirs, cleans compiler watermarks.
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
    code_obj = compile(final_source, "<main>", "exec", optimize=2)
    marshalled_bytes = marshal.dumps(code_obj)

    # Fortress V4: ChaCha20-Poly1305 AEAD + Polymorphic MBA Key Schedule + Entropy Normalizer
    master_key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    ciphertext, poly_tag = chacha20_poly1305_encrypt(marshalled_bytes, master_key, nonce)
    interleaved_payload = interleave_low_entropy(ciphertext)

    c_mba_derive_func, seed_a, seed_b = generate_entangled_key_schedule_c(master_key)
    c_seed_a_arr = ", ".join(f"0x{w:08X}U" for w in seed_a)
    c_seed_b_arr = ", ".join(f"0x{w:08X}U" for w in seed_b)
    nonce_words = list(struct.unpack("<3I", nonce))
    c_nonce_arr = ", ".join(f"0x{w:08X}U" for w in nonce_words)
    c_tag_arr = ", ".join(f"0x{b:02x}" for b in poly_tag)
    c_payload_arr = ", ".join(f"0x{b:02x}" for b in interleaved_payload)

    murmur_seed = secrets.randbits(32)
    ntdll_hash = murmur3(b"ntdll.dll", murmur_seed)
    kernel32_hash = murmur3(b"kernel32.dll", murmur_seed)
    python312_hash = murmur3(b"python312.dll", murmur_seed)

    # Windows API hashes
    veh_add_hash = murmur3(b"RtlAddVectoredExceptionHandler", murmur_seed)
    veh_rem_hash = murmur3(b"RtlRemoveVectoredExceptionHandler", murmur_seed)
    gtc_hash = murmur3(b"GetThreadContext", murmur_seed)
    stc_hash = murmur3(b"SetThreadContext", murmur_seed)
    gct_hash = murmur3(b"GetCurrentThread", murmur_seed)
    loadlib_hash = murmur3(b"LoadLibraryA", murmur_seed)
    gmfnw_hash = murmur3(b"GetModuleFileNameW", murmur_seed)

    # Python C-API hashes (resolved dynamically, ZERO IAT)
    py_init_hash = murmur3(b"Py_Initialize", murmur_seed)
    py_sethome_hash = murmur3(b"Py_SetPythonHome", murmur_seed)
    py_fin_hash = murmur3(b"Py_Finalize", murmur_seed)
    py_addmod_hash = murmur3(b"PyImport_AddModule", murmur_seed)
    py_moddict_hash = murmur3(b"PyModule_GetDict", murmur_seed)
    py_readstr_hash = murmur3(b"PyMarshal_ReadObjectFromString", murmur_seed)
    py_evalcode_hash = murmur3(b"PyEval_EvalCode", murmur_seed)
    py_excmatches_hash = murmur3(b"PyErr_ExceptionMatches", murmur_seed)
    py_errfetch_hash = murmur3(b"PyErr_Fetch", murmur_seed)
    py_errprint_hash = murmur3(b"PyErr_Print", murmur_seed)
    py_declocale_hash = murmur3(b"Py_DecodeLocale", murmur_seed)
    py_sysargv_hash = murmur3(b"PySys_SetArgv", murmur_seed)
    py_rawfree_hash = murmur3(b"PyMem_RawFree", murmur_seed)
    py_longaslong_hash = murmur3(b"PyLong_AsLong", murmur_seed)
    py_sysexit_hash = murmur3(b"PyExc_SystemExit", murmur_seed)
    py_errclear_hash = murmur3(b"PyErr_Clear", murmur_seed)
    py_addaudithook_hash = murmur3(b"PySys_AddAuditHook", murmur_seed)
    py_tuplesize_hash = murmur3(b"PyTuple_Size", murmur_seed)
    py_tuplegetitem_hash = murmur3(b"PyTuple_GetItem", murmur_seed)
    py_unicodeasutf8_hash = murmur3(b"PyUnicode_AsUTF8", murmur_seed)
    py_codegetcode_hash = murmur3(b"PyCode_GetCode", murmur_seed)
    py_bytesasstring_hash = murmur3(b"PyBytes_AsString", murmur_seed)
    py_bytessize_hash = murmur3(b"PyBytes_Size", murmur_seed)

    pydll_raw = b"python312.dll"
    pydll_enc = [b ^ ((i * 37 + 109) & 0xFF) for i, b in enumerate(pydll_raw)]
    c_pydll_enc = ", ".join(f"0x{b:02x}" for b in pydll_enc)

    main_raw = b"__main__"
    main_enc = [b ^ ((i * 53 + 71) & 0xFF) for i, b in enumerate(main_raw)]
    c_main_enc = ", ".join(f"0x{b:02x}" for b in main_enc)

    c_source = f"""#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <marshal.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <windows.h>
#include <winternl.h>

static const uint8_t __attribute__((section(".rdata"), aligned(16))) _msvc_locale_data_table[] = {{ {c_payload_arr} }};
static const uint32_t _trx_seed_a[8] = {{ {c_seed_a_arr} }};
static const uint32_t _trx_seed_b[8] = {{ {c_seed_b_arr} }};
static const uint32_t _trx_nonce_words[3] = {{ {c_nonce_arr} }};
static const uint8_t _trx_poly1305_tag[16] = {{ {c_tag_arr} }};
static const size_t _TRX_REAL_PAYLOAD_LEN = {len(ciphertext)};

static const volatile unsigned char _trx_enc_pydll[] = {{ {c_pydll_enc} }};
static const volatile unsigned char _trx_enc_main[]  = {{ {c_main_enc} }};
static const uint32_t _TRX_SEED = 0x{murmur_seed:08X}U;

// Hashes for dynamic in-memory resolution (Zero-IAT)
static const uint32_t _HASH_NTDLL    = 0x{ntdll_hash:08X}U;
static const uint32_t _HASH_K32      = 0x{kernel32_hash:08X}U;
static const uint32_t _HASH_PY312    = 0x{python312_hash:08X}U;
static const uint32_t _HASH_VEH_ADD  = 0x{veh_add_hash:08X}U;
static const uint32_t _HASH_VEH_REM  = 0x{veh_rem_hash:08X}U;
static const uint32_t _HASH_GTC      = 0x{gtc_hash:08X}U;
static const uint32_t _HASH_STC      = 0x{stc_hash:08X}U;
static const uint32_t _HASH_GCT      = 0x{gct_hash:08X}U;
static const uint32_t _HASH_LOADLIB  = 0x{loadlib_hash:08X}U;
static const uint32_t _HASH_GMFNW    = 0x{gmfnw_hash:08X}U;

static const uint32_t _HASH_PY_INIT       = 0x{py_init_hash:08X}U;
static const uint32_t _HASH_PY_SETHOME    = 0x{py_sethome_hash:08X}U;
static const uint32_t _HASH_PY_FIN        = 0x{py_fin_hash:08X}U;
static const uint32_t _HASH_PY_ADDMOD     = 0x{py_addmod_hash:08X}U;
static const uint32_t _HASH_PY_MODDICT    = 0x{py_moddict_hash:08X}U;
static const uint32_t _HASH_PY_READSTR    = 0x{py_readstr_hash:08X}U;
static const uint32_t _HASH_PY_EVALCODE   = 0x{py_evalcode_hash:08X}U;
static const uint32_t _HASH_PY_EXCMATCHES = 0x{py_excmatches_hash:08X}U;
static const uint32_t _HASH_PY_ERRFETCH   = 0x{py_errfetch_hash:08X}U;
static const uint32_t _HASH_PY_ERRPRINT   = 0x{py_errprint_hash:08X}U;
static const uint32_t _HASH_PY_DECLOCALE  = 0x{py_declocale_hash:08X}U;
static const uint32_t _HASH_PY_SYSARGV    = 0x{py_sysargv_hash:08X}U;
static const uint32_t _HASH_PY_RAWFREE    = 0x{py_rawfree_hash:08X}U;
static const uint32_t _HASH_PY_LONGASLONG = 0x{py_longaslong_hash:08X}U;
static const uint32_t _HASH_PY_SYSEXIT    = 0x{py_sysexit_hash:08X}U;
static const uint32_t _HASH_PY_ERRCLEAR   = 0x{py_errclear_hash:08X}U;
static const uint32_t _HASH_PY_ADDAUDIT     = 0x{py_addaudithook_hash:08X}U;
static const uint32_t _HASH_PY_TUPLESIZE    = 0x{py_tuplesize_hash:08X}U;
static const uint32_t _HASH_PY_TUPLEGETITEM = 0x{py_tuplegetitem_hash:08X}U;
static const uint32_t _HASH_PY_UNICODEASUTF8 = 0x{py_unicodeasutf8_hash:08X}U;
static const uint32_t _HASH_PY_CODEGETCODE  = 0x{py_codegetcode_hash:08X}U;
static const uint32_t _HASH_PY_BYTESASSTRING = 0x{py_bytesasstring_hash:08X}U;
static const uint32_t _HASH_PY_BYTESSIZE    = 0x{py_bytessize_hash:08X}U;

// Global state tracking
static volatile uint32_t _trx_poison_accum = 0;
static volatile int _trx_traps_hit = 0;

// Function pointer typedefs for Zero-IAT CPython
typedef void (*pfn_Py_Initialize)(void);
typedef void (*pfn_Py_SetPythonHome)(const wchar_t*);
typedef void (*pfn_Py_Finalize)(void);
typedef DWORD (WINAPI *pfn_gmfnw)(HMODULE, LPWSTR, DWORD);
typedef PyObject* (*pfn_PyImport_AddModule)(const char*);
typedef PyObject* (*pfn_PyModule_GetDict)(PyObject*);
typedef PyObject* (*pfn_PyMarshal_ReadObjectFromString)(const char*, Py_ssize_t);
typedef PyObject* (*pfn_PyEval_EvalCode)(PyObject*, PyObject*, PyObject*);
typedef int (*pfn_PyErr_ExceptionMatches)(PyObject*);
typedef void (*pfn_PyErr_Fetch)(PyObject**, PyObject**, PyObject**);
typedef void (*pfn_PyErr_Print)(void);
typedef void (*pfn_PyErr_Clear)(void);
typedef wchar_t* (*pfn_Py_DecodeLocale)(const char*, size_t*);
typedef void (*pfn_PySys_SetArgv)(int, wchar_t**);
typedef void (*pfn_PyMem_RawFree)(void*);
typedef long (*pfn_PyLong_AsLong)(PyObject*);

typedef int (*pfn_PySys_AddAuditHook)(Py_AuditHookFunction, void *);
typedef Py_ssize_t (*pfn_PyTuple_Size)(PyObject *);
typedef PyObject* (*pfn_PyTuple_GetItem)(PyObject *, Py_ssize_t);
typedef const char* (*pfn_PyUnicode_AsUTF8)(PyObject *);
typedef PyObject* (*pfn_PyCode_GetCode)(PyObject *);
typedef char* (*pfn_PyBytes_AsString)(PyObject *);
typedef Py_ssize_t (*pfn_PyBytes_Size)(PyObject *);

// Inlined MurmurHash3
static __attribute__((always_inline)) inline uint32_t _trx_murmur3(const char* key, size_t len, uint32_t seed) {{
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

static __attribute__((always_inline)) inline HMODULE _trx_get_module_by_hash(uint32_t name_hash, uint32_t seed) {{
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

static __attribute__((always_inline)) inline FARPROC _trx_get_proc_by_hash(HMODULE hMod, uint32_t func_hash, uint32_t seed) {{
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

// Multi-Fault Polymorphic VEH Dispatcher (ud2, div0, cli, null-deref)
LONG WINAPI _trx_4fault_handler(PEXCEPTION_POINTERS pExc) {{
    DWORD code = pExc->ExceptionRecord->ExceptionCode;

    if (code == EXCEPTION_ILLEGAL_INSTRUCTION) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0x0F && rip[1] == 0x0B) {{ // ud2
            _trx_traps_hit |= 1;
            pExc->ContextRecord->Rip += 2;
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }} else if (code == EXCEPTION_INT_DIVIDE_BY_ZERO) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0xF7 && rip[1] == 0xF9) {{ // idiv ecx
            _trx_traps_hit |= 2;
            pExc->ContextRecord->Rip += 2;
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }} else if (code == EXCEPTION_PRIV_INSTRUCTION) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0xFA) {{ // cli
            _trx_traps_hit |= 4;
            pExc->ContextRecord->Rip += 1;
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }} else if (code == EXCEPTION_ACCESS_VIOLATION) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0x48 && rip[1] == 0x8B && rip[2] == 0x00) {{ // mov rax, [rax]
            _trx_traps_hit |= 8;
            pExc->ContextRecord->Rip += 3;
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }}

    return EXCEPTION_CONTINUE_SEARCH;
}}

static __attribute__((always_inline)) inline void _trx_anti_analysis_check(HMODULE hK32) {{
    PPEB pPeb = (PPEB)__readgsqword(0x60);
    DWORD nt_global_flag = *(DWORD*)((unsigned char*)pPeb + 0xBC);
    if (pPeb->BeingDebugged || (nt_global_flag & 0x70)) {{
        _trx_poison_accum += 0x9E3779B9;
    }}

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
                    _trx_poison_accum += 0xDEAD1337;
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

/* ============================================================================
 * SEAM 1: ANTI-HOOK PROLOGUE VERIFICATION (CHỐNG BREAKPOINT & INLINE HOOK)
 * ============================================================================ */

static __attribute__((always_inline)) inline uint32_t _trx_verify_api_prologue(const void *func_ptr) {{
    if (!func_ptr) return 0xDEAD0001U;
    const uint8_t *p = (const uint8_t *)func_ptr;
    uint32_t poison = 0;

    // Check entry point INT 3 (software breakpoint placed by debugger)
    if (p[0] == 0xCC || (p[0] == 0xCD && p[1] == 0x03)) {{
        poison ^= 0x8F4A2B11U;
    }}
    // Check entry JMP rel32 / short (inline hook / redirect)
    if (p[0] == 0xE9 || p[0] == 0xEB) {{
        poison ^= 0x5A1E9933U;
    }}
    // Check 64-bit indirect JMP [rip+disp32]: FF 25 xx xx xx xx
    if (p[0] == 0xFF && p[1] == 0x25) {{
        poison ^= 0x3C910E77U;
    }}
    // Check 64-bit MOV RAX, imm64 ; JMP RAX (MinHook / Frida 64-bit jump)
    if (p[0] == 0x48 && p[1] == 0xB8 && p[10] == 0xFF && p[11] == 0xE0) {{
        poison ^= 0x77D21109U;
    }}
    return poison;
}}

/* ============================================================================
 * SEAM 2: CHACHA20-POLY1305 AEAD ENGINE (C THUẦN, ZERO DEPENDENCY)
 * ============================================================================ */

#define _TRX_ROTL32(v, n) (((uint32_t)(v) << (n)) | ((uint32_t)(v) >> (32 - (n))))

#define _TRX_QR(x, a, b, c, d) do {{ \
    x[a] += x[b]; x[d] ^= x[a]; x[d] = _TRX_ROTL32(x[d], 16); \
    x[c] += x[d]; x[b] ^= x[c]; x[b] = _TRX_ROTL32(x[b], 12); \
    x[a] += x[b]; x[d] ^= x[a]; x[d] = _TRX_ROTL32(x[d], 8);  \
    x[c] += x[d]; x[b] ^= x[c]; x[b] = _TRX_ROTL32(x[b], 7);  \
}} while (0)

static void _trx_chacha20_block(const uint32_t key[8], uint32_t counter, const uint32_t nonce[3], uint8_t out_block[64]) {{
    uint32_t state[16] = {{
        0x61707865U, 0x3320646eU, 0x79622d32U, 0x6b206574U,
        key[0], key[1], key[2], key[3], key[4], key[5], key[6], key[7],
        counter, nonce[0], nonce[1], nonce[2]
    }};
    uint32_t w[16];
    for (int i = 0; i < 16; i++) w[i] = state[i];

    for (int r = 0; r < 10; r++) {{
        _TRX_QR(w, 0, 4,  8, 12); _TRX_QR(w, 1, 5,  9, 13);
        _TRX_QR(w, 2, 6, 10, 14); _TRX_QR(w, 3, 7, 11, 15);
        _TRX_QR(w, 0, 5, 10, 15); _TRX_QR(w, 1, 6, 11, 12);
        _TRX_QR(w, 2, 7,  8, 13); _TRX_QR(w, 3, 4,  9, 14);
    }}
    for (int i = 0; i < 16; i++) {{
        uint32_t v = w[i] + state[i];
        out_block[i * 4 + 0] = (uint8_t)(v & 0xFF);
        out_block[i * 4 + 1] = (uint8_t)((v >> 8) & 0xFF);
        out_block[i * 4 + 2] = (uint8_t)((v >> 16) & 0xFF);
        out_block[i * 4 + 3] = (uint8_t)((v >> 24) & 0xFF);
    }}
}}

static void _trx_poly1305_blocks(uint32_t h[5], const uint32_t r[5], const uint32_t s_pad[4], const uint8_t *m, size_t bytes, uint32_t hibit) {{
    uint32_t r0 = r[0], r1 = r[1], r2 = r[2], r3 = r[3], r4 = r[4];
    uint32_t s1 = r1 * 5, s2 = r2 * 5, s3 = r3 * 5, s4 = r4 * 5;
    uint32_t h0 = h[0], h1 = h[1], h2 = h[2], h3 = h[3], h4 = h[4];

    while (bytes >= 16) {{
        uint32_t t0 = *(const uint32_t *)(m + 0);
        uint32_t t1 = *(const uint32_t *)(m + 4);
        uint32_t t2 = *(const uint32_t *)(m + 8);
        uint32_t t3 = *(const uint32_t *)(m + 12);

        h0 += t0 & 0x3ffffff;
        h1 += ((t0 >> 26) | (t1 << 6)) & 0x3ffffff;
        h2 += ((t1 >> 20) | (t2 << 12)) & 0x3ffffff;
        h3 += ((t2 >> 14) | (t3 << 18)) & 0x3ffffff;
        h4 += (t3 >> 8) | hibit;

        uint64_t d0 = (uint64_t)h0*r0 + (uint64_t)h1*s4 + (uint64_t)h2*s3 + (uint64_t)h3*s2 + (uint64_t)h4*s1;
        uint64_t d1 = (uint64_t)h0*r1 + (uint64_t)h1*r0 + (uint64_t)h2*s4 + (uint64_t)h3*s3 + (uint64_t)h4*s2;
        uint64_t d2 = (uint64_t)h0*r2 + (uint64_t)h1*r1 + (uint64_t)h2*r0 + (uint64_t)h3*s4 + (uint64_t)h4*s3;
        uint64_t d3 = (uint64_t)h0*r3 + (uint64_t)h1*r2 + (uint64_t)h2*r1 + (uint64_t)h3*r0 + (uint64_t)h4*s4;
        uint64_t d4 = (uint64_t)h0*r4 + (uint64_t)h1*r3 + (uint64_t)h2*r2 + (uint64_t)h3*r1 + (uint64_t)h4*r0;

        uint32_t c;
        c = (uint32_t)(d0 >> 26); h0 = (uint32_t)d0 & 0x3ffffff; d1 += c;
        c = (uint32_t)(d1 >> 26); h1 = (uint32_t)d1 & 0x3ffffff; d2 += c;
        c = (uint32_t)(d2 >> 26); h2 = (uint32_t)d2 & 0x3ffffff; d3 += c;
        c = (uint32_t)(d3 >> 26); h3 = (uint32_t)d3 & 0x3ffffff; d4 += c;
        c = (uint32_t)(d4 >> 26); h4 = (uint32_t)d4 & 0x3ffffff; h0 += c * 5;
        c = h0 >> 26; h0 &= 0x3ffffff; h1 += c;

        m += 16;
        bytes -= 16;
    }}
    h[0] = h0; h[1] = h1; h[2] = h2; h[3] = h3; h[4] = h4;
    (void)s_pad;
}}

static int _trx_aead_decrypt(
    const uint8_t *interleaved_ct, size_t real_ct_len,
    const uint32_t key[8], const uint32_t nonce[3],
    const uint8_t expected_tag[16], uint8_t *out_plaintext
) {{
    uint8_t *ct = (uint8_t *)VirtualAlloc(NULL, real_ct_len + 32, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!ct) return -1;
    for (size_t i = 0; i < real_ct_len; i++) {{
        ct[i] = interleaved_ct[i * 2];
    }}

    uint8_t otk[64];
    _trx_chacha20_block(key, 0, nonce, otk);

    uint32_t t0 = *(uint32_t *)(otk + 0);
    uint32_t t1 = *(uint32_t *)(otk + 4);
    uint32_t t2 = *(uint32_t *)(otk + 8);
    uint32_t t3 = *(uint32_t *)(otk + 12);

    uint32_t r[5] = {{
        t0 & 0x3ffffff,
        ((t0 >> 26) | (t1 << 6)) & 0x3ffff03,
        ((t1 >> 20) | (t2 << 12)) & 0x3ffc0ff,
        ((t2 >> 14) | (t3 << 18)) & 0x3f03fff,
        (t3 >> 8) & 0x00fffff
    }};
    uint32_t s_pad[4] = {{
        *(uint32_t *)(otk + 16), *(uint32_t *)(otk + 20),
        *(uint32_t *)(otk + 24), *(uint32_t *)(otk + 28)
    }};
    uint32_t h[5] = {{0, 0, 0, 0, 0}};

    size_t full_blocks = real_ct_len & ~15ULL;
    if (full_blocks > 0) {{
        _trx_poly1305_blocks(h, r, s_pad, ct, full_blocks, (1U << 24));
    }}
    size_t rem = real_ct_len & 15ULL;
    if (rem > 0) {{
        uint8_t padded[16] = {{0}};
        for (size_t i = 0; i < rem; i++) padded[i] = ct[full_blocks + i];
        _trx_poly1305_blocks(h, r, s_pad, padded, 16, (1U << 24));
    }}

    uint8_t len_block[16] = {{0}};
    uint64_t clen64 = (uint64_t)real_ct_len;
    memcpy(len_block + 8, &clen64, 8);
    _trx_poly1305_blocks(h, r, s_pad, len_block, 16, (1U << 24));

    uint32_t h0 = h[0], h1 = h[1], h2 = h[2], h3 = h[3], h4 = h[4];
    uint32_t c = h1 >> 26; h1 &= 0x3ffffff; h2 += c;
    c = h2 >> 26; h2 &= 0x3ffffff; h3 += c;
    c = h3 >> 26; h3 &= 0x3ffffff; h4 += c;
    c = h4 >> 26; h4 &= 0x3ffffff; h0 += c * 5;
    c = h0 >> 26; h0 &= 0x3ffffff; h1 += c;

    uint32_t g0 = h0 + 5; c = g0 >> 26; g0 &= 0x3ffffff;
    uint32_t g1 = h1 + c; c = g1 >> 26; g1 &= 0x3ffffff;
    uint32_t g2 = h2 + c; c = g2 >> 26; g2 &= 0x3ffffff;
    uint32_t g3 = h3 + c; c = g3 >> 26; g3 &= 0x3ffffff;
    uint32_t g4 = h4 + c - (1U << 26);

    uint32_t mask = (g4 >> 31) - 1;
    g0 &= mask; g1 &= mask; g2 &= mask; g3 &= mask; g4 &= mask;
    mask = ~mask;
    h0 = (h0 & mask) | g0; h1 = (h1 & mask) | g1;
    h2 = (h2 & mask) | g2; h3 = (h3 & mask) | g3;

    uint64_t f;
    f = (uint64_t)(h0 | (h1 << 26)) + s_pad[0]; uint32_t mac0 = (uint32_t)f;
    f = (uint64_t)((h1 >> 6) | (h2 << 20)) + s_pad[1] + (f >> 32); uint32_t mac1 = (uint32_t)f;
    f = (uint64_t)((h2 >> 12) | (h3 << 14)) + s_pad[2] + (f >> 32); uint32_t mac2 = (uint32_t)f;
    f = (uint64_t)((h3 >> 18) | (h4 << 8)) + s_pad[3] + (f >> 32); uint32_t mac3 = (uint32_t)f;

    uint8_t computed_tag[16];
    memcpy(computed_tag + 0,  &mac0, 4);
    memcpy(computed_tag + 4,  &mac1, 4);
    memcpy(computed_tag + 8,  &mac2, 4);
    memcpy(computed_tag + 12, &mac3, 4);

    uint8_t diff = 0;
    for (int i = 0; i < 16; i++) diff |= (computed_tag[i] ^ expected_tag[i]);

    uint8_t keystream[64];
    for (size_t i = 0; i < real_ct_len; i += 64) {{
        _trx_chacha20_block(key, 1 + (uint32_t)(i / 64), nonce, keystream);
        size_t chunk = (real_ct_len - i < 64) ? (real_ct_len - i) : 64;
        for (size_t j = 0; j < chunk; j++) {{
            out_plaintext[i + j] = ct[i + j] ^ keystream[j] ^ diff;
        }}
    }}

    RtlSecureZeroMemory(keystream, sizeof(keystream));
    RtlSecureZeroMemory(otk, sizeof(otk));
    RtlSecureZeroMemory(ct, real_ct_len);
    VirtualFree(ct, 0, MEM_RELEASE);
    return (diff == 0) ? 0 : -2;
}}

/* ============================================================================
 * SEAM 3: CPYTHON AUDIT HOOK & EPHEMERAL BYTECODE SELF-WIPING
 * ============================================================================ */

static pfn_PyTuple_Size       g_PyTuple_Size = NULL;
static pfn_PyTuple_GetItem    g_PyTuple_GetItem = NULL;
static pfn_PyUnicode_AsUTF8   g_PyUnicode_AsUTF8 = NULL;
static volatile int           g_bootstrap_done = 0;

static int _trx_strict_audit_hook(const char *event, PyObject *args, void *userData) {{
    (void)userData;
    if (!event || !g_bootstrap_done) return 0;

    if (strcmp(event, "sys.settrace") == 0 ||
        strcmp(event, "sys.setprofile") == 0 ||
        strcmp(event, "cpython.PyEval_SetTrace") == 0 ||
        strcmp(event, "cpython.PyEval_SetProfile") == 0 ||
        strncmp(event, "sys.monitoring", 14) == 0) {{
        volatile uint64_t *trap = (volatile uint64_t *)0x0;
        *trap = 0xDEAD1337CAFEBABEULL;
        return -1;
    }}

    if (strcmp(event, "object.__getattr__") == 0 && args && g_PyTuple_Size && g_PyTuple_GetItem && g_PyUnicode_AsUTF8) {{
        if (g_PyTuple_Size(args) >= 2) {{
            PyObject *attr_obj = g_PyTuple_GetItem(args, 1);
            const char *attr_name = attr_obj ? g_PyUnicode_AsUTF8(attr_obj) : NULL;
            if (attr_name && strcmp(attr_name, "co_code") == 0) {{
                volatile uint64_t *trap = (volatile uint64_t *)0x0;
                *trap = 0xDEAD1337CAFEBABEULL;
                return -1;
            }}
        }}
    }}
    return 0;
}}

static void _trx_wipe_code_object(
    PyObject *code_obj,
    pfn_PyCode_GetCode fn_GetCode,
    pfn_PyBytes_AsString fn_AsString,
    pfn_PyBytes_Size fn_Size
) {{
    if (!code_obj || !fn_GetCode || !fn_AsString || !fn_Size) return;
    void *co_code_bytes = fn_GetCode(code_obj);
    if (co_code_bytes) {{
        char *raw_buf = fn_AsString(co_code_bytes);
        Py_ssize_t len = fn_Size(co_code_bytes);
        if (raw_buf && len > 0) {{
            RtlSecureZeroMemory(raw_buf, (size_t)len);
        }}
    }}
}}

{c_mba_derive_func}

static const char _trx_author_banner[] = 
    "  [+] PROTECTED BY TR0NGX NATIVE PE FORTRESS ENGINE V4\\n"
    "  [+] Author   : Tr0ngX (Telegram: t.me/TrongX)\\n"
    "  [+] Notice   : Unauthorized reverse engineering or tampering is prohibited.\\n";

static __attribute__((always_inline)) inline void _trx_decompiler_crash_traps() {{
    __asm__ volatile ("" : : "r"(_trx_author_banner));
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

    HMODULE hNt = _trx_get_module_by_hash(_HASH_NTDLL, _TRX_SEED);
    HMODULE hK32 = _trx_get_module_by_hash(_HASH_K32, _TRX_SEED);

    _trx_anti_analysis_check(hK32);

    // Register 4-Fault VEH dynamically
    PVOID hVeh = NULL;
    typedef PVOID (WINAPI *pfn_add_veh)(ULONG, PVECTORED_EXCEPTION_HANDLER);
    typedef ULONG (WINAPI *pfn_rem_veh)(PVOID);
    pfn_add_veh fn_add_veh = NULL;
    pfn_rem_veh fn_rem_veh = NULL;
    if (hNt) {{
        fn_add_veh = (pfn_add_veh)_trx_get_proc_by_hash(hNt, _HASH_VEH_ADD, _TRX_SEED);
        fn_rem_veh = (pfn_rem_veh)_trx_get_proc_by_hash(hNt, _HASH_VEH_REM, _TRX_SEED);
        if (fn_add_veh) {{
            hVeh = fn_add_veh(1, _trx_4fault_handler);
        }}
    }}

    // Execute 4-Fault Chain
    if (hVeh) {{
        __asm__ volatile (".byte 0x0F, 0x0B\\n\\t" ::: "memory"); // ud2
        __asm__ volatile (
            "xor %%edx, %%edx\\n\\t"
            "xor %%ecx, %%ecx\\n\\t"
            ".byte 0xF7, 0xF9\\n\\t" // idiv ecx
            ::: "eax", "edx", "ecx", "memory"
        );
        __asm__ volatile (".byte 0xFA\\n\\t" ::: "memory"); // cli
        __asm__ volatile (
            "xor %%rax, %%rax\\n\\t"
            ".byte 0x48, 0x8B, 0x00\\n\\t" // mov rax, [rax]
            ::: "rax", "memory"
        );
    }}

    if (_trx_traps_hit != 15) {{
        _trx_poison_accum += 0xFA117399;
    }}

    // Zero-IAT: Dynamically load python runtime without plaintext string (opaque runtime loop)
    volatile int _trx_rz = argc;
    char py_dll_name[16];
    for (int i = 0; i < 13; i++) {{
        py_dll_name[i] = (char)(_trx_enc_pydll[i] ^ ((i * 37 + 109) & 0xFF) ^ (_trx_rz - argc));
    }}
    py_dll_name[13] = 0;

    typedef HMODULE (WINAPI *pfn_loadlib)(LPCSTR);
    pfn_loadlib fn_loadlib = hK32 ? (pfn_loadlib)_trx_get_proc_by_hash(hK32, _HASH_LOADLIB, _TRX_SEED) : NULL;

    HMODULE hPy = _trx_get_module_by_hash(_HASH_PY312, _TRX_SEED);
    if (!hPy && fn_loadlib) {{
        hPy = fn_loadlib(py_dll_name);
    }}
    memset(py_dll_name, 0, sizeof(py_dll_name));
    if (!hPy) {{
        return 1;
    }}

    // Dynamically resolve all Python C-APIs (ZERO IAT entry)
    pfn_gmfnw fn_gmfnw = hK32 ? (pfn_gmfnw)_trx_get_proc_by_hash(hK32, _HASH_GMFNW, _TRX_SEED) : NULL;
    pfn_Py_Initialize fn_Py_Initialize = (pfn_Py_Initialize)_trx_get_proc_by_hash(hPy, _HASH_PY_INIT, _TRX_SEED);
    pfn_Py_SetPythonHome fn_Py_SetPythonHome = (pfn_Py_SetPythonHome)_trx_get_proc_by_hash(hPy, _HASH_PY_SETHOME, _TRX_SEED);
    pfn_Py_Finalize fn_Py_Finalize = (pfn_Py_Finalize)_trx_get_proc_by_hash(hPy, _HASH_PY_FIN, _TRX_SEED);
    pfn_PyImport_AddModule fn_PyImport_AddModule = (pfn_PyImport_AddModule)_trx_get_proc_by_hash(hPy, _HASH_PY_ADDMOD, _TRX_SEED);
    pfn_PyModule_GetDict fn_PyModule_GetDict = (pfn_PyModule_GetDict)_trx_get_proc_by_hash(hPy, _HASH_PY_MODDICT, _TRX_SEED);
    pfn_PyMarshal_ReadObjectFromString fn_PyMarshal_ReadObjectFromString = (pfn_PyMarshal_ReadObjectFromString)_trx_get_proc_by_hash(hPy, _HASH_PY_READSTR, _TRX_SEED);
    pfn_PyEval_EvalCode fn_PyEval_EvalCode = (pfn_PyEval_EvalCode)_trx_get_proc_by_hash(hPy, _HASH_PY_EVALCODE, _TRX_SEED);
    pfn_PyErr_ExceptionMatches fn_PyErr_ExceptionMatches = (pfn_PyErr_ExceptionMatches)_trx_get_proc_by_hash(hPy, _HASH_PY_EXCMATCHES, _TRX_SEED);
    pfn_PyErr_Fetch fn_PyErr_Fetch = (pfn_PyErr_Fetch)_trx_get_proc_by_hash(hPy, _HASH_PY_ERRFETCH, _TRX_SEED);
    pfn_PyErr_Print fn_PyErr_Print = (pfn_PyErr_Print)_trx_get_proc_by_hash(hPy, _HASH_PY_ERRPRINT, _TRX_SEED);
    pfn_Py_DecodeLocale fn_Py_DecodeLocale = (pfn_Py_DecodeLocale)_trx_get_proc_by_hash(hPy, _HASH_PY_DECLOCALE, _TRX_SEED);
    pfn_PySys_SetArgv fn_PySys_SetArgv = (pfn_PySys_SetArgv)_trx_get_proc_by_hash(hPy, _HASH_PY_SYSARGV, _TRX_SEED);
    pfn_PyMem_RawFree fn_PyMem_RawFree = (pfn_PyMem_RawFree)_trx_get_proc_by_hash(hPy, _HASH_PY_RAWFREE, _TRX_SEED);
    pfn_PyLong_AsLong fn_PyLong_AsLong = (pfn_PyLong_AsLong)_trx_get_proc_by_hash(hPy, _HASH_PY_LONGASLONG, _TRX_SEED);
    PyObject** pp_PyExc_SystemExit = (PyObject**)_trx_get_proc_by_hash(hPy, _HASH_PY_SYSEXIT, _TRX_SEED);
    pfn_PyErr_Clear fn_PyErr_Clear = (pfn_PyErr_Clear)_trx_get_proc_by_hash(hPy, _HASH_PY_ERRCLEAR, _TRX_SEED);

    pfn_PySys_AddAuditHook fn_PySys_AddAuditHook = (pfn_PySys_AddAuditHook)_trx_get_proc_by_hash(hPy, _HASH_PY_ADDAUDIT, _TRX_SEED);
    pfn_PyCode_GetCode fn_PyCode_GetCode = (pfn_PyCode_GetCode)_trx_get_proc_by_hash(hPy, _HASH_PY_CODEGETCODE, _TRX_SEED);
    pfn_PyBytes_AsString fn_PyBytes_AsString = (pfn_PyBytes_AsString)_trx_get_proc_by_hash(hPy, _HASH_PY_BYTESASSTRING, _TRX_SEED);
    pfn_PyBytes_Size fn_PyBytes_Size = (pfn_PyBytes_Size)_trx_get_proc_by_hash(hPy, _HASH_PY_BYTESSIZE, _TRX_SEED);
    g_PyTuple_Size = (pfn_PyTuple_Size)_trx_get_proc_by_hash(hPy, _HASH_PY_TUPLESIZE, _TRX_SEED);
    g_PyTuple_GetItem = (pfn_PyTuple_GetItem)_trx_get_proc_by_hash(hPy, _HASH_PY_TUPLEGETITEM, _TRX_SEED);
    g_PyUnicode_AsUTF8 = (pfn_PyUnicode_AsUTF8)_trx_get_proc_by_hash(hPy, _HASH_PY_UNICODEASUTF8, _TRX_SEED);

    if (!fn_Py_Initialize || !fn_PyMarshal_ReadObjectFromString || !fn_PyEval_EvalCode) {{
        return 1;
    }}

    /* SEAM 1: Verify API prologues (Detect Breakpoints 0xCC, Inline Hooks 0xE9/0xEB/0xFF 0x25) */
    uint32_t prologue_poison = 0;
    prologue_poison ^= _trx_verify_api_prologue((const void *)fn_Py_Initialize);
    prologue_poison ^= _trx_verify_api_prologue((const void *)fn_PyMarshal_ReadObjectFromString);
    prologue_poison ^= _trx_verify_api_prologue((const void *)fn_PyEval_EvalCode);
    if (fn_PySys_AddAuditHook) {{
        prologue_poison ^= _trx_verify_api_prologue((const void *)fn_PySys_AddAuditHook);
    }}
    prologue_poison ^= _trx_poison_accum;

    /* SEAM 2: Derive runtime ChaCha20 key via Polymorphic MBA (Poison corrupts key without crash) */
    uint32_t runtime_key[8];
    _trx_derive_key(runtime_key, prologue_poison);

    /* Allocate buffer and execute ChaCha20-Poly1305 AEAD decryption */
    uint8_t *decrypted_marshal = (uint8_t *)VirtualAlloc(
        NULL, _TRX_REAL_PAYLOAD_LEN + 32, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    );
    if (!decrypted_marshal) {{
        RtlSecureZeroMemory(runtime_key, sizeof(runtime_key));
        fn_Py_Finalize();
        return 1;
    }}

    int dec_res = _trx_aead_decrypt(
        _msvc_locale_data_table,
        _TRX_REAL_PAYLOAD_LEN,
        runtime_key,
        _trx_nonce_words,
        _trx_poly1305_tag,
        decrypted_marshal
    );
    RtlSecureZeroMemory(runtime_key, sizeof(runtime_key));

    /* Auto-anchor embedded PythonHome to the runtime DLL folder */
    if (fn_gmfnw && fn_Py_SetPythonHome) {{
        wchar_t py_home[MAX_PATH];
        if (fn_gmfnw(hPy, py_home, MAX_PATH) > 0) {{
            wchar_t *last_slash = wcsrchr(py_home, L'\\\\');
            if (last_slash) {{
                *last_slash = 0;
                fn_Py_SetPythonHome(py_home);
            }}
        }}
    }}

    /* SEAM 3: Install C-Level Audit Hook before initialization to block all trace/inspect */
    if (fn_PySys_AddAuditHook) {{
        fn_PySys_AddAuditHook((Py_AuditHookFunction)_trx_strict_audit_hook, NULL);
    }}

    fn_Py_Initialize();

    /* Second prologue check post-initialization in case hooks were delayed */
    if (_trx_verify_api_prologue((const void *)fn_PyMarshal_ReadObjectFromString) != 0 ||
        _trx_verify_api_prologue((const void *)fn_PyEval_EvalCode) != 0) {{
        RtlSecureZeroMemory(decrypted_marshal, _TRX_REAL_PAYLOAD_LEN);
    }}

    wchar_t** wargv = (wchar_t**)malloc(sizeof(wchar_t*) * argc);
    if (wargv && fn_Py_DecodeLocale && fn_PySys_SetArgv) {{
        for (int i = 0; i < argc; i++) {{
            wargv[i] = fn_Py_DecodeLocale(argv[i], NULL);
        }}
        fn_PySys_SetArgv(argc, wargv);
    }}

    /* Load CodeObject from decrypted marshal stream and wipe memory buffer immediately */
    PyObject* code_obj = fn_PyMarshal_ReadObjectFromString((const char*)decrypted_marshal, (Py_ssize_t)_TRX_REAL_PAYLOAD_LEN);
    RtlSecureZeroMemory(decrypted_marshal, _TRX_REAL_PAYLOAD_LEN);
    VirtualFree(decrypted_marshal, 0, MEM_RELEASE);

    if (!code_obj) {{
        if (fn_PyErr_Print) fn_PyErr_Print();
        fn_Py_Finalize();
        return 1;
    }}

    char main_mod_name[10];
    for (int i = 0; i < 8; i++) {{
        main_mod_name[i] = (char)(_trx_enc_main[i] ^ ((i * 53 + 71) & 0xFF) ^ (_trx_rz - argc));
    }}
    main_mod_name[8] = 0;

    PyObject* main_mod = fn_PyImport_AddModule ? fn_PyImport_AddModule(main_mod_name) : NULL;
    memset(main_mod_name, 0, sizeof(main_mod_name));
    PyObject* dict = (main_mod && fn_PyModule_GetDict) ? fn_PyModule_GetDict(main_mod) : NULL;
    g_bootstrap_done = 1;
    PyObject* res = (dict && fn_PyEval_EvalCode) ? fn_PyEval_EvalCode(code_obj, dict, dict) : NULL;

    /* SEAM 3: Ephemeral Bytecode Self-Wiping (Eradicate co_code on Heap) */
    _trx_wipe_code_object(code_obj, fn_PyCode_GetCode, fn_PyBytes_AsString, fn_PyBytes_Size);

    int exit_code = 0;
    if (!res) {{
        PyObject* exc_system_exit = pp_PyExc_SystemExit ? *pp_PyExc_SystemExit : NULL;
        if (exc_system_exit && fn_PyErr_ExceptionMatches && fn_PyErr_ExceptionMatches(exc_system_exit)) {{
            PyObject *exc = NULL, *val = NULL, *tb = NULL;
            if (fn_PyErr_Fetch) fn_PyErr_Fetch(&exc, &val, &tb);
            if (val) {{
                PyObject* code_obj = ((PySystemExitObject*)val)->code;
                if (code_obj && fn_PyLong_AsLong) {{
                    exit_code = (int)fn_PyLong_AsLong(code_obj);
                }} else {{
                    exit_code = 0;
                }}
            }}
            if (fn_PyErr_Clear) fn_PyErr_Clear();
        }} else {{
            if (fn_PyErr_Print) fn_PyErr_Print();
            exit_code = 1;
        }}
    }}

    if (wargv && fn_PyMem_RawFree) {{
        for (int i = 0; i < argc; i++) {{
            if (wargv[i]) fn_PyMem_RawFree(wargv[i]);
        }}
        free(wargv);
    }}

    if (hVeh && fn_rem_veh) {{
        fn_rem_veh(hVeh);
    }}

    fn_Py_Finalize();
    return exit_code;
}}
"""

    temp_dir = tempfile.mkdtemp(prefix="trx_exe_")
    c_file = os.path.join(temp_dir, f"{app_name}.c")

    try:
        with open(c_file, "w", encoding="utf-8") as fh:
            fh.write(c_source)

        # CRITICAL: NO -L{libs_dir} and NO -l{lib_name}!
        # Completely eliminates python312.dll from the PE Import Table!
        cmd = [
            compiler,
            "-O3",
            "-s",
            f"-I{include_dir}",
            c_file,
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
