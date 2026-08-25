# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports repaired)
import sys
import random
import hashlib
import hmac
import secrets
import zlib
import bz2
import base64
import marshal

from . import config as _cfg
from .astpasses import ANTI_PYCDC
from .diagnostics import _log_stage_error
from .names import rd

# ═══════════════════════════════════════════════════════════════
# AUTHENTICATED STREAM ENCRYPTION (AEAD + PBKDF2-HMAC-SHA256)
# ═══════════════════════════════════════════════════════════════

def _derive_keys_argon2_or_pbkdf2(password: bytes, salt: bytes) -> tuple[bytes, bytes]:
    """Derive the single 256-bit AEAD key using Argon2id (RFC 9106 t=3 m=64MiB p=2)
    or PBKDF2-HMAC-SHA256 (600,000 rounds, OWASP 2024 minimum) as fallback."""
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        ke = Argon2id(salt=salt + b'__enc__', length=32, iterations=3, lanes=2, memory_cost=65536).derive(password)
        return ke, None
    except ImportError:
        ke = hashlib.pbkdf2_hmac('sha256', password, salt + b'__enc__', 600000, 32)
        return ke, None
    except Exception:
        ke = hashlib.pbkdf2_hmac('sha256', password, salt + b'__enc__', 600000, 32)
        return ke, None

def _derive_runtime_keys(salt: bytes):
    """Derive encryption key from salt + runtime environment (obfuscation-only mode).

    FIX (crypto P0): returns km=None so TRXH tags always use the SAME derivation
    formula as every emitted loader (sha256(ke + b'__mac__')). Previously this
    function derived km via pbkdf2 while loaders verified with sha256(ke|__mac__),
    producing artifacts that always failed HMAC verification when built on a
    machine without 'cryptography'.
    """
    import platform
    parts = []
    parts.append(sys.version[:5].encode())
    parts.append(platform.python_implementation().encode())
    parts.append(salt)
    parts.append(str(sys.maxsize).encode())
    parts.append(sys.byteorder.encode())
    combined = b''.join(parts)
    enc_k = hashlib.sha256(combined + b'__enc__').digest()
    ke = hashlib.pbkdf2_hmac('sha256', salt, enc_k, 50000, 32)
    return ke, None

def _auth_stream_encrypt(data: bytes, salt: bytes, ke: bytes, km: bytes = None):
    """AEAD v3 encryption. Primary path: ChaCha20-Poly1305 (cryptography lib).
    Returns (payload_with_magic, nonce). Payload format:
      b'TRXA' + salt(16) + nonce(12) + ciphertext||poly1305_tag
    Fallback when cryptography is unavailable: legacy HMAC-SHA256-CTR stream with
    explicit HMAC tag, format b'TRXH' + salt(16) + nonce(12) + tag(32) + ct.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        nonce = secrets.token_bytes(12)
        ct = ChaCha20Poly1305(ke).encrypt(nonce, data, salt)
        return b'TRXA' + salt + nonce + ct, nonce
    except ImportError:
        pass
    # Legacy fallback path (no cryptography available)
    nonce = secrets.token_bytes(12)
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(data):
        assert counter < 2**32, "CTR counter overflow: payload too large for 4-byte counter"
        block = hmac.new(ke, nonce + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
    keystream = keystream[:len(data)]
    ciphertext = bytes(a ^ b for a, b in zip(data, keystream))
    km_eff = km if km else hashlib.sha256(ke + b'__mac__').digest()
    tag = hmac.new(km_eff, salt + nonce + ciphertext, hashlib.sha256).digest()
    return b'TRXH' + salt + nonce + tag + ciphertext, nonce

def _select_armor_codec() -> tuple:
    """Per-build outer radix diversification.

    Source: PyObfuscate layered-encoder matrix (MIT, research note) - rotating the
    outermost codec among RFC4648 alphabets defeats fixed-alphabet YARA rules that
    key on a single b85 charset. Weighted toward b85 (25% size overhead vs b64's
    33%); b32 (+60%) and exotic radials stay opt-in via --base4096.
    """
    r = random.random()
    if r < 0.70:
        return 'b85encode', 'b85decode'
    if r < 0.90:
        return 'b64encode', 'b64decode'
    return 'b32encode', 'b32decode'


def _hw_fingerprint() -> bytes:
    """Machine fingerprint for optional env-key hardware lock.

    Source: bedrock-obfuscator --env-key fingerprint collector concept
    (Apache-2.0 + provisions, research note; independent implementation).
    NOTE: informational-strength binding - MAC/hostname/arch are spoofable.
    Wrong machine yields wrong keys -> authenticated decrypt failure (fail-closed).
    """
    try:
        import uuid as _uuid
        node = _uuid.getnode()
    except Exception:
        node = 0
    import platform as _plat
    parts = "|".join([
        str(node),
        _plat.system(),
        _plat.machine(),
        _plat.python_implementation(),
        f"{sys.version_info.major}.{sys.version_info.minor}",
    ])
    return hashlib.sha256(parts.encode('utf-8', 'replace')).digest()


def _multi_layer_encrypt(data: bytes, password: str = None):
    """Apply AEAD v3 encryption with Argon2id/PBKDF2 (if password provided) or environment-derived keys.

    Returns (armored_string, salt, armor_meta) where armor_meta describes the
    per-build outer codec + optional transforms so emitted loaders can mirror
    the exact decode chain:
      {'dec': 'b85decode'|'b64decode'|'b32decode', 'rev': bool, 'lzma': bool}
    Optional stages (research adoptions):
      - LZMA pre-encryption layer  (source: pyminifier compression.py lzma wrapper
        concept, GPL research note; stdlib lzma, safe for 3.10-3.14)
      - reversed payload storage   (source: PyObfuscate [::-1] trick, MIT)
      - randomized outer radix     (source: PyObfuscate codec matrix, MIT)
    """
    if password:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Password-protected builds require the 'cryptography' package for "
                "ChaCha20-Poly1305 AEAD. Install it with: pip install cryptography"
            )
    lzma_on = bool(_cfg._EngineState.lzma_layer)
    if lzma_on:
        try:
            import lzma as _lzma
            data = _lzma.compress(data, preset=9)
        except Exception:
            lzma_on = False
    data = zlib.compress(data, 6)
    salt = secrets.token_bytes(16)
    if _cfg._EngineState.env_key_lock and not password:
        # Hardware-lock blinding: stored salt is XOR-masked with the machine
        # fingerprint; loader re-derives the fingerprint and unmasks before KDF
        # (bedrock --env-key concept; wrong machine -> garbage keys -> auth fail).
        fp = _hw_fingerprint()
        salt_stored = bytes(salt[i] ^ fp[i] for i in range(16))
    else:
        salt_stored = salt
    if password:
        ke, km = _derive_keys_argon2_or_pbkdf2(password.encode('utf-8'), salt)
    else:
        ke, km = _derive_runtime_keys(salt)

    packed, nonce = _auth_stream_encrypt(data, salt, ke, km)
    if not password and _cfg._EngineState.env_key_lock:
        # Re-blind the transmitted salt so the artifact never carries it plain.
        # Keep magic prefix intact: [magic4][blinded salt16][nonce12][ciphertext...]
        packed = packed[:4] + salt_stored + nonce + packed[4 + 16 + 12:]
    payload_packed = bz2.compress(packed, 6)
    payload_packed = zlib.compress(payload_packed, 6)
    enc_name, dec_name = _select_armor_codec()
    armored = getattr(base64, enc_name)(payload_packed).decode('ascii')
    rev = bool(random.random() < 0.35)
    if rev:
        armored = armored[::-1]
    return armored, salt, {'dec': dec_name, 'rev': rev, 'lzma': lzma_on}


def _velimatix_compile(code_str):
    """Velimatix-style marshal compilation with FunctionType Anti-Funnel loader and dynamic token randomization (TRX-OBF-006/DEOB-014)."""
    b = marshal.dumps(compile(code_str, "<velimatix>", "exec"))
    b = zlib.compress(b, 6)
    b = base64.b64encode(b)

    v_matrix = rd('table')
    v_mod0 = rd('mod0')
    v_mod1 = rd('mod1')
    v_mod2 = rd('mod2')
    v_mod3 = rd('mod3')
    v_dict = rd('dict')
    v_k_ve = rd('key_ve')
    v_k_li = rd('key_li')
    v_k_matix = rd('key_matix')
    v_fnt = rd('fn_t')
    v_loop_k = rd('loop_k')
    v_loop_v = rd('loop_v')

    # Dynamic character pool matrix
    chars_pool = list("abcdefghijklmnopqrstuvwxyz0123456789_[]")
    random.shuffle(chars_pool)
    row_size = 5
    matrix = [chars_pool[i:i + row_size] for i in range(0, len(chars_pool), row_size)]

    def _get_path(word):
        coords = []
        for ch in word:
            for r_idx, row in enumerate(matrix):
                if ch in row:
                    coords.append(f"{v_matrix}[{r_idx}][{row.index(ch)}]")
                    break
        return "+".join(coords)

    path_marshal = _get_path("marshal")
    path_zlib = _get_path("zlib")
    path_base64 = _get_path("base64")
    path_types = _get_path("types")
    path_loads = _get_path("loads")
    path_decompress = _get_path("decompress")
    path_b64decode = _get_path("b64decode")

    return f"""
{v_matrix} = {matrix!r}
{v_mod0} = __import__({path_marshal})
{v_mod1} = __import__({path_zlib})
{v_mod2} = __import__({path_base64})
{v_mod3} = __import__({path_types})
{v_dict} = dict()
for {v_loop_k}, {v_loop_v} in vars({v_mod0}).items():
    if callable({v_loop_v}):
        if {v_loop_k} == {path_loads}: {v_dict}[{v_k_ve!r}] = {v_loop_v}
        else: {v_dict}[{v_loop_k}] = {v_loop_v}
for {v_loop_k}, {v_loop_v} in vars({v_mod1}).items():
    if callable({v_loop_v}):
        if {v_loop_k} == {path_decompress}: {v_dict}[{v_k_li!r}] = {v_loop_v}
        else: {v_dict}[{v_loop_k}] = {v_loop_v}
for {v_loop_k}, {v_loop_v} in vars({v_mod2}).items():
    if callable({v_loop_v}):
        if {v_loop_k} == {path_b64decode}: {v_dict}[{v_k_matix!r}] = {v_loop_v}
        else: {v_dict}[{v_loop_k}] = {v_loop_v}
globals().update({v_dict})
try:
    {v_fnt} = getattr({v_mod3}, "FunctionType")
    {v_fnt}({v_dict}[{v_k_ve!r}]({v_dict}[{v_k_li!r}]({v_dict}[{v_k_matix!r}]({b!r}))), globals())()
except Exception as _e:
    raise _e
"""


def _generate_strict_version_guard(target_ver_str: str) -> str:
    """
    Generates a multi-vector, anti-tamper Python runtime version & bytecode integrity enforcer.
    Verifies:
      1. sys.version_info tuple integrity, length, and immutable descriptor types (anti-monkeypatch)
      2. sys.hexversion bitmask verification against target major.minor
      3. importlib.util.MAGIC_NUMBER binary verification across Python 3.10-3.14
      4. C-level un-hookable Py_GetVersion() via ctypes
      5. Bytecode Opcode architecture-level invariant probing (dis.opmap / opcode.opmap)
      6. sys.implementation.version struct validation
    """
    if not target_ver_str or str(target_ver_str).lower() in ("off", "none", "n", "no"):
        return ""
    tgt = str(target_ver_str).strip()
    return f"""
def _enforce_strict_py_runtime():
    import sys, os
    _tgt = {tgt!r}
    _fail = False
    
    # 1. Structural tuple & immutable type check (detect monkeypatched sys.version_info)
    try:
        vi = sys.version_info
        if type(vi).__name__ != 'version_info' or getattr(type(vi), '__module__', '') != 'sys' or len(vi) != 5:
            _fail = True
        maj, min_ = vi[0], vi[1]
        tgt_parts = [int(p) for p in _tgt.split('.') if p.isdigit()]
        if len(tgt_parts) >= 1 and maj != tgt_parts[0]:
            _fail = True
        if len(tgt_parts) >= 2 and min_ != tgt_parts[1]:
            _fail = True
        if len(tgt_parts) >= 3 and vi[2] != tgt_parts[2]:
            _fail = True
    except Exception:
        _fail = True

    # 2. sys.hexversion bitmask verification
    try:
        hv = sys.hexversion
        if not isinstance(hv, int) or hv <= 0:
            _fail = True
        hv_maj = (hv >> 24) & 0xFF
        hv_min = (hv >> 16) & 0xFF
        if len(tgt_parts) >= 1 and hv_maj != tgt_parts[0]:
            _fail = True
        if len(tgt_parts) >= 2 and hv_min != tgt_parts[1]:
            _fail = True
    except Exception:
        _fail = True

    # 3. CPython Magic Number Invariant Check
    try:
        import importlib.util
        _magic_ranges = {{
            (3, 10): (3400, 3450),
            (3, 11): (3480, 3510),
            (3, 12): (3520, 3550),
            (3, 13): (3560, 3590),
            (3, 14): (3600, 3650)
        }}
        curr_magic = getattr(importlib.util, 'MAGIC_NUMBER', None)
        if curr_magic and len(curr_magic) >= 2 and (maj, min_) in _magic_ranges:
            m_val = int.from_bytes(curr_magic[:2], 'little')
            m_min, m_max = _magic_ranges[(maj, min_)]
            if not (m_min <= m_val <= m_max):
                _fail = True
    except Exception:
        pass

    # 4. Bytecode Opcode Architecture-Level Invariant Probe
    try:
        import opcode
        _opmap = getattr(opcode, 'opmap', {{}})
        if (maj, min_) == (3, 10):
            if not ('ROT_FOUR' in _opmap or 'GEN_START' in _opmap) or ('RESUME' in _opmap):
                _fail = True
        elif (maj, min_) == (3, 11):
            if ('RESUME' not in _opmap) or ('RETURN_CONST' in _opmap):
                _fail = True
        elif (maj, min_) == (3, 12):
            if ('RETURN_CONST' not in _opmap) or ('TO_BOOL' in _opmap):
                _fail = True
        elif (maj, min_) == (3, 13):
            if 'TO_BOOL' not in _opmap:
                _fail = True
    except Exception:
        pass

    # 5. C-Level Py_GetVersion Unhookable Native Pointer Verification
    try:
        import ctypes
        if hasattr(ctypes, 'pythonapi') and hasattr(ctypes.pythonapi, 'Py_GetVersion'):
            ctypes.pythonapi.Py_GetVersion.restype = ctypes.c_char_p
            c_ver = ctypes.pythonapi.Py_GetVersion()
            if c_ver:
                c_ver_str = c_ver.decode('utf-8', errors='ignore').split()[0]
                if not c_ver_str.startswith(_tgt):
                    _fail = True
    except Exception:
        pass

    # 6. sys.implementation verification
    try:
        impl = getattr(sys, 'implementation', None)
        if impl and hasattr(impl, 'version'):
            iv = impl.version
            if iv[0] != maj or iv[1] != min_:
                _fail = True
    except Exception:
        pass

    if _fail:
        _curr_str = sys.version.split()[0] if hasattr(sys, 'version') else 'Unknown'
        print(f"[-] STRICT RUNTIME INTEGRITY VIOLATION! Protected script strictly requires Python {{_tgt}} (Current: {{_curr_str}}). Execution aborted.", flush=True)
        os._exit(1)

_enforce_strict_py_runtime()
"""

def _double_compile(code_str, target_ver=None, password=None):
    """Double compile: Authenticated AEAD Payload INSIDE Velimatix loader with Dynamic Keys."""
    if target_ver is None:
        target_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    try:
        compiled = marshal.dumps(compile(code_str, "<tr0ngx>", "exec"))
    except SyntaxError as _syn_err:
        # FIX (crypto P0): previously returned plaintext SILENTLY - a silent crypto
        # bypass. Now the failure is tracked as a real stage error (respected by
        # --strict) and loudly warned so downstream packaging never mistakes an
        # unencrypted payload for a protected one.
        try:
            _log_stage_error("7_double_compile_syntax_error", _syn_err,
                             {"detail": "double-compile marshal failed; payload left unencrypted"})
        except Exception:
            pass
        print("[TR0NGX] [WARNING] double-compile failed at marshal stage; output is NOT encrypted.", flush=True)
        return code_str

    enc_b85, salt, _armor = _multi_layer_encrypt(compiled, password=password)
    del compiled
    _armor_dec = _armor['dec']
    _armor_rev = "[::-1]" if _armor['rev'] else ""
    # PERF (2026-08): embed the armored payload as 8 joined literal parts
    # instead of one giant literal - CPython parser arena shrinks drastically
    # on multi-hundred-MB payloads. Runtime join reproduces the identical
    # string, so the decode chain is unchanged.
    _pl_len = len(enc_b85)
    _pl_parts = 8
    _pl_names = [f"_pb{k}" for k in range(_pl_parts)]
    _parts_block = "".join(
        f"{_pl_names[k]}={enc_b85[(_pl_len * k) // _pl_parts:(_pl_len * (k + 1)) // _pl_parts]!r}\n"
        for k in range(_pl_parts)
    )
    _payload_expr = "''.join([" + ",".join(_pl_names) + "])"
    if _armor['lzma']:
        _lzma_step = "_s6 = lzma.decompress(_s5)" + chr(10) + "_s5 = _s6"
        _lzma_import = ", lzma"
    else:
        _lzma_step = ""
        _lzma_import = ""
    if not _lzma_step:
        # collapse: no extra stage
        _lzma_step = ""
    if _cfg._EngineState.env_key_lock and not password:
        # Env-key unmask snippet: loader re-derives the machine fingerprint and
        # unmasks the transmitted salt before KDF (bedrock --env-key concept).
        _envkey_unmask = chr(10).join([
            "    try:",
            "        import uuid as _trx_u",
            "        _trx_fp = hashlib.sha256(('|'.join([str(_trx_u.getnode()), platform.system(), platform.machine(), platform.python_implementation(), str(sys.version_info.major) + '.' + str(sys.version_info.minor)])).encode()).digest()",
            "        salt = bytes(salt[i] ^ _trx_fp[i] for i in range(16))",
            "    except Exception:",
            "        raise SystemExit(1)",
        ])
    else:
        _envkey_unmask = "# portable build: no hardware binding"

    if password:
        inner_loader = f"""
import base64, zlib, bz2, marshal, hashlib, hmac, types, sys, os, getpass, gc{_lzma_import}

sys.dont_write_bytecode = True
{_generate_strict_version_guard(target_ver)}

def _derive_key(password_bytes, salt):
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        return Argon2id(salt=salt + b'__enc__', length=32, iterations=3, lanes=2, memory_cost=65536).derive(password_bytes)
    except ImportError:
        return hashlib.pbkdf2_hmac('sha256', password_bytes, salt + b'__enc__', 600000, 32)

def _auth_decrypt(raw_bytes, pwd_str):
    magic = raw_bytes[:4]
    salt = raw_bytes[4:20]
    p_bytes = pwd_str.encode('utf-8')
    ke = _derive_key(p_bytes, salt)
    body = raw_bytes[20:]
    if magic == b'TRXA':
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        nonce = body[:12]
        ct = body[12:]
        try:
            return ChaCha20Poly1305(ke).decrypt(nonce, ct, salt)
        except Exception:
            print("[-] Authentication / Decryption Failed: Invalid password or tampered payload.", flush=True)
            sys.exit(1)
    elif magic == b'TRXH':
        nonce = body[:12]
        tag = body[12:44]
        ct = body[44:]
        km_eff = hashlib.sha256(ke + b'__mac__').digest()
        expected_tag = hmac.new(km_eff, salt + nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            print("[-] Authentication / Decryption Failed: Invalid password or tampered payload.", flush=True)
            sys.exit(1)
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ct):
            block = hmac.new(ke, nonce + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))
    print("[-] Unknown payload format.", flush=True)
    sys.exit(1)

_pwd = os.environ.get("TR0NGX_PASSWORD")
if not _pwd:
    _pwd = getpass.getpass("[TR0NGX] Enter decryption password: ")

{_parts_block}_payload_b85 = {_payload_expr}
_s1 = getattr(base64, {_armor_dec!r})(_payload_b85{_armor_rev})
_s2 = zlib.decompress(_s1)
_s3 = bz2.decompress(_s2)
_s4 = _auth_decrypt(_s3, _pwd)
_s5 = zlib.decompress(_s4){chr(10)}{_lzma_step}
exec(marshal.loads(_s5), globals(), globals())
# FIX (audit): previous scrub loop zeroed a bytearray COPY of immutable bytes -
# a no-op. Honest cleanup is reference deletion + gc; in-place wiping of
# immutable bytes is impossible from pure Python (documented limitation).
del _payload_b85, _s1, _s2, _s3, _s4, _s5, _pwd
gc.collect()
"""
    else:
        inner_loader = f"""
import base64, zlib, bz2, marshal, hashlib, hmac, types, sys, platform, gc{_lzma_import}

sys.dont_write_bytecode = True
{_generate_strict_version_guard(target_ver)}

def _derive_runtime_keys(salt):
    parts = []
    parts.append(sys.version[:5].encode())
    parts.append(platform.python_implementation().encode())
    parts.append(salt)
    parts.append(str(sys.maxsize).encode())
    parts.append(sys.byteorder.encode())
    combined = b''.join(parts)
    enc_k = hashlib.sha256(combined + b'__enc__').digest()
    mac_k = hashlib.sha256(combined + b'__mac__').digest()
    return enc_k, mac_k

def _auth_decrypt(raw_bytes):
    magic = raw_bytes[:4]
    salt = raw_bytes[4:20]
{_envkey_unmask}
    enc_k, mac_k = _derive_runtime_keys(salt)
    ke = hashlib.pbkdf2_hmac('sha256', salt, enc_k, 50000, 32)
    body = raw_bytes[20:]
    if magic == b'TRXA':
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        nonce = body[:12]
        ct = body[12:]
        return ChaCha20Poly1305(ke).decrypt(nonce, ct, salt)
    elif magic == b'TRXH':
        nonce = body[:12]
        tag = body[12:44]
        ct = body[44:]
        km_eff = hashlib.sha256(ke + b'__mac__').digest()
        expected_tag = hmac.new(km_eff, salt + nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise SystemExit(1)
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ct):
            block = hmac.new(ke, nonce + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))
    raise SystemExit(1)

{_parts_block}_payload_b85 = {_payload_expr}
_s1 = getattr(base64, {_armor_dec!r})(_payload_b85{_armor_rev})
_s2 = zlib.decompress(_s1)
_s3 = bz2.decompress(_s2)
_s4 = _auth_decrypt(_s3)
_s5 = zlib.decompress(_s4){chr(10)}{_lzma_step}
exec(marshal.loads(_s5), globals(), globals())
# FIX (audit): honest cleanup - see note in password variant above.
del _payload_b85, _s1, _s2, _s3, _s4, _s5
gc.collect()
"""

    return _velimatix_compile(ANTI_PYCDC + inner_loader)


