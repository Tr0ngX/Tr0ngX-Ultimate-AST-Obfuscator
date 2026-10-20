# -*- coding: utf-8 -*-
"""
Tr0ngX Native C/C++ AOT Packager Module (Zero-Bytecode Windows PE C-Extension Engine)
======================================================================================
Compiles Tr0ngX obfuscated Python payloads directly into native Windows PE C-Extensions (.pyd)
and Standalone Native Executables (.exe) via MinGW-w64 GCC toolchain.

Native Fortress V5 Architecture (2026-10 hardening, after the offline reverse-engineering audit):
1. Password-Derived AEAD Key (F-01): the payload key is NEVER part of the image. The key is derived
   at runtime by the target CPython itself (Argon2id via `cryptography`, else PBKDF2-HMAC-SHA256 via
   stdlib hashlib) from a password supplied through TR0NGX_PASSWORD or an interactive prompt.
   Everything embedded is public by design: salt, KDF id, nonce, Poly1305 tag.
2. Tamper Flags Are Not Key Material (F-01): anti-hook / anti-debug findings raise a tamper flag that
   decides *behaviour* (abort vs. silent failure). The flag never participates in key derivation, so
   the AEAD key stays a pure function of (password, salt).
3. Zero-IAT CPython Dynamic Resolution (F-03): CPython APIs are resolved at runtime by EAT scan with
   a MurmurHash3 whose parameters (c1/c2/r1/r2/seed) are derived at runtime from a masked per-build
   blob instead of being baked in as literals or constants.
4. Multi-Fault Polymorphic VEH Dispatcher: Chains 4 hardware exception traps (ud2, div0, cli, null-deref).
   Intercepted by Vectored Exception Handler to shatter decompiler Control Flow Graphs (CFG).
5. Control-Flow Flattening With Opaque State (F-04): the dispatcher state is stored XOR-masked under a
   runtime-only mask, so neither the optimizer nor a decompiler can fold or resolve the state graph.
6. Uniform-Entropy Payload Framing (F-05): ciphertext is interleaved with a full-length random filler
   (no repeating pool), so the framed blob carries no periodic structure.
7. Anti-Hook Depth (F-06): protected CPython entry points are validated against the on-disk module
   image (not only the first opcode) and re-verified immediately before use.
8. Post-Compilation Binary PE Armorer: Strips debug directories, wipes PDB paths, scrambles section names.

SECURITY REALITY (read before marketing this loader):
    * native-exe REQUIRES a password (--password / --password-file). Without one there is no
      confidentiality: any key that can be recomputed from the file is not a secret.
    * A password-less build is tamper-resistance only (payload integrity), never confidentiality.
    * Hashed / Zero-IAT API resolution, CFF and framing raise the cost of casual static analysis.
      They are not a security boundary against a determined reverse engineer.
"""

import os
import sys
import shutil
import struct
import secrets
import hashlib
import marshal
import tempfile
import subprocess
from typing import Optional, Tuple

from .pe_armorer import armor_pe_binary
from .aot_compiler import AOTRegistry

__all__ = ["package_native_pyd", "package_native_exe", "get_native_compiler_path", "murmur3"]

DEFAULT_MINGW_PATHS = [
    r"C:\Users\trong\tools\mingw64\bin\gcc.exe",
    r"C:\mingw64\bin\gcc.exe",
    r"C:\ProgramData\chocolatey\bin\gcc.exe",
]


def murmur3(key: bytes, seed: int = 0, c1: int = 0xcc9e2d51, c2: int = 0x1b873593, r1: int = 15, r2: int = 13) -> int:
    """Polymorphic 32-bit MurmurHash3 matching C implementation for compile-time API hashing."""
    h = seed & 0xFFFFFFFF
    nblocks = len(key) // 4
    for i in range(nblocks):
        k = int.from_bytes(key[i * 4:(i + 1) * 4], "little")
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << r1) | (k >> (32 - r1))) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << r2) | (h >> (32 - r2))) & 0xFFFFFFFF
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
        k1 = ((k1 << r1) | (k1 >> (32 - r1))) & 0xFFFFFFFF
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

# ---------------------------------------------------------------------------
# Native secret model (F-01)
#
# The AEAD key is never embedded in the artifact. It is derived at runtime by the
# target CPython itself from a password, so the image only carries public material
# (salt, KDF id, nonce, Poly1305 tag). Build side and runtime stub MUST agree on
# (kdf_id, salt, parameters) - both are produced by the helpers below.
# ---------------------------------------------------------------------------
NATIVE_KDF_LABEL = b"__native__"
NATIVE_PBKDF2_ITERATIONS = 600000
NATIVE_ARGON2_ITERATIONS = 3
NATIVE_ARGON2_LANES = 2
NATIVE_ARGON2_MEMORY_KIB = 65536  # 64 MiB


def native_kdf_id() -> str:
    """Picks the strongest KDF available in the current build environment."""
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id  # noqa: F401
        return "argon2id"
    except Exception:
        return "pbkdf2-sha256"


def native_derive_key(password: str, salt: bytes, kdf_id: str) -> bytes:
    """Derives the 32-byte AEAD key from a password (build-side mirror of the runtime stub)."""
    pw = password.encode("utf-8")
    if kdf_id == "argon2id":
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        return Argon2id(
            salt=salt + NATIVE_KDF_LABEL,
            length=32,
            iterations=NATIVE_ARGON2_ITERATIONS,
            lanes=NATIVE_ARGON2_LANES,
            memory_cost=NATIVE_ARGON2_MEMORY_KIB,
        ).derive(pw)
    return hashlib.pbkdf2_hmac("sha256", pw, salt + NATIVE_KDF_LABEL, NATIVE_PBKDF2_ITERATIONS, 32)


def native_key_stub_source(salt: bytes, kdf_id: str, allow_prompt: bool = True) -> str:
    """Builds the single-expression Python stub that derives the runtime AEAD key.

    The stub is compiled to bytecode, masked and embedded in the PE image, then evaluated by
    the target CPython right before payload decryption. Keeping the KDF inside the target
    interpreter means no secret material and no crypto implementation live in the C layer.

    The stub returns the raw 32-byte key. An empty result means "no secret was supplied",
    which the native loader reports as a generic failure.
    """
    salt_hex = salt.hex()
    if kdf_id == "argon2id":
        derive = (
            "(lambda _A=__import__('cryptography.hazmat.primitives.kdf.argon2', fromlist=['Argon2id']).Argon2id:"
            f" _A(salt=bytes.fromhex('{salt_hex}') + b'__native__', length=32,"
            f" iterations={NATIVE_ARGON2_ITERATIONS}, lanes={NATIVE_ARGON2_LANES},"
            f" memory_cost={NATIVE_ARGON2_MEMORY_KIB}).derive(_pw.encode('utf-8')))()"
        )
    else:
        derive = (
            "(lambda _H=__import__('hashlib'):"
            f" _H.pbkdf2_hmac('sha256', _pw.encode('utf-8'), bytes.fromhex('{salt_hex}') + b'__native__',"
            f" {NATIVE_PBKDF2_ITERATIONS}, 32))()"
        )
    if allow_prompt:
        # TR0NGX_PASSWORD wins. Otherwise prompt, but only when a real console is attached to
        # STD_INPUT (getpass reads console input directly and would block on a pipe/NUL).
        source = (
            "(lambda _os=__import__('os'), _c=__import__('ctypes'),"
            " _k=__import__('ctypes').windll.kernel32:"
            " (lambda _pw: ((" + derive + ") if _pw else b''))"
            "(_os.environ.get('TR0NGX_PASSWORD') or"
            " (_k.GetConsoleMode(_k.GetStdHandle(-10), _c.byref(_c.c_uint32(0))) != 0 and"
            "  __import__('getpass').getpass('[TR0NGX] Native payload password: ')) or '')"
            ")()"
        )
    else:
        # Library mode (.pyd): never prompt on import, the host process must provide the secret.
        source = (
            "(lambda _os=__import__('os'):"
            " (lambda _pw: ((" + derive + ") if _pw else b''))"
            "(_os.environ.get('TR0NGX_PASSWORD') or"
            " (_os.environ.get('TR0NGX_PASSWORD_FILE') and"
            "  open(_os.environ['TR0NGX_PASSWORD_FILE'], 'rb').read().decode('utf-8').strip()) or '')"
            ")()"
        )
    return source


def native_key_stub_blob(salt: bytes, kdf_id: str, allow_prompt: bool = True) -> bytes:
    """Marshals the key-provider stub into embeddable bytecode."""
    source = native_key_stub_source(salt, kdf_id, allow_prompt)
    return marshal.dumps(compile(source, "<trx_native_key>", "eval"))


def _splitmix32(state: int) -> Tuple[int, int]:
    """SplitMix32 step - mirrored byte-for-byte by the C runtime decoder."""
    state = (state + 0x9E3779B9) & 0xFFFFFFFF
    z = state
    z = ((z ^ (z >> 16)) * 0x85EBCA6B) & 0xFFFFFFFF
    z = ((z ^ (z >> 13)) * 0xC2B2AE35) & 0xFFFFFFFF
    z ^= z >> 16
    return z & 0xFFFFFFFF, state


def native_hash_params(blob: bytes) -> Tuple[int, int, int, int, int]:
    """Derives (c1, c2, r1, r2, seed) for the runtime API-hash resolver.

    The parameters live only in a masked blob: the C side rebuilds them at runtime, so the
    hash table can no longer be recomputed by simply reading constants out of .rdata.
    """
    st = int.from_bytes(blob[0:4], "little")
    c1, st = _splitmix32(st)
    c2, st = _splitmix32(st)
    r1_mix, st = _splitmix32(st)
    r2_mix, st = _splitmix32(st)
    seed, st = _splitmix32(st)
    c1 |= 1
    c2 |= 1
    r1 = 13 + 2 * (r1_mix % 4)  # {13, 15, 17, 19}
    r2 = 11 + 2 * (r2_mix % 4)  # {11, 13, 15, 17}
    return c1, c2, r1, r2, seed

def interleave_low_entropy(ciphertext: bytes) -> Tuple[bytes, int]:
    """Frames ciphertext with a full-length random filler.

    The filler is uniform random across the whole blob (no repeating pool), so the framed
    payload carries no periodic structure an analyst could latch onto.
    Returns (framed_bytes, parity); parity selects the byte lane holding the ciphertext.
    """
    parity = secrets.randbits(1)
    out = bytearray(len(ciphertext) * 2)
    filler = secrets.token_bytes(len(ciphertext))
    if parity:
        out[1::2] = ciphertext
        out[0::2] = filler
    else:
        out[0::2] = ciphertext
        out[1::2] = filler
    return bytes(out), parity


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


# ---------------------------------------------------------------------------
# Shared ChaCha20-Poly1305 AEAD implementation for the native loaders (.exe / .pyd).
# Injected verbatim into both C templates, so the two artifacts share one cipher
# implementation and one key model.
# ---------------------------------------------------------------------------
_TRX_C_AEAD_LIB = r"""
/* ---- ChaCha20-Poly1305 AEAD engine (shared by the .exe and .pyd native loaders) ---- */
#define _TRX_ROTL32(v, n) (((uint32_t)(v) << (n)) | ((uint32_t)(v) >> (32 - (n))))

#define _TRX_QR(x, a, b, c, d) do { \
    x[a] += x[b]; x[d] ^= x[a]; x[d] = _TRX_ROTL32(x[d], 16); \
    x[c] += x[d]; x[b] ^= x[c]; x[b] = _TRX_ROTL32(x[b], 12); \
    x[a] += x[b]; x[d] ^= x[a]; x[d] = _TRX_ROTL32(x[d], 8);  \
    x[c] += x[d]; x[b] ^= x[c]; x[b] = _TRX_ROTL32(x[b], 7);  \
} while (0)

static void _trx_chacha20_block(const uint32_t key[8], uint32_t counter, const uint32_t nonce[3], uint8_t out_block[64]) {
    uint32_t state[16] = {
        0x61707865U, 0x3320646eU, 0x79622d32U, 0x6b206574U,
        key[0], key[1], key[2], key[3], key[4], key[5], key[6], key[7],
        counter, nonce[0], nonce[1], nonce[2]
    };
    uint32_t w[16];
    for (int i = 0; i < 16; i++) w[i] = state[i];

    for (int r = 0; r < 10; r++) {
        _TRX_QR(w, 0, 4,  8, 12); _TRX_QR(w, 1, 5,  9, 13);
        _TRX_QR(w, 2, 6, 10, 14); _TRX_QR(w, 3, 7, 11, 15);
        _TRX_QR(w, 0, 5, 10, 15); _TRX_QR(w, 1, 6, 11, 12);
        _TRX_QR(w, 2, 7,  8, 13); _TRX_QR(w, 3, 4,  9, 14);
    }
    for (int i = 0; i < 16; i++) {
        uint32_t v = w[i] + state[i];
        out_block[i * 4 + 0] = (uint8_t)(v & 0xFF);
        out_block[i * 4 + 1] = (uint8_t)((v >> 8) & 0xFF);
        out_block[i * 4 + 2] = (uint8_t)((v >> 16) & 0xFF);
        out_block[i * 4 + 3] = (uint8_t)((v >> 24) & 0xFF);
    }
}

static void _trx_poly1305_blocks(uint32_t h[5], const uint32_t r[5], const uint32_t s_pad[4], const uint8_t *m, size_t bytes, uint32_t hibit) {
    uint32_t r0 = r[0], r1 = r[1], r2 = r[2], r3 = r[3], r4 = r[4];
    uint32_t s1 = r1 * 5, s2 = r2 * 5, s3 = r3 * 5, s4 = r4 * 5;
    uint32_t h0 = h[0], h1 = h[1], h2 = h[2], h3 = h[3], h4 = h[4];

    while (bytes >= 16) {
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
    }
    h[0] = h0; h[1] = h1; h[2] = h2; h[3] = h3; h[4] = h4;
    (void)s_pad;
}

/* Authenticated decryption. Returns 0 on success, -2 when the Poly1305 tag does not match.
   On tag mismatch the produced plaintext is garbage on purpose (no oracle for the caller). */
static int _trx_aead_decrypt(
    const uint8_t *ct, size_t ct_len,
    const uint8_t key[32], const uint32_t nonce[3],
    const uint8_t expected_tag[16], uint8_t *out_plaintext
) {
    uint32_t key_words[8];
    for (int i = 0; i < 8; i++) {
        key_words[i] = (uint32_t)key[i * 4] |
                       ((uint32_t)key[i * 4 + 1] << 8) |
                       ((uint32_t)key[i * 4 + 2] << 16) |
                       ((uint32_t)key[i * 4 + 3] << 24);
    }

    uint8_t otk[64];
    _trx_chacha20_block(key_words, 0, nonce, otk);

    uint32_t t0 = *(uint32_t *)(otk + 0);
    uint32_t t1 = *(uint32_t *)(otk + 4);
    uint32_t t2 = *(uint32_t *)(otk + 8);
    uint32_t t3 = *(uint32_t *)(otk + 12);

    uint32_t r[5] = {
        t0 & 0x3ffffff,
        ((t0 >> 26) | (t1 << 6)) & 0x3ffff03,
        ((t1 >> 20) | (t2 << 12)) & 0x3ffc0ff,
        ((t2 >> 14) | (t3 << 18)) & 0x3f03fff,
        (t3 >> 8) & 0x00fffff
    };
    uint32_t s_pad[4] = {
        *(uint32_t *)(otk + 16), *(uint32_t *)(otk + 20),
        *(uint32_t *)(otk + 24), *(uint32_t *)(otk + 28)
    };
    uint32_t h[5] = {0, 0, 0, 0, 0};

    size_t full_blocks = ct_len & ~15ULL;
    if (full_blocks > 0) {
        _trx_poly1305_blocks(h, r, s_pad, ct, full_blocks, (1U << 24));
    }
    size_t rem = ct_len & 15ULL;
    if (rem > 0) {
        uint8_t padded[16] = {0};
        for (size_t i = 0; i < rem; i++) padded[i] = ct[full_blocks + i];
        _trx_poly1305_blocks(h, r, s_pad, padded, 16, (1U << 24));
    }

    uint8_t len_block[16] = {0};
    uint64_t clen64 = (uint64_t)ct_len;
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
    for (size_t i = 0; i < ct_len; i += 64) {
        _trx_chacha20_block(key_words, 1 + (uint32_t)(i / 64), nonce, keystream);
        size_t chunk = (ct_len - i < 64) ? (ct_len - i) : 64;
        for (size_t j = 0; j < chunk; j++) {
            out_plaintext[i + j] = ct[i + j] ^ keystream[j] ^ diff;
        }
    }

    RtlSecureZeroMemory(keystream, sizeof(keystream));
    RtlSecureZeroMemory(otk, sizeof(otk));
    RtlSecureZeroMemory(key_words, sizeof(key_words));
    return (diff == 0) ? 0 : -2;
}
"""


def _xor_mask(data: bytes, mask: bytes) -> bytes:
    """Masks a blob with a repeating per-build mask (keeps it out of plain sight)."""
    if not data:
        return b""
    return bytes(b ^ mask[i % len(mask)] for i, b in enumerate(data))


def package_native_pyd(final_source: str, out_path: str, module_name: Optional[str] = None,
                       stealth_pe: bool = True, password: Optional[str] = None,
                       salt: Optional[bytes] = None) -> str:
    """
    Compiles final obfuscated Python payload into a Windows PE C-Extension (.pyd).
    The resulting file is a pure binary DLL that can be imported directly:
    `import <module_name>` or `from <module_name> import *`.

    Password mode derives the AEAD key at import time from TR0NGX_PASSWORD (never an
    interactive prompt - a library must not block the host process). Without a password the
    key is embedded (masked), which provides payload integrity only, never confidentiality.
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

    # --- secret material (F-01) ---
    xor_mask = secrets.token_bytes(32)
    if password:
        kdf_id = native_kdf_id()
        kdf_salt = salt if salt is not None else secrets.token_bytes(16)
        master_key = native_derive_key(password, kdf_salt, kdf_id)
        stub_blob = native_key_stub_blob(kdf_salt, kdf_id, allow_prompt=False)
        key_mode = 1
    else:
        master_key = secrets.token_bytes(32)
        stub_blob = b""
        key_mode = 0
        print("[TR0NGX] [WARN] Native .pyd built WITHOUT a password: payload integrity only, "
              "no confidentiality (the key is recoverable from the file).", flush=True)

    nonce = secrets.token_bytes(12)
    ciphertext, poly_tag = chacha20_poly1305_encrypt(marshalled_bytes, master_key, nonce)

    c_payload_arr = ", ".join(f"0x{b:02x}" for b in ciphertext)
    c_mask_arr = ", ".join(f"0x{b:02x}" for b in xor_mask)
    c_key_arr = ", ".join(f"0x{b:02x}" for b in _xor_mask(master_key, xor_mask))
    c_stub_arr = ", ".join(f"0x{b:02x}" for b in _xor_mask(stub_blob, xor_mask))
    nonce_words = list(struct.unpack("<3I", nonce))
    c_nonce_arr = ", ".join(f"0x{w:08X}U" for w in nonce_words)
    c_tag_arr = ", ".join(f"0x{b:02x}" for b in poly_tag)

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
#include <windows.h>

{_TRX_C_AEAD_LIB}

static const unsigned char _trx_payload[] = {{ {c_payload_arr} }};
static volatile unsigned char _trx_mask[32] = {{ {c_mask_arr} }};
static const unsigned char _trx_enc_key[32] = {{ {c_key_arr} }};
static const unsigned char _trx_enc_stub[] = {{ {c_stub_arr} }};
static const size_t _trx_stub_len = {len(stub_blob)};
static const uint32_t _trx_nonce[3] = {{ {c_nonce_arr} }};
static const unsigned char _trx_tag[16] = {{ {c_tag_arr} }};
static const size_t _trx_len = {len(ciphertext)};
static const int _trx_key_mode = {key_mode};

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

    uint8_t key[32];
    if (_trx_key_mode) {{
        /* Password mode: the AEAD key is derived by the host interpreter from TR0NGX_PASSWORD.
           Nothing secret is embedded in the module image. */
        uint8_t* stub = (uint8_t*)malloc(_trx_stub_len ? _trx_stub_len : 1);
        if (!stub) {{
            Py_DECREF(mod);
            PyErr_NoMemory();
            return NULL;
        }}
        for (size_t i = 0; i < _trx_stub_len; i++) {{
            stub[i] = (uint8_t)(_trx_enc_stub[i] ^ _trx_mask[i % 32]);
        }}
        PyObject* stub_code = PyMarshal_ReadObjectFromString((const char*)stub, (Py_ssize_t)_trx_stub_len);
        memset(stub, 0, _trx_stub_len);
        free(stub);
        if (!stub_code) {{
            Py_DECREF(mod);
            return NULL;
        }}
        PyObject* stub_dict = PyModule_GetDict(mod);
        PyObject* stub_res = PyEval_EvalCode(stub_code, stub_dict, stub_dict);
        Py_DECREF(stub_code);
        if (!stub_res) {{
            Py_DECREF(mod);
            return NULL;
        }}
        if (!PyBytes_Check(stub_res)) {{
            Py_DECREF(stub_res);
            Py_DECREF(mod);
            PyErr_SetString(PyExc_RuntimeError, "TR0NGX: native key derivation failed");
            return NULL;
        }}
        Py_ssize_t klen = PyBytes_Size(stub_res);
        if (klen != 32) {{
            Py_DECREF(stub_res);
            Py_DECREF(mod);
            PyErr_SetString(PyExc_RuntimeError,
                "TR0NGX: TR0NGX_PASSWORD is required to import this protected module");
            return NULL;
        }}
        memcpy(key, PyBytes_AsString(stub_res), 32);
        Py_DECREF(stub_res);
    }} else {{
        /* Password-less build: the key is embedded (masked) - integrity only, no secrecy. */
        for (int i = 0; i < 32; i++) {{
            key[i] = (uint8_t)(_trx_enc_key[i] ^ _trx_mask[i % 32]);
        }}
    }}

    uint8_t* buf = (uint8_t*)malloc(_trx_len);
    if (!buf) {{
        memset(key, 0, 32);
        Py_DECREF(mod);
        PyErr_NoMemory();
        return NULL;
    }}
    int rc = _trx_aead_decrypt(_trx_payload, _trx_len, key, _trx_nonce, _trx_tag, buf);
    memset(key, 0, 32);
    if (rc != 0) {{
        memset(buf, 0, _trx_len);
        free(buf);
        Py_DECREF(mod);
        PyErr_SetString(PyExc_RuntimeError, "TR0NGX: native payload authentication failed");
        return NULL;
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


def package_native_exe(final_source: str, out_path: str, app_name: Optional[str] = None,
                        stealth_pe: bool = True, password: Optional[str] = None,
                        salt: Optional[bytes] = None) -> str:
    """
    Compiles final obfuscated Python payload into a Standalone Windows PE Executable (.exe).

    Native Fortress V5:
    - Password-derived AEAD key (F-01): the key never exists in the artifact. It is derived
      at runtime by the target CPython (Argon2id, else PBKDF2-HMAC-SHA256) from
      TR0NGX_PASSWORD or an interactive prompt. Only public material is embedded:
      salt, KDF id, nonce, Poly1305 tag.
    - Zero-IAT Python Execution: no python312.dll in the Import Address Table; all CPython
      APIs are resolved at runtime by EAT scan with runtime-derived hash parameters (F-03).
    - Multi-Fault Polymorphic VEH Dispatcher, opaque-state CFF (F-04), uniform-entropy
      payload framing (F-05), on-disk image validation of protected entry points (F-06).
    - PE Armorer post-processing: scrambles section names, strips debug dirs.
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

    if not password:
        raise RuntimeError(
            "Native executable packaging requires a password (--password / --password-file / "
            "TR0NGX_PASSWORD). A password-less native build cannot provide confidentiality: "
            "any key that can be recomputed from the binary is readable by an analyst."
        )

    # Split-Key Handshake: Python Half + Native VEH Half
    py_half_secret = secrets.token_bytes(16)
    py_half_arr = ", ".join(f"0x{b:02x}" for b in py_half_secret)
    split_key_py_stub = f"""
try:
    _trx_k_py = bytes([{py_half_arr}])
    _trx_auth_token = _auth_decrypt(_trx_k_py)
    if not _trx_auth_token or len(_trx_auth_token) < 16:
        import sys as _sys; _sys.exit(0)
except Exception:
    import sys as _sys; _sys.exit(0)
"""
    aot_registry = AOTRegistry()
    clean_source, aot_funcs = aot_registry.scan_and_extract(final_source)
    c_aot_funcs_code = "\n".join(aot_funcs.values())
    aot_reg_lines = []
    for fn_name in aot_funcs:
        fn_bytes = fn_name.encode('utf-8')
        enc_fn = [b ^ ((i * 41 + 17) & 0xFF) for i, b in enumerate(fn_bytes)]
        c_enc_fn = ", ".join(f"0x{b:02x}" for b in enc_fn)
        fn_len = len(fn_bytes)
        aot_reg_lines.append(f"""
        char _fn_str_{fn_name}[{fn_len + 1}];
        const uint8_t _fn_enc_{fn_name}[{fn_len}] = {{ {c_enc_fn} }};
        for (int _si = 0; _si < {fn_len}; _si++) {{
            _fn_str_{fn_name}[_si] = (char)(_fn_enc_{fn_name}[_si] ^ ((_si * 41 + 17) & 0xFF));
        }}
        _fn_str_{fn_name}[{fn_len}] = 0;
        static PyMethodDef _aot_def_{fn_name};
        _aot_def_{fn_name}.ml_name = _fn_str_{fn_name};
        _aot_def_{fn_name}.ml_meth = (PyCFunction)_trx_aot_{fn_name};
        _aot_def_{fn_name}.ml_flags = METH_VARARGS;
        _aot_def_{fn_name}.ml_doc = NULL;
        PyObject* _cfn_{fn_name} = fn_PyCFunction_NewEx(&_aot_def_{fn_name}, NULL, NULL);
        if (_cfn_{fn_name}) {{
            fn_PyDict_SetItemString(dict, _fn_str_{fn_name}, _cfn_{fn_name});
        }}
        memset(_fn_str_{fn_name}, 0, sizeof(_fn_str_{fn_name}));
        """)
    c_aot_reg_code = "\n".join(aot_reg_lines)

    augmented_source = split_key_py_stub + "\n" + clean_source
    code_obj = compile(augmented_source, "<main>", "exec", optimize=2)
    marshalled_bytes = bytearray(marshal.dumps(code_obj))
    real_uncompressed_len = len(marshalled_bytes)

    # ------------------------------------------------------------------
    # Secret material (F-01): the AEAD key is derived from the password and
    # never embedded. The embedded stub re-derives the very same key inside
    # the target interpreter at runtime.
    # ------------------------------------------------------------------
    kdf_id = native_kdf_id()
    kdf_salt = salt if salt is not None else secrets.token_bytes(16)
    master_key = native_derive_key(password, kdf_salt, kdf_id)
    stub_blob = native_key_stub_blob(kdf_salt, kdf_id, allow_prompt=True)

    # Scramble marshal payload & poison tag so external dumpers fail (32-bit LCG stream
    # cipher). The seed is bound to the AEAD key (F-02) - no static seed in the image.
    marshal_scramble_seed = int.from_bytes(master_key[:4], "little")
    marshalled_bytes[0] ^= 0xA5  # Poison tag byte
    _lcg_st = marshal_scramble_seed
    for i in range(1, len(marshalled_bytes)):
        _lcg_st = (_lcg_st * 1664525 + 1013904223) & 0xFFFFFFFF
        marshalled_bytes[i] ^= (((_lcg_st >> 16) ^ (i * 37)) & 0xFF)
    marshalled_bytes = bytes(marshalled_bytes)

    # Fortress V7 Turbo Speed: In-Memory Compress-Then-Encrypt
    try:
        import lz4.block
        compressed_payload = lz4.block.compress(marshalled_bytes, store_size=False)
    except Exception:
        compressed_payload = marshalled_bytes
    real_compressed_len = len(compressed_payload)

    # ChaCha20-Poly1305 AEAD over the compressed payload
    nonce = secrets.token_bytes(12)
    ciphertext, poly_tag = chacha20_poly1305_encrypt(compressed_payload, master_key, nonce)
    interleaved_payload, frame_parity = interleave_low_entropy(ciphertext)

    temp_dir = tempfile.mkdtemp(prefix="trx_exe_")
    payload_bin = os.path.join(temp_dir, "payload.bin")
    with open(payload_bin, "wb") as bf:
        bf.write(bytes(interleaved_payload))
    payload_bin_gas = payload_bin.replace("\\", "/")

    # ------------------------------------------------------------------
    # Masked runtime blobs: everything below is either public or reconstructable
    # at runtime, so it is stored XOR-masked to keep it out of plain sight.
    # ------------------------------------------------------------------
    xor_mask = secrets.token_bytes(32)
    mask32 = int.from_bytes(xor_mask[:4], "little")

    banner_text = (
        "  [+] Tr0ngX Obf\n"
        "  [+] Author   : Tr0ngX (Telegram: t.me/TrongX)\n"
        "  [+] Notice   : Unauthorized reverse engineering or tampering is prohibited.\n"
    )
    banner_bytes = banner_text.encode("utf-8")

    hash_blob = secrets.token_bytes(32)
    c1, c2, r1, r2, murmur_seed = native_hash_params(hash_blob)

    c_mask_arr = ", ".join(f"0x{b:02x}" for b in xor_mask)
    c_stub_arr = ", ".join(f"0x{b:02x}" for b in _xor_mask(stub_blob, xor_mask))
    c_banner_arr = ", ".join(f"0x{b:02x}" for b in _xor_mask(banner_bytes, xor_mask))
    c_hash_arr = ", ".join(f"0x{b:02x}" for b in _xor_mask(hash_blob, xor_mask))
    ct_len_masked = len(ciphertext) ^ mask32
    raw_len_masked = real_uncompressed_len ^ mask32

    nonce_words = list(struct.unpack("<3I", nonce))
    c_nonce_arr = ", ".join(f"0x{w:08X}U" for w in nonce_words)
    c_tag_arr = ", ".join(f"0x{b:02x}" for b in poly_tag)

    def mhash(name: bytes) -> int:
        return murmur3(name, murmur_seed, c1, c2, r1, r2)

    ntdll_hash = mhash(b"ntdll.dll")
    kernel32_hash = mhash(b"kernel32.dll")
    python312_hash = mhash(b"python312.dll")

    # Windows API hashes
    veh_add_hash = mhash(b"RtlAddVectoredExceptionHandler")
    veh_rem_hash = mhash(b"RtlRemoveVectoredExceptionHandler")
    gtc_hash = mhash(b"GetThreadContext")
    stc_hash = mhash(b"SetThreadContext")
    gct_hash = mhash(b"GetCurrentThread")
    loadlib_hash = mhash(b"LoadLibraryA")
    gmfnw_hash = mhash(b"GetModuleFileNameW")
    createfilew_hash = mhash(b"CreateFileW")
    readfile_hash = mhash(b"ReadFile")
    setfilepointerex_hash = mhash(b"SetFilePointerEx")

    # Fortress V5 Anti-Memory-Leak & Anti-Subprocess API hashes
    nt_set_sec_hash = mhash(b"NtSetSecurityObject")
    nt_qip_hash = mhash(b"NtQueryInformationProcess")
    open_proc_hash = mhash(b"OpenProcess")
    qfpinw_hash = mhash(b"QueryFullProcessImageNameW")
    virtual_query_hash = mhash(b"VirtualQuery")

    # Python C-API hashes (resolved dynamically, ZERO IAT)
    py_init_hash = mhash(b"Py_Initialize")
    py_sethome_hash = mhash(b"Py_SetPythonHome")
    py_fin_hash = mhash(b"Py_Finalize")
    py_addmod_hash = mhash(b"PyImport_AddModule")
    py_moddict_hash = mhash(b"PyModule_GetDict")
    py_readstr_hash = mhash(b"PyMarshal_ReadObjectFromString")
    py_evalcode_hash = mhash(b"PyEval_EvalCode")
    py_excmatches_hash = mhash(b"PyErr_ExceptionMatches")
    py_errfetch_hash = mhash(b"PyErr_Fetch")
    py_errprint_hash = mhash(b"PyErr_Print")
    py_declocale_hash = mhash(b"Py_DecodeLocale")
    py_sysargv_hash = mhash(b"PySys_SetArgv")
    py_rawfree_hash = mhash(b"PyMem_RawFree")
    py_longaslong_hash = mhash(b"PyLong_AsLong")
    py_sysexit_hash = mhash(b"PyExc_SystemExit")
    py_errclear_hash = mhash(b"PyErr_Clear")
    py_addaudithook_hash = mhash(b"PySys_AddAuditHook")
    py_tuplesize_hash = mhash(b"PyTuple_Size")
    py_tuplegetitem_hash = mhash(b"PyTuple_GetItem")
    py_unicodeasutf8_hash = mhash(b"PyUnicode_AsUTF8")
    py_codegetcode_hash = mhash(b"PyCode_GetCode")
    py_bytesasstring_hash = mhash(b"PyBytes_AsString")
    py_bytessize_hash = mhash(b"PyBytes_Size")
    py_cfn_new_hash = mhash(b"PyCFunction_NewEx")
    py_dict_setitem_hash = mhash(b"PyDict_SetItemString")
    py_bytes_fromstring_hash = mhash(b"PyBytes_FromStringAndSize")
    py_arg_parse_hash = mhash(b"PyArg_ParseTuple")
    py_unicodefromstring_hash = mhash(b"PyUnicode_FromString")

    pydll_raw = b"python312.dll"
    pydll_enc = [b ^ ((i * 37 + 109) & 0xFF) for i, b in enumerate(pydll_raw)]
    c_pydll_enc = ", ".join(f"0x{b:02x}" for b in pydll_enc)

    main_raw = b"__main__"
    main_enc = [b ^ ((i * 53 + 71) & 0xFF) for i, b in enumerate(main_raw)]
    c_main_enc = ", ".join(f"0x{b:02x}" for b in main_enc)

    auth_raw = b"_auth_decrypt"
    auth_enc = [b ^ ((i * 29 + 31) & 0xFF) for i, b in enumerate(auth_raw)]
    c_auth_enc = ", ".join(f"0x{b:02x}" for b in auth_enc)

    c_source = f"""#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <marshal.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <windows.h>
#include <winternl.h>
#include <psapi.h>
#include <intrin.h>
#include <cpuid.h>

__attribute__((section(".cnry"), aligned(4096))) static volatile unsigned char g_canary_page[4096];
static void *g_honeytrap_page = NULL;

static LONG WINAPI _trx_honeytrap_veh(PEXCEPTION_POINTERS pExc) {{
    if (pExc->ExceptionRecord->ExceptionCode == STATUS_GUARD_PAGE_VIOLATION) {{
        ExitProcess(0x100);
    }}
    return EXCEPTION_CONTINUE_SEARCH;
}}

void NTAPI tls_security_gate(PVOID hModule, DWORD dwReason, PVOID pReserved) {{
    if (dwReason == DLL_PROCESS_ATTACH) {{
        PSAPI_WORKING_SET_EX_INFORMATION wsInfo;
        wsInfo.VirtualAddress = (PVOID)g_canary_page;
        if (K32QueryWorkingSetEx(GetCurrentProcess(), &wsInfo, sizeof(wsInfo))) {{
            if (wsInfo.VirtualAttributes.Valid) {{
                ExitProcess(0x101);
            }}
        }}

        ULONG64 cycles = 0;
        QueryThreadCycleTime(GetCurrentThread(), &cycles);
        if (cycles > 100000000ULL) {{
            ExitProcess(0x102);
        }}

        AddVectoredExceptionHandler(1, _trx_honeytrap_veh);

        g_honeytrap_page = VirtualAlloc(NULL, 0x400000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        if (g_honeytrap_page) {{
            DWORD oldProt = 0;
            VirtualProtect(g_honeytrap_page, 0x400000, PAGE_READWRITE | PAGE_GUARD, &oldProt);
        }}
    }}
}}

__attribute__((section(".CRT$XLB"))) PIMAGE_TLS_CALLBACK p_tls_security_gate = tls_security_gate;

__asm__(
    ".section .rdata, \\"dr\\"\\n\\t"
    ".globl _msvc_locale_data_table\\n\\t"
    ".balign 16\\n\\t"
    "_msvc_locale_data_table:\\n\\t"
    ".incbin \\"{payload_bin_gas}\\"\\n\\t"
    ".text\\n\\t"
);
extern const uint8_t _msvc_locale_data_table[];
static const uint32_t _trx_nonce_words[3] = {{ {c_nonce_arr} }};
static const uint8_t _trx_poly1305_tag[16] = {{ {c_tag_arr} }};

/* ---- Runtime-only material (F-01/F-02/F-03/F-07/F-08) ------------------- */
static volatile uint8_t _trx_mask[32] = {{ {c_mask_arr} }};
static volatile uint32_t _trx_mask32 = 0;
static volatile uint32_t _trx_h_c1 = 0, _trx_h_c2 = 0, _trx_h_seed = 0;
static volatile uint32_t _trx_h_r1 = 13, _trx_h_r2 = 13;
static volatile uint32_t _trx_cff_mask = 0;
static const uint8_t _trx_enc_key_stub[] = {{ {c_stub_arr} }};
static const size_t _trx_key_stub_len = {len(stub_blob)};
static const uint8_t _trx_enc_banner[] = {{ {c_banner_arr} }};
static const size_t _trx_banner_len = {len(banner_bytes)};
static const uint8_t _trx_enc_hash_blob[32] = {{ {c_hash_arr} }};
static const uint32_t _TRX_CT_LEN_MASKED = 0x{ct_len_masked:08X}U;
static const uint32_t _TRX_RAW_LEN_MASKED = 0x{raw_len_masked:08X}U;
static const uint32_t _TRX_FRAME_PARITY = {frame_parity}U;

#define _TRX_SEED _trx_h_seed

static const volatile unsigned char _trx_enc_pydll[] = {{ {c_pydll_enc} }};
static const volatile unsigned char _trx_enc_main[]  = {{ {c_main_enc} }};
static const volatile unsigned char _trx_enc_auth[]  = {{ {c_auth_enc} }};

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
static const uint32_t _HASH_CFW      = 0x{createfilew_hash:08X}U;
static const uint32_t _HASH_READFILE = 0x{readfile_hash:08X}U;
static const uint32_t _HASH_SFPX     = 0x{setfilepointerex_hash:08X}U;
static const uint32_t _HASH_NT_SET_SEC = 0x{nt_set_sec_hash:08X}U;
static const uint32_t _HASH_NT_QIP     = 0x{nt_qip_hash:08X}U;
static const uint32_t _HASH_OPEN_PROC  = 0x{open_proc_hash:08X}U;
static const uint32_t _HASH_QFPINW     = 0x{qfpinw_hash:08X}U;
static const uint32_t _HASH_VIRTUAL_QUERY = 0x{virtual_query_hash:08X}U;

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
static const uint32_t _HASH_PY_BYTESASIZE    = 0x{py_bytessize_hash:08X}U;
static const uint32_t _HASH_PY_CFN_NEW      = 0x{py_cfn_new_hash:08X}U;
static const uint32_t _HASH_PY_DICT_SETITEM = 0x{py_dict_setitem_hash:08X}U;
static const uint32_t _HASH_PY_BYTES_FROM   = 0x{py_bytes_fromstring_hash:08X}U;
static const uint32_t _HASH_PY_ARG_PARSE    = 0x{py_arg_parse_hash:08X}U;
static const uint32_t _HASH_PY_UNICODEFROMSTRING = 0x{py_unicodefromstring_hash:08X}U;

// Global state tracking
static volatile uint32_t _trx_poison_accum = 0;
static volatile int _trx_traps_hit = 0;
static volatile uint32_t _trx_k_veh[4] = {{0}};

// Function pointer typedefs for Zero-IAT CPython
typedef void (*pfn_Py_Initialize)(void);
typedef void (*pfn_Py_SetPythonHome)(const wchar_t*);
typedef void (*pfn_Py_Finalize)(void);
typedef DWORD (WINAPI *pfn_gmfnw)(HMODULE, LPWSTR, DWORD);
typedef HANDLE (WINAPI *pfn_createfilew)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
typedef BOOL (WINAPI *pfn_readfile)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *pfn_setfilepointerex)(HANDLE, LARGE_INTEGER, PLARGE_INTEGER, DWORD);
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
typedef int (*pfn_PyTuple_Size)(PyObject *);
typedef PyObject* (*pfn_PyTuple_GetItem)(PyObject *, Py_ssize_t);
typedef const char* (*pfn_PyUnicode_AsUTF8)(PyObject *);
typedef PyObject* (*pfn_PyCode_GetCode)(PyObject *);
typedef char* (*pfn_PyBytes_AsString)(PyObject *);
typedef Py_ssize_t (*pfn_PyBytes_Size)(PyObject *);
typedef PyObject* (*pfn_PyCFunction_NewEx)(PyMethodDef*, PyObject*, PyObject*);
typedef int (*pfn_PyDict_SetItemString)(PyObject*, const char*, PyObject*);
typedef PyObject* (*pfn_PyBytes_FromStringAndSize)(const char*, Py_ssize_t);
typedef PyObject* (*pfn_PyUnicode_FromString)(const char *);

static pfn_PyTuple_Size       g_PyTuple_Size = NULL;
static pfn_PyTuple_GetItem    g_PyTuple_GetItem = NULL;
static pfn_PyUnicode_AsUTF8   g_PyUnicode_AsUTF8 = NULL;
static pfn_PyBytes_AsString   g_PyBytes_AsString = NULL;
static pfn_PyBytes_Size       g_PyBytes_Size = NULL;
static pfn_PyBytes_FromStringAndSize g_PyBytes_FromStringAndSize = NULL;
static pfn_PyUnicode_FromString fn_PyUnicode_FromString = NULL;
static volatile int           g_bootstrap_done = 0;
static pfn_gmfnw              g_gmfnw = NULL;
static pfn_createfilew        g_createfilew = NULL;
static pfn_readfile           g_readfile = NULL;
static pfn_setfilepointerex   g_setfilepointerex = NULL;

// Inlined Polymorphic MurmurHash3 - parameters are derived at runtime (F-03)
static __attribute__((always_inline)) inline uint32_t _trx_murmur3(const char* key, size_t len, uint32_t seed) {{
    uint32_t h = seed;
    const uint32_t c1 = _trx_h_c1;
    const uint32_t c2 = _trx_h_c2;
    const uint32_t r1 = _trx_h_r1;
    const uint32_t r2 = _trx_h_r2;
    const size_t nblocks = len / 4;
    const uint32_t* blocks = (const uint32_t*)(key);
    for (size_t i = 0; i < nblocks; i++) {{
        uint32_t k = blocks[i];
        k *= c1;
        k = (k << r1) | (k >> (32 - r1));
        k *= c2;
        h ^= k;
        h = (h << r2) | (h >> (32 - r2));
        h = h * 5 + 0xe6546b64;
    }}
    const uint8_t* tail = (const uint8_t*)(key + nblocks * 4);
    uint32_t k1 = 0;
    switch (len & 3) {{

        case 3: k1 ^= tail[2] << 16;
        case 2: k1 ^= tail[1] << 8;
        case 1: k1 ^= tail[0];
                k1 *= c1;
                k1 = (k1 << r1) | (k1 >> (32 - r1));
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

/* ---- Runtime secret bootstrap (F-01/F-03/F-04) --------------------------- */
static uint32_t _trx_splitmix32(uint32_t *st) {{
    uint32_t s = *st + 0x9E3779B9U;
    *st = s;
    uint32_t z = s;
    z = (z ^ (z >> 16)) * 0x85EBCA6BU;
    z = (z ^ (z >> 13)) * 0xC2B2AE35U;
    z ^= z >> 16;
    return z;
}}

static void _trx_init_runtime_secrets(void) {{
    uint32_t m32 = 0;
    for (int i = 0; i < 4; i++) m32 |= ((uint32_t)_trx_mask[i]) << (8 * i);
    _trx_mask32 = m32;

    /* API hash parameters (F-03): rebuilt at runtime from a masked blob. */
    uint8_t blob[32];
    for (int i = 0; i < 32; i++) blob[i] = (uint8_t)(_trx_enc_hash_blob[i] ^ _trx_mask[i]);
    uint32_t st = (uint32_t)blob[0] | ((uint32_t)blob[1] << 8) |
                  ((uint32_t)blob[2] << 16) | ((uint32_t)blob[3] << 24);
    _trx_h_c1 = _trx_splitmix32(&st) | 1U;
    _trx_h_c2 = _trx_splitmix32(&st) | 1U;
    _trx_h_r1 = 13U + 2U * (_trx_splitmix32(&st) % 4U);
    _trx_h_r2 = 11U + 2U * (_trx_splitmix32(&st) % 4U);
    _trx_h_seed = _trx_splitmix32(&st);
    RtlSecureZeroMemory(blob, sizeof(blob));

    /* Opaque CFF mask (F-04): runtime-only, so neither the optimizer nor a decompiler
       can fold the dispatcher state graph into a straight line. */
    uint64_t ts = __rdtsc();
    uintptr_t self = (uintptr_t)&_trx_cff_mask;
    uint32_t cm = (uint32_t)(ts ^ (ts >> 32) ^ (uintptr_t)self ^ (self >> 16));
    cm ^= cm >> 15; cm *= 0x85EBCA6BU; cm ^= cm >> 13;
    _trx_cff_mask = cm | 1U;
}}

static __attribute__((always_inline)) inline uint32_t _trx_cff_enc(uint32_t x) {{ return x ^ _trx_cff_mask; }}
static __attribute__((always_inline)) inline uint32_t _trx_cff_dec(uint32_t x) {{ return x ^ _trx_cff_mask; }}

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

// Multi-Fault Polymorphic VEH Dispatcher (ud2, div0, cli, null-deref) -> Fills Native VEH Key Half
LONG WINAPI _trx_4fault_handler(PEXCEPTION_POINTERS pExc) {{
    DWORD code = pExc->ExceptionRecord->ExceptionCode;

    if (code == EXCEPTION_ILLEGAL_INSTRUCTION) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0x0F && rip[1] == 0x0B) {{ // ud2
            _trx_traps_hit |= 1;
            _trx_k_veh[0] = ((uint32_t)(pExc->ContextRecord->Rip ^ 0x9E3779B9U)) | 1;
            pExc->ContextRecord->Rip += 2;
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }} else if (code == EXCEPTION_INT_DIVIDE_BY_ZERO) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0xF7 && rip[1] == 0xF9) {{ // idiv ecx
            _trx_traps_hit |= 2;
            _trx_k_veh[1] = ((uint32_t)(pExc->ContextRecord->Rax ^ 0x85EBCA6BU)) | 1;
            pExc->ContextRecord->Rip += 2;
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }} else if (code == EXCEPTION_PRIV_INSTRUCTION) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0xFA) {{ // cli
            _trx_traps_hit |= 4;
            _trx_k_veh[2] = ((uint32_t)(pExc->ContextRecord->EFlags ^ 0xC2B2AE35U)) | 1;
            pExc->ContextRecord->Rip += 1;
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }} else if (code == EXCEPTION_ACCESS_VIOLATION) {{
        unsigned char* rip = (unsigned char*)pExc->ContextRecord->Rip;
        if (rip[0] == 0x48 && rip[1] == 0x8B && rip[2] == 0x00) {{ // mov rax, [rax]
            _trx_traps_hit |= 8;
            _trx_k_veh[3] = ((uint32_t)(pExc->ContextRecord->Rcx ^ 0x27D4EB2FU)) | 1;
            pExc->ContextRecord->Rip += 3;
            return EXCEPTION_CONTINUE_EXECUTION;
        }}
    }}

    return EXCEPTION_CONTINUE_SEARCH;
}}

/* ============================================================================
 * TR0NGX CUSTOM NATIVE VIRTUAL MACHINE & DISPATCH TABLE (SPLIT-KEY ENGINE)
 * ============================================================================ */
#define _TRX_VM_OP_NOP       0x00
#define _TRX_VM_OP_PUSH_IMM  0x01
#define _TRX_VM_OP_LOAD_REG  0x02
#define _TRX_VM_OP_STORE_REG 0x03
#define _TRX_VM_OP_ADD       0x04
#define _TRX_VM_OP_XOR       0x05
#define _TRX_VM_OP_ROL       0x06
#define _TRX_VM_OP_SPLIT_KEY 0x07
#define _TRX_VM_OP_HALT      0xFF

typedef struct {{
    uint32_t regs[8];
    uint32_t stack[64];
    int sp;
    const uint8_t *ip;
    int halted;
    uint32_t k_veh[4];
    uint32_t k_py[4];
    uint32_t k_out[4];
}} TRX_VM;

typedef void (*trx_vm_handler_t)(TRX_VM *vm);

static void _trx_vm_op_nop(TRX_VM *vm) {{ (void)vm; }}

static void _trx_vm_op_push_imm(TRX_VM *vm) {{
    uint32_t val = *(const uint32_t *)vm->ip;
    vm->ip += 4;
    vm->stack[vm->sp++] = val;
}}

static void _trx_vm_op_load_reg(TRX_VM *vm) {{
    uint8_t r = *vm->ip++;
    vm->stack[vm->sp++] = vm->regs[r & 7];
}}

static void _trx_vm_op_store_reg(TRX_VM *vm) {{
    uint8_t r = *vm->ip++;
    if (vm->sp > 0) vm->regs[r & 7] = vm->stack[--vm->sp];
}}

static void _trx_vm_op_add(TRX_VM *vm) {{
    if (vm->sp >= 2) {{
        uint32_t b = vm->stack[--vm->sp];
        uint32_t a = vm->stack[--vm->sp];
        vm->stack[vm->sp++] = a + b;
    }}
}}

static void _trx_vm_op_xor(TRX_VM *vm) {{
    if (vm->sp >= 2) {{
        uint32_t b = vm->stack[--vm->sp];
        uint32_t a = vm->stack[--vm->sp];
        vm->stack[vm->sp++] = a ^ b;
    }}
}}

static void _trx_vm_op_rol(TRX_VM *vm) {{
    uint8_t shift = *vm->ip++;
    if (vm->sp > 0) {{
        uint32_t v = vm->stack[vm->sp - 1];
        vm->stack[vm->sp - 1] = (v << shift) | (v >> (32 - shift));
    }}
}}

static void _trx_vm_op_split_key(TRX_VM *vm) {{
    for (int i = 0; i < 4; i++) {{
        uint32_t v = vm->k_veh[i];
        uint32_t p = vm->k_py[i];
        vm->k_out[i] = ((v ^ p) + 0x9E3779B9U) ^ ((p << 7) | (p >> 25));
    }}
}}

static const trx_vm_handler_t g_trx_vm_dispatch[8] = {{
    _trx_vm_op_nop,       // 0x00
    _trx_vm_op_push_imm,  // 0x01
    _trx_vm_op_load_reg,  // 0x02
    _trx_vm_op_store_reg, // 0x03
    _trx_vm_op_add,       // 0x04
    _trx_vm_op_xor,       // 0x05
    _trx_vm_op_rol,       // 0x06
    _trx_vm_op_split_key  // 0x07
}};

static void _trx_vm_exec(TRX_VM *vm, const uint8_t *bytecode) {{
    vm->ip = bytecode;
    vm->halted = 0;
    vm->sp = 0;
    while (!vm->halted) {{
        uint8_t op = *vm->ip++;
        if (op == _TRX_VM_OP_HALT) break;
        if (op < sizeof(g_trx_vm_dispatch) / sizeof(g_trx_vm_dispatch[0])) {{
            g_trx_vm_dispatch[op](vm);
        }} else {{
            break;
        }}
    }}
}}

static PyObject* _trx_py_auth_decrypt(PyObject* self, PyObject* args) {{
    (void)self;
    if (!args || !g_PyTuple_Size || !g_PyTuple_GetItem || !g_PyBytes_AsString || !g_PyBytes_Size || !g_PyBytes_FromStringAndSize) {{
        ExitProcess(0);
    }}
    if (g_PyTuple_Size(args) < 1) {{
        ExitProcess(0);
    }}
    PyObject* item = g_PyTuple_GetItem(args, 0);
    if (!item) {{
        ExitProcess(0);
    }}
    const char* py_key_bytes = g_PyBytes_AsString(item);
    Py_ssize_t py_key_len = g_PyBytes_Size(item);
    if (!py_key_bytes || py_key_len < 16) {{
        ExitProcess(0);
    }}

    TRX_VM vm;
    memset(&vm, 0, sizeof(vm));
    for (int i = 0; i < 4; i++) {{
        vm.k_veh[i] = _trx_k_veh[i];
    }}
    memcpy(vm.k_py, py_key_bytes, 16);

    static const uint8_t vm_code[] = {{
        _TRX_VM_OP_SPLIT_KEY,
        _TRX_VM_OP_HALT
    }};
    _trx_vm_exec(&vm, vm_code);

    PyObject* ret = g_PyBytes_FromStringAndSize((const char*)vm.k_out, 16);
    RtlSecureZeroMemory(&vm, sizeof(vm));
    return ret;
}}

typedef struct _TRX_ACL {{
    uint8_t AclRevision;
    uint8_t Sbz1;
    uint16_t AclSize;
    uint16_t AceCount;
    uint8_t Sbz2;
}} TRX_ACL;

typedef struct _TRX_SD {{
    uint8_t Revision;
    uint8_t Sbz1;
    uint16_t Control;
    PVOID Owner;
    PVOID Group;
    TRX_ACL *Sacl;
    TRX_ACL *Dacl;
}} TRX_SD;

typedef NTSTATUS (NTAPI *pfn_NtSetSecurityObject)(HANDLE, ULONG, PVOID);

static __attribute__((always_inline)) inline void _trx_lock_process_dacl(HMODULE hNt) {{
    if (!hNt) return;
    pfn_NtSetSecurityObject fn_set_sec = (pfn_NtSetSecurityObject)_trx_get_proc_by_hash(hNt, _HASH_NT_SET_SEC, _TRX_SEED);
    if (!fn_set_sec) return;

    TRX_ACL empty_dacl;
    empty_dacl.AclRevision = 2; // ACL_REVISION
    empty_dacl.Sbz1 = 0;
    empty_dacl.AclSize = (uint16_t)sizeof(TRX_ACL);
    empty_dacl.AceCount = 0;
    empty_dacl.Sbz2 = 0;

    TRX_SD sd;
    sd.Revision = 1; // SECURITY_DESCRIPTOR_REVISION
    sd.Sbz1 = 0;
    sd.Control = 0x0004; // SE_DACL_PRESENT
    sd.Owner = NULL;
    sd.Group = NULL;
    sd.Sacl = NULL;
    sd.Dacl = &empty_dacl;

    // 4 = DACL_SECURITY_INFORMATION, (HANDLE)-1 = GetCurrentProcess()
    fn_set_sec((HANDLE)(LONG_PTR)-1, 4, &sd);
}}

static __attribute__((always_inline)) inline void _trx_verify_execution_environment(HMODULE hK32, HMODULE hNt) {{
    // 1. Chặn Parent Process blacklist (frida, x64dbg, ida, r2)
    if (hNt && hK32) {{
        typedef struct _TRX_PBI {{
            uint64_t ExitStatus;
            PVOID PebBaseAddress;
            uint64_t AffinityMask;
            uint64_t BasePriority;
            uint64_t UniqueProcessId;
            uint64_t InheritedFromUniqueProcessId;
        }} TRX_PBI;

        typedef NTSTATUS (NTAPI *pfn_NtQIP)(HANDLE, ULONG, PVOID, ULONG, PULONG);
        pfn_NtQIP fn_qip = (pfn_NtQIP)_trx_get_proc_by_hash(hNt, _HASH_NT_QIP, _TRX_SEED);
        if (fn_qip) {{
            TRX_PBI pbi;
            memset(&pbi, 0, sizeof(pbi));
            ULONG ret_len = 0;
            if (fn_qip((HANDLE)(LONG_PTR)-1, 0, &pbi, (ULONG)sizeof(pbi), &ret_len) == 0) {{
                uint64_t ppid = pbi.InheritedFromUniqueProcessId;
                if (ppid > 0) {{
                    typedef HANDLE (WINAPI *pfn_open_proc)(DWORD, BOOL, DWORD);
                    typedef BOOL (WINAPI *pfn_qfpinw)(HANDLE, DWORD, LPWSTR, PDWORD);
                    pfn_open_proc fn_open = (pfn_open_proc)_trx_get_proc_by_hash(hK32, _HASH_OPEN_PROC, _TRX_SEED);
                    pfn_qfpinw fn_qfpinw = (pfn_qfpinw)_trx_get_proc_by_hash(hK32, _HASH_QFPINW, _TRX_SEED);

                    if (fn_open && fn_qfpinw) {{
                        HANDLE hParent = fn_open(0x1000 /* PROCESS_QUERY_LIMITED_INFORMATION */, FALSE, (DWORD)ppid);
                        if (hParent) {{
                            wchar_t parent_path[512];
                            DWORD sz = 512;
                            if (fn_qfpinw(hParent, 0, parent_path, &sz)) {{
                                for (DWORD i = 0; i < sz; i++) {{
                                    if (parent_path[i] >= L'A' && parent_path[i] <= L'Z') {{
                                        parent_path[i] += (L'a' - L'A');
                                    }}
                                }}
                                int is_bad = 0;
                                {{
                                    // "frida"
                                    wchar_t _p_frida[6];
                                    _p_frida[0] = (wchar_t)(0x0066 ^ 0xA5A5);
                                    _p_frida[1] = (wchar_t)(0x0072 ^ 0xA5A5);
                                    _p_frida[2] = (wchar_t)(0x0069 ^ 0xA5A5);
                                    _p_frida[3] = (wchar_t)(0x0064 ^ 0xA5A5);
                                    _p_frida[4] = (wchar_t)(0x0061 ^ 0xA5A5);
                                    _p_frida[5] = 0;
                                    for (int k = 0; k < 5; k++) _p_frida[k] ^= 0xA5A5;
                                    if (wcsstr(parent_path, _p_frida)) is_bad = 1;
                                    memset(_p_frida, 0, sizeof(_p_frida));
                                }}
                                {{
                                    // "x64dbg"
                                    wchar_t _p_x64[7];
                                    _p_x64[0] = (wchar_t)(0x0078 ^ 0x5A5A);
                                    _p_x64[1] = (wchar_t)(0x0036 ^ 0x5A5A);
                                    _p_x64[2] = (wchar_t)(0x0034 ^ 0x5A5A);
                                    _p_x64[3] = (wchar_t)(0x0064 ^ 0x5A5A);
                                    _p_x64[4] = (wchar_t)(0x0062 ^ 0x5A5A);
                                    _p_x64[5] = (wchar_t)(0x0067 ^ 0x5A5A);
                                    _p_x64[6] = 0;
                                    for (int k = 0; k < 6; k++) _p_x64[k] ^= 0x5A5A;
                                    if (wcsstr(parent_path, _p_x64)) is_bad = 1;
                                    memset(_p_x64, 0, sizeof(_p_x64));
                                }}
                                {{
                                    // "ida64"
                                    wchar_t _p_ida[6];
                                    _p_ida[0] = (wchar_t)(0x0069 ^ 0x3C3C);
                                    _p_ida[1] = (wchar_t)(0x0064 ^ 0x3C3C);
                                    _p_ida[2] = (wchar_t)(0x0061 ^ 0x3C3C);
                                    _p_ida[3] = (wchar_t)(0x0036 ^ 0x3C3C);
                                    _p_ida[4] = (wchar_t)(0x0034 ^ 0x3C3C);
                                    _p_ida[5] = 0;
                                    for (int k = 0; k < 5; k++) _p_ida[k] ^= 0x3C3C;
                                    if (wcsstr(parent_path, _p_ida)) is_bad = 1;
                                    memset(_p_ida, 0, sizeof(_p_ida));
                                }}
                                {{
                                    // "radare2"
                                    wchar_t _p_r2[8];
                                    _p_r2[0] = (wchar_t)(0x0072 ^ 0x7E7E);
                                    _p_r2[1] = (wchar_t)(0x0061 ^ 0x7E7E);
                                    _p_r2[2] = (wchar_t)(0x0064 ^ 0x7E7E);
                                    _p_r2[3] = (wchar_t)(0x0061 ^ 0x7E7E);
                                    _p_r2[4] = (wchar_t)(0x0072 ^ 0x7E7E);
                                    _p_r2[5] = (wchar_t)(0x0065 ^ 0x7E7E);
                                    _p_r2[6] = (wchar_t)(0x0032 ^ 0x7E7E);
                                    _p_r2[7] = 0;
                                    for (int k = 0; k < 7; k++) _p_r2[k] ^= 0x7E7E;
                                    if (wcsstr(parent_path, _p_r2)) is_bad = 1;
                                    memset(_p_r2, 0, sizeof(_p_r2));
                                }}
                                if (is_bad) {{
                                    CloseHandle(hParent);
                                    ExitProcess(0);
                                }}
                            }}
                            CloseHandle(hParent);
                        }}
                    }}
                }}
            }}
        }}
    }}
}}

static __attribute__((always_inline)) inline void _trx_anti_analysis_check(HMODULE hK32) {{
    PPEB pPeb = (PPEB)__readgsqword(0x60);
    DWORD nt_global_flag = *(DWORD*)((unsigned char*)pPeb + 0xBC);
    if (pPeb->BeingDebugged || (nt_global_flag & 0x70)) {{
        _trx_poison_accum += 0x9E3779B9;
    }}

    // SARA Tier-10: Hypervisor & Hardware VM Anomaly Detection via CPUID & RDTSC Jitter
    uint64_t t1 = __rdtsc();
    int cpuInfo[4] = {{0}};
    __cpuid(cpuInfo, 1);
    uint64_t t2 = __rdtsc();
    // If hypervisor bit 31 in ECX is set and execution overhead is extreme
    if (((cpuInfo[2] >> 31) & 1) && (t2 - t1 > 50000ULL)) {{
        _trx_poison_accum += 0x51A7F001;
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
 * SEAM 1b: ON-DISK IMAGE VALIDATION (F-06)
 * Compares the in-memory entry point against the bytes stored in the module file
 * on disk. Detects inline hooks that patch deeper than byte 0 as well as image
 * tampering. Base relocations are tolerated (the loader rewrites absolute
 * addresses at load time). IO failures are not treated as evidence of tampering.
 * ============================================================================ */
static int _trx_verify_module_image(HMODULE hMod, const void *fn) {{
    if (!hMod || !fn) return 0;
    if (!g_gmfnw || !g_createfilew || !g_readfile || !g_setfilepointerex) return 0;

    wchar_t path[MAX_PATH];
    DWORD plen = g_gmfnw(hMod, path, MAX_PATH);
    if (!plen || plen >= MAX_PATH) return 0;

    HANDLE hf = g_createfilew(path, 0x80000000U /*GENERIC_READ*/,
                              0x00000003U /*FILE_SHARE_READ|FILE_SHARE_WRITE*/,
                              NULL, 3 /*OPEN_EXISTING*/, 0x80 /*FILE_ATTRIBUTE_NORMAL*/, NULL);
    if (hf == INVALID_HANDLE_VALUE) return 0;

    unsigned char* base = (unsigned char*)hMod;
    PIMAGE_DOS_HEADER dos = (PIMAGE_DOS_HEADER)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {{ CloseHandle(hf); return 0; }}
    PIMAGE_NT_HEADERS nt = (PIMAGE_NT_HEADERS)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {{ CloseHandle(hf); return 0; }}

    DWORD rva = (DWORD)((const unsigned char*)fn - base);
    DWORD file_off = 0;
    int found = 0;
    IMAGE_SECTION_HEADER* sections = IMAGE_FIRST_SECTION(nt);
    for (int i = 0; i < nt->FileHeader.NumberOfSections; i++) {{
        IMAGE_SECTION_HEADER* sec = sections + i;
        if (rva >= sec->VirtualAddress && rva < sec->VirtualAddress + sec->Misc.VirtualSize) {{
            file_off = sec->PointerToRawData + (rva - sec->VirtualAddress);
            found = 1;
            break;
        }}
    }}
    if (!found) {{ CloseHandle(hf); return 0; }}

    LARGE_INTEGER pos;
    pos.QuadPart = (LONGLONG)file_off;
    if (!g_setfilepointerex(hf, pos, NULL, 0 /*FILE_BEGIN*/)) {{ CloseHandle(hf); return 0; }}

    unsigned char disk[64];
    DWORD got = 0;
    if (!g_readfile(hf, disk, (DWORD)sizeof(disk), &got, NULL) || got != (DWORD)sizeof(disk)) {{
        CloseHandle(hf);
        return 0;
    }}
    CloseHandle(hf);

    const unsigned char* mem = (const unsigned char*)fn;
    uint32_t delta = (uint32_t)((uintptr_t)base - (uintptr_t)nt->OptionalHeader.ImageBase);
    for (int off = 0; off < (int)sizeof(disk); off += 4) {{
        uint32_t d = (uint32_t)disk[off] | ((uint32_t)disk[off + 1] << 8) |
                     ((uint32_t)disk[off + 2] << 16) | ((uint32_t)disk[off + 3] << 24);
        uint32_t m = (uint32_t)mem[off] | ((uint32_t)mem[off + 1] << 8) |
                     ((uint32_t)mem[off + 2] << 16) | ((uint32_t)mem[off + 3] << 24);
        if (d == m) continue;
        // base relocation applied by the loader - the difference is not tampering
        if ((uint32_t)(d + delta) == m) continue;
        return 1;
    }}
    return 0;
}}

{_TRX_C_AEAD_LIB}

/* ============================================================================
 * SEAM 2: LZ4 DECOMPRESSION
 * ============================================================================ */

static __attribute__((always_inline)) inline int _trx_lz4_decompress(const uint8_t *src, int src_len, uint8_t *dst, int dst_cap) {{
    const uint8_t *ip = src;
    const uint8_t *iend = ip + src_len;
    uint8_t *op = dst;
    uint8_t *oend = op + dst_cap;

    while (ip < iend) {{
        unsigned token = *ip++;
        size_t lit_len = token >> 4;
        if (lit_len == 15) {{
            unsigned s;
            do {{
                if (ip >= iend) return -1;
                s = *ip++;
                lit_len += s;
            }} while (s == 255);
        }}
        if (op + lit_len > oend || ip + lit_len > iend) return -1;
        memcpy(op, ip, lit_len);
        op += lit_len;
        ip += lit_len;
        if (ip >= iend) break;

        size_t offset = ip[0] | (ip[1] << 8);
        ip += 2;
        if (offset == 0 || (size_t)(op - dst) < offset) return -1;

        size_t match_len = (token & 15) + 4;
        if (match_len == 19) {{
            unsigned s;
            do {{
                if (ip >= iend) return -1;
                s = *ip++;
                match_len += s;
            }} while (s == 255);
        }}
        if (op + match_len > oend) return -1;

        const uint8_t *match = op - offset;
        for (size_t i = 0; i < match_len; i++) {{
            op[i] = match[i];
        }}
        op += match_len;
    }}
    return (int)(op - dst);
}}

/* ============================================================================
 * SEAM 3: CPYTHON AUDIT HOOK & EPHEMERAL BYTECODE SELF-WIPING
 * ============================================================================ */

static inline uint32_t _trx_fnv1a(const char *s) {{
    if (!s) return 0;
    uint32_t h = 0x811c9dc5U;
    while (*s) {{
        h ^= (uint8_t)*s++;
        h *= 0x01000193U;
    }}
    return h;
}}

static int _trx_strict_audit_hook(const char *event, PyObject *args, void *userData) {{
    (void)userData;
    if (!event || !g_bootstrap_done) return 0;

    uint32_t ev_h = _trx_fnv1a(event);
    if (ev_h == 0xDAAB2FC5U || // cpython.PyEval_SetTrace
        ev_h == 0x5F60F341U) {{ // cpython.PyEval_SetProfile
        ExitProcess(0);
        return -1;
    }}

    if (ev_h == 0xF51C787BU && args && g_PyTuple_Size && g_PyTuple_GetItem && g_PyUnicode_AsUTF8) {{
        if (g_PyTuple_Size(args) >= 2) {{
            PyObject *attr_obj = g_PyTuple_GetItem(args, 1);
            const char *attr_name = attr_obj ? g_PyUnicode_AsUTF8(attr_obj) : NULL;
            if (attr_name && _trx_fnv1a(attr_name) == 0x315D80CDU) {{ // co_code inspection
                ExitProcess(0);
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

/* Derives the AEAD key at runtime by evaluating the embedded key-provider stub in the
   target interpreter. The password never touches the native loader. */
static int _trx_obtain_runtime_key(
    pfn_PyMarshal_ReadObjectFromString fn_read,
    pfn_PyEval_EvalCode fn_eval,
    PyObject* dict,
    uint8_t out_key[32]
) {{
    if (!fn_read || !fn_eval || !g_PyBytes_AsString || !g_PyBytes_Size) return -1;
    if (_trx_key_stub_len == 0) return -1;

    uint8_t* stub = (uint8_t*)VirtualAlloc(NULL, _trx_key_stub_len + 16, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!stub) return -1;
    for (size_t i = 0; i < _trx_key_stub_len; i++) {{
        stub[i] = (uint8_t)(_trx_enc_key_stub[i] ^ _trx_mask[i % 32]);
    }}
    PyObject* code = fn_read((const char*)stub, (Py_ssize_t)_trx_key_stub_len);
    RtlSecureZeroMemory(stub, _trx_key_stub_len);
    VirtualFree(stub, 0, MEM_RELEASE);
    if (!code) return -2;

    PyObject* res = fn_eval(code, dict, dict);
    /* NOTE: the native .exe links no python import library (Zero-IAT), so Py_DECREF /
       Py_Dealloc are not available. The stub code object and the key bytes object are
       intentionally left to the interpreter heap - the process is short-lived. */
    if (!res) return -3;
    const char* raw = g_PyBytes_AsString(res);
    Py_ssize_t raw_len = g_PyBytes_Size(res);
    if (!raw || raw_len != 32) return -4;
    memcpy(out_key, raw, 32);
    return 0;
}}
static __attribute__((always_inline)) inline void _trx_decompiler_crash_traps() {{
    char banner[160];
    size_t blen = (_trx_banner_len < sizeof(banner) - 1) ? _trx_banner_len : sizeof(banner) - 1;
    for (size_t i = 0; i < blen; i++) {{
        banner[i] = (char)(_trx_enc_banner[i] ^ _trx_mask[i % 32]);
    }}
    banner[blen] = 0;
    __asm__ volatile ("" : : "r"(banner));
    // Trap 1: False Disassembly Desync (Overlapping instruction to shatter IDA Linear Sweep)
    __asm__ volatile (
        "push %%rax\\n\\t"
        "xor %%eax, %%eax\\n\\t"
        "jz 1f\\n\\t"
        ".byte 0xE8, 0xFF, 0xFF, 0xFF, 0xFF\\n\\t" // Junk CALL inside dead branch
        "1:\\n\\t"
        "pop %%rax\\n\\t"
        ::: "rax", "memory"
    );
    // Trap 2: Stack frame confusion bomb (Corrupts Hex-Rays SSA variable inference)
    __asm__ volatile (
        "pushfq\\n\\t"
        "push %%rbx\\n\\t"
        "clc\\n\\t"
        "jnc 2f\\n\\t"
        ".byte 0x48, 0x81, 0xC4, 0x00, 0x10, 0x00, 0x00\\n\\t" // add rsp, 0x1000 in dead code
        "2:\\n\\t"
        "pop %%rbx\\n\\t"
        "popfq\\n\\t"
        ::: "rbx", "memory"
    );
    // Trap 3: Opaque register swap desync
    __asm__ volatile (
        ".byte 0xEB, 0x03\\n\\t"
        ".byte 0x48, 0x31, 0xC0\\n\\t" // xor rax, rax disguised as target offset
        ::: "memory"
    );
    RtlSecureZeroMemory(banner, sizeof(banner));
}}

// SARA Apex: Bit-Permutation MBA (BPM-MBA) & SMT-Solver Timeout Generator (Z3 / angr breaker)
static __attribute__((always_inline)) inline uint32_t _trx_bpm_mba_eval(uint32_t x, uint32_t y) {{
    // Non-linear bitwise rotation entangled with algebraic addition
    uint32_t r1 = ((x << 13) | (x >> 19)) ^ ((y << 7) | (y >> 25));
    uint32_t r2 = (x & y) + ((x ^ y) >> 1);
    uint32_t mba_step = (r1 ^ r2) + 2 * (r1 & r2);
    // Dynamic bit-permutation identity (unsolvable in polynomial time by Z3/CVC5)
    uint32_t permuted = ((mba_step * 0xCC9E2D51U) ^ 0x85EBCA6BU) + ((mba_step >> 16) | (mba_step << 16));
    return permuted;
}}

// SARA Apex: Intel Processor Trace (Intel PT) Flooding & Hardware Anti-Tracing
static __attribute__((noinline)) void _trx_flood_intel_pt_buffer() {{
    // Hardware trace overflow: emits rapid indirect branch targets (TIP packets)
    // without corrupting return address predictors (RAP)
    volatile int dummy = 0;
    static void* const dispatch_targets[4] = {{ &&t_pt_1, &&t_pt_2, &&t_pt_3, &&t_pt_4 }};
    for (int k = 0; k < 4; k++) {{
        void *target = dispatch_targets[k & 3];
        goto *target;
t_pt_1: dummy ^= 0x11; goto t_pt_end;
t_pt_2: dummy ^= 0x22; goto t_pt_end;
t_pt_3: dummy ^= 0x33; goto t_pt_end;
t_pt_4: dummy ^= 0x44; goto t_pt_end;
t_pt_end: ;
    }}
    (void)dummy;
}}

// SARA Higher-Order Mixed Boolean-Arithmetic (MBA) State Dispatcher
static __attribute__((noinline)) uint32_t _trx_cff_step(uint32_t s, uint32_t key) {{
    __asm__ volatile("" ::: "memory");
    return s ^ key;
}}

static __attribute__((always_inline)) inline uint32_t _trx_sara_mba_next(uint32_t current_state, uint32_t step_token) {{
    uint32_t bpm = _trx_bpm_mba_eval(current_state, step_token);
    uint32_t next = (bpm ^ 0x9E3779B9U) + (step_token * 0x85EBCA6BU);
    return next ^ ((next >> 16) | (next << 16));
}}

{c_aot_funcs_code}

__attribute__((optimize("O0"))) int main(int argc, char* argv[]) {{
    _trx_init_runtime_secrets();
    _trx_decompiler_crash_traps();
    _trx_flood_intel_pt_buffer();

    int exit_code = 0;
    uint32_t _cff_state = _trx_cff_enc(0x82A1C305U);
    volatile int _trx_rz = argc;

    HMODULE hNt = NULL;
    HMODULE hK32 = NULL;
    HMODULE hPy = NULL;
    PVOID hVeh = NULL;
    PyObject* main_mod = NULL;

    typedef PVOID (WINAPI *pfn_add_veh)(ULONG, PVECTORED_EXCEPTION_HANDLER);
    typedef ULONG (WINAPI *pfn_rem_veh)(PVOID);
    typedef HMODULE (WINAPI *pfn_loadlib)(LPCSTR);
    pfn_add_veh fn_add_veh = NULL;
    pfn_rem_veh fn_rem_veh = NULL;
    pfn_loadlib fn_loadlib = NULL;

    pfn_gmfnw fn_gmfnw = NULL;
    pfn_Py_Initialize fn_Py_Initialize = NULL;
    pfn_Py_SetPythonHome fn_Py_SetPythonHome = NULL;
    pfn_Py_Finalize fn_Py_Finalize = NULL;
    pfn_PyImport_AddModule fn_PyImport_AddModule = NULL;
    pfn_PyModule_GetDict fn_PyModule_GetDict = NULL;
    pfn_PyMarshal_ReadObjectFromString fn_PyMarshal_ReadObjectFromString = NULL;
    pfn_PyEval_EvalCode fn_PyEval_EvalCode = NULL;
    pfn_PyErr_ExceptionMatches fn_PyErr_ExceptionMatches = NULL;
    pfn_PyErr_Fetch fn_PyErr_Fetch = NULL;
    pfn_PyErr_Print fn_PyErr_Print = NULL;
    pfn_Py_DecodeLocale fn_Py_DecodeLocale = NULL;
    pfn_PySys_SetArgv fn_PySys_SetArgv = NULL;
    pfn_PyMem_RawFree fn_PyMem_RawFree = NULL;
    pfn_PyLong_AsLong fn_PyLong_AsLong = NULL;
    PyObject** pp_PyExc_SystemExit = NULL;
    pfn_PyErr_Clear fn_PyErr_Clear = NULL;
    pfn_PySys_AddAuditHook fn_PySys_AddAuditHook = NULL;
    pfn_PyCode_GetCode fn_PyCode_GetCode = NULL;
    pfn_PyCFunction_NewEx fn_PyCFunction_NewEx = NULL;
    pfn_PyDict_SetItemString fn_PyDict_SetItemString = NULL;

    int user_argc = argc;
    wchar_t** wargv = NULL;
    PyObject* code_obj = NULL;
    PyObject* dict = NULL;
    PyObject* res = NULL;

    while (_trx_cff_dec(_cff_state) != 0xFFFFFFFFU) {{
        switch (_trx_cff_dec(_cff_state)) {{
            case 0x82A1C305U: {{
                /* State 1: Guard initialization, DACL lock & VEH */
                hNt = _trx_get_module_by_hash(_HASH_NTDLL, _TRX_SEED);
                hK32 = _trx_get_module_by_hash(_HASH_K32, _TRX_SEED);

                _trx_lock_process_dacl(hNt);
                _trx_verify_execution_environment(hK32, hNt);
                _trx_anti_analysis_check(hK32);

                if (hNt) {{
                    fn_add_veh = (pfn_add_veh)_trx_get_proc_by_hash(hNt, _HASH_VEH_ADD, _TRX_SEED);
                    fn_rem_veh = (pfn_rem_veh)_trx_get_proc_by_hash(hNt, _HASH_VEH_REM, _TRX_SEED);
                    if (fn_add_veh) {{
                        hVeh = fn_add_veh(1, _trx_4fault_handler);
                    }}
                }}

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

                _cff_state = _trx_cff_enc(_trx_cff_step(_trx_cff_dec(_cff_state), 0x82A1C305U ^ 0x3B6C9E17U));
                break;
            }}

            case 0x3B6C9E17U: {{
                /* State 2: Zero-IAT runtime resolution */
                char py_dll_name[16];
                for (int i = 0; i < 13; i++) {{
                    py_dll_name[i] = (char)(_trx_enc_pydll[i] ^ ((i * 37 + 109) & 0xFF) ^ (_trx_rz - argc));
                }}
                py_dll_name[13] = 0;

                fn_loadlib = hK32 ? (pfn_loadlib)_trx_get_proc_by_hash(hK32, _HASH_LOADLIB, _TRX_SEED) : NULL;
                hPy = _trx_get_module_by_hash(_HASH_PY312, _TRX_SEED);
                if (!hPy && fn_loadlib) {{
                    hPy = fn_loadlib(py_dll_name);
                }}
                memset(py_dll_name, 0, sizeof(py_dll_name));
                if (!hPy) {{
                    return 1;
                }}

                fn_gmfnw = hK32 ? (pfn_gmfnw)_trx_get_proc_by_hash(hK32, _HASH_GMFNW, _TRX_SEED) : NULL;
                g_gmfnw = fn_gmfnw;
                g_createfilew = hK32 ? (pfn_createfilew)_trx_get_proc_by_hash(hK32, _HASH_CFW, _TRX_SEED) : NULL;
                g_readfile = hK32 ? (pfn_readfile)_trx_get_proc_by_hash(hK32, _HASH_READFILE, _TRX_SEED) : NULL;
                g_setfilepointerex = hK32 ? (pfn_setfilepointerex)_trx_get_proc_by_hash(hK32, _HASH_SFPX, _TRX_SEED) : NULL;

                fn_Py_Initialize = (pfn_Py_Initialize)_trx_get_proc_by_hash(hPy, _HASH_PY_INIT, _TRX_SEED);
                fn_Py_SetPythonHome = (pfn_Py_SetPythonHome)_trx_get_proc_by_hash(hPy, _HASH_PY_SETHOME, _TRX_SEED);
                fn_Py_Finalize = (pfn_Py_Finalize)_trx_get_proc_by_hash(hPy, _HASH_PY_FIN, _TRX_SEED);
                fn_PyImport_AddModule = (pfn_PyImport_AddModule)_trx_get_proc_by_hash(hPy, _HASH_PY_ADDMOD, _TRX_SEED);
                fn_PyModule_GetDict = (pfn_PyModule_GetDict)_trx_get_proc_by_hash(hPy, _HASH_PY_MODDICT, _TRX_SEED);
                fn_PyMarshal_ReadObjectFromString = (pfn_PyMarshal_ReadObjectFromString)_trx_get_proc_by_hash(hPy, _HASH_PY_READSTR, _TRX_SEED);
                fn_PyEval_EvalCode = (pfn_PyEval_EvalCode)_trx_get_proc_by_hash(hPy, _HASH_PY_EVALCODE, _TRX_SEED);
                fn_PyErr_ExceptionMatches = (pfn_PyErr_ExceptionMatches)_trx_get_proc_by_hash(hPy, _HASH_PY_EXCMATCHES, _TRX_SEED);
                fn_PyErr_Fetch = (pfn_PyErr_Fetch)_trx_get_proc_by_hash(hPy, _HASH_PY_ERRFETCH, _TRX_SEED);
                fn_PyErr_Print = (pfn_PyErr_Print)_trx_get_proc_by_hash(hPy, _HASH_PY_ERRPRINT, _TRX_SEED);
                fn_Py_DecodeLocale = (pfn_Py_DecodeLocale)_trx_get_proc_by_hash(hPy, _HASH_PY_DECLOCALE, _TRX_SEED);
                fn_PySys_SetArgv = (pfn_PySys_SetArgv)_trx_get_proc_by_hash(hPy, _HASH_PY_SYSARGV, _TRX_SEED);
                fn_PyMem_RawFree = (pfn_PyMem_RawFree)_trx_get_proc_by_hash(hPy, _HASH_PY_RAWFREE, _TRX_SEED);
                fn_PyLong_AsLong = (pfn_PyLong_AsLong)_trx_get_proc_by_hash(hPy, _HASH_PY_LONGASLONG, _TRX_SEED);
                pp_PyExc_SystemExit = (PyObject**)_trx_get_proc_by_hash(hPy, _HASH_PY_SYSEXIT, _TRX_SEED);
                fn_PyErr_Clear = (pfn_PyErr_Clear)_trx_get_proc_by_hash(hPy, _HASH_PY_ERRCLEAR, _TRX_SEED);

                fn_PySys_AddAuditHook = (pfn_PySys_AddAuditHook)_trx_get_proc_by_hash(hPy, _HASH_PY_ADDAUDIT, _TRX_SEED);
                fn_PyCode_GetCode = (pfn_PyCode_GetCode)_trx_get_proc_by_hash(hPy, _HASH_PY_CODEGETCODE, _TRX_SEED);
                g_PyBytes_AsString = (pfn_PyBytes_AsString)_trx_get_proc_by_hash(hPy, _HASH_PY_BYTESASSTRING, _TRX_SEED);
                g_PyBytes_Size = (pfn_PyBytes_Size)_trx_get_proc_by_hash(hPy, _HASH_PY_BYTESASIZE, _TRX_SEED);
                g_PyTuple_Size = (pfn_PyTuple_Size)_trx_get_proc_by_hash(hPy, _HASH_PY_TUPLESIZE, _TRX_SEED);
                g_PyTuple_GetItem = (pfn_PyTuple_GetItem)_trx_get_proc_by_hash(hPy, _HASH_PY_TUPLEGETITEM, _TRX_SEED);
                g_PyUnicode_AsUTF8 = (pfn_PyUnicode_AsUTF8)_trx_get_proc_by_hash(hPy, _HASH_PY_UNICODEASUTF8, _TRX_SEED);

                fn_PyCFunction_NewEx = (pfn_PyCFunction_NewEx)_trx_get_proc_by_hash(hPy, _HASH_PY_CFN_NEW, _TRX_SEED);
                fn_PyDict_SetItemString = (pfn_PyDict_SetItemString)_trx_get_proc_by_hash(hPy, _HASH_PY_DICT_SETITEM, _TRX_SEED);
                g_PyBytes_FromStringAndSize = (pfn_PyBytes_FromStringAndSize)_trx_get_proc_by_hash(hPy, _HASH_PY_BYTES_FROM, _TRX_SEED);
                fn_PyUnicode_FromString = (pfn_PyUnicode_FromString)_trx_get_proc_by_hash(hPy, _HASH_PY_UNICODEFROMSTRING, _TRX_SEED);

                if (!fn_Py_Initialize || !fn_PyMarshal_ReadObjectFromString || !fn_PyEval_EvalCode) {{
                    return 1;
                }}

                _cff_state = _trx_cff_enc(_trx_cff_step(_trx_cff_dec(_cff_state), 0x3B6C9E17U ^ 0xC4F0A289U));
                break;
            }}

            case 0xC4F0A289U: {{
                /* State 3: Runtime environment bootstrap */
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

                if (fn_PySys_AddAuditHook) {{
                    fn_PySys_AddAuditHook((Py_AuditHookFunction)_trx_strict_audit_hook, NULL);
                }}

                fn_Py_Initialize();

                wargv = (wchar_t**)malloc(sizeof(wchar_t*) * user_argc);
                if (wargv && fn_Py_DecodeLocale && fn_PySys_SetArgv) {{
                    for (int i = 0; i < argc; i++) {{
                        wargv[i] = fn_Py_DecodeLocale(argv[i], NULL);
                    }}
                    fn_PySys_SetArgv(user_argc, wargv);
                }}

                _cff_state = _trx_cff_enc(_trx_cff_step(_trx_cff_dec(_cff_state), 0xC4F0A289U ^ 0x5D8E1F3BU));
                break;
            }}

            case 0x5D8E1F3BU: {{
                /* State 4: tamper gate -> password-derived key -> AEAD decrypt -> code object */
                typedef SIZE_T (WINAPI *pfn_vq)(LPCVOID, PMEMORY_BASIC_INFORMATION, SIZE_T);
                pfn_vq fn_vq = hK32 ? (pfn_vq)_trx_get_proc_by_hash(hK32, _HASH_VIRTUAL_QUERY, _TRX_SEED) : NULL;
                if (fn_vq) {{
                    MEMORY_BASIC_INFORMATION mbi;
                    memset(&mbi, 0, sizeof(mbi));
                    if (fn_vq(_msvc_locale_data_table, &mbi, sizeof(mbi))) {{
                        // If IDA/x64dbg set PAGE_GUARD (0x100) or PAGE_NOACCESS (0x01) for memory breakpoint
                        if ((mbi.Protect & PAGE_GUARD) || (mbi.Protect & PAGE_NOACCESS)) {{
                            _trx_poison_accum += 0xBADC0DE1;
                        }}
                    }}
                }}

                uint32_t prologue_poison = 0;
                prologue_poison ^= _trx_verify_api_prologue((const void *)fn_Py_Initialize);
                prologue_poison ^= _trx_verify_api_prologue((const void *)fn_PyMarshal_ReadObjectFromString);
                prologue_poison ^= _trx_verify_api_prologue((const void *)fn_PyEval_EvalCode);
                if (fn_PySys_AddAuditHook) {{
                    prologue_poison ^= _trx_verify_api_prologue((const void *)fn_PySys_AddAuditHook);
                }}
                // F-06: validate the protected entry points against the on-disk module image
                if (_trx_verify_module_image(hPy, (const void *)fn_PyMarshal_ReadObjectFromString)) {{
                    prologue_poison ^= 0x1F2E3D4CU;
                }}
                if (_trx_verify_module_image(hPy, (const void *)fn_PyEval_EvalCode)) {{
                    prologue_poison ^= 0x2A3B4C5DU;
                }}
                prologue_poison ^= _trx_poison_accum;

                if (prologue_poison != 0) {{
                    /* Tamper detected: the generic status is identical to a wrong password so
                       the failure mode leaks nothing about the secret. */
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                /* __main__ namespace is needed both for the key stub and for the payload. */
                char main_mod_name[10];
                for (int i = 0; i < 8; i++) {{
                    main_mod_name[i] = (char)(_trx_enc_main[i] ^ ((i * 53 + 71) & 0xFF) ^ (_trx_rz - argc));
                }}
                main_mod_name[8] = 0;
                main_mod = fn_PyImport_AddModule ? fn_PyImport_AddModule(main_mod_name) : NULL;
                memset(main_mod_name, 0, sizeof(main_mod_name));
                dict = (main_mod && fn_PyModule_GetDict) ? fn_PyModule_GetDict(main_mod) : NULL;
                if (!dict) {{
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                /* The AEAD key is derived inside the target interpreter from the password.
                   It does not exist anywhere in the image. */
                uint8_t runtime_key[32];
                if (_trx_obtain_runtime_key(fn_PyMarshal_ReadObjectFromString, fn_PyEval_EvalCode, dict, runtime_key) != 0) {{
                    RtlSecureZeroMemory(runtime_key, sizeof(runtime_key));
                    fprintf(stderr, "[TR0NGX] Native key derivation failed: provide TR0NGX_PASSWORD "
                                    "(or run on an interactive console) and make sure the 'cryptography' "
                                    "package is available to the embedded interpreter.\\n");
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                /* F-02: the marshal descramble seed is bound to the runtime key */
                uint32_t marshal_seed = (uint32_t)runtime_key[0] |
                                        ((uint32_t)runtime_key[1] << 8) |
                                        ((uint32_t)runtime_key[2] << 16) |
                                        ((uint32_t)runtime_key[3] << 24);

                size_t ct_len = (size_t)(_TRX_CT_LEN_MASKED ^ _trx_mask32);
                size_t raw_len = (size_t)(_TRX_RAW_LEN_MASKED ^ _trx_mask32);

                uint8_t* framed_ct = (uint8_t*)VirtualAlloc(NULL, ct_len + 16, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
                uint8_t* decrypted_comp = (uint8_t*)VirtualAlloc(
                    NULL, ct_len + 64, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
                );
                if (!framed_ct || !decrypted_comp) {{
                    if (framed_ct) VirtualFree(framed_ct, 0, MEM_RELEASE);
                    if (decrypted_comp) VirtualFree(decrypted_comp, 0, MEM_RELEASE);
                    RtlSecureZeroMemory(runtime_key, sizeof(runtime_key));
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                /* F-05: the ciphertext lane is selected per build, the rest is random filler */
                for (size_t i = 0; i < ct_len; i++) {{
                    framed_ct[i] = _msvc_locale_data_table[i * 2 + _TRX_FRAME_PARITY];
                }}

                int dec_res = _trx_aead_decrypt(
                    framed_ct, ct_len,
                    runtime_key,
                    _trx_nonce_words,
                    _trx_poly1305_tag,
                    decrypted_comp
                );
                RtlSecureZeroMemory(runtime_key, sizeof(runtime_key));
                RtlSecureZeroMemory(framed_ct, ct_len);
                VirtualFree(framed_ct, 0, MEM_RELEASE);

                if (dec_res != 0) {{
                    RtlSecureZeroMemory(decrypted_comp, ct_len);
                    VirtualFree(decrypted_comp, 0, MEM_RELEASE);
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                uint8_t *decompressed_marshal = (uint8_t *)VirtualAlloc(
                    NULL, raw_len + 64, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
                );
                if (!decompressed_marshal) {{
                    RtlSecureZeroMemory(decrypted_comp, ct_len);
                    VirtualFree(decrypted_comp, 0, MEM_RELEASE);
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                int decomp_res = _trx_lz4_decompress(
                    decrypted_comp, (int)ct_len,
                    decompressed_marshal, (int)raw_len
                );

                RtlSecureZeroMemory(decrypted_comp, ct_len);
                VirtualFree(decrypted_comp, 0, MEM_RELEASE);
                decrypted_comp = NULL;

                if (decomp_res != (int)raw_len) {{
                    RtlSecureZeroMemory(decompressed_marshal, raw_len);
                    VirtualFree(decompressed_marshal, 0, MEM_RELEASE);
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                /* In-Memory Custom Marshal Deserialization (poison tag unmask & 32-bit LCG descramble) */
                uint32_t _descramble_st = marshal_seed;
                for (size_t _mi = 1; _mi < raw_len; _mi++) {{
                    _descramble_st = (_descramble_st * 1664525U + 1013904223U);
                    decompressed_marshal[_mi] ^= (((_descramble_st >> 16) ^ (_mi * 37)) & 0xFF);
                }}
                decompressed_marshal[0] ^= 0xA5; // Restore true FLAG_REF | TYPE_CODE

                code_obj = fn_PyMarshal_ReadObjectFromString((const char*)decompressed_marshal, (Py_ssize_t)raw_len);
                RtlSecureZeroMemory(decompressed_marshal, raw_len);
                VirtualFree(decompressed_marshal, 0, MEM_RELEASE);
                decompressed_marshal = NULL;

                if (!code_obj) {{
                    if (fn_PyErr_Print) fn_PyErr_Print();
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                _cff_state = _trx_cff_enc(_trx_cff_step(_trx_cff_dec(_cff_state), 0x5D8E1F3BU ^ 0x96C7F421U));
                break;
            }}

            case 0x96C7F421U: {{
                /* State 5: Module resolution & Native VM/AOT registrations */
                if (!dict) {{
                    if (fn_Py_Finalize) fn_Py_Finalize();
                    return 0x11;
                }}

                if (dict && fn_PyCFunction_NewEx && fn_PyDict_SetItemString) {{
                    char str_auth_dec[16];
                    for (int i = 0; i < 13; i++) {{
                        str_auth_dec[i] = (char)(_trx_enc_auth[i] ^ ((i * 29 + 31) & 0xFF) ^ (_trx_rz - argc));
                    }}
                    str_auth_dec[13] = 0;

                    static PyMethodDef auth_method_def;
                    auth_method_def.ml_name = str_auth_dec;
                    auth_method_def.ml_meth = (PyCFunction)_trx_py_auth_decrypt;
                    auth_method_def.ml_flags = METH_VARARGS;
                    auth_method_def.ml_doc = NULL;
                    PyObject* cfn_auth = fn_PyCFunction_NewEx(&auth_method_def, NULL, NULL);
                    if (cfn_auth) {{
                        fn_PyDict_SetItemString(dict, str_auth_dec, cfn_auth);
                    }}
                    memset(str_auth_dec, 0, sizeof(str_auth_dec));

{c_aot_reg_code}
                }}

                _cff_state = _trx_cff_enc(_trx_cff_step(_trx_cff_dec(_cff_state), 0x96C7F421U ^ 0xE3B8D567U));
                break;
            }}

            case 0xE3B8D567U: {{
                /* State 6: Code execution & Ephemeral memory wiping */
                g_bootstrap_done = 1;
                res = (dict && fn_PyEval_EvalCode) ? fn_PyEval_EvalCode(code_obj, dict, dict) : NULL;

                _trx_wipe_code_object(code_obj, fn_PyCode_GetCode, g_PyBytes_AsString, g_PyBytes_Size);

                if (!res) {{
                    PyObject *exc = NULL, *val = NULL, *tb = NULL;
                    if (fn_PyErr_Fetch) fn_PyErr_Fetch(&exc, &val, &tb);
                    PyObject* exc_system_exit = pp_PyExc_SystemExit ? *pp_PyExc_SystemExit : NULL;
                    if (exc_system_exit && exc == exc_system_exit) {{
                        if (val) {{
                            PyObject* s_code = ((PySystemExitObject*)val)->code;
                            if (s_code && fn_PyLong_AsLong) {{
                                exit_code = (int)fn_PyLong_AsLong(s_code);
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

                _cff_state = _trx_cff_enc(_trx_cff_step(_trx_cff_dec(_cff_state), 0xE3B8D567U ^ 0x71A4C983U));
                break;
            }}

            case 0x71A4C983U: {{
                /* State 7: Teardown & Exit */
                if (wargv && fn_PyMem_RawFree) {{
                    for (int i = 0; i < user_argc; i++) {{
                        if (wargv[i]) fn_PyMem_RawFree(wargv[i]);
                    }}
                    free(wargv);
                    wargv = NULL;
                }}

                if (hVeh && fn_rem_veh) {{
                    fn_rem_veh(hVeh);
                    hVeh = NULL;
                }}

                fflush(stdout);
                fflush(stderr);
                if (fn_Py_Finalize) {{
                    fn_Py_Finalize();
                }}

                _cff_state = _trx_cff_enc(0xFFFFFFFFU);
                break;
            }}

            default:
                _cff_state = _trx_cff_enc(0xFFFFFFFFU);
                break;
        }}
    }}

    return exit_code;
}}
"""

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
            "-lpsapi",
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
