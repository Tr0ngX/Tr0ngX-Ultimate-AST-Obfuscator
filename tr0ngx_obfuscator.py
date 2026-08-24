import sys
import argparse
import ast
import copy
import glob
import random
import zlib
import marshal
import base64
import bz2
import re
import os
import hashlib
import hmac
import time
import struct
import secrets
import math
import tokenize
import io
import logging
import traceback
import threading
import string
import tempfile
import subprocess
from typing import Any, List, Dict, Optional, Tuple, Union

# Ensure Windows console supports Unicode / ANSI characters & Virtual Terminal Processing
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        hStdOut = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode)):
            mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(hStdOut, mode)
except Exception:
    pass

# ═══════════════════════════════════════════════════════════════
# DEPENDENCY RESOLUTION WITH DETERMINISTIC ZERO-CRASH FALLBACKS
# ═══════════════════════════════════════════════════════════════


class _EngineState:
    verbose_debug = False
    profile_mode = False
    strict_mode = False
    log_file_path = None
    cli_quiet_mode = False
    use_cjk_names = False
    use_homoglyph_names = False
    use_rare_unicode_names = False
    use_zalgo_marks = False
    use_hyperion = False
    use_camouflage = False
    use_fused_names = False
    use_exotic_pools = None
    used_nfkc = None
    encryption_password = None
    use_math_opaque = False
    use_dyn_strings = False
    lzma_layer = False
    env_key_lock = False
    verify_mode = False
    use_anti_dump = False
    use_vm_obf = False
    custom_seed = None
    max_output_size = None

_HAS_PYSTYLE = False
_HAS_PSUTIL = False

try:
    import pystyle
    _HAS_PYSTYLE = True
except ImportError:
    _HAS_PYSTYLE = False

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

try:
    from pystyle import Col, Colors, Colorate, Write, Add, Center, Box
except ImportError:
    # Lớp giả lập pystyle dự phòng nếu môi trường không có mạng/pip lỗi
    class _FallbackCol:
        dark_gray = "\033[90m"
        light_gray = "\033[37m"
        green = "\033[92m"
        yellow = "\033[93m"
        pink = "\033[95m"
        blue = "\033[94m"
        red = "\033[91m"
        purple = "\033[35m"
        cyan = "\033[96m"
        white = "\033[97m"
        black = "\033[30m"
        reset = "\033[0m"

        @staticmethod
        def Symbol(symbol, col1="", col2=""):
            return f"[{symbol}]"

    class _FallbackColors:
        @staticmethod
        def DynamicMIX(cols):
            return cols
        @staticmethod
        def StaticMIX(cols):
            return cols[0] if cols else ""

    class _FallbackColorate:
        @staticmethod
        def Diagonal(col, text):
            return str(text)
        @staticmethod
        def Horizontal(col, text):
            return str(text)
        @staticmethod
        def Vertical(col, text):
            return str(text)

    class _FallbackWrite:
        @staticmethod
        def Print(text, col=None, interval=0):
            print(text, end="", flush=True)
        @staticmethod
        def Input(text, col=None, interval=0):
            return input(text)

    class _FallbackAdd:
        @staticmethod
        def Add(text1, text2, center=True):
            return f"{text1}\n{text2}"

    class _FallbackCenter:
        @staticmethod
        def XCenter(text):
            return str(text)
        @staticmethod
        def YCenter(text):
            return str(text)

    class _FallbackBox:
        @staticmethod
        def DoubleCube(text):
            return str(text)

    Col = _FallbackCol
    Colors = _FallbackColors
    Colorate = _FallbackColorate
    Write = _FallbackWrite
    Add = _FallbackAdd
    Center = _FallbackCenter
    Box = _FallbackBox

from getpass import getpass

if sys.version_info < (3, 10):
    print("Install Python Version = 3.10 or > 3.10 To Use This Code")
    sys.exit(1)

__import__('sys').setrecursionlimit(15000)

# ═══════════════════════════════════════════════════════════════
# UNIQUE NAME GENERATORS - COLLISION-FREE
# ═══════════════════════════════════════════════════════════════

_used_names = set()
_used_names_lock = threading.RLock()
_obf_execution_lock = threading.Lock()
# Cross-module frozen rename map for batch mode (--shared-symbols).
# Design source: Opy global word-list consistency model (Apache-2.0 research
# note), hardened into a two-phase frozen map: phase A (single-threaded) parses
# every batch target and pre-assigns ONE deterministic new name per symbol that
# is imported by another batch file; phase B (per-file pipeline) consumes the
# immutable map. Fixes the cross-package NameError class where each file's
# independent renamer broke `from sibling import func` contracts.
_FROZEN_NAME_MAP: Dict[str, str] = {}
# Seeded identifier RNG (--seed): when a seed is provided the ASCII fallback
# stream becomes reproducible instead of secrets-driven (audit fix for the
# "deterministic build" contract). Hostile Unicode pools still draw from
# secrets/OS entropy - full byte-reproducibility of those paths is documented
# as best-effort, not guaranteed.
_SEEDED_RNG = None


def _trx_rand(n: int) -> int:
    """Seeding-aware randbelow: honors --seed when set (reproducible identifier
    stream), falls back to OS entropy otherwise."""
    if _SEEDED_RNG is not None:
        return _SEEDED_RNG.randrange(n)
    return secrets.randbelow(n)


def _trx_choice(seq):
    if _SEEDED_RNG is not None:
        return _SEEDED_RNG.choice(seq)
    return secrets.choice(seq)


def _module_key_from_rel(rel: str) -> str:
    k = rel.replace("\\", "/")
    low = k.lower()
    if low.endswith(".pyw"):
        k = k[:-4]
    elif low.endswith(".py"):
        k = k[:-3]
    if k.endswith("/__init__"):
        k = k[: -len("/__init__")]
    return k.replace("/", ".")


def _collect_shared_symbol_map(targets: list, seed=None) -> Dict[str, str]:
    """Phase A of the batch shared-symbol feature: parse all targets, detect
    symbols imported across module boundaries, assign one deterministic new
    name per shared symbol so every consuming file agrees on the rename."""
    module_exports: Dict[str, set] = {}
    module_imports: Dict[str, set] = {}

    for t in targets:
        src = t.get("src")
        rel = t.get("rel") or os.path.basename(src)
        mkey = _module_key_from_rel(rel)
        try:
            with open(src, "r", encoding="utf-8", errors="replace") as fh:
                tree = ast.parse(fh.read())
        except Exception:
            continue
        exports = set()
        imports_here = set()
        parent_key = mkey.rsplit(".", 1)[0] if "." in mkey else ""
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                exports.add(node.name)
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and not tgt.id.startswith("__"):
                        exports.add(tgt.id)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imports_here.add((node.module, alias.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports_here.add((alias.name, None))
        module_exports[mkey] = exports
        module_imports[mkey] = imports_here

    salt = str(seed).encode() if seed is not None else b"TRX_SHARED"
    frozen: Dict[str, str] = {}
    for mkey, imports in module_imports.items():
        for imod, name in imports:
            candidates = [imod]
            if module_exports.get(imod) is None and "." in mkey:
                base = mkey.rsplit(".", 1)[0]
                candidates.append(f"{base}.{imod}")
                candidates.append(base + "." + imod.replace(".", "/"))
            resolved = next((c for c in candidates if c in module_exports), None)
            if not resolved or name is None or name == "*":
                continue
            if name in module_exports[resolved] and name not in frozen and not name.startswith("__"):
                digest = hashlib.sha256(salt + b"|" + name.encode()).hexdigest()[:12]
                frozen[name] = "_sx" + digest
    return frozen


def _rd():
    alphabet = string.ascii_lowercase
    with _used_names_lock:
        while True:
            k = _trx_rand(5) + 6
            name = "".join(_trx_choice(alphabet) for _ in range(k))
            if name not in _used_names:
                _used_names.add(name)
                return name

_EngineState.use_fused_names = False

def _gen_fused_name(scope='general'):
    """Tạo tên biến lai ma trận (Hybrid Blended Identifier):
       - 'state_machine': Homoglyphs (Cyrillic a, e, o, s, p lookalikes)
       - 'biopaque': Rare Unicode Kangxi radicals (𪚥, 龘, 鱻, 麤, 靐)
       - 'globals': PyCool CJK Ideographs
       - 'general': Luân phiên đa hình ngẫu nhiên
    """
    _init_rare_chars()
    if scope == 'state_machine':
        return _gen_homoglyph_name(_trx_rand(5) + 6)
    elif scope == 'biopaque':
        return _gen_rare_unicode_name(_trx_rand(3) + 3)
    elif scope == 'globals':
        return _gen_cjk_name(_trx_rand(5) + 6)
    else:
        picker = _trx_choice(['homo', 'rare', 'cjk', 'zalgo', 'invis'])
        if picker == 'homo':
            return _gen_homoglyph_name(_trx_rand(4) + 5)
        elif picker == 'rare':
            return _gen_rare_unicode_name(_trx_rand(3) + 3)
        elif picker == 'cjk':
            return _gen_cjk_name(_trx_rand(3) + 6)
        elif picker == 'zalgo':
            return _gen_zalgo_name(1, _trx_rand(21) + 25)
        else:
            return _gen_homoglyph_name(_trx_rand(5) + 6)

def rd(scope='general'):
    with _used_names_lock:
        if _EngineState.use_exotic_pools and _trx_rand(100) < 70:
            _n = _gen_exotic_name(scope)
            if _n:
                return _n
        if _EngineState.use_zalgo_marks:
            return _gen_zalgo_name()
        if _EngineState.use_fused_names:
            return _gen_fused_name(scope)
        if _EngineState.use_rare_unicode_names:
            return _gen_rare_unicode_name()
        if _EngineState.use_homoglyph_names:
            return _gen_homoglyph_name()
        if _EngineState.use_cjk_names:
            return _gen_cjk_name()
        alphabet = string.ascii_lowercase + string.digits
        while True:
            k = _trx_rand(4) + 5
            name = "_" + "".join(_trx_choice(alphabet) for _ in range(k))
            if name not in _used_names:
                _used_names.add(name)
                return name

def randomint():
    return str(_trx_rand(900000) + 100000)

def _gen_invisible_name(length=6):
    """Valid Python 3 invisible/combining mark variable names (XID_Continue)"""
    combining = [chr(i) for i in range(0x0300, 0x034F)]
    while True:
        name = '_' + ''.join(random.choices(combining, k=length))
        if name.isidentifier() and name not in _used_names:
            _used_names.add(name)
            return name

def _gen_cyrillic_name(length=10):
    """Cyrillic homoglyph names - looks like latin but isn't"""
    chars = ['О', 'о', 'А', 'а', 'Е', 'е', 'І', 'і', 'Ѕ', 'ѕ', 'Т', 'Р', 'р', 'Н', 'К', 'М', 'В', 'х', 'у']
    while True:
        name = ''.join(random.choices(chars, k=length))
        if name not in _used_names:
            _used_names.add(name)
            return name

def _gen_mixed_name():
    """Mix of underscores, numbers, and confusing chars"""
    parts = []
    for _ in range(random.randint(3, 6)):
        choice = random.randint(1, 4)
        if choice == 1:
            parts.append('_' * random.randint(1, 3))
        elif choice == 2:
            parts.append(str(random.randint(0, 99)))
        elif choice == 3:
            parts.append(random.choice(['O', 'l', 'I', 'o']))
        else:
            parts.append(random.choice(['ᅠ', 'ㅤ']))
    while True:
        name = '_' + ''.join(parts) + str(random.randint(0, 999))
        if name not in _used_names:
            _used_names.add(name)
            return name

def _get_forbidden_system_prefixes():
    prefixes = ['/etc', '/usr', '/bin', '/sbin', '/lib', '/lib64', '/boot', '/root', '/dev', '/proc', '/sys']
    if os.name == 'nt':
        sys_root = os.getenv('SystemRoot', 'C:\\Windows')
        prefixes.extend([
            sys_root,
            os.path.join(sys_root, 'System32'),
            os.getenv('ProgramFiles', 'C:\\Program Files'),
            os.getenv('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
            os.getenv('ProgramData', 'C:\\ProgramData'),
            'C:\\Windows', 'C:\\Program Files', 'C:\\Program Files (x86)'
        ])
    return [os.path.normpath(p).lower() for p in prefixes]

_FORBIDDEN_SYSTEM_PREFIXES = _get_forbidden_system_prefixes()

def _validate_and_sanitize_output_path(filepath: str, input_file: str = None) -> str:
    """Strictly canonicalize and validate output paths to prevent arbitrary path traversal, system directory clobbering, and dangerous symlink attacks (TRX-AST-401/402)."""
    norm_path = os.path.normpath(os.path.abspath(filepath))
    real_path = os.path.realpath(norm_path)

    # Check symlinks
    if os.path.islink(norm_path) or os.path.islink(real_path):
        err_str = f" [SECURITY ALERT] Refusing to write to symbolic link target: {filepath}"
        _v(_gradient_text(err_str, (255, 40, 40), (255, 120, 40)))
        sys.exit(1)

    # Check system directory blacklist
    for prefix in _FORBIDDEN_SYSTEM_PREFIXES:
        norm_prefix = os.path.normpath(prefix).lower()
        if real_path.lower().startswith(norm_prefix):
            err_str = f" [SECURITY ALERT] Refusing to write to protected system path: {filepath}"
            _v(_gradient_text(err_str, (255, 40, 40), (255, 120, 40)))
            sys.exit(1)

    # Check input file clobbering without explicit overwrite
    if input_file:
        real_input = os.path.realpath(os.path.abspath(input_file))
        if real_path.lower() == real_input.lower():
            err_str = f" [SECURITY ALERT] Refusing to overwrite input source file directly: {filepath}. Please specify a distinct output path."
            _v(_gradient_text(err_str, (255, 40, 40), (255, 120, 40)))
            sys.exit(1)

    return real_path

def _validate_input_source(code: str, max_size_mb: int = 25, max_ast_depth: int = 500):
    """Validate input source file to prevent memory exhaustion DoS and AST recursion crashes (TRX-AST-404/405)."""
    if not code or not code.strip():
        raise ValueError("Input source file is empty (0 bytes). Nothing to obfuscate.")
    raw_bytes_len = len(code.encode('utf-8', errors='ignore'))
    if raw_bytes_len > max_size_mb * 1024 * 1024:
        raise ValueError(f"Input source size ({raw_bytes_len:,} bytes) exceeds maximum security limit of {max_size_mb} MB.")
    
    tree = ast.parse(code)
    
    def _calc_depth(node, cur=0):
        if cur > max_ast_depth:
            raise RecursionError(f"AST recursion depth exceeded {max_ast_depth} levels. Script is too deeply nested for safe transformation.")
        depths = [_calc_depth(child, cur + 1) for child in ast.iter_child_nodes(node)]
        return max(depths, default=cur)
    
    _calc_depth(tree)

def _safe_atomic_write(filepath: str, content: str, input_file: str = None):
    """Safely write content to filepath atomically, strictly refusing symlinks and protected system paths."""
    filepath = _validate_and_sanitize_output_path(filepath, input_file=input_file)

    out_dir = os.path.dirname(filepath)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(dir=out_dir if out_dir else None, prefix=".tr0ngx_tmp_")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8", errors="replace") as f:
            f.write(str(content))
        os.replace(temp_path, filepath)
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise

# ═══════════════════════════════════════════════════════════════
# CJK / PYCOOL CHINESE IDENTIFIER & JUNK DOCSTRING GENERATOR
# ═══════════════════════════════════════════════════════════════

_CJK_CHARS = [chr(i) for i in range(0x4e00, 0x9fa5)]
_EngineState.use_cjk_names = False

def _gen_cjk_name(min_len=6, max_len=12):
    """Generate valid Python 3 CJK Ideograph identifiers (PyCool style)"""
    while True:
        name = ''.join(random.choices(_CJK_CHARS, k=random.randint(min_len, max_len)))
        if name.isidentifier() and name not in _used_names:
            _used_names.add(name)
            return name

# ═══════════════════════════════════════════════════════════════
# HOMOGLYPH OBFUSCATION - CYRILLIC / GREEK LOOKALIKE NAMES
# ═══════════════════════════════════════════════════════════════

_EngineState.use_homoglyph_names = False

# Characters that look identical to ASCII but are different Unicode codepoints
_HOMOGLYPH_MAP = {
    'a': '\u0430', 'c': '\u0441', 'e': '\u0435', 'o': '\u043e',
    'p': '\u0440', 'x': '\u0445', 'y': '\u0443', 's': '\u0455',
    'i': '\u0456', 'j': '\u0458', 'h': '\u04bb', 'k': '\u03ba',
    'A': '\u0410', 'B': '\u0412', 'C': '\u0421', 'E': '\u0415',
    'H': '\u041d', 'K': '\u041a', 'M': '\u041c', 'O': '\u041e',
    'P': '\u0420', 'T': '\u0422', 'X': '\u0425', 'S': '\u0405',
}
_HOMOGLYPH_BASES = list('aAcCeEoOpPxXyYsShHkKMBTI')

def _gen_homoglyph_name(length=10):
    """Generate names mixing ASCII and Cyrillic/Greek homoglyphs — visually confusing"""
    while True:
        parts = []
        for _ in range(length):
            ch = random.choice(_HOMOGLYPH_BASES)
            if random.random() < 0.5 and ch.lower() in _HOMOGLYPH_MAP:
                parts.append(_HOMOGLYPH_MAP.get(ch.lower(), ch) if ch.islower() else _HOMOGLYPH_MAP.get(ch, ch))
            else:
                parts.append(ch)
        name = ''.join(parts)
        if name.isidentifier() and name not in _used_names:
            _used_names.add(name)
            return name

# ═══════════════════════════════════════════════════════════════
# RARE UNICODE OBFUSCATION - CJK EXTENSION B / KANGXI / RARE
# ═══════════════════════════════════════════════════════════════

_EngineState.use_rare_unicode_names = False

# CJK Extension B (U+20000-U+2A6DF) — very rare, valid Python identifiers
# Kangxi Radicals (U+2F00-U+2FDF) — valid identifiers
# CJK Compatibility Ideographs (U+F900-U+FAFF)

class _RareChars:
    pool = None

def _init_rare_chars():
    if _RareChars.pool is not None:
        return
    pool = []
    # Pre-computed valid identifier ranges (verified with Python 3.10+)
    # Using batch range iteration instead of per-character isidentifier() calls
    _valid_ranges = [
        (0x13000, 0x1342E),   # Egyptian Hieroglyphs
        (0x12000, 0x123FF),   # Cuneiform
        (0xA000, 0xA48C),     # Yi Syllables
        (0x2F00, 0x2FD6),     # Kangxi Radicals
    ]
    for start, end in _valid_ranges:
        pool.extend(chr(i) for i in range(start, end))

    # Tangut - sample from large range
    tangut_sample = random.sample(range(0x17000, 0x187EC), min(1500, 0x187EC - 0x17000))
    pool.extend(chr(i) for i in tangut_sample)

    # CJK Extension B - sample
    ext_b_start = 0x20000
    ext_b_sample = random.sample(range(ext_b_start, ext_b_start + 5000), min(2500, 5000))
    pool.extend(chr(i) for i in ext_b_sample)

    # Complex ideographs
    for c in '龘鱻麤靐飍灥厵叒猋㵘𪚥𠜎𡚥𨰻𩙙𠀀':
        pool.append(c)

    # Filter once at the end (batch is faster than per-char)
    _RareChars.pool = [c for c in pool if c.isidentifier()]

def _gen_rare_unicode_name(min_len=3, max_len=6):
    """Generate names using Egyptian Hieroglyphs / Cuneiform / Tangut / CJK Ext-B chars"""
    _init_rare_chars()
    while True:
        name = ''.join(random.choices(_RareChars.pool, k=random.randint(min_len, max_len)))
        if name.isidentifier() and name not in _used_names:
            _used_names.add(name)
            return name

# ═══════════════════════════════════════════════════════════════
# EXTREME ZALGO COMBINING MARKS ENGINE (FULL DIACRITICS CASCADE)
# ═══════════════════════════════════════════════════════════════

_COMBINING_MARKS_VALID = None

def _init_combining_marks():
    global _COMBINING_MARKS_VALID
    if _COMBINING_MARKS_VALID is not None:
        return
    import unicodedata
    pool = []
    # Ranges of Combining Diacritical Marks in Unicode standard
    _ranges = [
        (0x0300, 0x036F),  # Combining Diacritical Marks (U+0300..U+036F)
        (0x1AB0, 0x1AFF),  # Combining Diacritical Marks Extended
        (0x1DC0, 0x1DFF),  # Combining Diacritical Marks Supplement
        (0x20D0, 0x20FF),  # Combining Diacritical Marks for Symbols
        (0xFE20, 0xFE2F),  # Combining Half Marks
    ]
    for start, end in _ranges:
        for cp in range(start, end + 1):
            ch = chr(cp)
            if unicodedata.category(ch) in ('Mn', 'Mc'):
                pool.append(ch)
    _COMBINING_MARKS_VALID = pool

def _gen_zalgo_name(base_len=1, mark_intensity=45):
    """Tạo tên biến hợp lệ trong Python chứa hàng chục dấu combining diacritical marks (Z͑͗͑͗...)
       gây quá tải rendering engine của IDE / Decompiler (DirectWrite, HarfBuzz, Scintilla, FreeType).
    """
    import unicodedata
    _init_combining_marks()
    _bases = ['Z', 'X', 'V', 'T', 'O', 'I', 'z', 'x', 'v', 't', 'o', 'i', 'a', 'e', 's', 'c']
    while True:
        parts = []
        for _ in range(base_len):
            base_ch = random.choice(_bases)
            marks = ''.join(random.choices(_COMBINING_MARKS_VALID, k=mark_intensity))
            parts.append(base_ch + marks)
        name = unicodedata.normalize('NFKC', ''.join(parts))
        if name.isidentifier() and name not in _used_names:
            _used_names.add(name)
            return name

def _gen_zalgo_cascade_docstring(paragraphs=1, lines_per_p=6, chars_per_line=12, marks_per_char=50):
    """Tạo khối docstring/comment cascade cực đại chứa hàng nghìn combining marks chồng chéo."""
    _init_combining_marks()
    tq = chr(39) * 3
    _bases = list("ZALGO_CHAOS_ENGINE_TR0NGX_MATRIX_AST_OBFUSCATOR_VOID_KYRIE_ELEISON")
    res_paragraphs = []
    for _ in range(paragraphs):
        lines = []
        for _ in range(lines_per_p):
            line_chars = []
            for _ in range(chars_per_line):
                b = random.choice(_bases)
                m = ''.join(random.choices(_COMBINING_MARKS_VALID, k=marks_per_char))
                line_chars.append(b + m)
            lines.append(''.join(line_chars))
        res_paragraphs.append(f"{tq}\n" + '\n'.join(lines) + f"\n{tq}")
    return '\n\n'.join(res_paragraphs)

def _gen_zalgo_chars(text, intensity=8):
    """Stack 4 tiers of combining diacritical marks onto characters (Extreme Zalgo Glitch)"""
    _init_combining_marks()
    res = []
    for c in text:
        res.append(c + ''.join(random.choices(_COMBINING_MARKS_VALID, k=intensity)))
    return ''.join(res)

def _gen_cjk_docstring(paragraphs=2, lines_per_p=4, chars_per_line=32):
    """Generate multi-script Ancient + CJK + Zalgo + BiDi + Zero-Width chaos docstrings"""
    _init_rare_chars()
    tq = chr(39) * 3
    bidi_ctrls = [chr(0x202E), chr(0x202D), chr(0x202C), chr(0x2066), chr(0x2067)]
    zw_chars = [chr(0x200B), chr(0x200C), chr(0x200D), chr(0x2060)]
    res = []
    for _ in range(paragraphs):
        lines = []
        for _ in range(lines_per_p):
            # Mix ancient hieroglyphs, cuneiform, tangut with CJK chars
            raw_chars = ''.join(random.choices(_RareChars.pool, k=chars_per_line))
            # Extreme Zalgo Glitch stacking
            raw_chars = _gen_zalgo_chars(raw_chars, intensity=random.randint(4, 10))
            # BiDi Direction Inversion & Zero-Width phantom injection
            parts = []
            for chunk in [raw_chars[i:i+8] for i in range(0, len(raw_chars), 8)]:
                parts.append(random.choice(bidi_ctrls) + chunk + random.choice(zw_chars))
            raw_chars = ''.join(parts) + chr(0x202C)
            lines.append(raw_chars)
        res.append(tq + '\n' + '\n'.join(lines) + '\n' + tq)
    return '\n\n'.join(res)

def _gen_tr0ngx_header():
    """Generate clean Cyberpunk / Matrix ASCII Banner Header without emojis/icons."""
    return r"""# ╔═══════════════════════════════════════════════════════════════════════════════════╗
# ║  ████████╗██████╗  ██████╗ ███╗   ██╗ ██████╗ ██╗  ██╗                            ║
# ║  ╚══██╔══╝██╔══██╗██╔═████╗████╗  ██║██╔════╝ ╚██╗██╔╝                            ║
# ║     ██║   ██████╔╝██║██╔██║██╔██╗ ██║██║  ███╗ ╚███╔╝                             ║
# ║     ██║   ██╔══██╗████╔╝██║██║╚██╗██║██║   ██║ ██╔██╗                             ║
# ║     ██║   ██║  ██║╚██████╔╝██║ ╚████║╚██████╔╝██╔╝ ██╗                            ║
# ║     ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝                            ║
# ╠═══════════════════════════════════════════════════════════════════════════════════╣
# ║  Make by Tr0ngX  |  GitHub: https://github.com/Tr0ngX                             ║
# ║  Notice: Do not attempt to reverse engineer. You will only find darkness!         ║
# ╚═══════════════════════════════════════════════════════════════════════════════════╝
"""

_EMBEDDED_5S_INTRO_B85 = 'c-jC+K)1g_T4*^jL0KkKS@eI0fB+v&e}DiG00_JP|NV$IqW}GW_upV={QxKc0000000007%c8Bh8(&Q_G}{_mYz<RtFx%PPKIe1OM|r7TO^ep9?g((Tk>~&b00+@X0001Qs6<c+02LH~q>=!lDkxNdkO-=g000!ELIk8$d;s53K}w|*Dydc2+QO+8v8}*nNhmY}K%fCu0ZVD2La0UC98yx+u>ne(7%B9v00poZ2qXn407W_|)Mx+z8VXW?06J2uK<*MqAPf+i1PBO?L8h3EMhzH~-l_=*geDa=BTR!p000dDVgLl0N=+)Lz$OIK08C5*Vqi=F0F%`vRK-mhGe{3fi1ji7kN_Gq#L&@%)Tt(VnpB_w$Y=ltnlc(_10VoWN|HZQ)g>SR4FRAs000JnH2hVzt$$zjQEj&QN--eRVx*Ez1dIMYKY_XYj>t>!Mg{Ap2lYrt_Wj?F;r?*Mf8oO=tL|&qoyvaYE}!Vd82^gf{D12S{~zJCzty3NBqy>jz<di6)W7*Yl)nA*(9iL5S)kNmgu{cEIRg=FOdLo4;%UUa9j<lAzK}Eh`f868t>P*SBDWFIql9NFIF0N^Wa6Y{areA^b^q7AfrZ*Fq-1e?p)0Y!ww`~pvgN^pGsf8gA@9pP;jB%v>(@QZFEG7mU6TyLVVMI1mllT?(THMXU*}Lr-`802?ft4dEapyJME1kP_}rI_H9JV?L3Q=q+aGRNW@ZLtm}X{XW@cfTh8dZTIMp7%)%I@FcUKfs&U4z&18__9voOu8cZ1|=8tvoLTmd4$k*N7NwR`5O`#-O@*UV!~!H3V*AGdz@&cJ^@y|--5#j&B&I_){I%!Xu<0&_bWnn|@sKK`HA&r`2z2`&Vb(b3ZSBdvY<o-RAryqT+9v2-XUbcD0|Ru#u3jYzqeVazgSH7JmWP*K{H4(*nCd+3&InD2Ss7jc`lhpPy@>+R}s%!}Jg^E$*3KPY1Px^Ug`#inQT`Sre3c9`>uzvXAbH~CvKGLCDVqC+gFr)}7V+|D48zom6AW2*~|envbOl3B~vL+!q)95(YmpPfcN4~A^`!qPA9YoJ=D`a4(sfg}8ZBc5+c=A`<05FbbrTTt}$u0FEI$*)Ru!c-B*rT)IRdRvl5l{xzQ!)t5_9d#;@8I^=G^yx=v#IVgtfonL)1?X|o;0-VKy9SC9tB?~iiGw5R#&;r4A$Jzc5|Qu5??6(L{)h=reVmZKppm@agBzzgF3`OHnZ{`fZ;%#cDq>04jD2SKa^vs!`aEUY+57EhlA`C$p&gDR52lVhbl|G=yExSJ|F{T8x9tRpey#poK=O3k-(knBUvDkK=g#Z*`7h#o4L>Bj-F(RmLC24e0Fcs_p)Oo;OsUN07CyEwtEcg2A4QjPXT4o&=`8C@*r689Ul(<E%8&kf8Ox3w_HA{L%sJW;<3q<f^lbj(5v%y1;7HEl^CrR?bL)I2+;Luoq*YI0t@Zs4huz-^8y4I1uJ1KIgmEXVbbM^K88EKWSmx$z+)Dj%HOUsjspLs^#6~W=QM7%k{4F+paM9X^V{MbT!kB2(WYF6Aym>m*(;{Xw3pVqGs*s6bpOiMG*S7y|XST-X{9;c!9o%lXap}4F;nNy68tInxKQtB{4em%pzAK?{;L{KhNUQ6jKxi57^X%U~<hNlG4m^2m`d_t(H_!6?`}udb$4wvNUcLRZpPKgd@7&fcf2()r)6(l(@8{!VZ%v)>cgrkH?M$WLFKAL<GArQ#kLU>*`TyR&+;9mS^`9}@o-A74zZd(rZqcvEvpN4H<Hp-Go6nvOCk*zvVX-~1+oyb;{STtwb8l^dBgSUl+IY9AK-bDbGPZ5!b;pHx!#|9!mwkB0jiTLONMQc{=*YxDrK#(fLR+0bA@*r~JLJrD?-IqArJ0$LGG}^lU<nlI>!w}1m0q!GKi#Qiwwlok1GJVA=kcfQBMIE?`|C@B{%W34B)?rs*UmMb`(^LG!nu?)eDv}2;@JELhDils>~znpIpxw=T$k(whj-_fWxgFaQ?nYgiaGi;W=E`f>v!Ougm`<YM-z98?u=&6pXUnmwNE;Bw#^}dieDq)qsvR@qkJ{nD%?S}Ds60gQM0DM1MS+_2n%)3CvSJgpB)WNa!)Ixw>lDpM#mEosRq=bh&ay>&JV7mo7+JnHUxcVjWgq!lI?C=@EfqxZN+=+j_H_5m>HRnvyOVL{97w;^@hCaNrn!wk9h(|-1UYKHQAwLV$ZjREZbW8j7FW?AFlO`KBsxTnUg!D%FCTYo@Ab+yW@A}BqG_(G{+&Xdvt^^ft>jE_P?$iz&|S8UYx#YWcHuTWg_EQTSYv9`DpCAnHS^fp#vEE(<k`Wi~=#Nullj)*e=2j1lH$`d8OU7_xEK6eN0*y=*#7^=0!LL3uVuE<G-4m;e|A-q4r}oW|I!!Z+*9nE_0cie=g%&i<_w)$t8~;YvK;m&c3Cst{K<>-H<&73|w5~uU>{@^%|P^e%3;_V{d6@GNly>ngT}+F1tlua$Pq&yUCN8E$A_kXgl`^7s$)o;?=6J21k*YZs$uK@WW&bGD*DpbGdkHb7^DD2;FLv6cHd~PXA4xc780NHGbYFoQCwy-)NLd29589o_b7kTr`PGZf8Oi(ARUOrAZVtepCdC{fm!1r$3W8Y&6%ejWp@w4?XSaWLIiOu|{*97@S5*SoP~SfQWI8$q3d^G6ac3-yb}?BJBH4J#c>AIJ4+loFTS|fN0%F+DmEeYkIIGPIAICzqKz(1h7{Kv~j1VbgKE#Xl<3*ei)P;pxPQRUR}0Nb6@HS8k*g1ZLkIxKR@zu;MUS@-Kyj}C1THp7vHo&B1`UHyH<WXI{na<+5XM=-J7?|+~3YUL#e@Tcejt1IdtT0n+xI4gC(}0<Zj6i_kaj-!q{Ylc)7rleZvreTpNVu0g;E>4;Or)U)hlB$v%^u-3@30J67tR?%o1W8HO2#W~W)5<4o|4xs4~MlKesxt(EoFxT#v_o|E&R26VcVgeG*A^cej-0!QQ|6`me%w78Oc0Ek@00u<*9>2=Ny^*gs-Xx+?T->zdp4xHsPuu=)bm}EA%SG;E|{<r4P$e+PVVorl%(>KUVb?4Fdcb&BV4YjqM*<9H^qp0$9PHOM;`VWsG%OstYv>l-iaHX)1NECnZ(E`>92){};r$`v;bg<4MrPl25)8>~**3rfI;cO5GY)ma_>Vyxg|4<}+0!Pgu8~yHg_R>iVYo2%d4&pqX+_H3Yj$1O%XH32vzL^GC;fJ*@2pTq?GpDX$a9!I4KuEZ)vNEw1U&Cl>+P1p0A%+HI%!Fn1W?!QH8~d3sLp9EZGI%6wq5av0h0Ich8ANQcOkap;`h=1EK_db9<H**0)`muScAjtWV)o3>C$X9YaN?Tj;UphpJsD+9b$)2kgE}!i5vG}WVt<w`fltpCkFl^As`lU3{WPArWBvEzM<gO3fwcOt?ACG5B<_^Z<rcO&YG8`w=30f$TGl&jSvisUwxZhng|?2<Lhk|qK41(al475{<r9i({n%u)Qw^n-W@T0@;!al<QGeAZ@xPG%NOU=XX;f&W6#Zzc?ybfKY>b(<Fui+dEHV!~nmzODqdcPC=c((~PZom@N8vB(6`Wg8%&cOVU3+<U1>fd=vy7n@+{YE_2^n4a7vRR2qa1ZH$5r_m56PRd#b=8+p^yC2Kh?%%)6g<CNDVT?yughX7!N^%i5joE#MH!B-W6;TZ1LG<;hqT>$1c@g$NERP7B93Pe1b<K+`qc<;0E6$B2Y{+OvO<^c>$OG43t=AE=5lxk9HG-(D)V>>1idgyr#W{h*L~g5%DF^-qDVRzoz}x+pd11`k328#!UYM_CK26Bk3T5WW*5!d+>(<@qxJc5X3OW3}ML-#`~W{srEO|(e_GL)%up#)NB+{-$&EF_4HofP4w-RGGAKyH{1RFz6iA<L}8p4hsUCfTW-g|@(eOVhpvca;9m{EKLSZjdV3vAQ4}2xr|nDpPjKwNXw{fW8613v(}!%XWYWMxCJff1d){oEyScUvkqmx^h2rbOpLg~Sb4TWQ;r)B}wdvpADf{JUr|;yAw$PGf%PEypQ}Jql0gkH6V&g+!9k#Vf;~E;Q(m$U2^j}HiC1n^jY{B@sbWN(t21-Bu{8DvDei4;EhL~jDQ>Rtb)U~>`Pj$7u0z^d?YHBjs@<vXiaa`2fDWqj`8k*ZFIj&!2I;6NSE7qG<)!{`w6{R+WHRkDckWa{sGSb*pmZ{2^w3sz*T1D6u%}mr!;MdC#pBmQGWMQLf876_DiBGnbL-bQhRvHBuHnz3dX_nU9ZE7g$%1f~d>a40R$y9ul)Dgm(Q8P7!*lcCCu*_<<%rew0tY*axtlLX1LRqPnQfMqjsgR$<4Hb)>QKH4QTT4w9v9w|}X{wc>Y(^6rQen2#XvDR(DP^`c%u6X`TG-m!jZtBRHGHJ%9USJ(OIs?zvKp4AkdBpFOkrOaLDERpR-0Ce#;7*7-L|H;Xvk|cQw14{mTF8btqoGai$YCWlWm(TS&WpCsK{2fQl_xYEk?9WYet}|Cd5|8mYPFDM%0Gbl4(mu+AXC~TQ;OM8ws;0vQiSsGipj<M#&0eGg@V7v1z56(W+`N)|Q&FtY#Q(Xx3{Oq_$C3QK>1hHCD9Niws*Wn-8qIHCCFIw%}^rn%R`lqA1a|QcF^(*->c5l94Q%8dhsDt4xzYengx_PAuBksM>9qY-X*Xt)g04O={NKL1=2m71i`p>iLbR&{o1*HWJ!YZ8F9Tgl$3Gbaef*ps$HPhG=RX7h`DH+L1$G+hAJBTQ<sSVMef8vQ4ukp|&eUwhE|>M9rd!EtIg*Qq+pnVVN?v)oC+hG)rK$lU7WPGFCK<X;jvUs|6)g#mN!?jB^-RiwY{E7;)nb2?8;qbkbV$`1bPOR9#omI%t;3RkCYHJmei^Vdql1tW}7Vm3f3_?v~}P8lz<!Q)-iGWHMtVwN@-zN|MoRSuGl~QIxf@8i=%6s+(n}#02cNLQqmIZNnf=z?cN*<MX-dCFTsaTP-5CB-oa;%?8V0_0+nnY+5CBj4QC|q~`5Gvlv;X7P+o;)or@XZUEU;tEnp?l4@mJTe350t-dP}ArMy9w9KSnr)4D=I%=H(R@AA!Z4|VYQr7C~w%{VhWoX*bRU*x!Q*4bfkhO|s!{)kde6})brnXID&6+l*s3O?4lx>vRHkgpw#jr+5gtpPGjj@?nl&xIqYh%ZX-WP`O=#yKk647LALa2sS6DpXz?luoO<Ib3RZn=7VJl<9lYz9<R1vUX3O1j!ETI5r0rb?Bsi*GCk-d{d^eMFuN3?_|bH0PUf)Q^e`m?FkDqS!T~WTLjzTT+Rp%?0UL^TV%EdG7)Ekue$t(Y%d2V%x)7kkr)MZC#L7OIqV*uC&ctZ8oHw!Od18Lbkc5D{HpVjk@h<(yOG#rqHx5-CecPJ8G-6<7R1<V^GZ-N^__s08=11k{zTC3_ZFqI+a(OU6O{jSVU;7rK+J;D??*aP*I|)qgg7&ipwOStXTv^bA&J`3<q0a;m4_U4)AHZXryT*u~{{#r(i^#2#F{SGIxUO2blZt<SgT5S0RE<?v*cTVlrlwZ+0_Kx?8t&h|ooBNhq#U8C1cf+;z2jNv>X}tJhU%)L>1a&#&R3@l?LGN7huX&dIsY!;EEBQ0OWmEQ6u2w2)XNY=x2^etYyo$8x%JMTclZ0y#zkRLG$Y2tL*kaw(JC9nO3_#8hK*j2J|~0<>?OcNp`r+1cmUdxz%{gGNKwYXiOmml=W}KtxqM_Srjlbne%1Ub|#ct3#xcNXtnCq1_~eTSBWKf@YB0vKT&Wf(-zPHIqRQsA&UWH%XalkrYXTX@lM2&{}Y0b{0iLEw-&~fe5vDWsrpr2GoHSfWYeXp9jMDYPIrPUdfO_Op9X4K}@DZg#@827sIzojfAFSXxQ3>*(?ZXiZzibrklFdVg}k`1k`W`N<|;WZ9%GFX9~tAp5wQN$NTv8IRzCFz~Rb#jV(!!n*W2d353V1w`Z(fTO@_qVf@|(G%;jDNwZ2z^1VJYZ<%bAg4$VSO}1&3i%LmDX{In5T4>X*PPcB^aMN~MYC;8a*?_@JFktByoG8p4EOH#>ZVVo_YPF}d>sT|vuj}2J9(&(B`?bc)T<_T0*rXzmv2-q^=2pUHwW(tUvY%%1lNw-{(-Sa`$e4ziycNGZz-6G_@=S$ktZkK(5)8&I1MK9g*^5SIizN>Q464QrV7!@mJlCGJkOsk+#_jLB$ELV_Sru+<n4<(XTLBpEwm`7N+D)ti4Lkxv3K;f+1$q9MtUOk;0@+*0+K-A>#x$^3WVK^4qZk6+<1RA?dPx}T8`LsAmg-@b?)B}~shLyF?2;UbQ$RW*6KE2{NDhG`S-$znZ(ENU3^bcN@3mLf45c_+=J($KvTDntGz`2vak#OwP-kuC2J>?Tb5bBh4YrWbaMDu$uNcM*=AO11_17hpjqR~@jt;Pdr5pM;s=|x6hB}BdM<5(AQ)pvjK*ZSENqUdgdclUxOq}z^_qP0NRXQMxVZ%Uj(l{DrqncAqS_6{<Z47Rpqhkh`#*hZpE2DmPsZO$W+{u>s4@2B&z{IxT5-<rENbRIL(G&(5QV@Xwmd1gM8U`>3z$gS|qrPmDj(3#xuKkaD<vd#5>2&sK8~NiB6Bxz|W{9@(Dg=izNwCI>2FB7GETR;e6#-U|Zp*D=Y%|W!ZTLD|D1jbVnCBwJPIUvcbz!EEVXHCNFi3U>c`_&_35AWLE)8NOWp{SFJ<UK!^Mf4wfg-(Fx5qo=<*l`{_AVIH0g1h?f<rwEn6d>_aW+g!X@g)(=7Nt>tp>OJeR{YwvAQ!|`J<-N!x&|*iEt1`Gixgd%*juB<&M^9DT4?--tgg`wM*5_^Lts(F<w`=5<iZ+OzkdVE7c*5DzYLg7}KZP9XQkQ5-&H{y>r>|o$XW28<dkhyWNI=U#<@h83t$M?NG+qxZ&;=&Xq==!U-6&zZb3|?}&Gup#*qsRFx9;)&9-_BJx->&sZSN{Bg9H)iit*d+#h>ce-nU^+W0DdP#ZS)P$(sgkHD15fKRBWpoS~_IZP47##qAXl)gtj-l9a<<Y{t5*R8;&J!V!9iGE0-3fS@uMws(p(CFi0Rg1O0T>nJj759N0pmgR8{33iexg*{UZA@3ycy@Qu7R}1-$&b)%R~tng6JX#q`;ndNdvn9mwvvrD^LQ3YqV$-U}Sb?s;K#4?D2$GvM<;^7J;TAw%FHelen5k#o-jVQSY3cjdXe%O;ZL8XbO);qn1mv2u4cH)Nk1?bxk2g9o#;SWRoTYQ4b~=u=yY8@!<Ad0nP+9OGWQwxCD;fwY0Zu42@~E=JR{u9iEDaf+JQL$hpixiYyge8)6gdA@6CAFnOTNNwiW43PbgBWMDLtMT|`iTy!;A`laY5WXv$hJSBB;I;v4*VRI5N1dFA40fs0%{H|G;97)6*nkNKWiGn2Dob1gSj{qczsfO2%r|V6=8a$I%edy-cZku4(rd%kUF^L@=5ON&u1TC2$vzu{Vg$NG|!9;noH!gL8%+|^@wy1zGGEuDA5GOHWN^WdaQ`mV0DYRJr9^|X++SU#UGA4R&O=d97MtJABnsEe%nKPape6?rtSnX;R=|IlbLm2}sVzn+Ve-|?~m&H62=EUqkwVP9{sLN$nj68LVoXqCUpkAux)TItPWd;Co2T+-)0hqwB&{G0#FC-nP!;Dj?{u$Nh_iQl3EU@WdN@vSrcTAwCdQTDx!UT30a}|Y$71D?AH@CNMb>WUSK)m;GU{M;C<+a$n4vfgdrZE^{Ub-+jmktzJ+nZ$Dwl&{&xFBK`x}!*ea?yc)V37Z64rP*a0|C@w*VEURRJUI5@c(P=!!v}Hj}8MyW=}f_1qxu`HROZY`*ZAgj#rG~%*SiSVKDCv2e3GExoC6m$)BfZzn0YJaArf8cJthWwoIloD6kE%+Ph?K$~SD|ztB#8=begf;*T52x0X0%1arC5VU66y<Bh?dI8{2ov&e98hG8L?W@b$OFBx&p_HEs#^78U6P3{uu(ZEI{{n^~4BZ8osSW)Raa86)Rv^Y_?jCL)LU3D#OP(lRzN`!z1Mfdk36rjw*GYOpvqN$psztCys&3Pk~(lm=}o}<w9TtOlljdzQP%z%cuNGEf3+|*{or&e4t5H~cbnkeq6Dna=NYb0Bo^X9q^?P?Oktjw&HT<g{S)C3pVB!9so$|fSPi$IzMfVC>fsc9BcRuQVE0ijwY{{)qkaIgI;ul=Zh@E89;fB9AZfS<%6>MHwDJt{FTMD<bWOM;}XMO9ovUa1$Vk?K+DB>qV#xlobrkEB=BlJ-^NOrRcwuX3dB74bvWD)&pIjugGry;VLEnkTUCqu?IV_f>w<L;Ro%;*U~Rqo`F`D(OQ?xD>LM3UaB1HB+f^6g44gi=-_@)P;%&$x9_y2<b}^(x|RVvWt|bO0_A}0_7!&P7A3lE(sSZEG5BCsIaFhs-L1SiC4uh!dHn8M17)qL-bYq5qgw*s(LCtNWCQVR}i8(B}#It9+gL;4^>Z5Ps$WWl)hCoIFO6YD!iz>MRpfboJx3<^i^Dkbaw?}sdka-87Ih|%D&}(ib!y*qJ5I$vRwgAQpyJ+>RK+S2NbzZB{@r})S@{q7b>E<TwH=9g>Viarxn0*3UNb)97$IwaYrPpgmS9jl&w{97F6UFNvd!;6?&v-s&ba0C&HGb92C?S(xS?$KPWUQeTguL@kq#__C=_n=`Bf1<W-`ne2FxoUBO_g{V9Y@N@%0>28vPg77+PWSR|=lB~UC$6nKh-X(*2sA*B+0idHI8`BE$ae2SVvU!)Bvk3~IF_7E&xl?vq|^s2rRdJCeiiC%?0NWFsjReUL0B7FnVUZVP>eiHU5@K4Z?Qxl@Bk#dNsX%|vf1E@-eR9p;|WV)qMI#trZ7*{HlR{-L&h{7%sDs>UWSt*h^RU+w4RU+vhx$sfIbczVRR0Q!wY65twzC?JW9G9tA3VI{-sXY|GM32!?`yxF7;;YemmQ_LBE4Usc1nLB?q8D{4yQ&@1ozjbm#020-{E&Sjo`LOG<i13FrE-(=QIxYS4Ja*mi|`j}lJK75cO`d3^$PVNc&KQrkgt+}bXAlE)f|w-omC<oA;~ffsnH~@Q=(Xol?uq<rc;usTAYfqs^X;%Qgu~;#Bw4y9E^#TIVvYa>X;TOa*B=%l(38|l~BcT9aRh@;5bUKIFpH1RGg~0N}8(blc`e@T%ea!p{S(lg6Tq-i$M&kuq4Fv43xeK`vChWdP#jHSE*03Q_(Nd9+a2hN1#0w>Yk`2@Pe-tl$VMEyhtwSi@Ha3L%NCe0=Y(ul2TsLI#BlkUg9rQPU26g4gvWisQQP(o+xTq*$p7AOWi}t4<w7l97WYD?wKW&JxYE_dJanP2kHtkBPA<UQ$<Tqj8L+LkcN?3k~LIdlGH||jFRyslCMf0sE-Oyv`<A(!i()hdQ^UZ^+Nhmo{BvYdaAgRt_qcKl}}Vd)KThz>Xmw>eNk1&tCa|QLy9Z1r*wq;6n#>j1Eu+*w5eDfBiRq4o?>5Arzl+m+LvW3)GM@fRa}GORAQzmSwV_}C|D}V7*&Z(O36%>ltxfB5vUl3kTOdMtVhJAQeUASr9Qy>Md=6G56MaD1N5mLf$%R?SE(M6z^XY_BI1Jdkv&MSRVSz~RVDQ$E>#7634JP@MeLITQ;A1)S8-I}Jk;z-<OZo6r1}Tt21l`ahq6A%_EYyFub*K*YKp{KP{^88GL*_jQkY6$mW50bY7wbJN>-G8B3V&>0QwYtqJ4?#N$8K+DDX@65cHP?Jyi4$RXC(d=~5{!Dy8ZQ^i+BjdJ6ebe2~1Vk8vp-ih8K8L0+i4qQ0svKu>fl<ewl<l&grY#nKlkJCXPU^iR1bpzt2Vyb$>S)g_5lsu-$dizx=Au?e9vm4T@=C1^^*RuZ*Jw1W`Rr|l4ueMw(QD<b+L#Y6C=V0Z?V;#P&+izz<INs8oFLy{PkT%;_C$rB;T3`xk73UU<Ga-$QGF-hWBuLWff3K)+BV0Z?oPZd^`;#NgZ608Hj4McdNG^dG7QQ)H#{0eFwC}|H88ld<iD0ooHPYO&A0MR@|!FUT1;EhC{Dom2_lF>Xw(Rhm!!8EG+N~{NfG*1yUqIfB3Po$<Qcq(Kb5NRigCZhPF)m|#H9uUB<2^lHjDX5Rah{$+D5#WrZ;*$yBOsm4IRCrWkUI}GKg+_q<pfsbzqY}bchk_Xwgjp2v5uxH39s#OHijjzTA)>DlR+M;@XbZp@NqACPh2n*Q;2AFoYA1>&MQRm-<QAe_gHpLr)TfG53&60aflWaCs2MK_Xt@@Y@K_F2Rj961RtF$qau$L-6G*&Bw58%$uLWW+1X@Rl7#;ztqIrQv706bS<t2o?Qn7L@4nWemO2XtV6O>IyDljXMF;tw2C6H4PQzWaxO0ZQP0;tMFuOSqQ!lbVPq^yMz;R+)HNjyrbSt3sf5@HbLP=*AjAWCWia-b$q4oU%%5pqaHs#PlF30eZVKvtv|DnV$fa*C#bIY63JoTW*DS0Gh{qmc_BxgfDhc%m61cu1NG@dau{;*n)h;Z$i<JP>G$ltq+RB^8p6NlO(T3XM`cRE$C3gAyl!R!Z=ds2(U7OOTeRu2mJ0T#;BVL13lIQ&c%rF%CpBsmWBqT!OV0sIp1nB+*Y1O(jnVrlNA9VmT3nu0mEp;#B*gL4OjYQY<Qg-3nO})Lwl&<+9xBwyzq(Y~V8r<*?I;O3@tA)w{d89%5KtMDFTNC=-LSaf)E=cPtwWnnLK^b%dsM!J@h6oE2NUw*y2S&t$~`#>nQ|pxEIJj(2X@u%f}S&d!D<1~X+=GmYKdoQs@w7bAt{K(|nANe2u=#m97TgTnSUI$Un-TOCThND8>?iHsLult&yK97bTCaE=m#x$Rs%$<X1)AiWdSs?U>l<?)$m@h8YKO-&80Hq_QKVz7{G)$>-(Hl||OYCSfF#OX|_)?ph(qgPtt8bpf}jcqGy+L&f+#T6>3g3~KyEtK0>wu+l**fwlzGeagr8cQ0O(<O{Xw#L;7X%J1CZIa2NB4SxWR!cOb%}|icO-(IkkgT+3RY^1}Y+9yEGh1zXs%ur|ph|+?mMWbsiDcT7D$^?lW}9<YQx&@y8%^Arn(e_GUD~?Iw%eN_G|etswM>S|lTDV4W;U|Pjg?Te+ZMDNEXLC+ByERvw%c8uImI$qmPBJwV$~yPrBh30#cDRJHFmg&(2XeC>Wym5lceidy0q<b+mXdBhF4au87Ve{cG|mIY{jE#sMP^8Wo*J`nO$p5QL{2_MyMpQovCGAql~Gnj4MlQnvJwj%^Il_NSiR-JDiqNDk~{nb<MJCGS<4yZCn{iF@>wK+g00TvLXaFjb&14plsVTwvucnhQidgp(7;K33gkRwR9A<XJodO^1f}6%T%0BOGQT47`3jetF&gNi$<l*wXIIn>#E%)c8QuxuBP0gq6{&%mb9u}ZrWoC)|QahZsw+PEp`RR3dq@Ivl*JW#>s;cMHbt3rrK9p>=Lz_*4ojg$zM6l>B)R(_*9nDX6v<Gt(c=4F{aceSynOBbgUY*w6vKMCI+J!sM-vZZKlzKBUPUo4ywjxZL?&|+gfeXWo5HYhss=z%2k_o)YnwfVhkEs&8F0{EG<}gW;*J%i!|EZl~;orrryhfh_h6*)w$GkFs?>6h}l}Hm};DjTI04En{2R*+e{;yG8<bVm4$ImRV-5?y9H|1mYCW_MUsjdrL$4AripE!8jVuZR+^)2Ho(}D+SaDBQ)JaKpwhLfCd(MHvK_9SWSwPmY@H)!(#mz$IL;az(NV6(Xw_tkV69=G0Fp4K(pse|r7Wz}%845(G-aC$V_<72($Lwp8r0U2rK4!IShBUW8AY;U+Dyr;Q)6UisKZzpm1Stt8a0+PMm3t!n^PJzS`AA^Z8cKLS&59vTE(eKAgsepp=vEk)ht@E8o`>@q}8e@6hzx-DywW|DT->P^#S%N`FhQc!<v(9RGLD{D65u*D@o_3-#y|GQ8rNI*&4~*DZowya*2z%dDzEO$2D=2lDL<+<GP{Ty`P51+4(oYI_WK8s;RE-;mtdPq7-uXP>`$7a!(wc+;dukg5Xxi5zGXMXcX+_ArR+v6cB>FmKx#5wcBgWYs=kuy|*zNdRwEL)p<Z<gHbZ{pMsy2w#As(G+AGksiAd5o?A2v<(g5Ye8I8JvYT4>w{6_XmWZO3?OOKMmP;DQP?U&mn@FvMY8bMnTS=zHGe)tnVX+w4t%_i64YH!zW|Kve6vdiLCdw>Z)aKeYlDXGcVYI^8)kxV&__c<X7`94fSyHQ4ma+uXW;8Jx+E=Y>%?VJY5_a26+I5Sr)X2qZHqjfFprS3?YV&fLXrZ3DjcV&xb=vDPFpzB4$YShbG%1X6rPkKA!ip)i!kJtm3cD)lGbY7cr>^R**1U<BRFiG2YT7oaw6&(9j5A24Or?uNL6Wf+qGKl7Y?6s2wJ6CdGzmnc%E}mQnu$eaZ8aM;O+uK-CT$xcnQIo*)f(FC+Ob)&jb*mN%o`~9qao95VUsMQDO;(vYUPbs^>sDvy4^D7XxSu0*n-ha+iq(s)V+B-(3vlF?%D4m9;GYEu~tT)m|Qy&yRBC?66`9PV70l3tF*C}LTX&=2!^s*V`ZG~*y&wd#B385YP}6duN~Ux15s<Xo!fb}6m8{owM<CHBC699Y-ZP2Yj%;NVAxU&Vw-M78m6*|nUI8;nuAfBHAT6~8#4n+RFr5fVNFqMU8t#>BWtErn9R2;sHS*XktJgV-dPNmlq5+jKs$1su|~$&bvVSub3_ShHrn9Yh}hPYr8TKGw3sTSs#>mv({oWpw&_j6+Kwk?)SD4)YYQS2meW<M8jM>QDQay<$ufK?ihft&=NZoKwsk|TLutg~T<KyKL_~`+it1deL^6zy450#8#vPIz;uytME+;V-iq4=#t7j8pAt2aYVk>B-Xo<{3*>X(+=`!XETFA>P=o%D)b~1*%nETgVhAmS~cT@^xRCZG<S`b^Khqp&@DX>R%)J%Dey)eefVLv&hu-IlUv#o?tlqK4#X=I3XCR8C3NUC(OgyTztZSXcDZIc<IR>0Xa2DNQtNXEcs*wvAlWvEk9vk~waa^#4IA+?Cmib^?csicikRJNspl1Qs*DAHK2r!{UB)Y}x=qoxySHm!|j?CDz4W!BWz=S?VvHi|VWB_-VE(z>;&iDHdhw{_gb-P+D$MAq17(MTdJwvl6OVX~WORLzW8sj;b7W0KihGC8es0gRfuQ(HwXQq;8Ah$5nkMz)o8T&sjr6{WS@II1gGcDqK~a+=Uu%G5^LQmZT=+i7uy*_x|bmdIM8QAngWcL>!RYMt7vmt4zrw#=E^qof?sH4>Sl1|~KcD%jT3Z7o}N#;DsW;~`p{uG~tl3qYF2rnc<bxwWRcmn^fT)`+M|StUfQvT2iHmIlU?8BC*1VQI}PX?BKfYBj8Bn=G2h+cc(0igB54JDC=Ww=zddX03I$-B}B2)|$g;Q)p_k7EGqe4bDRCO|6$=cI~rWt<AO(qADT^HuZd~Yvr-Av5>-v@;6@hdG6cW&vxSPX4jb3-Mq0{GKFUdB6lisR_vMKISg^g#f8quR*2#|U=-2-1RzLsuPbA)08R^CaH#APgb*=udgfI0N4R^~_ffU$s~v@d1a9qN$$-NJjgFW$+zyUol}sjJuye3-VN5wy7S$0YOv!4aGg*nG6Id0JriN=3hyzHd^&ItWjOU6nh{*Ph=t+{>E^`#rjX@x*EKQ2qGV+<PZtlCTWl_S3gOIQwsE2j9)JhA2(<Sp($ya1sRN0vuT4c!CSH0G~kXGL0^LX29X-%<U*)Y{xO=}n^ie#f=QdLl6YL+8~03_r`gkap-4rs+1GVO!3DZyyE6He~j!w`tG(|~c^HtmBXy}}MR9Crd;x>-zHC8a3Qq^K%N#bZ&UWe{eQNo}HLQKrU?T8P$=i()Mn%`q`)MvAFsF@-^(F|1S~4U&^2(`}5Rl(tr`TI1bv&AhZxCL<X4BHi4*;c<1ico}x+K-}^ehYC3h5-ysfa*DZayKL25v9=5hM5ALR8y4o|!V&<xZ7Ih(<$)gR;9Mxx64^AV8cSr;mqP|qJ5tWbY7)p(Dhp>$(8D06#MY@X83q;xbUUl9uAJK&7+ely?VD<w-qqfdz2)m(R!tVh*uiQP+HD(QF;YSXrc_jz3L^?K43!`PfC7Pz0qW+sd#>%VXD$r8Y`7O<cOA@H*x-6LQM6=%>Sj1e%Jy+}xlry$GL->5DxfYlg9nGl9(mol+QHnNS%tyZbI=^+*cW6$>Ws}4R9kiJs`A&pZKiqNC!ux3S)t+%O|7{y;WA-za~uR!xd(2J?x|Y1c-#^J#86U5po*0RHv*`YO^|Y^qmz_gw{~FdB6g1A0e5gc*vxU!iycl?1r;1PLzH{pqoY+$o2gYnLZ&zg6oiJGbchi-fzaG?^l*_{7o(O5BupLd*4|G%lV+jrkfzJmEwR@q>~LU?UfdzZ*o8ZE@kw$=YEII0aXdA<3B}XGFC3B2PjK>_#xR_8z1_s>PP1{)j^LAoLhhZ(l<nKAwhkN}_toAiMGozr!Zwr;8a8?3ns`J*gP{w!rwU~-pozB}cXQ11uI9OCT&zb|T*o||9onAcfEduCIJ>%wj$Asi3fs8t+el!c%5*{|IB;{!Cv7N#bFsU+yQ&gTj`{TKf-38jp6Q1!-35)^U}>8MI9D8XPj&!M&vmxaBbODyvDJyBIZg^YJ=YwLNeszA#iu*oyRUWWYe&08R4SpwghURTiBQH=q16=?IaGHY!Pz@DOwHW9adz13Az=qc9jmS)dEBYOa9V6!tJX;rVu8%=jv>zDy5Q;ymqob%J8{P<m~tm0#m^J9v5uDGy6lPBAv>O|mAi;rhq~NbxJRzVz+$WyWh0fStB$!TxSIyW4`LK_V22GNy+u{#+TKjtZshk67k0f>)Ml2v<f0@>O-41Y&2)q-mboBC(C*ww+62_+MD8m0oY!;O&<jy)S7jK}DV5X?u@u4=E;i?5WH4(bJ662jT&^ssHq9}&C_}g{MCO5XjzEb8NM1}hS+%9xK|GBP8x#j;4VYrV%99Bq>`EPH1G(FnP@Z<}B4=l8cDtklI29KI4kgCy5oZe&XCjNWZMDXVJ%!m8Mz2)cSI6VNT<%2Dh=V1KCWdo&F)IxaQ;M3EG8zX_3b3m*n_`gIffjD-p1Nn4dz_9oE4XaELPK#ba<$ny;o|N)j!s4G$b#t(MzfrX1**`HCu5F2>}|efK32Z*V}pWDXs}^Jh9QpbR9s;|5EL*c1G1<nLC11+K^<iW8zHc;QEJ@BMyF~-$qaoy<73F>ySqi)@@RHM%dmHMNp#Q{ozs*u<aLWiR!nL!8BN^g$-L|W^e(!(yO}uWj=Je3inAOX-QH{wbS^SDGcvOkkW3k8Iy4Iwut-8qwF@{Z+925}5|v`mLuni&lVJJv`|UgmHiYiub`?_{L%6$|db_i(;ESFjBJSqV7GT)!t~%oG;^6oXqYU9G(2UbTQGraj1ffO{W?(VTffh$oGf_-dQL2)eY?LzSCMLu&IEO(F(hIV&5FsvXDg-3yhdE)BV;=)!?%IUl5$p$W<x#1^mPnAR-j}<?%_yX^C?fXRRMyJbyK~2Sxv1L)k-GBDxht*O>Z}q1J1L3X%TP(syl_gRkp_%XQEy)A@}q5**2bD8wy;4{Cao)JRV6V^QChxbvNoE|Ns-p7X@Rn3i7ahtN@0Y$+pQwgb=z)MEn+s6t`u9g8&cW38?|#wR|%^&R$B(iO{Qg`Xl*UB7>32NnzGnQwuuaD7Ajk2vS`|?t*e;pt7!Gtz2@~aWr#2fg*mAE>Og~<h<>+YJA^SQ1>UW$^h!!N#pK?Tj@%t>Web$<Q0uFXE)h!`a%}^}(m;c9J;~b0_gLJDrZ+bZv?JJd0Sxk`a9h%+f}etzeASA4DaCyF+iN3%b_DnD(IioKwZlU8=ex2UbQ>Ki^>fMGTyTz%;pDjJd$<@&ussNlR1>3~##3^=xZ+&*cU&L>bq+PVUAj({BQe}ECn>}nF2^8b<^t~LjwJ4Y+7kk*<Ulvj*n?p)j{{@2!MDDjM1@+V6m^m+5tt&<$s$Us#4A#uIJF`$eK*4+5Qw%m9c7UqK_g@cQ`6#oeJ;4}CMfBLH()y*Y-dK83G1YLPbxKK*+}G~dbxUT=$oajZXTUxL_2QX^bNbw7kyRQK?+nw(8RTo+hVqf#>5i^s1#~NOCy$*RiKn6NQGf>h+GbvSVb!v6zD~Yh>SU0D58Khi#joE!E7TqYMKT~wP;{#MB*S<N-6XbTQclos>5qb2+LC=NP<F`gcoBB<{}2vDwMj=cpCyivCz{g5jrBRJ0)S7aZ)RUP|}>2DctB}=`PEmHcc3*fR-345^|`UE>Rtl!>A1)h$tZpD@#$Ln3W156?0-xnqY+pgk?~+&XP7<Duz-aiX90I#7<m@KsYB26SBe@>yqo7#oMhK1fm3rQ6PYcS#(o2OGLEnlL=5OT4qJkD(eh9dY--RH@$aO*M%6+R+28^?be8Z?t&+z?w+$fjtE>YsuhwUv9P5i(@>069TP_!>!HrN>gXdO5TJ-?T^4PZQ5JEw_v_wm(C$-_<>R+7al)r1+BhxH;|Dk{;fw<JaqvBTLKJFsrDjJ!<w>tMkRKduh`npI%She3mvhOa<|#;Jxpu(vL`ur9bjNacXPyo4`{;KX;T7nP;XAu`JW8E0#m^DfS?7+p)|t^g%QiMRj?Zz+!*_6OcKhVtSF5)XWpU3T&~x2TOEZ_dyH{|$Bt3NsOm??iKpBgo<D}u2xVW?(ZfU!|ef2GBrnl7U*EbYsI~=GBjG%*^(uizxYF;{l?cH592NkXkI_tBJ;mHFXJqISh_gwX<YnN?~B9Y^S<D1W?hpoopc}tk?-6`F;Zib$@UAu>+6RCT;#DaD%=XBf-XyJJ7l&V!CQB=uBQV~w|DaxqfLv<k=OmrRH9EUX%b~X{YIIim}-QCPv7`o<eWuB{dAj!LvqJ$I-sa0B<a!H6Wq}mdu4pkHrK_@3M%7h)oJ<z6=#2h?~a`AC%3JQX+2*N{8MFMOQPCBX^RVtlSDgkXEF$*PFsbt}cxo#fi$VYD7lZfOJBLs(3sH$aEP~{;Zqz11<a?=|eZV|<}UY=Hyp5v=dz>F{`Ztd<DmNnkqdiPDoy~N5REz6I7lHJa@2ymE1Ko?QK!yP<H$8$Y*aoxvs!aQ-h<>1(!UgL%?o4DNM?nt}U=_rXNQ5-=LwkSayLsL4N5R@q(AvOgJp#xbe1|USqWFjKTB_mC4a}?a{*Jhk^ciNRy|K=zwB+6?kjnNapa3wGB00IC37k~f%vj)^(|F8c0><PEMfB*mh0027sumJaU^`ep|QAW(qyI#%jLVLZpyIJR#K>GXb6)w~oYJ&RIN>ES$ee?kk04j<BKmw!ykO4(SKq*xUsFGDlP^kh(k3qgs>9*5a+KXzk)QfN(xr(4D02~9dfzS?!g;GUTR44!xdSX=qs04cSan_mxAOH_QpaMxIm;?j}8YVyqrliT`Jxv~`rjhD1%7Q^cOic+UkN^gN000Bj00}ac4OKy)(V);|!3K>0(;#W4CYdq`JyKMsr4i~h4FJdh20#NqWB>`NN+b1C)hU{d7)=>8U;<(>3`{jNWWW@Zlsz=1AOHXW0004z>HvR^ty_OL^6e3WTUXK}B^ok~s7?pz{#Vd1&t%v4eQds8*Z=r`gYtWz_Y)V}`dZc*e@~3l(_NVTSLS}d#(@Jc34VX?FSdF8ziLcP_vp26Y1^XS5g21t;kUzZ(|Kk+Pdv|dTuCHk4=GXeD3Ixt&Tee#<Nd6=ugt9LZ8E+-7byE!c#!=G+K#nHaP8G+`M&o-c;0mmux|vC*Oe*4l-aAVDR25XoOg_kAzoZfs52%RFwDu2$%bt4F{Tq#kLgUN;vgI<j^T@D%M!tAW40+JE}!8fvcC245>iQJF`1JCFw6|K20!lFZ{Z^iYHT++W_B(|J$d7<pfe_5VUf=zMp<b6|6W<5U@2k&R~Tj59JsF41Cz6rc{wfPbd`m#KNOO!STNthypDTlxZtzm8Gu3iZ<5LX>1UPUjm6(vtFAm_olVL;kS}CT;(e7+YZm81_g5h$W2-9Qsv`j5$G(k_&Cc-saIwyVnPd!4NxP1bgCuDrg$A{!D5G#<dETA+<v9?VSxy(-y7TuWm-9&}_;ToE@a=9IcBRpA!;#ypKWozJ;d`W_GYK8X9GfTUFy_o_S}YPtf{h1VP|+lzoled=<Pb<DmO*uZ%<(RLFI_1BTcH%1n-36EFX9MBS<z5Ml1mzWkbRMTK9ETH6s{8+N+6=?K65A;{}@fI6{@rMyO5XUl2w}&Tj5&O<g?}Xr>Tt#e}+tIWHFG!b<5ulJrYZ<QCG2GWVf&##ZQ?MMo;hSKMFLJMTJQ(<@Kq8@6o}*amSSL`ShU;>(sZZ6AS8+T&KP%C3wW{^QdM=%EGl?eQI2_dwqA}vIc7ipVzt6^RBj_riyC#vA2uP?!%6m>9?x0QbJ!`uvKp*uhfUQ7m`Tduo9Pw`G?|Nq>y5y1Xb{~)WcG}9zlDszr%%MY|KTOMDj>W|58dBK`&BCL(3dnJ9g{?l1ay!NkSS0(99k%A&HD><LXf-<|m|+ix~OQ6~Eo0MF~rXE)-WPB8HYL<dRytdr*A{(~FalCHN$jhwpLCJg;muJuZFD6Qf6Z(BBJM)jgS4E4y3Vt(xC!9<@WsfH_#diQ$)W%*(|#W@n=5*_ul@GtPGewBh4p+O8t&g}x`nm`s=$OvzI;lJcbpOmfWkbaXsq<AkyJG^Xo&5=-(xGD&>zKbObWy;$)qLLD|d`Wtjs=au`s*lw)cvhnTg73ba_=2dVs^YEO}vm}<p$+C^Oei%h?Z&r*NPdL)@1#^ix91{XwlFmX`kQHVbGcdq05<+E!wkP>jB)s*mr5dSo3s|?1fTn7M*AtjjRbHO6Y4)BBgHo)gGijPrg?G@hxx*`7_gpJZv?)q$QVAtPZFpGvL$I}KxSYGb9dbU|M6qC57xONz4061|FGg;1NGay4R3)`iD_!v`Is$N&5-3MjHTWc!)uhr1p%XH;FL~UMx|y7QmZ}k2I5_S<bdrrib=G1drE>?hQup+2K9$$LTBMU$5>(h2#6+r5olNoYr3}F>J8u+Sgfk|+%ez0F%h@`;Bjhv4TW-%7G*=0|l1tGej(PkLmQ9uTB|8^g>L$~f*kebkEyK!{?apFTW)Q(!jWjG7ai>1LEVyu(RIb#F$++cTb!)mo@6Xre?mX?!xNDqpxpc!I>V##*!WurM3|`6Vq@Wq0WBy{t{4Y1m672b;mzqg8;+SAzlO|*^z|{|>gcT=i4(!6GpUaN6jVJ8c)?zsY&gsoSo-Tw}SeTl8@F2(A2_A>F9@@GkJ(MtJpcLx<arYJ|$;eAX+h|hMYYXS1&mu_+$c>CXI6;c3q?WYCe!2&4^ooqgG(iXTNh-=xIqmON<nzK`CVOc^VI{AV<%um)W}iDrT0)Q5z;NYsC4v%T5Ikr@zVeL;6Bz1IgO@)mA8)tW@6R5;Gu9OSdaOmNzhrQ#<xL+(GORYS8Xg6~%!>IEO4aTdmCw4i&2!-iOHWDn%<ZIY2wEy0zi+K&p()>?XJsUN=Q2OI+e&lx{vP`j-m%3bzFz;Iy!Vtfs;zINPj93M9npfHqM^KrMyCyr!?ofK3-#>`g^{LftEN(c+F*s_S|v#g!o?IQyC7m~iaFH_tR!%)9)zeApiIZJ=ae5WzwVEEOCdmAiXi4`CEN#?7%xv$lwLCUtWWN&%fyh_9vsl`@`P0^GFLN0O*|&Ogpi3Ohq)6?aJo`MGT8>gOFyWb1Cmh~PeCNi7z87}ne+7Q(MfGR8jkSa3k=pC!V55m2VvSB<Cl1kqhOhs8NJ>>IANKF6D6yi+F;BuGs$>FlvIImI_5i&VJ{SC%3d#XDh_O-|En=`ZI?vdjMZy1hjeU$awhH>U@^8@46|HCWo{O`H^@j2z+g<k00N3<_-)x%ZC`q%sjp2NO|%XgGRo5_e?3=9=4&?FVrm%KHcHiuq`X;dxT#_H--2weiB64ePoI{?&|`-PqB&i-0oa-|un{K)jH6plOD82a3nIweMzq$jwhNp6!%0_#K4Xwa&O_yplkTHwk}}6CWnrTXl~0ytn>IvprjtV<iJ(XHRb&;jYJ<h1D^+9@EW=S$=~hTxDzpz;p~j*xF<4|8jMFljSj%B%hN84q7?u3hYAqTZqfwe{*{dSM0Lr#(ZDxyUYAXyzBNAlOX|!ttTLuQiwnHmviniCnt_L>aoF)vWVuf%uE6vHpQnsry3zTkI3?XHTEoR#+rqx<#B|%}0w5rvZvQ`T=%GqeK1u9t7Y*bMiGg@jjrY)eODX>|wkwT_LnwYFvO=+=Bi)JjW$)*fVn=;#Bw8}PV8n!FqJ8suGwUXLa&9=Fsu4^+H60H;(Rx?^?VNo<nl-o&-HcLSJg~XI|R@)mS){vPkt0dv%JjaTavKFunwW+id<o#c-!cy`d`)a1z>!h(pX39}fYFeeXX3=X(rC>6uD2y9aYYa^p8y3lvN|>=`WMAiz*Qee1KL5!<_QZDhZSKhA!M^uphDnMfgq|RTR*(f0qMln;qI{YY%`0ghE8pYz{yp(^=iBS!&jyy0X;x_sOD&CrWwxsmTDDDUv{=S^+IzGIGnB-FV<Dq$oQ~KYzsIPh(;)cdzt>KcE{iDV4aDY0Sh<5R>6JNJX{^DsVp|gVe5;GTUk_Yc*N;5CqMrK28Ct95hLbFo_jc{JYxi1Zv@$F)uwLG!9uWdDjWmJ;HMp2kn(M9F(W4ckY*tLFtFF*;Q%hN`kt-`=+GNrO!V?xE)fF1DR3jp+lP$9{Zg{c$Jil7sqs0<J*|dSQFl_+F+8b4XMvxYEq=Q#EDT2a0w9tUw(_>h2?Tm=Kap=1sf;=Amdh*_FCo`PmYc^U>Z*SG-*w^;ta?LRLd-wRiHRsm0#>;7%TQ=HJK-fhAC|v+SN6@(W?(BOF9A`8e3b)gyR&4!@1QE0}REs{F2rA2tXO|E~iP`sR#1@3uw6%o<Au&>Yq$sK_shQA+8Z}#OwSDjVzW06p-E+@9cb$9Bx#uoHJoCRE`TWr<w>tt7-{2;IJMijW$O9jQdxn#Dqc77S=Ig<RL60VerL5ElE>wc}__#zyXfOgg(5cwi1E)Wu%yzXg8F1}IolS0}Fhx#hS(gW`QFd-=%gk-}0eq#$4P4d&N2*yB-clD-5tb^r$G!OX(fUDh&Hescqr9zKqY_5j2lou@i$j`M{Z;ob44WJ^TRyZbFiQU9;JQ1|Kyv+PaY17czSQMcCNC1%815fdV5=NsGFsR0r+`R7sHT{7D(=_I@o#!2KzEeV7AaLPGy>*iZ+5;vNNO3=|2LZa5&nEC>c9Va0gHZWhHOJ#aMl;Hzw&egem>jx6vGeR<Q^DE!h*Cw(vlMp|3}VY&OxRnr2h1ks-U^7XMT*d6aqs3OZ;=^;!oD`1_d)S+b^^X-xeuB$FJW2iAjdZJ+qZ+O6$I~neOPz%*t;Ky0it77ZVQA>!JmcouSLM_Z+PhMin5NaMc@P)%yz5i1D6t=qDHVa_m5p^aJCn;o;QZY^DnF6qa|RVfJ|H_iu}udJ}~{JGJ3OZ;SGkRquF4R{e2h;H0OJ?$>LgU{VtWOg~z=_PFcd=ku=KllLuu*NM$k0rkOp<wcKM@%NFz{=s2j#VX=MndfhZQvZPLMV$Oq`59|GkwV7Br13K{!t9^C*Xn%oF~6gZwsvo9pWo&fp$-cjgI>2$s1BI?5anp~o#4tKMAVL4{r6Vo<~T2?26_A0-nQDI^jwb#Xq%4v`ya}41<j!SpIvQu(*4HW;K~&BDnxlvdfPYP=7d*tcb8M=jjMGJ#2)X`>~n~V;xt7eTZ5)4vWB6jrCfBZP3?aa3l(|K<Hq{V>b1~+A6&d?l6+^|FuxvfZUz{pafq6V%xWc!WmSs#pQfibTJ1Y7zIHD%fA{<LpG)3ve^+3>&tKnFxb3w9>KzNn5(`plyE`cJF+ws@tDwvy@`<itx^RkT{+MY%{~sR?Cd}id-WGx1q#mGR!(p_r^ujHn#QvykzPz%H^RFg(zt%qcGr&FpT`9Wpha%>?*$Un4hhcrn!ie3de8h8CPUvgmtt1&N8O9=GGoa%pirw9nbG<%+ShAtJkD~BvSy6kr{uqH?`+^1G0@<X_)nBzGY1d)8t~UeUiVK}!f>(f4h{A;PT-$fW`d@@>gv?wX4ELyKK2D~3HL2hDgJJmUhwcZ`|1PdAiU0Um7vqsho-7b^>ZICLnG9fpuKpK`|9D_h1v9w$lM8qJ(oL}67&1BDe`IAfW^JD^Oe_Go3L9pAJ}p>%&~;~El=fl!aOvS^{NwsSlywmHn_*|&KD1u>W3!EtLb;5<?0jEyUq7%&TKvn`4?9WU{(cE#RyOvij8`h1CLUTo@N@KC5m(9=ZSL(dI!q^F{_DSPac5Zg*fcjuv9u=-_N#Amp{lRGL-2*Iud-zZMxh|7TUj12d}e$-kU@^m>8VD4q-F<Bd`SkDqBMnXDBdz_fT2<jTB-v|r^?*jVavc$KhgTQQIllgO28p4<WJ#H@sbT-^^d3+y1{)&{p#0-w-1gF4I`dEc$}}Y&_vD_x+eApZ4#KZt8WbU-I?S<4ZpokNqCcdsXqc0#VY!0W&-<dMk?lChsR*P*kh(@x29I4Sarb_|4_xWQUSeM|Ko4<leYgFC~WS)MaQS@(2<X>5!6(9p4naZgA|}QxT#%Gzgbs@E+ZUM5?1q@%J(-Z<u~qyMvWoGU){gqMEeYvNoY~%t@lzdN!M7949o5Y{dPq!XIdIu_ayqq8jzi9Z+PXUz3Y1RM0Dju)?fEGVR{D?MU**|T{#>pU87l^)s0xR>hQ0wY>jy^=yeZll_8q<ws+C=wy=u@#eTf%#xK7)?;iek^4#b?1^7d~tK3VCywt*d>L|g0UEhI@&nz2e+<*6P&fFvkU>CEU7Me5_Yz_Hc*53&6pw}+OcE(wza#2G}s+8~HA3L`BPuJMYTgJilsiytjf~DIi0sE_I-2x{39bA^=Q)1ToTZtvz`G>-a@(Kzf$Pf9>9MsTgdO`6<<0I45Uo~xBdVZSvcK}vgA%wE~z<lP!G_awk;f353@Np~2bl~OHK~CS$j#=8z5=39pX^{AZpL13I*~29Il2)g2<MyA*wR3BKM?9}7OYN8Reg8)7l@&j1AZRVOjo5TU5|i0`?dLOg){Vd_#`vm(vATD=J)kz!Qu@isrv&{-#!Ho(S51-&9zC)`v#B%^piAkfNbddRdCy7#HQ#~F(?6KN$5MIsYriq$1Ao3roZ>%<cP>0nrovoT$}a`4!g+5<s((&>8Wy{$qp&c&nEmh-NBY)Fi-J_xwpKshQmop>G<s>$$wt`ug$n+m7FIaH3P`I52S}eD{Vp2!A#zE5B9&p9;JHq~_TG-Y-Y-_b)i6PSdK=gc(;LvfkIb_?$rAaZAbqdBEe1}+E&u)Gt8qcwd6SD~|3jypQxkkd{v{0*EN6!kuw_u%ykO*fkk@6ZbG}fxbMrseE%3a5eX;qc?04R;KVkoCdN}>dPY<F)!(GYlB7iw!1C?3kD&21CXzo~l$sB18_~mv3or|z=``MHVut3Zy>Xz<)wBcH9UBi*4zqE?flan0ghbOC0T#GsGUC`c@KG9Rz;=OA+g$7P}!L91h)^mCt0N=JSV+jdeL>MN_v{CS~`-PTV?~>T&XiB^9xmaSm2e38+7A+jDsY?QkD*EPOIE|8<ki0^`6u@sD3%V`3jXY9c9|o*jP#=~((>Z~ULB_H(PY~m>^5>dkWE0&I0g1%*yHp*6@p(PhQK!EEskxg);Mj^-Rm4N5y7@1S;{qk-#h;Dhx<D4_;c4M<G1x~3oxod8m=Okgy;e?J4MH@~+04lEZOo(AI<ET)wF0Ak8^F=6mwheiU=H1qu3Ia;t{dCV@fE2>j2SrQ`VVL|k7LxE$6}k!g>zIe)Qb%Td9fMjYuEKKSHF}ayR5Incw%`L7m+BA7tEq<w)yZW6|~-gEaeqgPK${yPs(g&A@AtuUq;qzJPNtg*x=X=R@KqJa5r4W?jjHEpL?XUaQ-l><SxJuoMb8PkgIWweyDzA^Rc5W`YyHo)M_7b+<t7k0Qj5;8Tpy9eNCs1nu4)&ZyzZr-a<$<-2!>Ws>$oNinWKBN;_QI2y1Tl)gf=7a;EHou{qSO#$1JR^d?dQ)U3AcDiw0)i(5_{)p1Xb>bPIOpsFhYOl*(AY+ebuE9=LtAAOituXf~+me?ZHnv)2c%_9MuIWptO#HMGmiM9!v3|%vF#R4)_!#rd94w2i6QOWxoLGkho%_&@Qc<qrX(Y_~7u17q)eCiet3sG(R?$oq>7D{C?>bWD<wZ)r#%}*zVJ)=vV21HyW+>GcVnwV(>nJxtytF>!~`equyINWMiYkAqtaAVOD>#c!yB1OecsgXF@D74u=ewkXUSth3&4bRj9jk~HF+B_<mg87$>%gbu&jO9{|@)*yo%1C+12n+Q@x1S($`6pMU4(|dWTMlO(=@XAfCEUw#nI2Z6&2A@_pW$PrV_ifmUUkQSU2;<le3rPMb_!`oLNWootKaCLor*{M3O>>;@OAR{k`$pt3NJcUpm_G##l5Rm94tA7iYYVF7&S)H+`=vA3nhEtmp$92+c?g$eIB-ft$D4v4&m1<Kg&;DvArweH+i<&FYPCs=y(DiL2t^sYCt%mBX@=G0<KBlk;E>T5oNfo0p`?aIbGymrLj+^9$L<W^T`(I=aPSse>xr-I3-_^x>NSdLAtKw5E1NYz2FQC*UB~0gHgpmkH&grq^o2=*Nt>00}zePT0-9&IexjxC{D$bhq^^VsR-1(IbvUQ{u&}Sy+XP;n&Kx?ky$~MPqT3J3v(THsBEpQE8RdcKpw&M+3kYX-;3;AXD59{zG^>n_RC-Jcyj7c_BaX7E$Rb2!D*s9b+}4pIQY3)Xf8#|IzUU;sKQPUohtRkZco19nO$O051jEYe?Q$#2q&>MHwGp=incwIDOrEPTsRSQggJz73-6O<#vNuW=B`n@q*Cp0O+{8$_rFv8I7jfY4TIS)chD&wZCzlVIr7khVWYvc(WS|bLT%^tz(gZ^8^>umr)pxev#79t&$Yfbz-Q6d*5l^m*C9Lr1zS9MSP0uJ1wYL5#x|D_?Aql6FuB-VZ}|{s&F+G>!?t-dw*@mar!|-+AJ&acA16SZjv#Jz&7Q6t9E>0%%a&z87!VlG1<XSU_9@WEgFD*A&~X{oN1`wSdF)6F#i%mVYQ=>Ecqko$+vu{f84AK+<iFP7Vw?I1h0<)<@y~kl{)~zceE<)lJ|{++99@RC^HArP#d5#cp237d<lyB%Hh{S7Er@HO@Z58GT2DW@&6(NG2A&DTVcT)}j27*{U^DeLY@4USs6Ty{cE(HAOt+iFxo&n*;)TSEGi7EOa?QN*Gm<d^h)jSr_JydH1z$@N(CksDm9Zws=^mnxgr-q~D7=q}Cdd^ZsZ$9p4#B~sDWz6ibzOTVYD=S<#O-6ltu`^)0cYOI?+HGvmJjpv2=Ky~NsnrFJI+GX+|LuJa_OX5M6ND24Orxb6qH6-NF$78<(p;Y%G$cDb)g!=>VT)V--t3!R(oIps^by5gxtn<1W_BzFt&kt22IVG1{}E@`W&E4wMof}XVpYK0=XlwW$r)&ZgV<)#7LAO3NRRltDC7qb9uJY64PQ-ZCum5#JreHw=?;WJgS<0Jv%^5_fU6IlL^W_Gq{diWw&CN$ri>r;OvPjC|M621jq(<*JYkLa=xzpdYG{&6U`yWh|nhsA$>H>zCv9B#n51ESi|yvTbI?J%9`iUU?JH5e5Y+xxLQArnJPF@LVlocFZyYXFIH=7)*lZJk*ty--YIO-PIk$t!W`LDGcMYQ!6iF=6gLaoZ-}u*B1!YCZG$aU7GZ@0uRLH6DC8u;iIRtbD~Q%W(8i(25hK>X49|{@nUKlaF)i#!h+>nHK1fZ+*O0b$5vngOC?D#NrlCzgZVIa}Nd`=%iPtK+%V={tUAC(VYMi%O2Y8-tf!)fbsi#$#6c)HfI>b)4Y|7Zh*eHZTh0cfKb9*Ce0Fr1_xI4N-3D~2IevQ|9-P}~RV(-NBwud6BU6g9{Q6W9OKB1#tHXIr_rXi<9_kAa(#_R0)l1n6ab#WgtIp?fZgQ{FK;Y~9-mCD@}jH>bj!&y~<3waYe4f|c<@vI29AW+{zHKnR)D2(sF?cNhg-Sn-cEwb^V1ZG@=y;>BDj%+HF*2|OS!*%d<LAC7+>35+mr7kVjCdHwP2$Yf|eQ+{7!oDza%*XD@A|s&D22ZgsX`!0vt|;1%Gh*?0iaS)%&yZ#E3NM^bERONGsI9LO+X@b<)K818m5{;sZ&qPipaG@cTemdjZyEOxA5GI(BRm&sh&xNqt2;1|M|w~jlVPkRt}oYIJx`<LYKe>M8#8#0JgphtyEbNosfW`bq}E*p3eE?ayo#Lba-v81z^ON3^hh5)@C+T3HdWr)pb2s}cENf<x2vj0sRq~aGHK%&e@=xYUoPLog+?x4pf&J#<K;@1mF@It3>tD|uCv_PzDlk#Ke8ETi~?6zGj(Kc7}4;~N;tjtCc_%z!s4k;A5W$dRErx4a%<}hn`Mn<NyCj69_52OOjb~MO1Pm`u3-aphF4A#@YG_NaA=qsyOi^vGm<0Nl%5EZmoKZ+Cy<skKfhvG{cGCZ#E++TuPX2-CH9NzW~{?aE0H6@NIWkhO}oiplR@87KVF+o;osLISkSS&<kI|`58_T&W1@#wkEXx9Yb9k6hc-7jUb{IqnT&g$Y|oPP^Ej*9M=|fBYe+Z2t=fXBi!x7E1QIH`EY9~wkS_&6lZS^h`dBREj`w`6UayQi3SmqYfRmT^xnWr29*f1`j0=f{>P?28-Z&>GD736s-C9Hszq7a>uG8-9;*AST^Dvp0JfiirM?~;~LntO*Pg{s_VYg99MR<=G@9i*Vp>HP^A0K)n_=9`=4Vk={a=kF#Uf5ih2fjZgcHbDFG}mKP;pMs(|GEp$`Z9-`V3FH+T>gzfcLDV4O6A~XJ0wn*%nbr7J4rgC7n{@PpuI3djlO($jJh&@zYA2bqM=0n&hqgMHDXoe_86DomC*;yOT!VodEDwsas$Kmn+KL#b02T~>NXr#9jX@@VmsY3xfC9^Ki$Dto@@D%mv^f4JzN#6%sXas2Wfn?Rw1So!BU{F#VyEax%9&{bljmRkXB21RZyt1EWR4As2DYwGbeKan(M<<4y;+=<*lvz&-AbiJi<DM>MTv|a*;cWMlGJxuplM$T%nF#2LJ$%C=&p>6nX^nqxhk8A8$i1Bx{E6K2C06%3iW0tel}E@Xy}A)dB(Yn6?=%Les7dVuNxQVVa({{;ZWz%@WlXl^Jxw8@`4lraZT|#mf-l*lx`*<$bYL8-A0>(a9y*<PXHITE(E)gUgHCzUhQ5_N?;8bN7{VFflWoOSbu7N`<E<(2*z*0SgdV9W2m3o01rTDp`C`C~i73JajQKbVY+v7V;&*rMsn#m@ng_EXOsFGw^aXGN!U}ur#t;U}dDZ>lBKx2=~zmd9wsp8f?3XnS=zELt9uz5KuXzvl-vaz?d92od+*4SIQaAo_xE`wOb?n9Bqu!TpNurw6MJR$}n@Hxraer2&f9J<Y^cqn1YB(EP;*3^CR6Ht6?=JOlj+B9+26*6xvZ<&Tk8cb>nbcJC;dQg^TX-KC~p*$)yjBBP*eB-c#jhCIkfy46U+5=`$Ae`!x<+#tLL3`aKf7U%PMTbz+o*ln5rTeLQ>8)hh60m(bEnVAktK|8~gk#@B}yF04&s%>aoXq$BLrA1Uum^r}Vn`>Sr&G?QIY*6zk7xEDJ}y2kPa=0*iZU#KeQQ(AmjyDA9MfrD{fT2u-tm}C=1;&}39h;Gxgtd=Kjg$OySo=@0(WGI)5X?HnbtG-zh_1bkFI*Ct0mbAF%1y@=5efyEdthm`9pOk1&%=oHk!_YFem*PJ#9WR^d0QkQyQ(1ifBLU00brZqXvW!*B6FPU=qXiBPMD(=vLc$iFb)*a*zkYi^aSbx5?1X!i=^!UzNAjsY4pOpIx&B7t-8+(au5XB&8*u1i`0|Vkkka?aN=ZEb9eyePotCpGSe8vUVYsL+?&;zgQ`hbj5}1vEsS7+fyCqFi=@JK6c?;XQWI_+W&ix>4Y;V*^NjG|97n6%+h7Ih9zDEN~f^K*f8Llm3)!owfK+~b|Z5&h`acpsoP!aMnnzv<Ze-9ftG56BVULs~HUC=n)1;;PTDnITQsM0`F93xvW%d0VhVlm4DLT)Z)CRNKzD$xPa?sV6!xGRF!93ZAUsDYfs<3e=9F=N|TB+yLf+}cNiy#?d6?{wh<j}D7?(V$)pHuS|PPON@p9Q9u~Nzem+t_Un#El^Q%d70oTd$9mga@ipm)rKlfu!#L3LsGm6P<1EB8opa~6{O*_8N(JYwNQiDm$Apy)|Li4Bz=<A^wyhW)8V8qlIDkZ#aWAdv*zA7@MOjsr^xK`9CKOX`09mw{mL|!!`aJF@|b5gK>`T5Bw_}DB>1bZ93PeTM@j6+vsLX^*|aE`p`p@pDmOcJ#M&Z3TjkEoRS}zGsgaiHhPwHLsPo$pc81C!>H*eb_2f-1ay8+>WXs`6$nxY-@0+KtVkr-q>lOYY#}}Qr{neuczQtR=;roPr@a2B&+RH0<rC!Y~#jN6+>bB3xnYwAldVmrjD%CF|^VtssLx%dL;6uBl&RSJ-<262WQHt+arr#GW-HDJMkpYY36+?)AN36X8zwHm_-*B7T)?XR~2_3bD7}b<YTNnmL{wQ*{M$!+`x!%SFK9p_0dS=|-P(K_DlO#&+Vn5w?WQ-Ro)lUq3tiNnz;3u6=Dm5T@2-7!>)T*L$7wBoyFwrZZ_@x>@SfXYEs*F7WbkKmRna&Mr-9C3!%|ZL7_i556qb#RD9-BTz%^Ea~f)vhi`1r3Qw$r3Z`d!5aV_8p@rO+})N=T~QtUhX05TEOd@E)l&HSKE+HQ9|l2;FdHH^Dv(_E#=n)2Qy!IM(1qu@ijoYcXSAfo94qqLC@jbTjh<yMFkSxmi575nN!{@u0>RRy=>_(dC{dPTB|SFUNc<5WPxPHqGEPWbv~|+o9{R#<n3PZdpcUT)Q*ioP~v&W^T*GjP3*yIH|TVi!c;TI(YR)Z>?t<YZHAFv(lK+@6C@oM&)d741Rm8qs6u7%}Qo!0P(}g&4R9RJz{104JzF_?han+-NlPSzNmD&F_`<r`|tdj@cPjSGqv3i=g-=r!(Do38$3T)t;`|D!tvK6Y?XE|i@)}o#`dTt+>k7AjtsoiFisjeyIU|J2X-nsD_qZifb>G>9Q7Sww9ZOZ6f@9tMqjCXb&Ku*4D!*>5b>TTm%BU4MV3>boOy1@g2^gXWS-XqW6}9=0zajqo_CVo5Pa=7!TQo{UD8WD^FmgN#YB`}B0cFtG4JK|ev4kJSd}gRhTPt2%@F9EmD{cUY7hS{|Ib%1zElqFjhsaOb@a8jXB-W8JXia}7rJU*aW~?{>Vv5sa+k^WaeZ+qOXApc<rut`Lfp@iaH%%kR5xATQf8`(B2*FtUKG|K+30ouFIPpb{q}u(TG0(g#ZtIECU@m8)>SN*HC6gPk?qzHf~IR++L?&$gVwxw{rO5wDLck2vNR6!;)N>ZIC*E&fx=UZSr@GTN7Q*o@~Nr|V|~h1gCF5Ne!+%FU2K<8ql$Q?Ur-}Q-_X#|BZ}<C4=gM>VQp_3FaU^Nwzrql5sDVCs)r1Yk+zX-;CM@6m0sLFQRwNDX|b_kDb#&59J+l@-L4cR4V*2Y0b0^D)WZq+YKNPM^OzA9)OFkk)iC|UZ44+AA+cf&^iV8=2fxCNx=k1BjeS%q4nSO@Mcm2>^d*WsGG$fBMIz}1lh$xM*^crO47FF|R_3SsbOU~H3{z4h#?=&oZhf{Wd+xAA&8EPnw?RM95Z{sdFTKxoGq$z4X)+fSwoTVvk9$P2|HvK<Zn4cv3x~sVI)ZqSgFpYXX=@;8Ze=!z_6>B%7nJ<#dFtGeY4nE*QwOk+q3Rre;6;MA#hAITgX&q*jmV!D?=7Tn+*(acyeVVd@6&ybF$j++XDf=Bg{^^;NYjEZc)vjJdC%=6?p(4O*#MX&M6viJ)0Q+FoqKdVYlz(qw}}4u$#3E>PHp_0EL3>ODENpI{X^{JGe7wh(s$Gg>#xDDe&4fv_QBg>Y7%c(`xG0ca_iBywy$Yy<<_WA1c6;k5q4$_+=@Uh?}a;=X}G+z6a>1T+hq@q2r2!QJ&IaH^}cINpL)R$Uz^R#*--5*-|b-2kJpo(el3|IUOs>R+3k8$S5#DGltfkvX!6|fntO@5AM?+Pb(x2Gdl*#~27`4(?}_N@6lkWaYCe4@rDLyGHjyt8onZv6yi~4zdhtB#&wmWI@}i%r!!)nl`9DLd_Ot'

def _gen_5s_ascii_intro_code():
    """Generate heavily obfuscated 5-second ASCII Video Intro loader (Zero Plaintext)."""
    intro_template = """try:
    import sys, os, time, zlib, bz2, base64
    if os.name == 'nt':
        try:
            import ctypes
            k = ctypes.windll.kernel32
            for s in (-11, -12):
                h = k.GetStdHandle(s)
                m = ctypes.c_ulong()
                k.GetConsoleMode(h, ctypes.byref(m))
                m.value |= 0x0004 | 0x0001 | 0x0002
                k.SetConsoleMode(h, m)
        except Exception: pass
    _r = bz2.decompress(zlib.decompress(base64.b85decode({b85_repr}.encode('ascii')))).decode('utf-8')
    _fs = _r.split(chr(31))
    _d = 5.0 / max(1, len(_fs))
    sys.stdout.write(chr(27) + '[?25l' + chr(27) + '[2J')
    sys.stdout.flush()
    _t0 = time.time()
    for _f in _fs:
        _st = time.perf_counter()
        _rem = max(0.0, 5.0 - (time.time() - _t0))
        sys.stdout.write(chr(27) + '[H' + _f + chr(10) + chr(27) + '[1;36m[Tr0ngX] Celestial Protection Initializing... (' + f'{_rem:.1f}' + 's) | https://github.com/Tr0ngX' + chr(27) + '[0m' + chr(10))
        sys.stdout.flush()
        _sl = _d - (time.perf_counter() - _st)
        if _sl > 0: time.sleep(_sl)
except Exception: pass
finally:
    sys.stdout.write(chr(27) + '[?25h' + chr(27) + '[0m' + chr(10) + chr(27) + '[1;32m[Tr0ngX] Celestial Shield Online. Executing Protected Payload...' + chr(27) + '[0m' + chr(10) + chr(10))
    sys.stdout.flush()
"""
    raw_intro = intro_template.replace("{b85_repr}", repr(_EMBEDDED_5S_INTRO_B85))
    compiled = marshal.dumps(compile(raw_intro, "<intro>", "exec"))
    compressed = zlib.compress(compiled, 9)
    b85 = base64.b85encode(compressed).decode("ascii")
    alpha = "abcdefghijklmnopqrstuvwxyz0123456789"
    obf_intro = (
        f"(lambda _a='{alpha}',_p='{b85}':"
        f"getattr(__import__(_a[1]+_a[20]+_a[8]+_a[11]+_a[19]+_a[8]+_a[13]+_a[18]), "
        f"_a[4]+_a[23]+_a[4]+_a[2])("
        f"__import__(_a[12]+_a[0]+_a[17]+_a[18]+_a[7]+_a[0]+_a[11]).loads("
        f"__import__(_a[25]+_a[11]+_a[8]+_a[1]).decompress("
        f"__import__(_a[1]+_a[0]+_a[18]+_a[4]+_a[32]+_a[30]).b85decode(_p.encode('ascii')))), "
        f"globals()))()"
    )
    return obf_intro

def _gen_pycool_header():
    """Generate PyCool signature headers & watermarks with CJK blocks"""
    cjk_p1 = _gen_cjk_docstring(paragraphs=1, lines_per_p=4, chars_per_line=35)
    cjk_p2 = _gen_cjk_docstring(paragraphs=1, lines_per_p=4, chars_per_line=35)
    cjk_p3 = _gen_cjk_docstring(paragraphs=1, lines_per_p=4, chars_per_line=35)
    sig_bytes = secrets.token_bytes(32)
    
    header = f"""{cjk_p1}

{cjk_p2}
__OWN__ = "Tr0ngX"
__OBF__ = "Tr0ngX Ultimate Obfuscator"
__VER__ = "6.0"
__SRC__ = "https://github.com/Tr0ngX"
__CMT__ = "Make by Tr0ngX - https://github.com/Tr0ngX"
__WM_SIG__ = {repr(sig_bytes)}

{cjk_p3}
"""
    return header

# ═══════════════════════════════════════════════════════════════
# VELIMATIX ENGINE - ADVANCED AST TRANSFORMERS
# ═══════════════════════════════════════════════════════════════

class Utils:
    def randomize_name(alphabet: str, length: int) -> str:
        if _EngineState.use_cjk_names:
            return _gen_cjk_name(min_len=max(6, length // 2), max_len=max(8, length))
        name = ''.join(random.choice(alphabet) for _ in range(length))
        while name[0].isdigit():
            name = ''.join(random.choice(alphabet) for _ in range(length))
        return name

    def generate_next_num(current: int, max: int):
        next_val = current + random.randint(1, 1000)
        return next_val

    def find_parent(node, targets):
        parent = node.parent
        while True:
            for target in targets:
                if isinstance(parent, target):
                    return parent
                elif isinstance(parent, ast.Module):
                    return None
            parent = parent.parent

    def find_class(tree, node: ast.Call):
        for _node in ast.walk(tree):
            for child in ast.iter_child_nodes(_node):
                name = node.func.id
                if isinstance(child, ast.FunctionDef):
                    if child.name == name:
                        return child.parent
                elif isinstance(child, ast.ClassDef):
                    if child.name == name:
                        return child
        return None

    def get_chance():
        return random.randint(0, 100)


class BiOpaqueUtils:
    possible_args = []
    possible_functions = []
    alphabet = ""
    length = 16
    safe_mode = False

    def get_possible_functions(tree: ast.Module):
        if BiOpaqueUtils.possible_functions != []:
            return BiOpaqueUtils.possible_functions
        possible_functions = [ast.Name(id=func_id) for func_id in dir(__builtins__) if not func_id.startswith("_")]
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef):
                    if isinstance(child.parent, ast.ClassDef):
                        possible_functions.append(ast.Attribute(value=ast.Name(id=child.parent.name), attr=child.name))
                    else:
                        possible_functions.append(ast.Name(id=child.name))
        BiOpaqueUtils.possible_functions = possible_functions
        return BiOpaqueUtils.possible_functions

    def get_possible_args(tree: ast.Module):
        if BiOpaqueUtils.possible_args != []:
            return BiOpaqueUtils.possible_args
        possible_args = []
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Call):
                    for arg in child.args:
                        # ★ Skip Starred expressions — invalid outside call context
                        if not isinstance(arg, ast.Starred):
                            possible_args.append(arg)
        BiOpaqueUtils.possible_args = possible_args
        return BiOpaqueUtils.possible_args

    def get_random_function(tree: ast.Module):
        possible_functions = BiOpaqueUtils.get_possible_functions(tree)
        return random.choice(possible_functions)

    def get_random_args(tree: ast.Module):
        possible_args = BiOpaqueUtils.get_possible_args(tree)
        if not possible_args:
            return []
        return [random.choice(possible_args) for i in range(random.randint(0, 2))]

    def generate_bogus_body(tree, node):
        bogus = type(node).__new__(type(node))
        bogus.__dict__.update(node.__dict__)
        for name, field in ast.iter_fields(bogus):
            if isinstance(field, ast.Call):
                new_call = type(field).__new__(type(field))
                new_call.__dict__.update(field.__dict__)
                if isinstance(new_call.func, ast.Name) or isinstance(new_call.func, ast.Attribute):
                    new_call.func = BiOpaqueUtils.get_random_function(tree)
                    # ★ Filter starred from random args too
                    new_call.args = [a for a in BiOpaqueUtils.get_random_args(tree)
                                     if not isinstance(a, ast.Starred)]
                setattr(bogus, name, new_call)
            if isinstance(bogus, ast.Assign) and name == 'value':
                args = BiOpaqueUtils.get_possible_args(tree)
                # ★ Double-filter: no Starred in assignment values
                safe_args = [a for a in args if not isinstance(a, ast.Starred)]
                if safe_args:
                    new_value = random.choice(safe_args)
                    if isinstance(bogus.value, ast.List) or isinstance(bogus.value, ast.Dict):
                        new_value = ast.List(elts=[random.choice(safe_args)
                                                   for _ in range(random.randint(2, 6))])
                    setattr(bogus, name, new_value)
            if isinstance(bogus, ast.AugAssign) and name == 'value':
                args = BiOpaqueUtils.get_possible_args(tree)
                # ★ Double-filter: no Starred in aug-assignment values
                safe_args = [a for a in args if not isinstance(a, ast.Starred)]
                if safe_args:
                    new_value = random.choice(safe_args)
                    if isinstance(bogus.value, ast.List) or isinstance(bogus.value, ast.Dict):
                        new_value = ast.List(elts=[random.choice(safe_args)
                                                   for _ in range(random.randint(2, 6))])
                    setattr(bogus, name, new_value)
                    setattr(bogus, 'op', random.choice([ast.Add(), ast.Sub(), ast.Div(),
                            ast.Mult(), ast.BitXor(), *([node.op] * 3)]))
        return bogus

    def generate_roadline(goal: int):
        num = random.randint(1, 100)
        current_num = num
        roadline = []
        iterations = 0
        while current_num != goal and iterations < 1000:
            iterations += 1
            if current_num > goal:
                val = random.randint(1, num + 1)
                current_num -= val
                roadline.append([ast.Sub(), val])
            elif current_num < goal:
                val = random.randint(1, num + 1)
                current_num += val
                roadline.append([ast.Add(), val])
        return (num, roadline)

    def obscure_bool(value: bool, arg_name: str):
        roadline = BiOpaqueUtils.generate_roadline(value)
        attempts = 0
        while len(roadline[1]) > 6 and attempts < 100:
            roadline = BiOpaqueUtils.generate_roadline(value)
            attempts += 1
        original_number = roadline[0]
        roadline = roadline[1]
        binop_name = Utils.randomize_name(BiOpaqueUtils.alphabet, BiOpaqueUtils.length)
        binop = ast.Name(id=binop_name)
        for action in roadline:
            key = random.randint(1, 6996)
            xored_binop = ast.BinOp(left=ast.Constant(action[1] ^ key), op=ast.BitXor(), right=ast.Constant(value=key))
            binop = ast.BinOp(
                left=binop, op=action[0],
                right=ast.Call(
                    func=ast.Lambda(
                        args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                        body=xored_binop
                    ), args=[], keywords=[]
                )
            )
        if BiOpaqueUtils.safe_mode:
            return (ast.Call(
                func=ast.Lambda(
                    args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=binop_name)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                    body=binop
                ), args=[ast.Constant(value=original_number)], keywords=[]
            ), None)
        return (ast.Call(
            func=ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=binop_name)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=binop
            ), args=[ast.Name(id=arg_name)], keywords=[]
        ), original_number)

    def generate_opaquepredicate(tree, node, arg_name: str):
        test = BiOpaqueUtils.obscure_bool(True, arg_name)
        ret_node = ast.If(test=test[0], body=[node], orelse=[BiOpaqueUtils.generate_bogus_body(tree, node)])
        if Utils.get_chance() > 50:
            test = BiOpaqueUtils.obscure_bool(False, arg_name)
            ret_node.body, ret_node.orelse = ret_node.orelse, ret_node.body
            ret_node.test = test[0]
        return (ret_node, test[1])

    def fix_calls(tree, func_name: str, arg_name: str, value: int):
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Lambda):
                        continue
                    elif isinstance(child.func, ast.Name):
                        if child.func.id == func_name:
                            child.args.append(ast.Constant(value=value))
                    elif isinstance(child.func, ast.Attribute):
                        if child.func.attr == func_name:
                            child.args.append(ast.Constant(value=value))


class BiOpaqueTransformer():
    def __init__(self, alphabet: str, length: int, safe_mode: bool):
        BiOpaqueUtils.alphabet = alphabet
        BiOpaqueUtils.length = length
        BiOpaqueUtils.safe_mode = safe_mode

    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        biopaque = BiOpaqueTransformer._BiOpaqueTransformerInner(self.tree)
        self.tree = biopaque.visit(self.tree)
        self.tree = ast.parse(ast.unparse(tree))
        return self.tree

    class _BiOpaqueTransformerInner(ast.NodeTransformer):
        def __init__(self, tree: ast.Module):
            self.tree = tree

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if isinstance(node, list):
                return node
            if node.args.vararg is not None or node.args.kwarg is not None:
                return node
            if node.name.startswith("__"):
                return node
            body = node.body
            body_length = len(body)
            bad_list = [ast.Global, ast.If, ast.For, ast.Return, ast.Pass, ast.Try, ast.ExceptHandler]
            chance = 75
            chance_step = int(50 / max(body_length, 1))
            if body_length == 1:
                return node
            for i in range(body_length):
                child = body[i]
                if isinstance(child, list):
                    continue
                if chance <= 0 or chance >= 100:
                    break
                if Utils.get_chance() > chance and not type(child) in bad_list:
                    arg_name = Utils.randomize_name(BiOpaqueUtils.alphabet, BiOpaqueUtils.length)
                    predicate = BiOpaqueUtils.generate_opaquepredicate(self.tree, child, arg_name)
                    if not BiOpaqueUtils.safe_mode:
                        node.args.args.append(ast.arg(arg=arg_name))
                        BiOpaqueUtils.fix_calls(self.tree, node.name, arg_name, predicate[1])
                    body[i] = predicate[0]
                    chance += chance_step
            return node


def _gen_opaque_zero_ast():
    """Generates an AST node evaluating to 0 at runtime using non-literal invariant constructs that break static AST constant folding (TRX-AST-B1)."""
    kind = _trx_rand(4)
    if kind == 0:
        k_val = _trx_rand(300) + 12
        return ast.BinOp(
            left=ast.BinOp(
                left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=3)),
                op=ast.Sub(),
                right=ast.Constant(value=k_val)
            ),
            op=ast.Mod(),
            right=ast.Constant(value=6)
        )
    elif kind == 1:
        return ast.BinOp(
            left=ast.Call(
                func=ast.Name(id='len'),
                args=[ast.Attribute(value=ast.Call(func=ast.Name(id='type'), args=[ast.Constant(value=0)], keywords=[]), attr='__name__')],
                keywords=[]
            ),
            op=ast.Sub(),
            right=ast.Constant(value=3)
        )
    elif kind == 2:
        n_val = _trx_rand(300) + 15
        return ast.BinOp(
            left=ast.BinOp(
                left=ast.Constant(value=n_val),
                op=ast.Mult(),
                right=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Add(), right=ast.Constant(value=1))
            ),
            op=ast.Mod(),
            right=ast.Constant(value=2)
        )
    else:
        x_val = _trx_rand(0xFFFF) + 200
        return ast.BinOp(
            left=ast.Constant(value=x_val),
            op=ast.BitAnd(),
            right=ast.UnaryOp(op=ast.Invert(), operand=ast.Constant(value=x_val))
        )


class MutatorUtils:
    alphabet = ""
    length = 16
    safe_mode = False

    def generate_stack_elts(real: int):
        elts = [ast.Constant(value=random.randint(0xFF * len(str(str(real))) * 100, 0xFFFFFF * len(str(str(real))) * 10)) for _ in range(random.randint(0, 15))]
        elts.append(ast.Constant(value=real))
        random.shuffle(elts)
        index = -1
        for elt in elts:
            if elt.value == real:
                index = elts.index(elt)
        return [elts, index]

    def proceed_int_assign(node: ast.Assign, ladder: int):
        old_value = node.value.value
        name = Utils.randomize_name(MutatorUtils.alphabet, MutatorUtils.length)
        keys = [~(random.randint(0xFF, 0xFFFFFFF)) for _ in range(ladder)]
        obscured = old_value
        for key in keys:
            obscured = obscured ^ ~(key)
        elts = MutatorUtils.generate_stack_elts(obscured)
        stack = ast.Assign(targets=[ast.Name(id=name)], value=ast.List(elts=elts[0]), lineno=None)
        key_index = random.randint(0xFF, 0xFFFFFFF)
        node.value.value = elts[1] ^ key_index
        name_obj = node.targets[0]
        body = []
        for key in keys:
            body.append(ast.Assign(
                targets=[ast.Subscript(value=ast.Name(id=name), slice=ast.BinOp(left=ast.Constant(value=key_index), op=ast.BitXor(), right=name_obj))],
                value=ast.BinOp(
                    left=ast.Subscript(value=ast.Name(id=name), slice=ast.BinOp(left=ast.Constant(value=key_index), op=ast.BitXor(), right=name_obj)),
                    op=ast.BitXor(),
                    right=ast.UnaryOp(op=ast.Invert(), operand=ast.Constant(value=key))
                ), lineno=None
            ))
        body.append(ast.Assign(
            targets=node.targets,
            value=ast.Subscript(value=ast.Name(id=name), slice=ast.BinOp(left=ast.Constant(value=key_index), op=ast.BitXor(), right=name_obj)),
            lineno=None
        ))
        return [node, stack, body]

    def generate_binopt_int(value: int, keys):
        obscured_value = value
        for key in keys:
            obscured_value ^= key
        binopt = ast.BinOp(left=ast.Constant(value=obscured_value), op=ast.BitXor(), right=ast.Constant(value=keys[0]))
        for key in keys:
            if keys[0] == key:
                continue
            binopt = ast.BinOp(left=binopt, op=ast.BitXor(), right=ast.Constant(value=key))
        binopt = ast.BinOp(left=binopt, op=ast.BitXor(), right=_gen_opaque_zero_ast())
        return binopt

    def generate_binopt_float(value: float, keys):
        obscured_value = value
        point_len = len(str(value).split('.')[1])
        for key in keys:
            obscured_value += key
        binopt = ast.BinOp(left=ast.Constant(value=obscured_value), op=ast.Sub(), right=ast.Constant(value=keys[0]))
        for key in keys:
            if keys[0] == key:
                continue
            binopt = ast.BinOp(left=binopt, op=ast.Sub(), right=ast.Constant(value=key))
        binopt = ast.Call(func=ast.Name(id='round'), args=[binopt, ast.Constant(value=point_len)], keywords=[])
        return binopt

    def proceed_int_constant(node: ast.Constant, ladder):
        keys = [random.randint(-0xFFFFFFFFF, 0xFFFFFFFFF) for _ in range(ladder)]
        name = Utils.randomize_name(MutatorUtils.alphabet, MutatorUtils.length)
        node = ast.Call(
            func=ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=name)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=ast.Call(func=ast.Name(id=name), args=[], keywords=[])
            ),
            args=[ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=MutatorUtils.generate_binopt_int(node.value, keys)
            )], keywords=[]
        )
        return node

    def proceed_float_constant(node: ast.Constant, ladder):
        keys = [random.uniform(0xFFFF, 0xFFFFFFFFF) for _ in range(ladder)]
        name = Utils.randomize_name(MutatorUtils.alphabet, MutatorUtils.length)
        node = ast.Call(
            func=ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=name)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=ast.Call(func=ast.Name(id=name), args=[], keywords=[])
            ),
            args=[ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=MutatorUtils.generate_binopt_float(node.value, keys)
            )], keywords=[]
        )
        return node


class ExceptionJumpUtils:
    alphabet = ""
    length = 16

    @staticmethod
    def _sparse_keys(count: int) -> list:
        # Sparse dispatcher states - source: Tr0ngX veli-3 ControlFlowUtils scheme
        # backported into the veli>=2 exception-jump dispatcher so state values are
        # non-contiguous and cannot be recovered by sorting indices (research note:
        # sequential 1..n dispatchers are trivially re-serializable by analysts,
        # cf. ObfuXtreme ControlFlowFlattener analysis, research_repos).
        keys = []
        seen = set()
        guard = 0
        while len(keys) < count and guard < count * 200 + 1000:
            guard += 1
            k = _trx_rand(0xFFFFFFF) + 1024
            if k in seen:
                continue
            seen.add(k)
            keys.append(k)
        return keys

    def generate_junk(ex_name: str, max_val: int):
        cases = []
        line = max_val + 1
        for i in range(random.randint(0, 3)):
            case_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
            cases.append(ast.If(
                test=ast.Compare(
                    left=ast.Subscript(value=ast.Attribute(value=ast.Name(id=ex_name), attr='args'), slice=ast.Constant(value=0)),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=line)]
                ),
                body=[ast.Assign(targets=[ast.Name(id=case_name)], value=ast.Constant(value=random.randint(0xFFFFF, 0xFFFFFFFFFFFF)), lineno=None)],
                orelse=[]
            ))
            line += 1
        return cases

    def generate_blockV(body):
        old_body = list(body)
        if not old_body:
            return []
        var_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        ex_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        # NOTE: Global/Nonlocal declarations are treated as regular flow statements
        # here (declaration semantics are scope-wide regardless of textual position),
        # matching pre-existing behavior of this helper.
        keys = ExceptionJumpUtils._sparse_keys(len(old_body))
        sentinel = max(keys) + _trx_rand(0xFFFF) + 17
        body.append(ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=keys[0]), lineno=None))
        case = ast.While(
            test=ast.Compare(left=ast.Name(id=var_name), ops=[ast.NotEq()], comparators=[ast.Constant(value=sentinel)]),
            body=[
                ast.Try(
                    body=[ast.Raise(exc=ast.Call(func=ast.Name(id='VELIMATIX'), args=[ast.Name(id=var_name)], keywords=[]))],
                    handlers=[ast.ExceptHandler(type=ast.Name(id='VELIMATIX'), name=ex_name, body=[])],
                    orelse=[], finalbody=[]
                )
            ], orelse=[]
        )
        for idx, body_node in enumerate(old_body):
            nxt = keys[idx + 1] if idx + 1 < len(keys) else sentinel
            case.body[0].handlers[0].body.append(ast.If(
                test=ast.Compare(
                    left=ast.Subscript(value=ast.Attribute(value=ast.Name(id=ex_name), attr='args'), slice=ast.Constant(value=0)),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=keys[idx])]
                ),
                body=[body_node,
                      ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=nxt), lineno=None)],
                orelse=[]
            ))
        junk = ExceptionJumpUtils.generate_junk(ex_name, 0xFFFFFFF)
        case.body[0].handlers[0].body.extend(junk)
        random.shuffle(case.body[0].handlers[0].body)
        body.append(case)
        return body

    def generate_block(node):
        old_body = node.body
        node.body = []
        var_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        ex_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        case = ast.While(
            test=ast.Compare(left=ast.Name(id=var_name), ops=[ast.NotEq()], comparators=[ast.Constant(value=1)]),
            body=[
                ast.Try(
                    body=[ast.Raise(exc=ast.Call(func=ast.Name(id='VELIMATIX'), args=[ast.Name(id=var_name)], keywords=[]))],
                    handlers=[ast.ExceptHandler(type=ast.Name(id='VELIMATIX'), name=ex_name, body=[])],
                    orelse=[], finalbody=[]
                )
            ], orelse=[]
        )
        decls = []
        flow_stmts = []
        # FIX (correctness): ast.Nonlocal hoisted to function top alongside Global -
        # relocating a nonlocal declaration inside try>handler>if is scoping-unsafe
        # (lesson source: ObfuXtreme BLOCKED-set analysis, research_repos).
        for body_node in old_body:
            if isinstance(body_node, (ast.Global, ast.Nonlocal)):
                decls.append(body_node)
            else:
                flow_stmts.append(body_node)
        if not flow_stmts:
            node.body = old_body
            return node
        keys = ExceptionJumpUtils._sparse_keys(len(flow_stmts))
        sentinel = max(keys) + _trx_rand(0xFFFF) + 17
        node.body.append(ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=keys[0]), lineno=None))
        case.body[0] = ast.Try(
            body=[ast.Raise(exc=ast.Call(func=ast.Name(id='VELIMATIX'), args=[ast.Name(id=var_name)], keywords=[]))],
            handlers=[ast.ExceptHandler(type=ast.Name(id='VELIMATIX'), name=ex_name, body=[])],
            orelse=[], finalbody=[]
        )
        case.test = ast.Compare(left=ast.Name(id=var_name), ops=[ast.NotEq()], comparators=[ast.Constant(value=sentinel)])
        for idx, body_node in enumerate(flow_stmts):
            nxt = keys[idx + 1] if idx + 1 < len(keys) else sentinel
            case.body[0].handlers[0].body.append(ast.If(
                test=ast.Compare(
                    left=ast.Subscript(value=ast.Attribute(value=ast.Name(id=ex_name), attr='args'), slice=ast.Constant(value=0)),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=keys[idx])]
                ),
                body=[body_node,
                      ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=nxt), lineno=None)],
                orelse=[]
            ))
        junk = ExceptionJumpUtils.generate_junk(ex_name, 0xFFFFFFF)
        case.body[0].handlers[0].body.extend(junk)
        random.shuffle(case.body[0].handlers[0].body)
        node.body.append(case)
        for decl in decls:
            node.body.insert(0, decl)
        return node


class ExceptionJumpTransformer():
    def __init__(self, alphabet: str, length: int):
        ExceptionJumpUtils.alphabet = alphabet
        ExceptionJumpUtils.length = length

    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        renamer = ExceptionJumpTransformer._ExceptionJumpInner()
        self.tree = renamer.visit(self.tree)
        return self.tree

    class _ExceptionJumpInner(ast.NodeTransformer):
        @staticmethod
        def _has_break_or_continue(node) -> bool:
            for child in ast.walk(node):
                if isinstance(child, (ast.Break, ast.Continue)):
                    return True
            return False

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef):
            # Skip if contains yield, yield from, or await (coroutine/generator)
            for child in ast.walk(node):
                if isinstance(child, (ast.Yield, ast.YieldFrom, ast.Await)):
                    return node
            if self._has_break_or_continue(node):
                return node
            node = ExceptionJumpUtils.generate_block(node)
            return node

        def visit_If(self, node: ast.If):
            if self._has_break_or_continue(node):
                return node
            node = ExceptionJumpUtils.generate_block(node)
            return node

        def visit_Assign(self, node: ast.Assign):
            if self._has_break_or_continue(node):
                return node
            node = ExceptionJumpUtils.generate_blockV([node])
            return node


class ControlFlowUtils:
    alphabet, length = "", 16

    def generate_junk_controlflow_block(maps, max_val, node: ast.FunctionDef):
        cases = []
        for i in range(random.randint(0, 3)):
            num = random.randint(1, max_val)
            attempts = 0
            while num in maps and attempts < 100:
                num = random.randint(1, max_val)
                attempts += 1
            case_name = Utils.randomize_name(ControlFlowUtils.alphabet, ControlFlowUtils.length)
            _junk_const = ast.Constant(value=num)
            _junk_const._no_mutate = True
            case = ast.match_case(
                pattern=ast.MatchValue(value=_junk_const),
                body=[ast.Assign(targets=[ast.Name(id=case_name)], value=ast.Constant(value=random.randint(0xFFFFF, 0xFFFFFFFFFFFF)), lineno=None)]
            )
            fixed_body = node.body
            if len(fixed_body) > 1:
                choice = random.choice(fixed_body)
                if isinstance(choice, (ast.Global, ast.Nonlocal)):
                    choice = ast.Pass()
                elif isinstance(choice, list):
                    choice = ast.Pass()
                elif isinstance(choice, ast.Expr) and isinstance(choice.value, ast.Call):
                    # Skip call expressions that might contain lambdas
                    choice = ast.Pass()
                else:
                    choice = copy.deepcopy(choice)
                case.body.append(choice)
            cases.append(case)
        return cases

    def generate_controlflow_block(node):
        old_body = node.body
        current = Utils.generate_next_num(0, 0xFFFF)
        next_num = Utils.generate_next_num(current, 0xFFFFFFFFFFFFFF)
        maps = []
        global_list = []
        turn_name = Utils.randomize_name(ControlFlowUtils.alphabet, ControlFlowUtils.length)
        base = [
            ast.Assign(targets=[ast.Name(id=turn_name)], value=ast.Constant(value=current), lineno=None),
            ast.While(
                test=ast.Compare(left=ast.Name(id=turn_name), ops=[ast.Lt()], comparators=[ast.Constant(value=0xFFFFFFFFFFFFFF + 1)]),
                body=[], orelse=[]
            )
        ]
        new_base = ast.Match(subject=ast.Name(id=turn_name), cases=[])
        for body_node in old_body:
            if isinstance(body_node, ast.Global):
                global_list.append(body_node)
                continue
            pattern_const = ast.Constant(value=current)
            pattern_const._no_mutate = True
            new = ast.match_case(pattern=ast.MatchValue(value=pattern_const), body=[body_node])
            if len(old_body) > 1:
                new.body.append(ast.Assign(targets=[ast.Name(id=turn_name)], value=ast.Constant(value=next_num), lineno=None))
            new_base.cases.append(new)
            maps.append(next_num)
            current = next_num
            next_num = Utils.generate_next_num(current, 0xFFFFFFFFFFFFFFFF)
        base[1].test.comparators[0].value = next_num
        new_base.cases[len(new_base.cases) - 1].body.append(ast.Break())
        junk_cases = ControlFlowUtils.generate_junk_controlflow_block(maps + [base[0].value.value], next_num, node)
        new_base.cases.extend(junk_cases)
        random.shuffle(new_base.cases)
        base[1].body.append(new_base)
        for global_def in global_list:
            base.insert(0, global_def)
        node.body = base


class CallUtils:
    def get_object_for_letter(letter):
        objs = dir(__builtins__)
        random.shuffle(objs)
        for obj in objs:
            if letter in obj and hasattr(getattr(__builtins__, obj), '__name__') and getattr(__builtins__, obj).__name__ == obj and ('exception' in obj.lower() or 'error' in obj.lower() or '__' in obj.lower()):
                return [obj, obj.find(letter)]
        return None

    def generate_builtin_attr_block(node: ast.Call):
        name = node.func.id
        block = ast.Call(
            func=ast.Call(
                func=ast.Name(id="__import__('builtins').getattr"),
                args=[
                    ast.Name(id='__builtins__'),
                    ast.Call(func=ast.Attribute(value=ast.Constant(value=''), attr='join'), args=[ast.List(elts=[])], keywords=[])
                ], keywords=[]
            ),
            args=node.args, keywords=node.keywords
        )
        for letter in name:
            obj = CallUtils.get_object_for_letter(letter)
            if obj:
                block.func.args[1].args[0].elts.append(
                    ast.Subscript(value=ast.Attribute(value=ast.Name(id=obj[0]), attr='__name__'), slice=ast.Constant(value=obj[1]))
                )
            else:
                # Fallback: use letter directly if no builtin found
                block.func.args[1].args[0].elts.append(ast.Constant(value=letter))
        return block


class CallTransformer():
    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        call = CallTransformer._CallTransformerInner()
        self.tree = call.visit(self.tree)
        return self.tree

    class _CallTransformerInner(ast.NodeTransformer):
        SAFE_BUILTIN_CALLS = frozenset({
            'abs', 'aiter', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes',
            'callable', 'chr', 'complex', 'dict', 'divmod', 'enumerate', 'filter',
            'float', 'format', 'frozenset', 'getattr', 'hasattr', 'hash', 'hex',
            'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map', 'max',
            'min', 'next', 'oct', 'ord', 'pow', 'print', 'range', 'repr',
            'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'str', 'sum',
            'tuple', 'type', 'zip',
        })

        def visit_Call(self, node: ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ('super', 'locals', 'eval', 'exec', '__import__'):
                    return node
                is_builtin = str(node.func.id) in self.SAFE_BUILTIN_CALLS
                if is_builtin:
                    if isinstance(__builtins__, dict):
                        is_builtin = node.func.id in __builtins__
                    else:
                        is_builtin = hasattr(__builtins__, node.func.id)
                    if is_builtin:
                        return CallUtils.generate_builtin_attr_block(node)
            return node


# ═══════════════════════════════════════════════════════════════
# CONTROL FLOW FLATTENING - MATCH-CASE STATE MACHINE (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class ControlFlowTransformer():
    def __init__(self, alphabet: str, length: int):
        ControlFlowUtils.alphabet = alphabet
        ControlFlowUtils.length = length

    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        transformer = ControlFlowTransformer._Inner(self.tree)
        self.tree = transformer.visit(self.tree)
        return self.tree

    class _Inner(ast.NodeTransformer):
        def __init__(self, tree):
            self.tree = tree

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if node.name.startswith('__'):
                return node
            # Skip if contains yield, yield from, or await (coroutine/generator)
            for child in ast.walk(node):
                if isinstance(child, (ast.Yield, ast.YieldFrom, ast.Await)):
                    return node
            if len(node.body) <= 1:
                return node
            real_stmts = [n for n in node.body if not isinstance(n, (ast.Global, ast.Nonlocal))]
            if len(real_stmts) <= 1:
                return node
            try:
                ControlFlowUtils.generate_controlflow_block(node)
            except Exception:
                pass
            return node


# ═══════════════════════════════════════════════════════════════
# CONSTANT MUTATOR - XOR CHAIN + LAMBDA WRAP (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class MutatorTransformer():
    def __init__(self, alphabet: str, length: int, ladder: int = 3):
        MutatorUtils.alphabet = alphabet
        MutatorUtils.length = length
        self.ladder = ladder

    def proceed(self, tree: ast.Module):
        self.tree = tree
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        transformer = MutatorTransformer._Inner(self.ladder)
        self.tree = transformer.visit(self.tree)
        return self.tree

    class _Inner(ast.NodeTransformer):
        def __init__(self, ladder):
            self.ladder = ladder
            self._depth = 0

        def visit_Constant(self, node: ast.Constant):
            if self._depth > 0:
                return node
            # Skip if marked as no_mutate
            if getattr(node, '_no_mutate', False):
                return node
            # Skip if parent is MatchValue or match_case
            if hasattr(node, 'parent') and isinstance(node.parent, (ast.MatchValue, ast.match_case)):
                return node
            # Also skip if any ancestor is a match_case pattern
            if hasattr(node, 'parent'):
                p = node.parent
                while hasattr(p, 'parent'):
                    if isinstance(p, ast.MatchValue):
                        return node
                    if isinstance(p, ast.match_case) and hasattr(p, 'pattern'):
                        try:
                            if node in ast.walk(p.pattern):
                                return node
                        except Exception:
                            pass
                    p = p.parent
            try:
                if isinstance(node.value, bool):
                    return node
                if isinstance(node.value, int) and abs(node.value) > 0 and abs(node.value) < 0xFFFFFFF:
                    if random.random() > 0.4:
                        self._depth += 1
                        result = MutatorUtils.proceed_int_constant(node, self.ladder)
                        self._depth -= 1
                        return result
                elif isinstance(node.value, float) and abs(node.value) < 0xFFFFFFF:
                    if random.random() > 0.6:
                        self._depth += 1
                        result = MutatorUtils.proceed_float_constant(node, self.ladder)
                        self._depth -= 1
                        return result
            except Exception:
                pass
            return node


# ═══════════════════════════════════════════════════════════════
# METHOD CLONER - FAKE FUNCTION COPIES (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class MethodClonerTransformer():
    """Injects fake copies of real functions with swapped bodies"""
    def __init__(self, alphabet: str, length: int, count: int = 5):
        self.alphabet = alphabet
        self.length = length
        self.count = count

    def proceed(self, tree: ast.Module):
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node

        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith('__')]
        if len(funcs) < 1:
            return tree

        clones = []
        for _ in range(min(self.count, len(funcs) * 2)):
            source = random.choice(funcs)
            clone_name = Utils.randomize_name(self.alphabet, self.length)

            decoy_body = []
            if len(funcs) > 1:
                donor = random.choice(funcs)
                for stmt in donor.body[:random.randint(1, max(1, len(donor.body)))]:
                    try:
                        decoy_body.append(ast.parse(ast.unparse(stmt)).body[0])
                    except Exception:
                        decoy_body.append(ast.Pass())
            if not decoy_body:
                decoy_body = [ast.Pass()]

            junk_var = Utils.randomize_name(self.alphabet, self.length)
            decoy_body.insert(0, ast.Assign(
                targets=[ast.Name(id=junk_var)],
                value=ast.BinOp(
                    left=ast.Constant(value=random.randint(0, 0xFFFFFF)),
                    op=random.choice([ast.BitXor(), ast.Add(), ast.Sub()]),
                    right=ast.Constant(value=random.randint(0, 0xFFFFFF))
                ), lineno=None
            ))

            clone = ast.FunctionDef(
                name=clone_name,
                args=ast.arguments(
                    posonlyargs=[], args=[ast.arg(arg=Utils.randomize_name(self.alphabet, 8)) for _ in range(random.randint(0, 3))],
                    kwonlyargs=[], kw_defaults=[], defaults=[]
                ),
                body=decoy_body,
                decorator_list=[],
                returns=None,
                lineno=None
            )
            clones.append(clone)

        for clone in clones:
            pos = random.randint(0, len(tree.body))
            tree.body.insert(pos, clone)

        return tree


# ═══════════════════════════════════════════════════════════════
# BUILTIN RENAMER - OBFUSCATE ALL BUILTIN REFERENCES (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class BuiltinRenamerTransformer():
    """Rename ALL builtin references to random names with runtime mapping"""

    EXTRA_BUILTINS = [
        'sum', 'sorted', 'round', 'repr', 'pow', 'oct', 'next', 'min', 'max',
        'iter', 'issubclass', 'id', 'hash', 'hasattr', 'format',
        'divmod', 'delattr', 'breakpoint', 'bin', 'ascii', 'any', 'all',
        'abs', 'hex', 'reversed', 'quit', 'exit', 'enumerate', 'compile',
        'globals', 'float', 'frozenset', 'filter', 'complex', 'classmethod',
        'staticmethod', 'property', 'object', 'memoryview', 'zip',
        'slice', 'set', 'tuple', 'dict', 'open', 'list',
        'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
        'AttributeError', 'ImportError', 'RuntimeError', 'StopIteration',
        'FileNotFoundError', 'PermissionError', 'OSError', 'IOError',
        'NameError', 'SyntaxError', 'ZeroDivisionError', 'OverflowError',
        'UnicodeDecodeError', 'UnicodeEncodeError', 'ModuleNotFoundError',
        'KeyboardInterrupt', 'SystemExit', 'EOFError', 'NotImplementedError',
        'RecursionError', 'MemoryError', 'ConnectionError', 'TimeoutError',
    ]

    def __init__(self, alphabet: str, length: int):
        self.alphabet = alphabet
        self.length = length
        self.mapping = {}

    def proceed(self, tree: ast.Module):
        for builtin_name in self.EXTRA_BUILTINS:
            try:
                if isinstance(__builtins__, dict):
                    exists = builtin_name in __builtins__
                else:
                    exists = hasattr(__builtins__, builtin_name)
                if exists:
                    # Verify builtin actually exists before mapping
                    try:
                        if isinstance(__builtins__, dict):
                            _ = __builtins__[builtin_name]
                        else:
                            _ = getattr(__builtins__, builtin_name)
                        self.mapping[builtin_name] = Utils.randomize_name(self.alphabet, self.length)
                    except Exception:
                        pass
            except Exception:
                continue

        bound_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(getattr(node, 'ctx', None), (ast.Store, ast.Del)):
                bound_names.add(node.id)
            elif isinstance(node, ast.arg):
                bound_names.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound_names.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    bound_names.add((alias.asname or alias.name).split('.')[0])
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound_names.add(node.name)
            elif isinstance(node, ast.NamedExpr):
                bound_names.add(node.target.id)
            elif isinstance(node, ast.Global) or isinstance(node, ast.Nonlocal):
                bound_names.update(node.names)
        for shadowed in list(self.mapping.keys()):
            if shadowed in bound_names:
                del self.mapping[shadowed]

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(getattr(node, 'ctx', None), ast.Load) and node.id in self.mapping:
                node.id = self.mapping[node.id]

        xor_key = _trx_rand(200) + 55
        setup_stmts = []
        for original, renamed in self.mapping.items():
            try:
                # Verify builtin actually exists before generating code
                if isinstance(__builtins__, dict):
                    _ = __builtins__[original]
                else:
                    _ = getattr(__builtins__, original)
                enc_bytes = [b ^ xor_key for b in original.encode('utf-8')]
                # Dynamic stealth resolver with zero plaintext string literals
                res_expr = f"{renamed} = getattr(__import__('builtins'), bytes([_b ^ {xor_key} for _b in {enc_bytes}]).decode('utf-8'))"
                stmt = ast.parse(res_expr).body[0]
                setup_stmts.append(stmt)
                if "_DEBUG_MAP" in globals():
                    _DEBUG_MAP["renamed_builtins"][original] = renamed
            except (KeyError, AttributeError):
                # Remove from mapping if builtin doesn't actually exist
                continue

        # Inject Decoy Trap Builtin variables (anti-analysis honeypots)
        decoy_names = ['_sys_guard', '_eval_lock', '_mem_sec', '_debug_trap', '_ast_sig']
        for dname in decoy_names:
            rand_trap_id = Utils.randomize_name(self.alphabet, self.length)
            decoy_expr = f"{rand_trap_id} = (lambda *a, **k: None)"
            setup_stmts.append(ast.parse(decoy_expr).body[0])

        random.shuffle(setup_stmts)
        tree.body = setup_stmts + tree.body
        return tree


# ═══════════════════════════════════════════════════════════════
# NUMBER-THEORETIC MATHEMATICAL OPAQUE PREDICATES (MODULE B)
# ═══════════════════════════════════════════════════════════════

class MathOpaqueTransformer(ast.NodeTransformer):
    """Injects number-theoretic opaque invariants (Quadratic Non-Residues mod 7, Coprimality, Euler) to force path explosion in symbolic execution / SMT solvers (TRX-AST-B4/FEAT-002)."""

    def __init__(self, alphabet: str = None, length: int = 12):
        self.alphabet = alphabet or string.ascii_lowercase
        self.length = length

    def _gen_opaque_true_test(self) -> ast.AST:
        """Generates an expression that is mathematically proven to be ALWAYS TRUE at runtime.

        Predicate families (7): QNR mod 7, Fermat/Euler k^3-k, n(n+1) parity,
        Carmichael composites (Fermat pseudoprime for ALL bases), MBA bitwise
        identity (x+y == (x^y)+2(x&y)), Collatz odd-step parity, modular inverse
        via Fermat little theorem. Family breadth modeled after the opaque-predicate
        library in bedrock-obfuscator (Apache-2.0, research note); implementation
        here is independent.
        """
        pick = _trx_rand(7)
        if pick == 0:
            x_val = _trx_rand(1000) + 11
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=x_val), op=ast.Mult(), right=ast.Constant(value=x_val)),
                    op=ast.Mod(),
                    right=ast.Constant(value=7)
                ),
                ops=[ast.NotEq()],
                comparators=[ast.Constant(value=3)]
            )
        elif pick == 1:
            k_val = _trx_rand(500) + 13
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=3)),
                        op=ast.Sub(),
                        right=ast.Constant(value=k_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=6)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        elif pick == 2:
            n_val = _trx_rand(500) + 9
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.Constant(value=n_val),
                        op=ast.Mult(),
                        right=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Add(), right=ast.Constant(value=1))
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=2)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        elif pick == 3:
            # Carmichael number: a^n ≡ a (mod n) holds for EVERY integer a when n
            # is a Carmichael composite (561, 1105, 1729, 2465, 2821, 6601).
            carmichael = (561, 1105, 1729, 2465, 2821, 6601)[_trx_rand(6)]
            base = _trx_rand(97) + 2
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=base), op=ast.Pow(), right=ast.Constant(value=carmichael)),
                        op=ast.Sub(),
                        right=ast.Constant(value=base)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=carmichael)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        elif pick == 4:
            # MBA identity: (x ^ y) + ((x & y) << 1) == x + y for all non-negative ints.
            a = _trx_rand(0xFFFFF) + 7
            b = _trx_rand(0xFFFFF) + 3
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=a), op=ast.BitXor(), right=ast.Constant(value=b)),
                    op=ast.Add(),
                    right=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=a), op=ast.BitAnd(), right=ast.Constant(value=b)),
                        op=ast.LShift(),
                        right=ast.Constant(value=1)
                    )
                ),
                ops=[ast.Eq()],
                comparators=[ast.BinOp(left=ast.Constant(value=a), op=ast.Add(), right=ast.Constant(value=b))]
            )
        elif pick == 5:
            # Collatz odd step: for any odd m, (3m + 1) is even.
            m = 2 * (_trx_rand(9999) + 1) + 1
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=m), op=ast.Mult(), right=ast.Constant(value=3)),
                        op=ast.Add(),
                        right=ast.Constant(value=1)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=2)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        else:
            # Modular inverse via Fermat's little theorem: a * a^(p-2) ≡ 1 (mod p), p prime.
            p = (101, 103, 107, 109, 113, 127, 131, 137, 139, 149)[_trx_rand(10)]
            inv_a = _trx_rand(p - 2) + 2
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.Constant(value=inv_a),
                        op=ast.Mult(),
                        right=ast.BinOp(left=ast.Constant(value=inv_a), op=ast.Pow(), right=ast.Constant(value=p - 2))
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=p)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=1)]
            )

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        if node.name.startswith("__") or len(node.body) < 2:
            return node
        
        new_body = []
        for stmt in node.body:
            if _trx_rand(100) < 60 and not isinstance(stmt, (ast.Return, ast.Yield, ast.YieldFrom, ast.Global, ast.Nonlocal, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                bogus_var = rd('biopaque')
                bogus_stmt = ast.Assign(
                    targets=[ast.Name(id=bogus_var)],
                    value=ast.BinOp(
                        left=ast.Constant(value=_trx_rand(0xFFFFFF)),
                        op=ast.BitXor(),
                        right=ast.Constant(value=_trx_rand(0xFFFFFF))
                    ),
                    lineno=None
                )
                wrapped_if = ast.If(
                    test=self._gen_opaque_true_test(),
                    body=[stmt],
                    orelse=[bogus_stmt]
                )
                ast.copy_location(wrapped_if, stmt)
                ast.fix_missing_locations(wrapped_if)
                new_body.append(wrapped_if)
            else:
                new_body.append(stmt)
        node.body = new_body
        return node

def _math_opaque_obf(code_str: str) -> str:
    """Apply Number-Theoretic Mathematical Opaque Predicates to code."""
    tree = ast.parse(code_str)
    transformer = MathOpaqueTransformer()
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# ═══════════════════════════════════════════════════════════════
# DYNAMIC PER-CALLSITE STRING XOR ENCRYPTION (MODULE C)
# ═══════════════════════════════════════════════════════════════

class DynamicStringXORTransformer(ast.NodeTransformer):
    """Replaces string literals with dynamic per-callsite XOR decryption expressions derived from AST coordinates (TRX-AST-B3/FEAT-003)."""

    def __init__(self, master_seed: int = None):
        self.master_seed = master_seed or (_trx_rand(0x7FFFFFFF) + 1000)
        self.protected_ids = set()

    @staticmethod
    def _collect_docstrings(tree) -> set:
        protected = set()
        for anc in ast.walk(tree):
            if isinstance(anc, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(anc, 'body', [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    protected.add(id(body[0].value))
        return protected

    def visit_JoinedStr(self, node: ast.JoinedStr):
        # Do not descend into f-string expressions: pre-3.12 unparse cannot safely
        # re-nest quotes when string constants become Lambda calls (PEP 701 gate).
        return node

    def visit_match_case(self, node: ast.match_case):
        # In Python 3.10+, match patterns cannot contain Call/Lambda expressions
        for child in ast.walk(node.pattern):
            self.protected_ids.add(id(child))
        if node.guard:
            node.guard = self.visit(node.guard)
        node.body = [self.visit(stmt) for stmt in node.body]
        return node

    @staticmethod
    def _make_int_algebra_expr(value: int, site_key: int) -> ast.BinOp:
        """Exact integer reconstruction via (a ^ b) + c where c = value - (a ^ b).
        Strategy source: pyshield passes/constants.py int tiers (MIT, research note)."""
        a = (site_key % 0x7F) + 1
        b = ((site_key >> 7) % 0x7F) + 1
        c = value - (a ^ b)
        return ast.BinOp(
            left=ast.BinOp(left=ast.Constant(value=a), op=ast.BitXor(), right=ast.Constant(value=b)),
            op=ast.Add(),
            right=ast.Constant(value=c)
        )

    def _build_bytes_decode_lambda(self, payload_expr: ast.expr, elt_builder) -> ast.Call:
        """Shared anonymous-decoder shell: lambda s: bytes(<genexp over enumerate(s)>).decode('utf-8')."""
        v_s = _rd()
        v_i = _rd()
        v_b = _rd()
        return ast.Call(
            func=ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=v_s)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=ast.Call(
                    func=ast.Attribute(
                        value=ast.Call(
                            func=ast.Name(id='bytes'),
                            args=[
                                ast.ListComp(
                                    elt=elt_builder(v_i, v_b),
                                    generators=[
                                        ast.comprehension(
                                            target=ast.Tuple(elts=[ast.Name(id=v_i), ast.Name(id=v_b)]),
                                            iter=ast.Call(func=ast.Name(id='enumerate'), args=[ast.Name(id=v_s)], keywords=[]),
                                            ifs=[], is_async=0
                                        )
                                    ]
                                )
                            ],
                            keywords=[]
                        ),
                        attr='decode'
                    ),
                    args=[ast.Constant(value='utf-8')],
                    keywords=[]
                )
            ),
            args=[payload_expr],
            keywords=[]
        )

    def visit_Constant(self, node: ast.Constant):
        if id(node) in self.protected_ids:
            return node
        # Exact float -> integer-ratio reconstruction. Source: pyshield
        # ConstantTransformer Fraction idea (MIT), hardened: Python floats carry an
        # EXACT rational via as_integer_ratio(), so n / d reproduces the ORIGINAL
        # float bit-for-bit (no limit_denominator approximation drift).
        if isinstance(node.value, float) and not isinstance(node.value, bool):
            try:
                ratio_n, ratio_d = node.value.as_integer_ratio()
            except (OverflowError, ValueError):
                return node
            if abs(ratio_n) < (1 << 62) and ratio_d.bit_length() <= 62 and ratio_d != 0:
                lineno_f = getattr(node, 'lineno', 1) or 1
                col_f = getattr(node, 'col_offset', 0) or 0
                fkey = (self.master_seed ^ (lineno_f * 31337) ^ (col_f * 101) ^ 0xF70A7) & 0xFFFFFFFF
                num_expr = self._make_int_algebra_expr(ratio_n, fkey)
                den_expr = self._make_int_algebra_expr(ratio_d, (fkey ^ 0x5A5A5A) & 0xFFFFFFFF)
                div_expr = ast.BinOp(left=num_expr, op=ast.Div(), right=den_expr)
                ast.copy_location(div_expr, node)
                ast.fix_missing_locations(div_expr)
                return div_expr
            return node
        if isinstance(node.value, str) and len(node.value) > 0:
            if (node.value.startswith("__") and node.value.endswith("__")) or len(node.value) > 20000:
                return node
            
            val_bytes = node.value.encode('utf-8')
            lineno = getattr(node, 'lineno', 1) or 1
            col_offset = getattr(node, 'col_offset', 0) or 0
            
            site_key = (self.master_seed ^ (lineno * 31337) ^ (col_offset * 101) ^ len(val_bytes)) & 0xFFFFFFFF

            # Weighted per-callsite cipher heterogeneity - source: pyshield
            # DistributedStringEncryptor dispatcher (MIT, research note): three
            # structurally distinct inline schemes so no single deobfuscation
            # pattern can sweep every callsite.
            strat_pick = site_key % 100
            if strat_pick < 50:
                strategy = 'coord_xor'      # legacy rolling coordinate keystream
            elif strat_pick < 75:
                strategy = 'poly_affine'    # enc[i] = (b + salt*(i+1)) mod 256
            else:
                strategy = 'chunked_xor'    # single-key XOR + randomized chunk split

            if strategy == 'coord_xor':
                enc_bytes = bytearray()
                for idx, b in enumerate(val_bytes):
                    k_byte = (site_key + idx * 31337 + (idx ^ 0x5A)) & 0xFF
                    enc_bytes.append(b ^ k_byte)
                
                enc_bytes_list = list(enc_bytes)
                
                v_s = _rd()
                v_k = _rd()
                v_i = _rd()
                v_b = _rd()
                
                dec_expr = ast.Call(
                    func=ast.Lambda(
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg=v_s), ast.arg(arg=v_k)],
                            kwonlyargs=[], kw_defaults=[], defaults=[]
                        ),
                        body=ast.Call(
                            func=ast.Attribute(
                                value=ast.Call(
                                    func=ast.Name(id='bytes'),
                                    args=[
                                        ast.ListComp(
                                            elt=ast.BinOp(
                                                left=ast.Name(id=v_b),
                                                op=ast.BitXor(),
                                                right=ast.BinOp(
                                                    left=ast.BinOp(
                                                        left=ast.BinOp(
                                                            left=ast.Name(id=v_k),
                                                            op=ast.Add(),
                                                            right=ast.BinOp(left=ast.Name(id=v_i), op=ast.Mult(), right=ast.Constant(value=31337))
                                                        ),
                                                        op=ast.Add(),
                                                        right=ast.BinOp(left=ast.Name(id=v_i), op=ast.BitXor(), right=ast.Constant(value=90))
                                                    ),
                                                    op=ast.BitAnd(),
                                                    right=ast.Constant(value=255)
                                                )
                                            ),
                                            generators=[
                                                ast.comprehension(
                                                    target=ast.Tuple(elts=[ast.Name(id=v_i), ast.Name(id=v_b)]),
                                                    iter=ast.Call(func=ast.Name(id='enumerate'), args=[ast.Name(id=v_s)], keywords=[]),
                                                    ifs=[],
                                                    is_async=0
                                                )
                                            ]
                                        )
                                    ],
                                    keywords=[]
                                ),
                                attr='decode'
                            ),
                            args=[ast.Constant(value='utf-8')],
                            keywords=[]
                        )
                    ),
                    args=[
                        ast.Call(func=ast.Name(id='bytes'), args=[ast.List(elts=[ast.Constant(value=x) for x in enc_bytes_list])], keywords=[]),
                        ast.Constant(value=site_key)
                    ],
                    keywords=[]
                )
                ast.copy_location(dec_expr, node)
                ast.fix_missing_locations(dec_expr)
                return dec_expr

            if strategy == 'poly_affine':
                salt = (site_key % 127) + 1
                enc_list = [(b + salt * (i + 1)) % 256 for i, b in enumerate(val_bytes)]
                payload = ast.Call(func=ast.Name(id='bytes'),
                                   args=[ast.List(elts=[ast.Constant(value=x) for x in enc_list])],
                                   keywords=[])

                def _unshift(i_name, b_name):
                    return ast.BinOp(
                        left=ast.BinOp(
                            left=ast.Name(id=b_name),
                            op=ast.Sub(),
                            right=ast.BinOp(
                                left=ast.Constant(value=salt),
                                op=ast.Mult(),
                                right=ast.BinOp(left=ast.Name(id=i_name), op=ast.Add(), right=ast.Constant(value=1))
                            )
                        ),
                        op=ast.Mod(),
                        right=ast.Constant(value=256)
                    )

                dec_expr = self._build_bytes_decode_lambda(payload, _unshift)
                ast.copy_location(dec_expr, node)
                ast.fix_missing_locations(dec_expr)
                return dec_expr

            # chunked_xor
            kb = ((site_key >> 7) & 0xFF) or 0x5B
            enc_full = bytes(b ^ kb for b in val_bytes)
            n_chunks = 2 + (site_key % 4)
            if len(enc_full) <= n_chunks:
                chunks = [enc_full]
            else:
                bounds = set()
                lcg = site_key | 1
                attempts = 0
                while len(bounds) < n_chunks - 1 and attempts < 64:
                    attempts += 1
                    lcg = (lcg * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
                    bounds.add((lcg >> 33) % (len(enc_full) - 1) + 1)
                cuts = [0] + sorted(bounds) + [len(enc_full)]
                chunks = [enc_full[cuts[k]:cuts[k + 1]] for k in range(len(cuts) - 1)]
            chunk_nodes = []
            for ch in chunks:
                if not ch:
                    continue
                chunk_nodes.append(ast.Call(func=ast.Name(id='bytes'),
                                            args=[ast.List(elts=[ast.Constant(value=x) for x in ch])],
                                            keywords=[]))
            if not chunk_nodes:
                chunk_nodes.append(ast.Call(func=ast.Name(id='bytes'),
                                            args=[ast.List(elts=[])], keywords=[]))
            joined = chunk_nodes[0]
            for extra in chunk_nodes[1:]:
                joined = ast.BinOp(left=joined, op=ast.Add(), right=extra)

            def _unxor(i_name, b_name):
                return ast.BinOp(
                    left=ast.Name(id=b_name),
                    op=ast.BitXor(),
                    right=ast.Constant(value=kb)
                )

            dec_expr = self._build_bytes_decode_lambda(joined, _unxor)
            ast.copy_location(dec_expr, node)
            ast.fix_missing_locations(dec_expr)
            return dec_expr
        return node

def _dyn_strings_obf(code_str: str, seed: int = None) -> str:
    """Apply Dynamic Per-Callsite String XOR Encryption."""
    tree = ast.parse(code_str)
    transformer = DynamicStringXORTransformer(master_seed=seed)
    transformer.protected_ids = transformer._collect_docstrings(tree)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# ═══════════════════════════════════════════════════════════════
# BEDROCK-GRADE DECOMPILER TRAP & SECRET SHARING ENGINES
# ═══════════════════════════════════════════════════════════════

def _ast_touches_exception_frames(node: ast.AST) -> bool:
    """Eligibility sniff (source: bedrock-obfuscator UnsupportedOpcode gates,
    Apache-2.0 research note): True when the subtree produces CPython exception
    tables / frame setup at bytecode level. Conservative transforms skip these
    units - silent wrong output is strictly worse than skipping a transform."""
    for child in ast.walk(node):
        if isinstance(child, (ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith)):
            return True
        if hasattr(ast, 'TryStar') and isinstance(child, ast.TryStar):
            return True
    return False


class DecompilerTrapTransformer(ast.NodeTransformer):
    """Wraps AST statement blocks in opaque mathematical predicates and overlapping trap structures that break decompilers (uncompyle6/decompyle3/pycdc)."""

    def __init__(self, density: float = 0.5, seed: int = None):
        self.density = density
        self.rng = random.Random(seed or _trx_rand(0x7FFFFFFF))

    def _make_opaque_true(self):
        n_val = self.rng.randint(2, 9999)
        inv_type = self.rng.randint(0, 2)
        if inv_type == 0:
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Pow(), right=ast.Constant(value=2)),
                        op=ast.Add(),
                        right=ast.Constant(value=n_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=2)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        elif inv_type == 1:
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Pow(), right=ast.Constant(value=3)),
                        op=ast.Sub(),
                        right=ast.Constant(value=n_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=3)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            )
        else:
            return ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=n_val), op=ast.Pow(), right=ast.Constant(value=2)),
                    op=ast.Add(),
                    right=ast.Constant(value=1)
                ),
                ops=[ast.Gt()],
                comparators=[ast.Constant(value=0)]
            )

    def _make_dead_trap_body(self):
        v_tmp = f"_trap_{self.rng.randint(1000, 99999)}"
        return [
            ast.While(
                test=ast.Constant(value=False),
                body=[
                    ast.Assign(targets=[ast.Name(id=v_tmp, ctx=ast.Store())], value=ast.Constant(value=0xDEADBEEF)),
                    ast.Expr(value=ast.Call(func=ast.Name(id="exit", ctx=ast.Load()), args=[ast.Constant(value=1)], keywords=[])),
                    ast.Break()
                ],
                orelse=[]
            )
        ]

    def _wrap_stmts(self, stmts):
        new_stmts = []
        for stmt in stmts:
            if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Global, ast.Nonlocal)):
                new_stmts.append(self.visit(stmt))
            elif self.rng.random() < self.density and not isinstance(stmt, (ast.Return, ast.Yield, ast.YieldFrom, ast.Break, ast.Continue)):
                trap_if = ast.If(
                    test=self._make_opaque_true(),
                    body=[self.visit(stmt)],
                    orelse=self._make_dead_trap_body()
                )
                ast.copy_location(trap_if, stmt)
                new_stmts.append(trap_if)
            else:
                new_stmts.append(self.visit(stmt))
        return new_stmts

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Eligibility gate: leave exception-table-producing functions untouched.
        if _ast_touches_exception_frames(node):
            return node
        node.body = self._wrap_stmts(node.body)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if _ast_touches_exception_frames(node):
            return node
        node.body = self._wrap_stmts(node.body)
        return node

    def visit_Module(self, node: ast.Module):
        node.body = self._wrap_stmts(node.body)
        return node

def _dec_trap_obf(code_str: str, density: float = 0.5, seed: int = None) -> str:
    """Apply Decompiler Control Flow Trapping Matrix."""
    tree = ast.parse(code_str)
    transformer = DecompilerTrapTransformer(density=density, seed=seed)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


class VariableSplittingTransformer(ast.NodeTransformer):
    """Splits local integer assignments into XOR secret shares (s1 ^ s2) dynamically inside functions."""

    def __init__(self, seed: int = None):
        self.rng = random.Random(seed or _trx_rand(0x7FFFFFFF))

    def visit_Assign(self, node: ast.Assign):
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) 
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, int) 
                and not isinstance(node.value.value, bool)
                and not node.targets[0].id.startswith("__")):
            val = node.value.value
            mask = self.rng.randint(1, 0xFFFFFF)
            s1 = mask
            s2 = val ^ mask
            node.value = ast.BinOp(
                left=ast.Constant(value=s1),
                op=ast.BitXor(),
                right=ast.Constant(value=s2)
            )
            return node
        return self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if (isinstance(node.value, ast.Constant) and isinstance(node.value.value, int)
                and not isinstance(node.value.value, bool)):
            val = node.value.value
            mask = self.rng.randint(1, 0xFFFFFF)
            s1 = mask
            s2 = val ^ mask
            node.value = ast.BinOp(
                left=ast.Constant(value=s1),
                op=ast.BitXor(),
                right=ast.Constant(value=s2)
            )
            return node
        return self.generic_visit(node)

def _var_split_obf(code_str: str, seed: int = None) -> str:
    """Apply Integer Variable Secret Sharing Transformation."""
    tree = ast.parse(code_str)
    transformer = VariableSplittingTransformer(seed=seed)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


class StringFragmentationTransformer(ast.NodeTransformer):
    """Fragments string literals >= 6 chars into XOR-encrypted pools with decoys and dynamic assembly (strfrag2)."""

    def __init__(self, seed: int = None):
        self.rng = random.Random(seed or _trx_rand(0x7FFFFFFF))
        self.key1 = self.rng.randint(1, 254)
        self.key2 = self.rng.randint(1, 254)
        self.fn_name = rd('biopaque')
        self.pool_name = rd('state_machine')
        self.final_pool = []
        self.protected_ids = set()

    def _xor_bytes(self, b_data: bytes, k: int) -> bytes:
        return bytes(b ^ k for b in b_data)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        return node

    @staticmethod
    def _collect_protected(tree) -> set:
        protected = set()
        for anc in ast.walk(tree):
            if isinstance(anc, ast.match_case):
                for child in ast.walk(anc.pattern):
                    protected.add(id(child))
            elif isinstance(anc, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(anc, 'body', [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    protected.add(id(body[0].value))
        return protected

    def _transform_string(self, node: ast.Constant):
        if isinstance(node.value, str) and len(node.value) >= 6 and not (node.value.startswith("__") and node.value.endswith("__")) and len(node.value) < 10000:
            raw_bytes = node.value.encode("utf-8")
            chunk_size = max(2, len(raw_bytes) // 3)
            chunks = [raw_bytes[i:i + chunk_size] for i in range(0, len(raw_bytes), chunk_size)]

            chunk_indices = []
            for ch in chunks:
                enc_ch = self._xor_bytes(ch, self.key1)
                idx = len(self.final_pool)
                self.final_pool.append(enc_ch)
                chunk_indices.append(idx ^ self.key2)

            call_expr = ast.Call(
                func=ast.Name(id=self.fn_name, ctx=ast.Load()),
                args=[
                    ast.List(elts=[ast.Constant(value=i) for i in chunk_indices], ctx=ast.Load()),
                    ast.Constant(value=self.key1)
                ],
                keywords=[]
            )
            return ast.copy_location(call_expr, node)
        return node

    def visit_match_case(self, node: ast.match_case):
        for child in ast.walk(node.pattern):
            self.protected_ids.add(id(child))
        node.body = [self.visit(stmt) for stmt in node.body]
        if node.guard is not None:
            node.guard = self.visit(node.guard)
        return node

    def visit_Constant(self, node: ast.Constant):
        if id(node) in self.protected_ids:
            return node
        return self._transform_string(node)

    def build_preamble(self) -> str:
        if not self.final_pool:
            return ""
        n_decoys = max(3, len(self.final_pool) // 3)
        for _ in range(n_decoys):
            decoy = bytes(self.rng.randint(0, 255) for _ in range(self.rng.randint(2, 8)))
            self.final_pool.append(self._xor_bytes(decoy, self.key1))

        pool_repr = "[" + ", ".join(repr(c) for c in self.final_pool) + "]"
        return f"""
{self.pool_name} = {pool_repr}
def {self.fn_name}(idxs, k):
    res = bytearray()
    for _i in idxs:
        chunk = {self.pool_name}[_i ^ {self.key2}]
        res.extend(b ^ k for b in chunk)
    return res.decode('utf-8', 'replace')
"""

def _str_frag_obf(code_str: str, seed: int = None) -> str:
    """Apply String Fragmentation and Dynamic Assembly."""
    tree = ast.parse(code_str)
    transformer = StringFragmentationTransformer(seed=seed)
    transformer.protected_ids = transformer._collect_protected(tree)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    preamble = transformer.build_preamble()
    res_code = ast.unparse(tree)
    if preamble.strip():
        lines = res_code.split("\n")
        insert_at = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("from __future__ import"):
                insert_at = i + 1
            elif insert_at == 0 and (stripped.startswith("#") or stripped == ""):
                continue
            elif insert_at == 0:
                break
        lines.insert(insert_at, preamble.strip())
        return "\n".join(lines)
    return res_code

def _generate_debug_poison_shield() -> str:
    """Generate Deceptive Poison State Machine shield (Bedrock-grade silent degradation)."""
    fn_name = rd('state_machine')
    return f"""
# ═══ DECEPTIVE DEBUG POISON STATE MACHINE ═══
__trx_poison_state__ = [0]
def __trx_poison(weight, tag):
    global __trx_poison_state__
    _mix = int.from_bytes(__import__('hashlib').sha256(str(tag).encode()).digest()[:4], 'big')
    __trx_poison_state__[0] = ((__trx_poison_state__[0] << 5) ^ _mix ^ (weight * 0x45D9F3B)) & 0xFFFFFFFF

def {fn_name}():
    import sys
    if getattr(sys, 'gettrace', None) and sys.gettrace():
        __trx_poison(9, 'debugger_trace')
    if hasattr(sys, 'monitoring'):
        try:
            _mon = sys.monitoring
            for _tid in (1, 2, 3, 4, 5):
                if _mon.get_tool(_tid) is not None:
                    __trx_poison(8, 'sys_monitoring')
                    break
        except Exception:
            pass
try:
    {fn_name}()
except Exception:
    pass
"""

def _generate_spoof_meta_shield(target_module: str = "<frozen importlib._bootstrap>") -> str:
    """Generate Metadata Spoofing & Signature Debranding shield."""
    fn_name = rd('guard')
    return f"""
# ═══ METADATA SPOOFING & SIGNATURE DEBRANDING ═══
def {fn_name}():
    import sys
    try:
        if '__file__' in globals():
            globals()['__file__'] = '{target_module}'
        if __name__ in sys.modules:
            sys.modules[__name__].__file__ = '{target_module}'
    except Exception:
        pass
try:
    {fn_name}()
except Exception:
    pass
"""


# ═══════════════════════════════════════════════════════════════
# IN-MEMORY ANTI-DUMP & GC OBJECT SCRUBBING (MODULE D)
# ═══════════════════════════════════════════════════════════════

def _generate_anti_dump_shield() -> str:
    """Generate in-memory anti-dump shield, GC object scrubber, and code object metadata neutralizer (TRX-DEOB-009/FEAT-004)."""
    fn_name = rd('state_machine')
    abort_fn = rd('guard')
    
    return f'''
# ═══ IN-MEMORY ANTI-DUMP & GC SCANNER SCRUBBER ═══
def {fn_name}():
    import sys, gc, types, os

    def {abort_fn}():
        try:
            os._exit(1)
        except Exception:
            sys.exit(1)

    # 1. Neutralize / Filter gc.get_objects to hide code objects and frames from heap dumpers
    try:
        _orig_get_objects = gc.get_objects
        def _safe_get_objects():
            _objs = _orig_get_objects()
            return [_o for _o in _objs if not isinstance(_o, (types.CodeType, types.FrameType))]
        gc.get_objects = _safe_get_objects
    except Exception:
        pass

    # 2. Linux prctl(PR_SET_DUMPABLE, 0) to prevent /proc/pid/mem dumping & gdb attach
    if os.name == 'posix':
        try:
            import ctypes
            _libc = ctypes.CDLL(None)
            if hasattr(_libc, 'prctl'):
                _libc.prctl(4, 0, 0, 0, 0)
        except Exception:
            pass

    # 3. Background GC watchdog to detect inspection objects
    try:
        import threading, time
        def _dump_watchdog():
            _bad_modules = {{'objgraph', 'pympler', 'memory_profiler', 'guppy', 'heapy', 'frida', 'cheatengine'}}
            while True:
                try:
                    if set(sys.modules.keys()) & _bad_modules:
                        {abort_fn}()
                    time.sleep(1.0)
                except Exception:
                    pass
        _t = threading.Thread(target=_dump_watchdog, daemon=True)
        _t.start()
    except Exception:
        pass

try:
    {fn_name}()
except Exception:
    pass
'''


# ═══════════════════════════════════════════════════════════════
# DEAD CODE INJECTOR - REALISTIC JUNK (VELIMATIX)
# ═══════════════════════════════════════════════════════════════

class DeadCodeInjector():
    """Injects realistic-looking dead code that never executes"""
    def __init__(self, alphabet: str, length: int, density: int = 5):
        self.alphabet = alphabet
        self.length = length
        self.density = density

    def _gen_dead_block(self):
        var1 = Utils.randomize_name(self.alphabet, self.length)
        var2 = Utils.randomize_name(self.alphabet, self.length)
        var3 = Utils.randomize_name(self.alphabet, self.length)

        k_val = random.randint(11, 9999)
        impossible = random.choice([
            # Fermat / Euler invariant: (k^3 - k) % 3 != 0 is ALWAYS FALSE for any integer k
            ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=3)),
                        op=ast.Sub(),
                        right=ast.Constant(value=k_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=3)
                ),
                ops=[ast.NotEq()],
                comparators=[ast.Constant(value=0)]
            ),
            # Parity invariant: (k^2 + k) % 2 != 0 is ALWAYS FALSE for any integer k
            ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=2)),
                        op=ast.Add(),
                        right=ast.Constant(value=k_val)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=2)
                ),
                ops=[ast.NotEq()],
                comparators=[ast.Constant(value=0)]
            ),
            # Odd square modulo 8 invariant: ((2*k + 1)^2) % 8 == 0 is ALWAYS FALSE (always 1)
            ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(
                        left=ast.BinOp(
                            left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Mult(), right=ast.Constant(value=2)),
                            op=ast.Add(),
                            right=ast.Constant(value=1)
                        ),
                        op=ast.Pow(),
                        right=ast.Constant(value=2)
                    ),
                    op=ast.Mod(),
                    right=ast.Constant(value=8)
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)]
            ),
            # Non-negative square invariant: (k^2 + 1) < 0 is ALWAYS FALSE
            ast.Compare(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=k_val), op=ast.Pow(), right=ast.Constant(value=2)),
                    op=ast.Add(),
                    right=ast.Constant(value=1)
                ),
                ops=[ast.Lt()],
                comparators=[ast.Constant(value=0)]
            ),
            ast.Call(func=ast.Name(id='isinstance'), args=[ast.Constant(value=0), ast.Name(id='str')], keywords=[]),
        ])

        body_choices = [
            [ast.Assign(targets=[ast.Name(id=var1)], value=ast.BinOp(
                left=ast.Constant(value=random.randint(0, 0xFFFF)),
                op=random.choice([ast.Add(), ast.BitXor(), ast.Mult()]),
                right=ast.Constant(value=random.randint(0, 0xFFFF))
            ), lineno=None)],
            [ast.Assign(targets=[ast.Name(id=var1)], value=ast.List(elts=[
                ast.Constant(value=random.randint(0, 0xFF)) for _ in range(random.randint(3, 8))
            ]), lineno=None),
             ast.Expr(value=ast.Call(func=ast.Attribute(value=ast.Name(id=var1), attr='append'),
                                     args=[ast.Constant(value=random.randint(0, 0xFFFF))], keywords=[]))],
            [ast.Assign(targets=[ast.Name(id=var1)], value=ast.Constant(value=random.randint(0, 0xFFFFFF)), lineno=None),
             ast.AugAssign(target=ast.Name(id=var1), op=ast.BitXor(),
                           value=ast.Constant(value=random.randint(0, 0xFFFF)))],
            [ast.Expr(value=ast.Call(func=ast.Name(id='str'), args=[
                ast.BinOp(left=ast.Constant(value=random.randint(0, 999)),
                           op=ast.Add(), right=ast.Constant(value=random.randint(0, 999)))
            ], keywords=[]))],
        ]

        return ast.If(test=impossible, body=random.choice(body_choices), orelse=[])

    def proceed(self, tree: ast.Module):
        new_body = []
        for node in tree.body:
            new_body.append(node)
            if random.random() < (self.density / 10.0):
                for _ in range(random.randint(1, 3)):
                    new_body.append(self._gen_dead_block())
        tree.body = new_body

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith('__'):
                injected = []
                for stmt in node.body:
                    injected.append(stmt)
                    if random.random() < (self.density / 15.0):
                        injected.append(self._gen_dead_block())
                node.body = injected

        return tree


# ═══════════════════════════════════════════════════════════════
# STRING ENCODER - BYTEWISE XOR (VELIMATIX STYLE)
# ═══════════════════════════════════════════════════════════════

class StringEncoderTransformer():
    """Encode string constants using bytewise XOR operations"""
    def __init__(self):
        self._depth = 0

    def proceed(self, tree: ast.Module):
        _skip_ids = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.match_case) and hasattr(n, 'pattern') and n.pattern:
                for child in ast.walk(n.pattern):
                    _skip_ids.add(id(child))
            if isinstance(n, ast.arg) and hasattr(n, 'annotation') and n.annotation:
                for child in ast.walk(n.annotation):
                    _skip_ids.add(id(child))
            if isinstance(n, ast.AnnAssign) and hasattr(n, 'annotation') and n.annotation:
                for child in ast.walk(n.annotation):
                    _skip_ids.add(id(child))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(n, 'returns') and n.returns:
                for child in ast.walk(n.returns):
                    _skip_ids.add(id(child))
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(n, 'decorator_list'):
                for d in n.decorator_list:
                    for child in ast.walk(d):
                        _skip_ids.add(id(child))

        transformer = StringEncoderTransformer._Inner(_skip_ids)
        tree = transformer.visit(tree)
        return tree

    class _Inner(ast.NodeTransformer):
        def __init__(self, skip_ids=None):
            self._depth = 0
            self._skip_ids = skip_ids or set()

        def visit_Constant(self, node: ast.Constant):
            if self._depth > 0:
                return node
            if id(node) in self._skip_ids:
                return node
            if not isinstance(node.value, str):
                return node
            if hasattr(node, 'parent') and isinstance(node.parent, ast.MatchValue):
                return node
            if len(node.value) == 0 or len(node.value) > 100:
                return node
            if random.random() > 0.6:
                return node

            try:
                self._depth += 1
                s = node.value
                magic = random.randint(1000000, 9999999)
                parts = []
                for ch in s:
                    logic = random.randint(1, 4)
                    key = ord(ch)
                    if logic == 1:
                        key3 = ~key ^ ~magic
                        parts.append(f"chr(~({key3} ^ ~{magic}))")
                    elif logic == 2:
                        shift = random.randint(1, 12)
                        key3 = key << shift
                        parts.append(f"chr({key3} >> {shift})")
                    elif logic == 3:
                        key3 = key + magic
                        parts.append(f"chr({key3} - {magic})")
                    else:
                        key3 = key * magic
                        parts.append(f"chr({key3} // {magic})")

                code = f"(lambda: ''.join([{', '.join(parts)}]))()"
                result = ast.parse(code, mode='eval').body
                self._depth -= 1
                return result
            except Exception:
                self._depth -= 1
                return node


class ObfuscatorSettings:
    def __init__(self):
        self.transformers = []

    def add_transformer(self, transformer):
        self.transformers.append(transformer)

    def exceptionjmp_transformer(self, alphabet: str, length: int):
        self.add_transformer(ExceptionJumpTransformer(alphabet, length))

    def call_transformer(self):
        self.add_transformer(CallTransformer())

    def biopaque_transformer(self, alphabet: str, length: int, safe_mode: bool):
        self.add_transformer(BiOpaqueTransformer(alphabet, length, safe_mode))

    def controlflow_transformer(self, alphabet: str, length: int):
        self.add_transformer(ControlFlowTransformer(alphabet, length))

    def mutator_transformer(self, alphabet: str, length: int, ladder: int = 3):
        self.add_transformer(MutatorTransformer(alphabet, length, ladder))

    def method_cloner(self, alphabet: str, length: int, count: int = 5):
        self.add_transformer(MethodClonerTransformer(alphabet, length, count))

    def builtin_renamer(self, alphabet: str, length: int):
        self.add_transformer(BuiltinRenamerTransformer(alphabet, length))

    def dead_code(self, alphabet: str, length: int, density: int = 5):
        self.add_transformer(DeadCodeInjector(alphabet, length, density))

    def string_encoder(self):
        self.add_transformer(StringEncoderTransformer())


def OBF_Spam(code, level=2):
    """Apply ALL Velimatix transformers with configurable intensity"""
    alphabet = "Ox" + ''.join(random.choices([str(i) for i in range(10)], k=6))
    length = 17

    try:
        setting = ast.parse(code)
        setting = ast.unparse(setting)
    except Exception:
        return code

    # ★ FIX: Prepend VELIMATIX class when ExceptionJump will be used
    if level >= 2:
        setting = "class VELIMATIX(MemoryError): pass\n" + setting

    for pass_num in range(level):
        BiOpaqueUtils.possible_args = []
        BiOpaqueUtils.possible_functions = []

        settings = ObfuscatorSettings()

        settings.biopaque_transformer(alphabet, length, safe_mode=True)
        settings.call_transformer()

        if level >= 2:
            settings.exceptionjmp_transformer(alphabet, length)
            settings.dead_code(alphabet, length, density=3 + pass_num)

        if level >= 3:
            settings.controlflow_transformer(alphabet, length)
            settings.mutator_transformer(alphabet, length, ladder=2 + pass_num)
            settings.method_cloner(alphabet, length, count=3 + pass_num * 2)
            settings.string_encoder()

        try:
            tree = ast.parse(setting)
            for transformer in settings.transformers:
                try:
                    tree = transformer.proceed(tree)
                except Exception:
                    pass
            setting = ast.unparse(tree)

            # ★ FIX: Re-prepend after each pass for same reason
            if level >= 2:
                setting = "class VELIMATIX(MemoryError): pass\n" + setting

        except Exception:
            break

    return setting


class OBF_Formatter(ast.NodeTransformer):
    """Convert f-strings to .format() calls"""
    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.Call:
        template, args = _render_fstring_template(node)
        return ast.Call(
            func=ast.Attribute(value=ast.Constant(value=template), attr="format", ctx=ast.Load()),
            args=args,
            keywords=[]
        )


def OBF_Import(code):
    """Convert import statements to __import__ calls"""
    imports_ = []
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports_.append(name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            for name in node.names:
                if name.name == '*':
                    imports_.append((module, '*'))
                else:
                    imports_.append((module, name.name, name.asname))
    result_lines = code.splitlines()
    for i, line in enumerate(result_lines):
        if line.startswith('import') or line.startswith('from'):
            result_lines[i] = ''
    for imp in imports_:
        if isinstance(imp, tuple):
            if imp[1] == '*':
                result_lines.insert(0, f'from {imp[0]} import *')
            elif imp[2]:
                result_lines.insert(0, f"{imp[2]} = getattr(__import__({imp[0]!r}, fromlist=[{imp[1]!r}]), {imp[1]!r})")
            else:
                result_lines.insert(0, f"{imp[1]} = getattr(__import__({imp[0]!r}, fromlist=[{imp[1]!r}]), {imp[1]!r})")
        else:
            as_target = imp.asname if imp.asname else imp.name
            result_lines.insert(0, f"{as_target} = __import__({imp.name!r})")
    return '\n'.join(result_lines)

def _velimatix_obf(code, mode=2):
    """Apply FULL Velimatix engine based on mode level
    Mode 1: BiOpaque + CallObf + DeadCode
    Mode 2: + ExceptionJump + Import obf + BuiltinRename
    Mode 3: + ControlFlow + Mutator + MethodClone + StringEncode + Multi-pass
    """
    try:
        tree = ast.parse(code)
        tree = OBF_Formatter().visit(tree)
        code = ast.unparse(tree)

        if mode >= 2:
            try:
                code = OBF_Import(code)
            except Exception:
                pass

        code = "class VELIMATIX(MemoryError): pass\n" + code

        passes = 1
        alphabet = "Ox" + ''.join(random.choices([str(i) for i in range(10)], k=6))
        length = 17

        for pass_num in range(passes):
            BiOpaqueUtils.possible_args = []
            BiOpaqueUtils.possible_functions = []

            settings = ObfuscatorSettings()

            settings.biopaque_transformer(alphabet, length, safe_mode=True)
            settings.call_transformer()
            settings.dead_code(alphabet, length, density=3)

            if mode >= 2:
                settings.exceptionjmp_transformer(alphabet, length)
                if pass_num == 0:
                    settings.builtin_renamer(alphabet, length)

            if mode >= 3:
                settings.controlflow_transformer(alphabet, length)
                settings.mutator_transformer(alphabet, length, ladder=2 + pass_num)
                settings.method_cloner(alphabet, length, count=4)
                settings.string_encoder()

            try:
                tree = ast.parse(code)
                for transformer in settings.transformers:
                    try:
                        tree = transformer.proceed(tree)
                    except Exception:
                        continue
                code = ast.unparse(tree)

                # ★ FIX: Always re-prepend VELIMATIX class at the very top
                # after each pass. BuiltinRenamer pushes 60+ Assign nodes
                # above the old class def; on the next pass ExceptionJump
                # wraps those assigns with raise VELIMATIX(...) — which
                # fails because VELIMATIX isn't defined yet.
                # Re-prepending guarantees VELIMATIX is defined before
                # any ExceptionJump block can reference it.
                if mode >= 2:
                    code = "class VELIMATIX(MemoryError): pass\n" + code

            except Exception:
                break

        return code
    except Exception as e:
        return code

# ═══════════════════════════════════════════════════════════════
# DYNAMIC KEY DERIVATION - NOT HARDCODED
# ═══════════════════════════════════════════════════════════════

def _derive_key_code():
    """Generate code that derives key at runtime from environment"""
    salt = secrets.token_hex(16)
    return f"""
def _dk():
    import hashlib, sys, os, struct, platform
    parts = []
    parts.append(sys.version[:5].encode())
    parts.append(platform.python_implementation().encode())
    parts.append(b'{salt}')
    parts.append(str(sys.maxsize).encode())
    parts.append(sys.byteorder.encode())
    combined = b''.join(parts)
    return hashlib.sha256(combined).digest()
"""




# ═══════════════════════════════════════════════════════════════
# MULTI-STRATEGY STRING OBFUSCATION
# ═══════════════════════════════════════════════════════════════

def _chrobf(x):
    return ord(x) + 0xFF78FF

def obfstr(v, _depth=0):
    if v == "":
        return f"''"

    # Limit recursion depth to prevent stack overflow
    if _depth > 3:
        # Fallback to simple lambda chain
        x = [ord(c) + 0xFF78FF for c in v]
        return f"(lambda: globals()['{_join}'](globals()['{_list}'](globals()['{_map}'](globals()['{_hexrun}'], {x}))))()"

    strategy = random.randint(1, 6)

    if strategy == 1:
        # Lambda chain (original enhanced)
        x = [ord(c) + 0xFF78FF for c in v]
        _str_ = f"(lambda: globals()['{_join}'](globals()['{_list}'](globals()['{_map}'](globals()['{_hexrun}'], {x}))))()"
        return _str_

    elif strategy == 2:
        # Reverse + decode
        reversed_v = v[::-1]
        x = [ord(c) + 0xFF78FF for c in reversed_v]
        return f"(lambda: globals()['{_join}'](globals()['{_list}'](globals()['{_map}'](globals()['{_hexrun}'], {x})))[::-1])()"

    elif strategy == 3:
        # Recursive split (only for strings > 1 char)
        if len(v) <= 1:
            x = [ord(c) + 0xFF78FF for c in v]
            return f"(lambda: globals()['{_join}'](globals()['{_list}'](globals()['{_map}'](globals()['{_hexrun}'], {x}))))()"
        mid = len(v) // 2
        part1 = obfstr(v[:mid], _depth=_depth+1)
        part2 = obfstr(v[mid:], _depth=_depth+1)
        _a = rd()
        return f"(lambda: (lambda {_a}: {_a})({part1} + {part2}))()"

    elif strategy == 4:
        # XOR with random magic
        keys = []
        magic = _trx_rand(9000000) + 1000000
        for char in v:
            logic = _trx_rand(5) + 1
            key = ord(char)
            key2 = magic
            if logic == 1:
                key3 = key ^ magic
                keys.append(f"(lambda: chr({key3} ^ {key2}))()")
            elif logic == 2:
                shift = _trx_rand(12) + 1
                key3 = key << shift
                keys.append(f"(lambda: chr({key3} >> {shift}))()")
            elif logic == 3:
                key3 = key + magic
                keys.append(f"(lambda: chr({key3} - {key2}))()")
            elif logic == 4:
                key3 = key * magic
                keys.append(f"(lambda: chr({key3} // {key2}))()")
            else:
                # NOT + XOR
                key3 = ~key ^ ~magic
                keys.append(f"(lambda: chr(~({key3} ^ ~{magic})))()")
        return f"(lambda: ''.join([{', '.join(keys)}]))()"

    elif strategy == 5:
        # Bytewise encoding with shuffled indices
        indices = list(range(len(v)))
        shuffled = indices[:]
        # seeding-aware shuffle (SystemRandom ignored --seed; audit fix)
        if _SEEDED_RNG is not None:
            _SEEDED_RNG.shuffle(shuffled)
        else:
            secrets.SystemRandom().shuffle(shuffled)
        encoded = [(shuffled[i], ord(v[shuffled[i]]) + 0xFF78FF) for i in range(len(v))]
        pairs_str = str(encoded)
        return f"(lambda: ''.join(globals()['{_hexrun}'](c) for _, c in sorted({pairs_str})))()"

    else:
        # Multi-base encoding
        encoded_bytes = v.encode('utf-8')
        nums = [b for b in encoded_bytes]
        xor_val = _trx_rand(255) + 1
        xored = [n ^ xor_val for n in nums]
        return f"(lambda: bytes([x ^ {xor_val} for x in {xored}]).decode('utf-8'))()"


# ═══════════════════════════════════════════════════════════════
# MULTI-STRATEGY INTEGER OBFUSCATION
# ═══════════════════════════════════════════════════════════════

def _byte(v):
    byte_array = bytearray()
    byte_array.extend(v.to_bytes((v.bit_length() + 7) // 8, 'big'))
    return b"tr0ngx/" + byte_array

def obfint(v):
    n = rd()
    if 'bool' in str(type(v)):
        if str(v) == 'True':
            return f'(lambda: (lambda {n}: {n} + (lambda: H2SbF7({(1 + 0x7777)}))())(0) == 1)()'
        else:
            return f'(lambda: (lambda {n}: {n} - (lambda: H2SbF7(({(1 + 0x7777)})))())(0) == 1)()'
    else:
        strategy = _trx_rand(8) + 1
        val = int(v)

        # Strategy 1 (_byte) only works for non-negative integers
        if strategy == 1:
            if val >= 0:
                return f'(lambda: c2h6({_byte(val)}))()'
            else:
                # Fallback for negative numbers: use XOR strategy
                xor_key = _trx_rand(0xFFFFF - 0x1000) + 0x1000
                return f'(lambda: (lambda: {val ^ xor_key} ^ {xor_key})())()'

        elif strategy == 2:
            offset = _trx_rand(0xFFFFF - 0x5000) + 0x5000
            return f'(lambda: (lambda: {val + offset} - {offset})())()'

        elif strategy == 3:
            xor_key = _trx_rand(0xFFFFF - 0x1000) + 0x1000
            return f'(lambda: (lambda: {val ^ xor_key} ^ {xor_key})())()'

        elif strategy == 4:
            mult = _trx_choice([2, 3, 5, 7, 11, 13])
            remainder = val % mult
            base = val // mult
            return f'(lambda: (lambda: {base} * {mult} + {remainder})())()'

        elif strategy == 5:
            return f'(lambda: H2SbF7({(val + 0x7777)}))()'

        elif strategy == 6:
            return f'(lambda: ~~{val})()'

        elif strategy == 7:
            a = _trx_rand(10000) + 1
            b = val + a
            _p = rd()
            return f'(lambda: (lambda {_p}: {_p} - {a})({b}))()'

        else:
            # Bit shift reconstruction
            if val == 0:
                return f'(lambda: 0 >> 1)()'
            high = val >> 8
            low = val & 0xFF
            return f'(lambda: ({high} << 8) | {low})()'


def varsobf(v):
    r1, r2, r3, r4 = randomint(), randomint(), randomint(), randomint()
    _result = f"""({(v)}) if bool(bool(bool({(v)}))) < bool(type(int({r1})>int({r2})<int({r3})>int({r4}))) and bool(str(str({r1})>int({r2})<int({r3})>int({r4}))) > 2 else {v}"""
    try:
        ast.parse(f"_x = {_result}")
        return _result
    except SyntaxError:
        return str(v)


# ═══════════════════════════════════════════════════════════════
# GLOBAL CHEMICAL VARIABLE NAMES
# ═══════════════════════════════════════════════════════════════

_join = "h2o"
_lambda = "ᅠ"
_int = "h2so4"
_str = "co2"
_bool = "mol"
_type = "feo2"
_bytes = "feso4"
_vars = "agno3"
_ip = "hno3"
ngoac = "{"
_ngoac = "}"
___import__ = "ch2oh4p2so4"
_movdiv = "h2"
_hexrun = "o2"
_argshexrun = "h2so3"
__print = r"tryᅠ"
__input = r"exceptᅠ"
_eval = "h2o3"
_list = "agno4"
_map = "h3o"
_exec = "nacl"
_chr = "hcl"
_ord = "naoh"
_len = "caso4"
_range = "fe2o3"
_getattr = "al2o3"
_setattr = "sio2"
_isinstance = "caco3"


def unicodeobf(x):
    return [ord(i) + 0xFF78FF for i in x]

def _uni(x):
    return unicodeobf(x)


__bool = rd()
__exx = rd()
_temp = rd()
_temp1 = rd()
_wt = rd()
_exp = rd()

# ═══════════════════════════════════════════════════════════════
# STATE MACHINE CONTROL FLOW FLATTENING
# ═══════════════════════════════════════════════════════════════

def _generate_state_machine(statements):
    """Convert sequential code into a state machine - hard to trace"""
    if not statements:
        return ""

    states = list(range(len(statements)))
    random.shuffle(states)

    state_var = rd()
    dispatch_var = rd()

    lines = []
    lines.append(f"{state_var} = {states[0]}")
    lines.append(f"while {state_var} != -1:")

    for original_idx, state_num in enumerate(states):
        next_state = states[original_idx + 1] if original_idx + 1 < len(states) else -1
        indent = "    "
        lines.append(f"{indent}if {state_var} == {state_num}:")

        if isinstance(statements[original_idx], str):
            for line in statements[original_idx].split('\n'):
                if line.strip():
                    lines.append(f"{indent}    {line.strip()}")
        else:
            lines.append(f"{indent}    {statements[original_idx]}")

        lines.append(f"{indent}    {state_var} = {next_state}")

    # Add junk states
    for _ in range(random.randint(3, 8)):
        junk_state = random.randint(1000, 9999)
        junk_var = rd()
        lines.append(f"    if {state_var} == {junk_state}:")
        lines.append(f"        {junk_var} = {random.randint(0, 0xFFFFFF)}")
        lines.append(f"        {state_var} = -1")

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════
# CHUNKED EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════

def _generate_chunked_executor():
    """Generate code that decrypts and executes in chunks - never full code in RAM"""
    chunk_key_var = rd()
    chunk_data_var = rd()
    chunk_func = rd()
    decrypt_func = rd()

    return f"""
def {decrypt_func}(chunk, key_part):
    import hashlib
    dk = hashlib.sha256(key_part).digest()
    result = bytearray()
    for i, b in enumerate(chunk):
        result.append(b ^ dk[i % len(dk)])
    return bytes(result)

def {chunk_func}(chunks, keys):
    import marshal, types
    for i in range(len(chunks)):
        decrypted = {decrypt_func}(chunks[i], keys[i])
        code_obj = marshal.loads(decrypted)
        exec(code_obj)
        del decrypted, code_obj
"""

# ═══════════════════════════════════════════════════════════════
def _generate_var_block():
    global var
    var = fr"""

globals()['{_bool}'] = {varsobf('bool')}
globals()['{_str}'] = {varsobf('str')}
globals()['{_type}'] = {varsobf('type')}
globals()['{_int}'] = {varsobf('int')}
globals()['{_bytes}'] = {varsobf('bytes')}
globals()['{_vars}'] = {varsobf('vars')}
globals()['{_movdiv}'] = {varsobf('callable')}
globals()['{_eval}'] = {varsobf('eval')}
globals()['{_list}'] = {varsobf('list')}
globals()['{_map}'] = {varsobf('map')}
globals()['{_exec}'] = {varsobf('exec')}
globals()['{_chr}'] = {varsobf('chr')}
globals()['{_ord}'] = {varsobf('ord')}
globals()['{_len}'] = {varsobf('len')}
globals()['{_range}'] = {varsobf('range')}
globals()['{_getattr}'] = {varsobf('getattr')}
globals()['{_setattr}'] = {varsobf('setattr')}
globals()['{_isinstance}'] = {varsobf('isinstance')}

globals()['{___import__}'] = {varsobf('__import__')}

globals()['tryᅠ'] = {varsobf('print')}
globals()['exceptᅠ'] = {varsobf('input')}

def {_join}(july, *k):
    if k:
        tr0ngx = '+'
        op = "+"
    else:
        tr0ngx = ''
        op = ''
    globals()['{__exx}'] = {obfint(True)}
    globals()['{_join}'] = {_join}
    globals()['{_str}'] = {_str}
    globals()['july'] = july
    for globals()['tr0ngx_'] in globals()['july']:
        if not {__exx}:
            globals()['tr0ngx_'] += (lambda: '')()
        tr0ngx += {_str}(tr0ngx_)
        f = {obfint(True)}
    return tr0ngx

def H2SbF7(x):
    return globals()['{_int}'](x - 0x7777)

def c2h6(e):
    br = bytearray(e[globals()['{_len}'](b"tr0ngx/"):])
    r = 0
    for b in br:
        r = r * 256 + b
    return r

def longlongint(x):
    ar = []
    for i in x:
        ar.append(globals()['{_eval}'](i))
    return ar

if {obfint(True)}:
    def {_hexrun}({_argshexrun}):
        {_argshexrun} = {_argshexrun} - 0xFF78FF
        if {_argshexrun} <= 0x7F:
            return globals()['{_str}'](globals()['{_bytes}']([{_argshexrun}]), "utf8")
        elif {_argshexrun} <= 0x7FF:
            if 1 < 2:
                b1 = 0xC0 | ({_argshexrun} >> 6)
            b2 = 0x80 | ({_argshexrun} & 0x3F)
            return globals()['{_str}'](globals()['{_bytes}']([b1, b2]), "utf8")
        elif {_argshexrun} <= 0xFFFF:
            b1 = 0xE0 | ({_argshexrun} >> 12)
            if 2 > 1:
                b2 = 0x80 | (({_argshexrun} >> 6) & 0x3F)
            b3 = 0x80 | ({_argshexrun} & 0x3F)
            return globals()['{_str}'](globals()['{_bytes}']([b1, b2, b3]), "utf8")
        else:
            b1 = 0xF0 | ({_argshexrun} >> 18)
            if 2 == 2:
                b2 = 0x80 | (({_argshexrun} >> 12) & 0x3F)
            if 1 < 2 < 3:
                b3 = 0x80 | (({_argshexrun} >> 6) & 0x3F)
            b4 = 0x80 | ({_argshexrun} & 0x3F)
            return globals()['{_str}'](globals()['{_bytes}']([b1, b2, b3, b4]), "utf8")

    def _hex(j):
        {_argshexrun} = ''
        for _hex in j:
            {_argshexrun} += (globals()['{_hexrun}'](_hex))
        return {_argshexrun}
else:
    "tr0ngx"
"""
    return var

def _refresh_runtime_symbols():
    global _str, _bool, _type, _int, _bytes, _vars, _ip, ___import__, _movdiv, _hexrun, _argshexrun
    global _eval, _list, _map, _exec, _chr, _ord, _len, _range, _getattr, _setattr, _isinstance
    global _join, __bool, __exx, _temp, _temp1, _wt, _exp, var
    _str = rd()
    _bool = rd()
    _type = rd()
    _int = rd()
    _bytes = rd()
    _vars = rd()
    _ip = rd()
    ___import__ = rd()
    _movdiv = rd()
    _hexrun = rd()
    _argshexrun = rd()
    _eval = rd()
    _list = rd()
    _map = rd()
    _exec = rd()
    _chr = rd()
    _ord = rd()
    _len = rd()
    _range = rd()
    _getattr = rd()
    _setattr = rd()
    _isinstance = rd()
    _join = rd()
    __bool = rd()
    __exx = rd()
    _temp = rd()
    _temp1 = rd()
    _wt = rd()
    _exp = rd()
    _generate_var_block()

# NOTE (determinism fix): the legacy module-import-time call above made the var
# block bake OS entropy into a template BEFORE --seed could influence it, so two
# seeded processes produced different artifacts. The block is now regenerated
# inside obfuscate_single_target() AFTER per-file seeding; import-time call kept
# only as fallback for direct-API users that skip the pipeline entry.

# ═══════════════════════════════════════════════════════════════
# ANTI-PYCDC ENHANCED (COMPACT & FAST DECOMPILER KILLER)
# ═══════════════════════════════════════════════════════════════

antipycdc = ''
for i in range(120):
    antipycdc += f"你器(你器(你器(''))),"
antipycdc = "try:tr0ngx=[" + antipycdc + "]\nexcept:pass"

ANTI_PYCDC = f"""
def 你器(你):
    return 你
try:
    pass
except Exception:
    pass
finally:
    pass
{antipycdc}
"""

# ═══════════════════════════════════════════════════════════════
# MEGA ANTI-DEBUG / ANTI-HOOK / ANTI-REVERSE
# ═══════════════════════════════════════════════════════════════

anti = r"""
import traceback, marshal, sys, os, threading, time, struct, types, gc, random

# ═══ CORE PROTECTION LAYER ═══
_SHIELD = type('Shield', (), {'_active': True, '_checks': 0})()
_ORIGINAL_BUILTINS = {}

def _obliterate():
    '''Nuclear exit - multiple fallback methods'''
    try:
        gc.collect()
        # Corrupt own memory before exit
        for obj in gc.get_objects():
            if isinstance(obj, types.CodeType):
                try:
                    pass  # Can't modify frozen, but try
                except:
                    pass
    except:
        pass
    try:
        os._exit(1)
    except:
        try:
            import ctypes
            ctypes.CDLL(None).abort()
        except:
            try:
                raise SystemExit(1)
            except:
                while True:
                    pass  # Infinite loop as last resort

# ═══ HOOK DETECTION ENGINE ═══
def _snapshot_builtins():
    '''Take snapshot of original builtins for tamper detection'''
    import builtins
    critical = ['exec', 'eval', 'compile', '__import__', 'open',
                'getattr', 'setattr', 'delattr', 'print', 'input',
                'globals', 'locals', 'vars', 'dir', 'type', 'isinstance']
    for name in critical:
        func = getattr(builtins, name, None)
        if func is not None:
            _ORIGINAL_BUILTINS[name] = id(func)

def _verify_builtins():
    '''Detect if any builtin was hooked/replaced'''
    import builtins, marshal
    _safe_names = ('_safe_exec', '_safe_eval', '_guarded_loads', '_safe_loads', '_wrapped', '<lambda>', 'exec', 'eval', 'loads', 'compile')
    for name, orig_id in _ORIGINAL_BUILTINS.items():
        if name == 'marshal.loads':
            current = getattr(marshal, 'loads', None)
        else:
            current = getattr(builtins, name, None)
        if current is None:
            _obliterate()
        curr_id = id(current)
        # Allow nested Tr0ngX safe closures
        if curr_id != orig_id and not (hasattr(current, '__name__') and current.__name__ in _safe_names):
            _obliterate()

# ═══ EXEC/EVAL PROTECTION (ZERO-ATTRIBUTE-LEAK CLOSURES) ═══
def _protect_exec_eval():
    '''Make exec/eval tamper-resistant using closed lexical closures with zero inspectable attribute leaks (TRX-DEOB-007)'''
    import builtins
    import hashlib

    _real_exec = builtins.exec
    _real_eval = builtins.eval
    _real_exec_id = id(_real_exec)
    _real_eval_id = id(_real_eval)
    _exec_checksum = hashlib.sha256(_real_exec.__code__.co_code).digest()[:8] if hasattr(_real_exec, '__code__') else None
    _eval_checksum = hashlib.sha256(_real_eval.__code__.co_code).digest()[:8] if hasattr(_real_eval, '__code__') else None

    def _safe_exec(*args, **kwargs):
        if id(_real_exec) != _real_exec_id:
            _obliterate()
        if _exec_checksum is not None and hasattr(_real_exec, '__code__'):
            if hashlib.sha256(_real_exec.__code__.co_code).digest()[:8] != _exec_checksum:
                _obliterate()
        return _real_exec(*args, **kwargs)

    def _safe_eval(*args, **kwargs):
        if id(_real_eval) != _real_eval_id:
            _obliterate()
        if _eval_checksum is not None and hasattr(_real_eval, '__code__'):
            if hashlib.sha256(_real_eval.__code__.co_code).digest()[:8] != _eval_checksum:
                _obliterate()
        return _real_eval(*args, **kwargs)

    builtins.exec = _safe_exec
    builtins.eval = _safe_eval
    _ORIGINAL_BUILTINS['exec'] = id(builtins.exec)
    _ORIGINAL_BUILTINS['eval'] = id(builtins.eval)

# ═══ MARSHAL PROTECTION (ZERO-ATTRIBUTE-LEAK CLOSURE) ═══
def _protect_marshal():
    '''Deep marshal.loads protection without __wrapped__ or exposed function references (TRX-DEOB-007)'''
    _real_loads = marshal.loads
    _real_loads_id = id(_real_loads)

    def _guarded_loads(data, *args, **kwargs):
        if id(_real_loads) != _real_loads_id:
            _obliterate()
        # Walk up frame stack to find real caller (skip wrapper layers)
        frame = sys._getframe(1)
        for _depth in range(6):
            if frame is None:
                break
            caller_file = frame.f_code.co_filename
            if any(bad in caller_file.lower() for bad in
                   ['decompile', 'uncompyle', 'pycdc', 'xdis', 'marshal_dump', 'spy_hook']):
                _obliterate()
            frame = frame.f_back
        return _real_loads(data, *args, **kwargs)

    marshal.loads = _guarded_loads
    _ORIGINAL_BUILTINS['marshal.loads'] = id(_guarded_loads)

# ═══ ANTI-DEBUGGER (MULTI-VECTOR) ═══

# ═══ ANTI-AUDIT-HOOK & TAMPER SHIELD (PEP 578) ═══
# NOTE: sys.audit/addaudithook override only replaces the Python-level attribute.
# C-level PySys_Audit() and previously registered audit hooks still function.
# This is best-effort protection - a determined attacker with C-level access can bypass it.
try:
    if hasattr(sys, 'audit'):
        sys.audit = lambda *a, **k: None
    if hasattr(sys, 'addaudithook'):
        # FIX (audit P0): snapshot the REAL builtin before nulling so Vector 15
        # canary can still register through it (previously self-defeated).
        globals()['_trx_real_addaudithook'] = sys.addaudithook
        sys.addaudithook = lambda *a, **k: None
except Exception:
    pass

def _anti_debugger():
    # Vector 1: Trace detection & monkeypatch defense
    if hasattr(sys, 'gettrace'):
        if type(sys.gettrace).__name__ != 'builtin_function_or_method' or getattr(sys.gettrace, '__module__', '') != 'sys':
            _obliterate()
        if sys.gettrace() is not None:
            _obliterate()

    # Vector 2: Profile detection & monkeypatch defense
    if hasattr(sys, 'getprofile'):
        if type(sys.getprofile).__name__ != 'builtin_function_or_method' or getattr(sys.getprofile, '__module__', '') != 'sys':
            _obliterate()
        if sys.getprofile() is not None:
            _obliterate()

    if hasattr(sys, 'settrace'):
        if type(sys.settrace).__name__ != 'builtin_function_or_method' or getattr(sys.settrace, '__module__', '') != 'sys':
            _obliterate()

    # Vector 3: Monitoring detection (Python 3.12+) - only block known debugger/tracing tools
    if hasattr(sys, 'monitoring') and hasattr(sys.monitoring, 'get_tool'):
        _debug_tool_names = {'debugpy', 'pydevd', 'coverage', 'pdb', 'trace', 'profiler'}
        for tool_id in range(6):
            try:
                tool = sys.monitoring.get_tool(tool_id)
                if tool and isinstance(tool, str) and tool.lower() in _debug_tool_names:
                    _obliterate()
            except Exception:
                pass

    # Vector 4: Known debugger modules
    poison = {'pydevd', 'pydevd_frame_evaluator', '_pydevd_bundle',
              'debugpy', 'ipdb', 'pudb', 'rpdb', 'wdb',
              'pydevd_plugins', 'pydevd_tracing',
              'hunter', 'snooper', 'snoop', 'objgraph',
              'pympler', 'line_profiler', 'memory_profiler'}
    loaded = set(sys.modules.keys())
    if loaded & poison:
        _obliterate()

    # Vector 5: Frame inspection
    frame = sys._getframe(0)
    while frame is not None:
        fn = frame.f_code.co_filename.lower()
        if any(d in fn for d in ['pydevd', 'debugpy', 'tracer_hook', 'spy_dump']):
            _obliterate()
        frame = frame.f_back

    # Vector 6: Timing attack detection (5s threshold to avoid false positives on loaded machines)
    t1 = time.perf_counter_ns()
    _dummy = sum(range(5000))
    t2 = time.perf_counter_ns()
    if (t2 - t1) > 5_000_000_000:  # 5000ms for trivial op = heavily single-stepped debugger
        _obliterate()

    # Vector 7: Frame depth anomaly detection
    try:
        _frames = sys._current_frames()
        for _tid, _frame in _frames.items():
            _depth = 0
            _f = _frame
            while _f is not None:
                _depth += 1
                _f = _f.f_back
            if _depth > 200:  # Abnormally deep call stack
                _obliterate()
    except Exception:
        pass

    # Vector 8: C-level trace hook detection via ctypes
    try:
        import ctypes
        _py = ctypes.pythonapi
        # Check if PyEval_SetTrace has been hooked by reading the function pointer
        # If a debugger set a C-level trace, this would be non-null
        _trace_ptr = ctypes.c_void_p.in_dll(_py, "PyEval_SetTrace")
    except Exception:
        pass

    # Vector 9: Win32 PEB IsDebuggerPresent check
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            if ctypes.windll.kernel32.IsDebuggerPresent() != 0:
                _obliterate()
    except Exception:
        pass

    # Vector 10: Win32 CheckRemoteDebuggerPresent check
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            _is_dbg = ctypes.c_bool(False)
            if ctypes.windll.kernel32.CheckRemoteDebuggerPresent(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(_is_dbg)) != 0:
                if _is_dbg.value:
                    _obliterate()
    except Exception:
        pass

    # Vector 11: Comprehensive GUI Window Title & Window Class Matrix (100+ patterns)
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32'):
            _u32 = ctypes.windll.user32
            _buf_title = ctypes.create_unicode_buffer(1024)
            _buf_class = ctypes.create_unicode_buffer(256)
            
            _BAD_TITLES = (
                'extremedumper', 'extremedumper-x86', 'dnspy', 'dnspy-x86', 'dnspy.console',
                'ilspy', 'ilspy.b35', 'ilspycmd', 'dotdumper', 'dotnetdatacollector',
                'cheat engine', 'cheatengine', 'cheatengine-x86_64', 'cheatengine-x86_64-sse4-avx2',
                'cheatengine-i386', 'cheatengine-x86_64-sse4', 'x64dbg', 'x32dbg', 'x96dbg', 'x64_dbg', 'x32_dbg',
                'ollydbg', 'immunity debugger', 'process hacker', 'system informer', 'processhacker',
                'httpdebugger', 'http debugger', 'httpdebuggerui', 'httpdebuggersvc', 'http debugger pro',
                'fiddler', 'fiddler classic', 'fiddler everywhere', 'wireshark', 'charles proxy', 'charles debug',
                'ida pro', 'ida free', 'ida v', 'ida:', 'ida64', 'idaw', 'idag',
                'ghidra', 'binary ninja', 'radare2', 'cutter -', 'scylla', 'scyllahide', 'megadumper',
                'process monitor', 'procmon', 'process explorer', 'procexp', 'everything',
                'pe-bear', 'pe-sieve', 'hollowshunter', 'lordpe', 'resource hacker', 'reshacker',
                'hxd hex editor', 'hxd', '010 editor', 'frida', 'api monitor', 'reclass.net', 'reclass',
                'ksdumper', 'ksdumper 11', 'ksdumperclient', 'blackbone', 'xenos injector', 'xenos',
                'simple assembly explorer', 'de4dot', 'unpyc', 'pycdc', 'decompyle++', 'justdecompile',
                'detect it easy', 'exeinfo pe', 'peid', 'titanengine', 'tcpview', 'dbgview', 'debugview',
                'hookshark', 'pestudio', 'cff explorer', 'windbg', 'syser', 'softice', 'dumpert', 'userdump'
            )

            _BAD_CLASSES = (
                'ollydbg', 'zeta debugger', 'rock debugger', 'id', 'x64dbg', 'x32dbg',
                'procmon_window_class', 'cheatengine', 'processhacker', 'httpdebugger',
                'dbgviewclass', 'tformcheatengine', 'tformmain', 'tformaddresschanger'
            )

            def _enum_wnd_cb(hwnd, lparam):
                if _u32.IsWindowVisible(hwnd):
                    len_t = _u32.GetWindowTextW(hwnd, _buf_title, 1024)
                    len_c = _u32.GetClassNameW(hwnd, _buf_class, 256)
                    t_lower = _buf_title.value.lower() if len_t > 0 else ""
                    c_lower = _buf_class.value.lower() if len_c > 0 else ""
                    
                    if t_lower:
                        for b in _BAD_TITLES:
                            if b in t_lower:
                                # Special filter for Everything search utility: only trigger if searching memory/dump/debug
                                if b == 'everything':
                                    if any(k in t_lower for k in ('.dmp', '.dump', 'debug', 'memory', 'ida', 'dnspy', 'cheat')):
                                        _obliterate()
                                else:
                                    _obliterate()
                    if c_lower:
                        for cl in _BAD_CLASSES:
                            if cl in c_lower:
                                _obliterate()
                return True

            _WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            _u32.EnumWindows(_WNDPROC(_enum_wnd_cb), 0)
    except Exception:
        pass

    # Vector 12: Process Image & Toolhelp32/EnumProcesses Inspection (100+ process names)
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            _k32 = ctypes.windll.kernel32
            
            _BAD_PROCS = frozenset({
                'extremedumper.exe', 'extremedumper-x86.exe', 'extremedumper',
                'dnspy.exe', 'dnspy-x86.exe', 'dnspy.console.exe', 'dnspy',
                'ilspy.exe', 'ilspy.b35.exe', 'ilspycmd.exe', 'ilspy',
                'dotdumper.exe', 'dotdumper', 'de4dot.exe', 'de4dot-x64.exe', 'de4dot',
                'megadumper.exe', 'megadumper', 'simpleassemblyexplorer.exe',
                'justdecompile.exe', 'dotnetspy.exe', 'dnspy.runtime.exe',
                'cheatengine-x86_64.exe', 'cheatengine-x86_64-sse4-avx2.exe',
                'cheatengine-i386.exe', 'cheatengine.exe', 'cheatengine-x86_64-sse4.exe',
                'cheatengine', 'cheat engine.exe',
                'ksdumper.exe', 'ksdumper11.exe', 'ksdumperclient.exe', 'ksdumper',
                'scylla.exe', 'scylla_x64.exe', 'scylla_x86.exe', 'scylla',
                'procdump.exe', 'procdump64.exe', 'procdump', 'dumpert.exe', 'userdump.exe',
                'reclass.net.exe', 'reclass64.exe', 'reclass.exe', 'reclass',
                'xenos.exe', 'xenos64.exe', 'blackbone.exe', 'blackbone',
                'x64dbg.exe', 'x32dbg.exe', 'x96dbg.exe', 'x64dbg', 'x32dbg',
                'ollydbg.exe', 'ollydbg', 'immunitydebugger.exe', 'immunity debugger.exe',
                'windbg.exe', 'windbg', 'devenv.exe', 'vsjitdebugger.exe',
                'gdb.exe', 'gdb', 'lldb.exe', 'lldb',
                'ida.exe', 'ida64.exe', 'idag.exe', 'idag64.exe', 'idaw.exe', 'idaw64.exe', 'ida', 'ida64',
                'ghidra.exe', 'ghidrarun.bat', 'ghidra', 'binaryninja.exe', 'binaryninja',
                'radare2.exe', 'radare2', 'r2.exe', 'r2', 'cutter.exe', 'cutter',
                'wdbg.exe', 'cdb.exe', 'ntsd.exe', 'kd.exe', 'drwatson.exe', 'drwtsn32.exe',
                'processhacker.exe', 'processhacker', 'systeminformer.exe', 'systeminformer',
                'procmon.exe', 'procmon64.exe', 'procmon', 'procexp.exe', 'procexp64.exe', 'procexp',
                'apimonitor-x64.exe', 'apimonitor-x86.exe', 'apimonitor.exe', 'apimonitor',
                'hookshark.exe', 'tcpview.exe', 'tcpview64.exe', 'tcpview',
                'autoruns.exe', 'autorunsc.exe', 'autoruns',
                'dbgview.exe', 'dbgview64.exe', 'dbgview',
                'httpdebuggerui.exe', 'httpdebuggersvc.exe', 'httpdebugger.exe', 'httpdebugger',
                'fiddler.exe', 'fiddlerclassic.exe', 'fiddlereverywhere.exe', 'fiddler',
                'wireshark.exe', 'wireshark', 'tshark.exe', 'tshark',
                'charles.exe', 'charles64.exe', 'charles',
                'mitmproxy.exe', 'mitmdump.exe', 'mitmweb.exe',
                'burpsuite.exe', 'burpsuite_free.exe', 'burpsuite_pro.exe', 'burpsuite',
                'netmon.exe', 'netmon64.exe', 'networkminer.exe', 'smartsniffer.exe', 'capsa.exe',
                'pe-bear.exe', 'pe-bear', 'pe-sieve.exe', 'pe-sieve', 'hollowshunter.exe',
                'lordpe.exe', 'lordpe', 'reshacker.exe', 'resourcehacker.exe',
                'hxd.exe', 'hxd64.exe', 'hxd', '010editor.exe', '010editor',
                'die.exe', 'die_x64.exe', 'exeinfope.exe', 'peid.exe', 'pestudio.exe',
                'petools.exe', 'cff explorer.exe', 'cffexplorer.exe', 'protection_id.exe',
                'unpyc.exe', 'pycdc.exe', 'pycdc', 'uncompyle6.exe', 'decompyle++.exe',
                'frida.exe', 'frida-server.exe', 'frida-helper.exe', 'frida-agent.exe', 'frida',
                'regshot.exe', 'regshot64.exe', 'syser.exe', 'softice.exe'
            })

            # Snapshot iteration
            class PROCESSENTRY32W(ctypes.Structure):
                _fields_ = [
                    ('dwSize', ctypes.c_uint32),
                    ('cntUsage', ctypes.c_uint32),
                    ('th32ProcessID', ctypes.c_uint32),
                    ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', ctypes.c_uint32),
                    ('cntThreads', ctypes.c_uint32),
                    ('th32ParentProcessID', ctypes.c_uint32),
                    ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', ctypes.c_uint32),
                    ('szExeFile', ctypes.c_wchar * 260)
                ]

            TH32CS_SNAPPROCESS = 0x00000002
            h_snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if h_snap and h_snap != -1:
                pe = PROCESSENTRY32W()
                pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
                if _k32.Process32FirstW(h_snap, ctypes.byref(pe)):
                    while True:
                        exe_name = pe.szExeFile.lower()
                        if exe_name in _BAD_PROCS:
                            _k32.CloseHandle(h_snap)
                            _obliterate()
                        if not _k32.Process32NextW(h_snap, ctypes.byref(pe)):
                            break
                _k32.CloseHandle(h_snap)
    except Exception:
        pass

    # Vector 13: Kernel Driver Device, Named Pipe & Mutex Inspection
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            _k32 = ctypes.windll.kernel32
            _GENERIC_READ = 0x80000000
            _OPEN_EXISTING = 3
            
            _BAD_OBJECTS = (
                r"\\.\pipe\x64dbg", r"\\.\pipe\x32dbg", r"\\.\pipe\CheatEngine",
                r"\\.\pipe\HTTPDebugger", r"\\.\pipe\Frida", r"\\.\pipe\ExtremeDumper",
                r"\\.\pipe\ProcessHacker",
                r"\\.\CEDRIVER73", r"\\.\CEDRIVER74", r"\\.\DBK64", r"\\.\DBK32",
                r"\\.\KProcessHacker2", r"\\.\KProcessHacker3", r"\\.\PROCEXP152",
                r"\\.\HTTPDebuggerSdk", r"\\.\ScyllaHide", r"\\.\TitanHide", r"\\.\BlackBone"
            )
            for obj_path in _BAD_OBJECTS:
                h_file = _k32.CreateFileW(obj_path, _GENERIC_READ, 0, None, _OPEN_EXISTING, 0, None)
                if h_file and h_file != -1:
                    _k32.CloseHandle(h_file)
                    _obliterate()
    except Exception:
        pass

    # Vector 14: POSIX / Linux /proc cmdline inspection fallback
    if os.name == 'posix' and os.path.exists('/proc'):
        try:
            for pid_dir in os.listdir('/proc'):
                if pid_dir.isdigit():
                    cmd_path = os.path.join('/proc', pid_dir, 'cmdline')
                    if os.path.isfile(cmd_path):
                        with open(cmd_path, 'rb') as f:
                            cmd_raw = f.read().replace(b'\x00', b' ').lower()
                            if any(d in cmd_raw for d in (b'gdb', b'lldb', b'radare2', b'strace', b'ltrace', b'frida', b'pycdc', b'uncompyle6')):
                                _obliterate()
        except Exception:
            pass

    # Vector 15: Audit-hook liveness canary (detects audit-hook stripping)
    try:
        _g = globals()
        if '_trx_audit_count' not in _g:
            _g['_trx_audit_count'] = [0]
            def _trx_audit_hook(event, args):
                _g['_trx_audit_count'][0] += 1
            # FIX (audit P0): register through the preserved real builtin, not the nulled attr.
            (_g.get('_trx_real_addaudithook') or sys.addaudithook)(_trx_audit_hook)
        else:
            _c_before = _g['_trx_audit_count'][0]
            try:
                os.stat(os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else '.')
            except Exception:
                os.stat('.')
            _c_after = _g['_trx_audit_count'][0]
            if _c_after <= _c_before:
                _obliterate()
    except Exception:
        pass

    # Vector 16: sys.monitoring tool-slot ownership guard
    try:
        if hasattr(sys, 'monitoring') and hasattr(sys.monitoring, 'use_tool'):
            _mon = sys.monitoring
            if '_trx_mon_tool' not in globals():
                _tid = None
                for _i in (3, 4, 5):
                    try:
                        if _mon.get_tool(_i) is None:
                            _mon.use_tool(_i, 'tr0ngx_canary')
                            _mon.set_events(_i, 0)
                            _tid = _i
                            break
                    except Exception:
                        continue
                if _tid is not None:
                    globals()['_trx_mon_tool'] = _tid
            else:
                try:
                    if _mon.get_tool(globals()['_trx_mon_tool']) != 'tr0ngx_canary':
                        _obliterate()
                except Exception:
                    pass
    except Exception:
        pass

    # Vector 17: Core builtin identity watchdog (monkeypatch detection)
    try:
        import builtins as _trx_bi
        _trx_sig = (id(_trx_bi.__import__), id(_trx_bi.open), id(_trx_bi.exec),
                    id(_trx_bi.eval), id(_trx_bi.compile), id(_trx_bi.__build_class__))
        if '_trx_bi_sig' not in globals():
            globals()['_trx_bi_sig'] = _trx_sig
        elif _trx_sig != globals()['_trx_bi_sig']:
            _obliterate()
    except Exception:
        pass

    # Vector 18: Deferred trace escalation (silent one-cycle latch defeats breakpoint-and-inspect)
    try:
        if getattr(sys, 'gettrace', None) and sys.gettrace():
            if globals().get('_trx_trace_latch'):
                _obliterate()
            globals()['_trx_trace_latch'] = True
        else:
            globals()['_trx_trace_latch'] = False
    except Exception:
        pass

    # Vector 19: Linux TracerPid detection (/proc/self/status).
    # Source: pyshield protection/anti_analysis.py TracerPid vector (MIT, research
    # note) - closes the native-gdb-attach gap in the previous matrix.
    try:
        if sys.platform.startswith('linux'):
            with open('/proc/self/status', 'r') as _tps:
                for _tp_line in _tps:
                    if _tp_line.startswith('TracerPid:'):
                        if int(_tp_line.split(':', 1)[1].strip() or '0') != 0:
                            _obliterate()
                        break
    except Exception:
        pass

    # Vector 20: Dual builtins identity cross-check. Fresh import gives a pristine
    # namespace; id() equality catches attribute replacement while the type()
    # equality against print() catches proxy objects spoofing __name__.
    # Source: pyshield anti_analysis.py builtins identity check (MIT, research note).
    try:
        import builtins as _trx_bi2
        import importlib as _trx_il2
        _trx_pristine = _trx_il2.import_module('builtins')
        if id(_trx_bi2.exec) != id(_trx_pristine.exec):
            _obliterate()
        if id(_trx_bi2.compile) != id(_trx_pristine.compile):
            _obliterate()
        if type(_trx_bi2.exec) is not type(_trx_bi2.print):
            _obliterate()
        if type(_trx_bi2.compile) is not type(_trx_bi2.print):
            _obliterate()
        del _trx_pristine
    except SystemExit:
        raise
    except Exception:
        pass

# ═══ ANTI-IMPORT HOOK ═══
class _ImportBlocker:
    '''Block dangerous decompilation & debugger imports at meta_path level (PEP 451 compatible) (TRX-DEOB-009/010)'''
    _BLOCKED = frozenset({
        'uncompyle6', 'decompyle3', 'decompyle++', 'decompyle', 'xdis', 'pycdc', 'bytecode_tools',
        'pydevd', 'debugpy', 'coverage', 'hunter', 'snooper', 'snoop', 'objgraph', 'pympler',
        'unpyc', 'easy_python_decompiler', 'pickletools', 'pydevd_tracing', 'pydevd_bundle'
    })

    def find_spec(self, name, path=None, target=None):
        name_lower = name.lower()
        if any(name_lower == blocked or name_lower.startswith(blocked + '.') for blocked in self._BLOCKED):
            _obliterate()
        return None

    # Legacy fallback for Python < 3.4
    def find_module(self, name, path=None):
        name_lower = name.lower()
        if any(name_lower == blocked or name_lower.startswith(blocked + '.') for blocked in self._BLOCKED):
            return self
        return None

    def load_module(self, name):
        _obliterate()

def _install_import_blocker():
    blocker = _ImportBlocker()
    if blocker not in sys.meta_path:
        sys.meta_path.insert(0, blocker)

# ═══ ANTI-MEMORY DUMP, REFLECTION NEUTRALIZATION & C-LEVEL TRACE PURGE ═══
def _anti_memory_analysis():
    '''Make memory analysis harder, neutralize reflection/bytecode dumpers, wipe linecache, clear tracebacks and wipe C-level trace hooks (TRX-DEOB-009/010)'''
    try:
        gc.collect()
        if hasattr(gc, 'set_debug'):
            gc.set_debug(0)
    except Exception:
        pass

    # Neutralize pure disassembly and debugging tools if already loaded
    for _mod_name, _func_names in [
        ('dis', ['dis', 'show_code', 'disassemble', 'distb', 'disco']),
        ('pdb', ['set_trace', 'Pdb']),
    ]:
        if _mod_name in sys.modules and sys.modules[_mod_name] is not None:
            try:
                _m = sys.modules[_mod_name]
                for _fn in _func_names:
                    if hasattr(_m, _fn):
                        setattr(_m, _fn, lambda *a, **k: None)
            except Exception:
                pass

    # Clear source line cache to prevent debuggers/inspect from extracting original source lines
    try:
        import linecache
        linecache.clearcache()
    except Exception:
        pass

    # Wipe exception/traceback residue from sys
    for attr in ('last_traceback', 'last_value', 'last_type', 'last_exc'):
        if hasattr(sys, attr):
            try:
                delattr(sys, attr)
            except Exception:
                pass

    # Null out Python-level tracing & profiling
    # IMPORTANT: Must use None (not a lambda) so sys.gettrace()/getprofile() return None,
    # otherwise _anti_debugger() will detect a non-None trace and call _obliterate().
    try:
        sys.settrace(None)
        if hasattr(sys, 'setprofile'):
            sys.setprofile(None)
    except Exception:
        pass

# ═══ SELF-INTEGRITY CHECK (BYTECODE OPCODES CHECKSUM) ═══
def _self_verify():
    '''Verify own functions and bytecode opcodes have not been patched or hooked'''
    checks = [_obliterate, _anti_debugger, _verify_builtins,
              _protect_marshal, _anti_memory_analysis]
    for check in checks:
        if not callable(check):
            _obliterate()
        if not isinstance(check, types.FunctionType):
            _obliterate()
        if not hasattr(check, '__code__') or not check.__code__.co_code:
            _obliterate()

# ═══ CONTINUOUS MONITORING THREAD ═══
def _start_watchdog():
    def _monitor():
        _check_count = 0
        while _SHIELD._active:
            try:
                _check_count += 1
                _anti_debugger()
                _verify_builtins()
                _self_verify()
                if '_hidden_check' in dir() and callable(_hidden_check):
                    _hidden_check()

                # Periodic deep scan every 10 checks
                if _check_count % 10 == 0:
                    _anti_memory_analysis()

                # Randomize sleep to avoid timing-based bypass
                time.sleep(random.uniform(0.3, 1.5))
            except SystemExit:
                os._exit(1)
            except Exception:
                pass

    t = threading.Thread(target=_monitor, daemon=True, name=''.join(
        random.choices('abcdefghijklmnop', k=12)))
    t.start()

# ═══ ANTI-MONKEY PATCHING ═══
def _freeze_critical():
    '''Make critical objects harder to monkey-patch'''
    import builtins

    # Store references that can't be easily found
    _hidden = type('', (), {
        '_e': builtins.exec,
        '_v': builtins.eval,
        '_c': builtins.compile,
        '_i': builtins.__import__,
        '_m': marshal.loads,
    })()

    # Verify periodically
    def _check_hidden():
        _safe_names = ('_safe_exec', '_safe_eval', '_guarded_loads', '_safe_loads', '_wrapped', '<lambda>', 'exec', 'eval', 'loads', 'compile')
        _cur_e = getattr(builtins, 'exec', None)
        _cur_v = getattr(builtins, 'eval', None)
        if _cur_e is not None and id(_hidden._e) != id(_cur_e):
            if not (hasattr(_cur_e, '__name__') and _cur_e.__name__ in _safe_names):
                _obliterate()
        if _cur_v is not None and id(_hidden._v) != id(_cur_v):
            if not (hasattr(_cur_v, '__name__') and _cur_v.__name__ in _safe_names):
                _obliterate()
        if id(_hidden._m) != id(marshal.loads.__wrapped__ if hasattr(marshal.loads, '__wrapped__') else marshal.loads):
            pass  # We wrapped it ourselves

    return _check_hidden

# ═══ INITIALIZE ALL PROTECTION ═══
try:
    _snapshot_builtins()
    _anti_debugger()
    _install_import_blocker()
    _protect_marshal()
    _protect_exec_eval()
    _anti_memory_analysis()
    _self_verify()
    _hidden_check = _freeze_critical()
    _start_watchdog()
except SystemExit:
    os._exit(1)
except Exception:
    pass
"""

# ═══════════════════════════════════════════════════════════════
# VELIMATIX ANTI-HOOK ENGINE
# ═══════════════════════════════════════════════════════════════

velimatix_anti_hook = r"""
import traceback as _tb_, marshal as _m_, sys as _s_, types as _tp_, random as _rnd

class _VELIMATIX_SHIELD_(MemoryError): pass

class _VeliGuard_:
    _HOOKED = set()
    _FUNC_TYPES = {}

    @staticmethod
    def _terminate():
        try:
            __import__('gc').collect()
        except: pass
        try:
            __import__('os')._exit(1)
        except Exception:
            raise _VELIMATIX_SHIELD_('>> PROTECTION TRIGGERED <<') from None

    @staticmethod
    def verify_hook(func, module_name):
        # Check if function module looks suspicious (blocklist approach)
        if callable(func) and hasattr(func, '__module__'):
            mod = func.__module__
            if mod and isinstance(mod, str):
                # Blocklist - only block known bad reversing modules
                blocked = ['uncompyle', 'decompyle', 'pycdc', 'xdis', 'pydevd', 'debugpy', 'frida']
                if any(bad in mod.lower() for bad in blocked):
                    _VeliGuard_._HOOKED.add(mod)
                    _VeliGuard_._terminate()

    @staticmethod
    def guard_wrapper(func):
        def _wrapped(*args, **kwargs):
            if args and isinstance(args[0], str) and args[0] in _VeliGuard_._HOOKED:
                _VeliGuard_._terminate()
            return func(*args, **kwargs)
        _wrapped.__module__ = func.__module__
        _wrapped.__name__ = func.__name__
        return _wrapped

    @staticmethod
    def verify_stack():
        try:
            stack = _tb_.extract_stack()
            if stack and isinstance(stack, list):
                for frame in stack[:-2]:
                    fn = frame.filename.lower()
                    if any(bad in fn for bad in ['uncompyle', 'decompyle', 'pycdc', 'xdis', 'pydevd', 'debugpy', 'frida']):
                        _VeliGuard_._terminate()
        except Exception:
            pass

    @staticmethod
    def verify_type_integrity(module_name, func_name):
        mod = __import__(module_name)
        func = getattr(mod, func_name, None)
        if func is None:
            _VeliGuard_._terminate()
        _VeliGuard_._FUNC_TYPES[f"{module_name}.{func_name}"] = type(func)
        _VeliGuard_.verify_hook(func, module_name)

    @staticmethod
    def check_type_changed():
        for key, expected_type in list(_VeliGuard_._FUNC_TYPES.items()):
            parts = key.split('.', 1)
            try:
                mod = __import__(parts[0])
                func = getattr(mod, parts[1], None)
                if func is not None:
                    # Allow builtins/functions wrapped by internal guard closures
                    if type(func) != expected_type and not callable(func):
                        _VeliGuard_._terminate()
            except Exception:
                pass

    @staticmethod
    def protect_marshal():
        import marshal as _real_m
        _real_loads = _real_m.loads
        _real_loads_id = id(_real_loads)

        def _safe_loads(data, *args, **kwargs):
            frame = _s_._getframe(1)
            caller = frame.f_code.co_filename.lower()
            if any(x in caller for x in ['uncompyle', 'decompyle', 'pycdc', 'xdis', 'pydevd', 'debugpy', 'frida']):
                _VeliGuard_._terminate()
            if id(_real_loads) != _real_loads_id:
                _VeliGuard_._terminate()
            return _real_loads(data, *args, **kwargs)

        _real_m.loads = _safe_loads
        _s_.modules['marshal'] = _real_m
        # Update stored type after wrapping to avoid false positives
        _VeliGuard_._FUNC_TYPES['marshal.loads'] = type(_safe_loads)

    @staticmethod
    def anti_monkey_patch():
        import builtins as _b
        _safe_names = ('_safe_exec', '_safe_eval', '_guarded_loads', '_safe_loads', '_wrapped', '<lambda>', 'exec', 'eval', 'loads', 'compile')
        _snapshot = {
            'exec': id(_b.exec),
            'eval': id(_b.eval),
            'compile': id(_b.compile),
            '__import__': id(_b.__import__),
            'open': id(_b.open),
            'getattr': id(_b.getattr),
        }

        def _check_patch():
            for name, orig_id in _snapshot.items():
                current = getattr(_b, name, None)
                if current is None:
                    _VeliGuard_._terminate()
                curr_id = id(current)
                # Allow internal Tr0ngX guard closures and recognized safe wrappers
                _is_known_guard = (
                    hasattr(current, '_func') or
                    curr_id in globals().get('_ORIGINAL_BUILTINS', {}).values() or
                    (hasattr(current, '__name__') and current.__name__ in _safe_names)
                )
                if curr_id != orig_id and not _is_known_guard:
                    _VeliGuard_._terminate()
            _VeliGuard_.check_type_changed()

        return _check_patch

    @staticmethod
    def continuous_guard():
        import threading, time
        # Check if anti-debug shield's watchdog is already running
        # to avoid duplicate patrol threads competing with each other
        _existing_threads = [t.name for t in threading.enumerate()]
        _anti_shield_active = any('_SHIELD' in str(t) for t in threading.enumerate())
        if _anti_shield_active or '_SHIELD' in dir(__builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)):
            # Anti-debug shield already has its own watchdog - skip duplicate
            return

        _checker = _VeliGuard_.anti_monkey_patch()

        def _patrol():
            while True:
                try:
                    _checker()
                    _VeliGuard_.verify_stack()

                    poison = {'pydevd', 'debugpy', 'pdb', 'coverage', 'hunter', 'snooper',
                              'uncompyle6', 'decompyle3', 'xdis', 'bytecode'}
                    if set(_s_.modules.keys()) & poison:
                        _VeliGuard_._terminate()

                    if _s_.gettrace() is not None:
                        _VeliGuard_._terminate()

                    time.sleep(_rnd.uniform(0.5, 2.0))
                except _VELIMATIX_SHIELD_:
                    __import__('os')._exit(1)
                except SystemExit:
                    __import__('os')._exit(1)
                except Exception:
                    pass

        t = threading.Thread(target=_patrol, daemon=True,
                             name=''.join(_rnd.choices('abcdefghijklmnop', k=16)))
        t.start()

    @staticmethod
    def init():
        # protect_marshal MUST come first to update types before we store them
        _VeliGuard_.protect_marshal()
        _VeliGuard_.verify_type_integrity('marshal', 'loads')
        _VeliGuard_.verify_type_integrity('builtins', 'exec')
        _VeliGuard_.verify_type_integrity('builtins', 'eval')
        _VeliGuard_.verify_type_integrity('builtins', 'compile')
        _VeliGuard_.verify_stack()
        _VeliGuard_.continuous_guard()

try:
    _VeliGuard_.init()
except _VELIMATIX_SHIELD_:
    __import__('os')._exit(1)
except SystemExit:
    __import__('os')._exit(1)
except Exception:
    pass
"""

# ═══════════════════════════════════════════════════════════════
# AST TRANSFORMATION ENGINE - ENHANCED
# ═══════════════════════════════════════════════════════════════

def _moreobf(tree):
    """Enhanced AST obfuscation with junk code injection"""

    def rd_local():
        return str(random.randint(0x1E000000000, 0x7E000000000))

    def generate_junk_expr():
        junk_type = random.randint(1, 8)
        if junk_type == 1:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='str'),
                args=[ast.Constant(value=random.randint(0, 99999))],
                keywords=[]
            ))
        elif junk_type == 2:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='bool'),
                args=[ast.Constant(value=random.randint(0, 1))],
                keywords=[]
            ))
        elif junk_type == 3:
            return ast.Assign(
                targets=[ast.Name(id="_v_" + rd_local())],
                value=ast.Constant(value=random.randint(0, 0xFFFFFF)),
                lineno=None
            )
        elif junk_type == 4:
            return ast.Assign(
                targets=[ast.Name(id="_v_" + rd_local())],
                value=ast.BinOp(
                    left=ast.Constant(value=random.randint(1, 1000)),
                    op=random.choice([ast.Add(), ast.Sub(), ast.Mult(), ast.BitXor(), ast.BitOr()]),
                    right=ast.Constant(value=random.randint(1, 1000))
                ),
                lineno=None
            )
        elif junk_type == 5:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='type'),
                args=[ast.Constant(value=random.choice([0, '', [], None, True, False]))],
                keywords=[]
            ))
        elif junk_type == 6:
            # Junk if statement
            return ast.If(
                test=ast.Compare(
                    left=ast.Constant(value=random.randint(100, 999)),
                    ops=[ast.Gt()],
                    comparators=[ast.Constant(value=random.randint(1000, 9999))]
                ),
                body=[ast.Assign(
                    targets=[ast.Name(id="_v_" + rd_local())],
                    value=ast.Constant(value=None),
                    lineno=None
                )],
                orelse=[]
            )
        elif junk_type == 7:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='len'),
                args=[ast.Constant(value=secrets.token_hex(4))],
                keywords=[]
            ))
        else:
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='int'),
                args=[ast.BinOp(
                    left=ast.Constant(value=random.randint(1, 100)),
                    op=ast.Add(),
                    right=ast.Constant(value=random.randint(1, 100))
                )],
                keywords=[]
            ))

    def junk(en, max_value):
        cases = []
        line = max_value + 1
        for i in range(random.randint(3, 8)):
            case_name = "_v_" + rd_local()
            case_body = [
                ast.If(
                    test=ast.Compare(
                        left=ast.Subscript(
                            value=ast.Attribute(value=ast.Name(id=en), attr='args'),
                            slice=ast.Constant(value=0)
                        ),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value=line)]
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id=case_name)],
                            value=ast.Constant(value=random.randint(0xFFFFF, 0xFFFFFFFFFFFF)),
                            lineno=None
                        ),
                        generate_junk_expr(),
                    ],
                    orelse=[]
                )
            ]
            cases.extend(case_body)
            line += 1
        return cases

    def bl(body):
        var_name = "_v_" + rd_local()
        en = "_v_" + rd_local()

        tb = [
            ast.AugAssign(target=ast.Name(id=var_name), op=ast.Add(), value=ast.Constant(value=1)),
            ast.Try(
                body=[ast.Raise(exc=ast.Call(func=ast.Name(id='MemoryError'),
                                             args=[ast.Name(id=var_name)], keywords=[]))],
                handlers=[ast.ExceptHandler(type=ast.Name(id='MemoryError'), name=en, body=[])],
                orelse=[], finalbody=[]
            )
        ]

        for i in body:
            tb[1].handlers[0].body.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Subscript(
                            value=ast.Attribute(value=ast.Name(id=en), attr='args'),
                            slice=ast.Constant(value=0)
                        ),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value=1)]
                    ),
                    body=[i], orelse=[]
                )
            )

        tb[1].handlers[0].body.extend(junk(en, len(body) + 1))
        pre_junk = [generate_junk_expr() for _ in range(random.randint(1, 3))]

        node = ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=0), lineno=None)
        return pre_junk + [node] + tb

    def _bl(node):
        olb = node.body
        var_name = "_v_" + rd_local()
        en = "_v_" + rd_local()

        tb = [
            ast.AugAssign(target=ast.Name(id=var_name), op=ast.Add(), value=ast.Constant(value=1)),
            ast.Try(
                body=[ast.Raise(exc=ast.Call(func=ast.Name(id='MemoryError'),
                                             args=[ast.Name(id=var_name)], keywords=[]))],
                handlers=[ast.ExceptHandler(type=ast.Name(id='MemoryError'), name=en, body=[])],
                orelse=[], finalbody=[]
            )
        ]
        for i in olb:
            tb[1].handlers[0].body.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Subscript(
                            value=ast.Attribute(value=ast.Name(id=en), attr='args'),
                            slice=ast.Constant(value=0)
                        ),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value=1)]
                    ),
                    body=[i], orelse=[]
                )
            )
        tb[1].handlers[0].body.extend(junk(en, len(olb) + 1))
        node.body = [ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=0), lineno=None)] + tb
        return node

    def on(node):
        if isinstance(node, ast.FunctionDef):
            return _bl(node)
        return node

    nb = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nb.append(on(node))
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            nb.extend(bl([node]))
        elif isinstance(node, ast.Expr):
            nb.extend(bl([node]))
        elif isinstance(node, (ast.If, ast.While, ast.For)):
            nb.extend(bl([node]))
        else:
            nb.append(node)

    tree.body = nb
    return tree


def __moreobf(x):
    try:
        return ast.unparse(_moreobf(ast.parse(x)))
    except Exception as e:
        return x


# ═══════════════════════════════════════════════════════════════
# F-STRING HANDLER
# ═══════════════════════════════════════════════════════════════

def _render_fstring_template(node: ast.JoinedStr):
    parts = []
    args = []

    def render(joined: ast.JoinedStr) -> str:
        seg_parts = []
        for value in joined.values:
            if isinstance(value, ast.FormattedValue):
                idx = len(args)
                args.append(value.value)
                seg = "{" + str(idx)
                if value.conversion is not None and value.conversion != -1:
                    seg += "!" + chr(value.conversion)
                if value.format_spec is not None:
                    if isinstance(value.format_spec, ast.JoinedStr):
                        seg += ":" + render(value.format_spec)
                    elif isinstance(value.format_spec, ast.Constant) and isinstance(value.format_spec.value, str):
                        spec_text = str(value.format_spec.value).replace("{", "{{").replace("}", "}}")
                        seg += ":" + spec_text
                seg += "}"
                seg_parts.append(seg)
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                seg_parts.append(str(value.value).replace("{", "{{").replace("}", "}}"))
        return "".join(seg_parts)

    return render(node), args


def fm(node: ast.JoinedStr) -> ast.Call:
    template, args = _render_fstring_template(node)
    return ast.Call(
        func=ast.Attribute(
            value=ast.Constant(value=template),
            attr="format",
            ctx=ast.Load(),
        ),
        args=args,
        keywords=[],
    )


# ═══════════════════════════════════════════════════════════════
# SYNTAX OBFUSCATION
# ═══════════════════════════════════════════════════════════════

def _syntax(x):
    def v(node):
        if node.name:
            new_body = []
            for idx, statement in enumerate(node.body):
                if isinstance(statement, (ast.Global, ast.Nonlocal, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    new_body.append(statement)
                    continue
                # Skip docstring (first Expr containing Constant string)
                if idx == 0 and isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                    new_body.append(statement)
                    continue
                ten = ast.Try(
                    body=[
                        ast.parse("0/0").body[0],
                        ast.parse(f"""if "ngocuyen" == "deptrai":{rd()},{rd()},{rd()},{rd()},{rd()}\nelse:pass""").body[0]
                    ],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id='ZeroDivisionError', ctx=ast.Load()),
                            name=None,
                            body=[z(statement)]
                        )
                    ],
                    orelse=[], finalbody=[]
                )
                new_body.append(ten)
            node.body = new_body
            return node

    def z(statement):
        return ast.Try(
            body=[ast.parse("0/0").body[0]],
            handlers=[
                ast.ExceptHandler(
                    type=ast.Name(id='ZeroDivisionError', ctx=ast.Load()),
                    name=None,
                    body=[statement]
                )
            ],
            orelse=[ast.Pass()],
            finalbody=[ast.parse("str(100)").body[0]]
        )

    tree = ast.parse(x)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            v(node)
    return ast.unparse(tree)


# ═══════════════════════════════════════════════════════════════
# CORE OBFUSCATION ENGINE
# ═══════════════════════════════════════════════════════════════

_obf_progress = {'current': 0, 'total': 0}

def _print_progress_bar(current, total, prefix='[TR0NGX]', suffix='biến đã obfuscate', length=40):
    """Hiển thị progress bar cực đẹp với animation (tắt trong quiet/CLI mode)"""
    if _EngineState.cli_quiet_mode:
        return
    import sys
    percent = float(current) * 100 / total if total > 0 else 0
    filled_length = int(length * current // total) if total > 0 else 0
    bar = '█' * filled_length + '░' * (length - filled_length)
    
    # Emoji theo progress
    if percent < 25:
        emoji = "🚀"
    elif percent < 50:
        emoji = "⚡"
    elif percent < 75:
        emoji = "🔥"
    elif percent < 90:
        emoji = "💎"
    else:
        emoji = "⭐"
    
    sys.stdout.write(f'\r{prefix}         {emoji} [{bar}] {percent:5.1f}% | {current}/{total} {suffix}')
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write('\n')
        sys.stdout.flush()

class _MainAstTransformer(ast.NodeTransformer):
    def __init__(self, skip_ids):
        self._skip_ids = skip_ids

    def visit_Constant(self, node: ast.Constant):
        if id(node) in self._skip_ids:
            return node
        if isinstance(node.value, bool):
            try:
                return ast.parse(obfint(node.value)).body[0].value
            except Exception:
                return node
        elif isinstance(node.value, str):
            try:
                return ast.parse(obfstr(node.value)).body[0].value
            except Exception:
                return node
        elif isinstance(node.value, int):
            try:
                return ast.parse(obfint(node.value)).body[0].value
            except Exception:
                return node
        return node

    def visit_JoinedStr(self, node: ast.JoinedStr):
        try:
            return fm(node)
        except Exception:
            return node

def obfuscate(node):
    # Collect all AST node IDs that must NOT have constants replaced with lambda expressions
    _skip_ids = set()
    for n in ast.walk(node):
        if isinstance(n, ast.match_case) and hasattr(n, 'pattern') and n.pattern:
            for child in ast.walk(n.pattern):
                _skip_ids.add(id(child))
        if isinstance(n, ast.arg) and hasattr(n, 'annotation') and n.annotation:
            for child in ast.walk(n.annotation):
                _skip_ids.add(id(child))
        if isinstance(n, ast.AnnAssign) and hasattr(n, 'annotation') and n.annotation:
            for child in ast.walk(n.annotation):
                _skip_ids.add(id(child))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(n, 'returns') and n.returns:
            for child in ast.walk(n.returns):
                _skip_ids.add(id(child))
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(n, 'decorator_list'):
            for d in n.decorator_list:
                for child in ast.walk(d):
                    _skip_ids.add(id(child))

    transformer = _MainAstTransformer(_skip_ids)
    return transformer.visit(node)


def rename_function(node, ol, nn):

    if isinstance(node, str):
        node = ast.parse(node)
    # Scope safety: if the target name is locally bound (parameter, store target,
    # except-handler alias, import alias), renaming Loads would rebind user code
    # to the wrong object. Bail out of renaming for this pass.
    for i in ast.walk(node):
        if isinstance(i, ast.arg) and i.arg == ol:
            _DEBUG_MAP["skipped_renames"].append(ol)
            return node
        if isinstance(i, ast.Name) and isinstance(i.ctx, (ast.Store, ast.Del)) and i.id == ol:
            _DEBUG_MAP["skipped_renames"].append(ol)
            return node
        if isinstance(i, ast.ExceptHandler) and i.name == ol:
            _DEBUG_MAP["skipped_renames"].append(ol)
            return node

    _DEBUG_MAP["renamed_functions"][ol] = nn
    for i in ast.walk(node):
        if isinstance(i, ast.FunctionDef) and i.name == ol:
            i.name = nn
        elif isinstance(i, ast.AsyncFunctionDef) and i.name == ol:
            i.name = nn
        elif isinstance(i, ast.Attribute) and isinstance(i.value, ast.Name) and i.value.id == ol:
            i.value.id = nn
        elif isinstance(i, ast.Call) and isinstance(i.func, ast.Name) and i.func.id == ol:
            i.func.id = nn
        elif isinstance(i, ast.Name) and isinstance(i.ctx, ast.Load) and i.id == ol:
            i.id = nn
    return node


# ═══════════════════════════════════════════════════════════════
# MATCH-CASE JUNK GENERATOR
# ═══════════════════════════════════════════════════════════════

def random_match_case():
    val = randomint()
    var1 = ast.Constant(value=val, kind=None)
    var2 = ast.Constant(value=val, kind=None)

    junk_assigns = []
    for _ in range(random.randint(2, 5)):
        junk_assigns.append(
            ast.Assign(
                lineno=0, col_offset=0,
                targets=[ast.Name(id=rd(), ctx=ast.Store())],
                value=ast.Constant(value=random.randint(0, 0xFFFFFF), kind=None),
            )
        )

    return ast.Match(
        subject=ast.Compare(left=var1, ops=[ast.Eq()], comparators=[var2]),
        cases=[
            ast.match_case(
                pattern=ast.MatchValue(value=ast.Constant(value=True, kind=None)),
                body=[
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id="MemoryError", ctx=ast.Load()),
                            args=[ast.Constant(value=True)],
                            keywords=[]
                        )
                    )
                ],
            ),
            ast.match_case(
                pattern=ast.MatchValue(value=ast.Constant(value=False, kind=None)),
                body=[
                    ast.Assign(
                        lineno=0, col_offset=0,
                        targets=[ast.Name(id=rd(), ctx=ast.Store())],
                        value=ast.Constant(value=[[True], [False], [None]], kind=None),
                    ),
                    ast.Expr(
                        lineno=0, col_offset=0,
                        value=ast.Call(
                            func=ast.Name(id=_str, ctx=ast.Load()),
                            args=[ast.Constant(value=[rd()], kind=None)],
                            keywords=[],
                        ),
                    ),
                ] + junk_assigns,
            ),
        ],
    )


def trycatch(body, loop=1):
    ar = []
    for x in body:
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Try)):
            ar.append(x)
            continue
        j = x
        for _ in range(loop):
            j = ast.Try(
                body=[random_match_case()],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="MemoryError", ctx=ast.Load()),
                        name=rd(), body=[j],
                    )
                ],
                orelse=[], finalbody=[],
            )
        ar.append(j)
    return ar


# ═══════════════════════════════════════════════════════════════
# MAIN OBFUSCATION PIPELINE
# ═══════════════════════════════════════════════════════════════

def obf(code, layer=1):
    def ps(x):
        if isinstance(x, str):
            return ast.parse(x)
        return x

    # Rename print/input once on layer 1
    if layer == 1:
        code = rename_function(ps(code), "print", __print)
        code = rename_function(code, "input", __input)

    tree = ps(code)
    obfuscate(tree)
    # Only inject match-case decoy try-except on layer 1 to prevent exponential bloat
    tbd = trycatch(tree.body, 1) if layer == 1 else tree.body

    def ast_to_code(node):
        if isinstance(node, list):
            return '\n'.join(ast.unparse(n) for n in node)
        return ast.unparse(node)

    return ast_to_code(tbd)


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
    lzma_on = bool(_EngineState.lzma_layer)
    if lzma_on:
        try:
            import lzma as _lzma
            data = _lzma.compress(data, preset=9)
        except Exception:
            lzma_on = False
    data = zlib.compress(data, 6)
    salt = secrets.token_bytes(16)
    if _EngineState.env_key_lock and not password:
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
    if not password and _EngineState.env_key_lock:
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
    _armor_dec = _armor['dec']
    _armor_rev = "[::-1]" if _armor['rev'] else ""
    if _armor['lzma']:
        _lzma_step = "_s6 = lzma.decompress(_s5)" + chr(10) + "_s5 = _s6"
        _lzma_import = ", lzma"
    else:
        _lzma_step = ""
        _lzma_import = ""
    if not _lzma_step:
        # collapse: no extra stage
        _lzma_step = ""
    if _EngineState.env_key_lock and not password:
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

_payload_b85 = {enc_b85!r}
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

_payload_b85 = {enc_b85!r}
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


# ═══════════════════════════════════════════════════════════════
# SELF-MODIFYING & STEALTH ANTI-TAMPER ENGINE
# ═══════════════════════════════════════════════════════════════

def _generate_self_modify_wrapper():
    """Generate stealth multi-hash anti-tamper and zero-width self-morphing engine."""
    v_fn = rd('state_machine')
    v_sf = rd('guard')
    v_raw = rd('biopaque')
    v_zw = rd('guard')
    v_c = rd('state_machine')
    v_h = rd('state_machine')
    v_sig = rd('guard')
    v_b = rd('state_machine')
    v_fr = rd('guard')
    v_co = rd('state_machine')
    v_bits = rd('state_machine')
    v_nw = rd('guard')

    return f"""
def {v_fn}():
    try:
        import os, sys, hashlib, time
        {v_sf} = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else (__file__ if '__file__' in globals() else None)
        if {v_sf} and os.path.exists({v_sf}):
            with open({v_sf}, 'rb') as {v_raw}:
                _orig_bytes = {v_raw}.read()
            {v_c} = _orig_bytes
            # Multi-layer canonical strip (removes invisible zero-width unicode & trailing spaces)
            {v_zw} = [b'\\xe2\\x80\\x8b', b'\\xe2\\x80\\x8c', b'\\xef\\xbb\\xbf', b'\\xe2\\x80\\x8d']
            for {v_b} in {v_zw}:
                {v_c} = {v_c}.replace({v_b}, b'')
            {v_c} = {v_c}.rstrip()
            {v_h} = hashlib.sha256({v_c}).hexdigest()
            # Frame stack & Merkle Bytecode Verification (co_code + co_consts + co_names)
            try:
                {v_fr} = sys._getframe(1)
                _m_nodes = [{v_fr}.f_code.co_code]
                for _const in {v_fr}.f_code.co_consts:
                    if isinstance(_const, (bytes, str, int, float, bool)):
                        _m_nodes.append(str(_const).encode('utf-8', 'ignore'))
                for _name in {v_fr}.f_code.co_names:
                    _m_nodes.append(_name.encode('utf-8', 'ignore'))
                {v_co} = hashlib.sha256(b''.join(_m_nodes)).hexdigest()
            except Exception:
                {v_co} = {v_h}
            # Anti-hooking integrity: verify builtins/sys trace
            if getattr(sys, 'gettrace', lambda: None)() is not None:
                return
            # Invisible Zero-Width Morphing (Zero plain text markers!)
            {v_bits} = ''.join(f'{{ord({v_b}):08b}}' for {v_b} in {v_h}[:16])
            {v_sig} = '# ' + ''.join('\\u200c' if {v_b} == '1' else '\\u200b' for {v_b} in {v_bits})
            _sig_b = {v_sig}.encode('utf-8')
            if _sig_b not in _orig_bytes:
                {v_nw} = _orig_bytes.rstrip() + b'\\n' + _sig_b
                try:
                    with open({v_sf}, 'wb') as {v_raw}:
                        {v_raw}.write({v_nw})
                except Exception:
                    pass
    except Exception:
        pass

try:
    {v_fn}()
except Exception:
    pass
"""

def _generate_anti_vm_shield() -> str:
    """Generate hyper-strict industrial-grade Anti-VM, Sandbox & Virtual Network detection shield."""
    fn_name = rd('state_machine')
    abort_fn = rd('guard')
    cores_var = rd('biopaque')
    user_var = rd('state_machine')
    host_var = rd('guard')
    
    return f"""
# ═══ ANTI-VIRTUALIZATION, SANDBOX & VIRTUAL NETWORK MATRIX ═══
def {fn_name}():
    import os, sys

    def {abort_fn}():
        try:
            import gc
            gc.collect()
        except Exception:
            pass
        try:
            os._exit(1)
        except Exception:
            sys.exit(1)

    # 1. CPU Core & Memory Quantity Check (Automated analysis sandboxes often allocate <= 1 vCPU or <= 2GB RAM)
    try:
        {cores_var} = os.cpu_count()
        if {cores_var} is not None and {cores_var} <= 1:
            {abort_fn}()
    except Exception:
        pass

    # 2. Known Automated Sandbox Usernames & Hostnames
    try:
        {user_var} = (os.getenv('USERNAME') or os.getenv('USER') or '').upper()
        {host_var} = (os.getenv('COMPUTERNAME') or os.getenv('HOSTNAME') or '').upper()
        _bad_identities = {{'SANDBOX', 'VIRUS', 'MALTEST', 'TEQUILABOOMBOOM', 'SAMPLE', 'CURRENTUSER', 'DESKTOP-ANALYSIS', 'USER-PC', 'JOHN-PC', 'TEST-PC', 'KLONE', 'MALWARE', 'CUCKOO'}}
        if {user_var} in _bad_identities or {host_var} in _bad_identities:
            {abort_fn}()
    except Exception:
        pass

    # 3. Virtual Machine MAC Address OUI & Virtual Network Interface Inspection
    try:
        import uuid
        _mac_num = uuid.getnode()
        _mac_hex = f"{{_mac_num:012x}}".upper()
        _mac_oui = ':'.join([_mac_hex[i:i+2] for i in range(0, 6, 2)])
        # VMware, VirtualBox, Parallels, QEMU/KVM, Xen virtual OUI prefixes
        _bad_ouis = (
            '00:05:69', '00:0C:29', '00:1C:14', '00:50:56', # VMware
            '08:00:27',                                     # VirtualBox
            '00:1C:42',                                     # Parallels
            '52:54:00', '54:52:00',                         # QEMU / KVM
            '00:16:3E',                                     # Xen
            '00:03:FF', '00:15:5D'                          # Microsoft Virtual
        )
        for _bad_prefix in _bad_ouis:
            if _mac_oui.startswith(_bad_prefix):
                {abort_fn}()
    except Exception:
        pass

    # 4. Windows-Specific VM, Virtual Network & Hypervisor Deep Inspection
    if os.name == 'nt':
        # A. Screen Resolution Metrics (Headless sandboxes often have small/default resolution)
        try:
            import ctypes
            if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32'):
                _w = ctypes.windll.user32.GetSystemMetrics(0)
                _h = ctypes.windll.user32.GetSystemMetrics(1)
                if 0 < _w < 800 or 0 < _h < 600:
                    {abort_fn}()
        except Exception:
            pass

        # B. System Uptime Check (Fresh sandbox snapshots often have uptime < 60s)
        try:
            import ctypes
            if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
                _uptime = ctypes.windll.kernel32.GetTickCount64()
                if 0 < _uptime < 60000:
                    {abort_fn}()
        except Exception:
            pass

        # C. VM Artifact & Driver Files Detection
        try:
            _sys_root = os.getenv('SystemRoot', r'C:\\Windows')
            _drv_dir = os.path.join(_sys_root, 'System32', 'drivers')
            _vm_drivers = {{'vboxmouse.sys', 'vboxguest.sys', 'vboxsf.sys', 'vboxvideo.sys',
                           'vmmouse.sys', 'vmhgfs.sys', 'vmusbmouse.sys', 'qemu-ga.exe', 'prl_fs.sys'}}
            if os.path.exists(_drv_dir):
                for _fname in os.listdir(_drv_dir):
                    if _fname.lower() in _vm_drivers:
                        {abort_fn}()
        except Exception:
            pass

        # D. BIOS & Hardware Manufacturer Registry Check
        try:
            import winreg
            _reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\\Description\\System\\BIOS"),
                (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\\Description\\System"),
            ]
            _vm_kw = (b'vmware', b'virtualbox', b'innotek', b'qemu', b'bochs', b'kvm', b'parallels', b'xen', b'seabios')
            for _hkey, _subkey in _reg_paths:
                try:
                    with winreg.OpenKey(_hkey, _subkey) as _k:
                        for _i in range(winreg.QueryInfoKey(_k)[1]):
                            _, _vdata, _ = winreg.EnumValue(_k, _i)
                            _vstr = str(_vdata).lower().encode()
                            if any(_kw in _vstr for _kw in _vm_kw):
                                {abort_fn}()
                except Exception:
                    pass
        except Exception:
            pass

        # E. Virtual Disk & SCSI Storage Device Models Check
        try:
            import winreg
            _scsi_reg = r"HARDWARE\\DEVICEMAP\\Scsi"
            _bad_disk_kw = (b'vbox', b'vmware', b'qemu', b'virtio', b'virtual disk', b'parallels')
            def _scan_key_recursive(_hk, _path):
                try:
                    with winreg.OpenKey(_hk, _path) as _k:
                        num_sub, num_val, _ = winreg.QueryInfoKey(_k)
                        for _i in range(num_val):
                            _vn, _vd, _ = winreg.EnumValue(_k, _i)
                            _vd_bytes = str(_vd).lower().encode()
                            if any(_kw in _vd_bytes for _kw in _bad_disk_kw):
                                {abort_fn}()
                        for _j in range(num_sub):
                            _sub_name = winreg.EnumKey(_k, _j)
                            _scan_key_recursive(_hk, _path + chr(92) + _sub_name)
                except Exception:
                    pass
            _scan_key_recursive(winreg.HKEY_LOCAL_MACHINE, _scsi_reg)
        except Exception:
            pass

        # F. Virtual Network Adapters Registry & Sandboxed NAT Gateway Inspection
        try:
            import winreg
            _net_class_reg = r"SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}"
            _vm_net_kw = (b'virtualbox', b'vmware accelerated', b'vmware virtual', b'red hat virtio', b'parallels virtual', b'qemu virtio')
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _net_class_reg) as _net_key:
                for _idx in range(winreg.QueryInfoKey(_net_key)[0]):
                    try:
                        _sk_name = winreg.EnumKey(_net_key, _idx)
                        if _sk_name.isdigit():
                            with winreg.OpenKey(_net_key, _sk_name) as _dev_key:
                                try:
                                    _desc, _ = winreg.QueryValueEx(_dev_key, "DriverDesc")
                                    _desc_b = str(_desc).lower().encode()
                                    if any(_kw in _desc_b for _kw in _vm_net_kw):
                                        {abort_fn}()
                                except Exception:
                                    pass
                    except Exception:
                        pass
        except Exception:
            pass

    # 5. Linux & POSIX Container / VM Deep Inspection
    if os.name == 'posix':
        try:
            _dmi_files = ['/sys/class/dmi/id/product_name', '/sys/class/dmi/id/sys_vendor', '/sys/class/dmi/id/board_vendor', '/sys/hypervisor/type']
            _vm_tags = ['virtualbox', 'vmware', 'qemu', 'kvm', 'bochs', 'xen', 'innotek', 'parallels', 'hyper-v']
            for _dpath in _dmi_files:
                if os.path.exists(_dpath):
                    with open(_dpath, 'r', errors='ignore') as _df:
                        _dcontent = _df.read().lower()
                        if any(_t in _dcontent for _t in _vm_tags):
                            {abort_fn}()
        except Exception:
            pass

        # Network interface MAC & driver on Linux
        try:
            if os.path.exists('/sys/class/net'):
                for _iface in os.listdir('/sys/class/net'):
                    _addr_file = os.path.join('/sys/class/net', _iface, 'address')
                    if os.path.isfile(_addr_file):
                        with open(_addr_file, 'r', errors='ignore') as _af:
                            _mac_line = _af.read().strip().upper()
                            for _bp in ('00:05:69', '00:0C:29', '00:50:56', '08:00:27', '52:54:00', '00:1C:42'):
                                if _mac_line.startswith(_bp):
                                    {abort_fn}()
        except Exception:
            pass

        try:
            if os.path.exists('/.dockerenv') or os.path.exists('/run/systemd/container'):
                {abort_fn}()
        except Exception:
            pass

try:
    {fn_name}()
except Exception:
    pass
"""

# ═══════════════════════════════════════════════════════════════
# TR0NGX TRUE VIRTUAL MACHINE (TVM 2.0) HIGH-ASSURANCE ENGINE
# Translates Python AST into Custom ISA Bytecode and executes via
# a Polymorphic Frame-Based Virtual Machine Interpreter.
# 100% Zero-exec fallback: FunctionDef, ClassDef, Try/Except,
# Loops, Closures, and Slices are fully virtualized.
# ═══════════════════════════════════════════════════════════════

class TVMEmitError(Exception):
    """Typed error for TVM compiler emission violations (16-bit arg range etc.)."""


_TVM_TOKENS: Dict[str, str] = {}


class _TVMOpcodes:
    # Stack & Data
    LOAD_CONST       = 1
    LOAD_GLOBAL      = 2
    STORE_GLOBAL     = 3
    LOAD_FAST        = 4
    STORE_FAST       = 5
    DUP_TOP          = 6
    POP_TOP          = 7
    ROT_TWO          = 8
    ROT_THREE        = 9

    # Exception block management (TVM 4.0): explicit handler-pop so
    # break/continue/return leaving a try frame cannot strand stale handlers.
    POP_EXC_HANDLER  = 250

    # Arithmetic & Bitwise
    BINARY_ADD       = 10
    BINARY_SUB       = 11
    BINARY_MUL       = 12
    BINARY_DIV       = 13
    BINARY_FLOORDIV  = 14
    BINARY_MOD       = 15
    BINARY_POW       = 16
    BINARY_AND       = 17
    BINARY_OR        = 18
    BINARY_XOR       = 19
    BINARY_LSHIFT    = 20
    BINARY_RSHIFT    = 21
    UNARY_NEG        = 22
    UNARY_NOT        = 23
    UNARY_INVERT     = 24
    BINARY_MATMUL    = 25

    # Comparisons
    COMPARE_OP       = 30

    # Control Flow
    JUMP             = 40
    JUMP_IF_TRUE     = 41
    JUMP_IF_FALSE    = 42
    JUMP_IF_FALSE_OR_POP = 43
    JUMP_IF_TRUE_OR_POP  = 44
    RETURN_VALUE     = 45

    # Object / Attribute / Subscript / Deletion
    GET_ATTR         = 50
    SET_ATTR         = 51
    GET_ITEM         = 52
    SET_ITEM         = 53
    DEL_ITEM         = 54
    DEL_ATTR         = 55
    DEL_FAST         = 56
    DEL_GLOBAL       = 57

    # Collections & Unpacking
    BUILD_LIST       = 60
    BUILD_TUPLE      = 61
    BUILD_SET        = 62
    BUILD_DICT       = 63
    UNPACK_SEQUENCE  = 64
    BUILD_SLICE      = 65
    UNPACK_EX        = 66

    # Functions, Calls, Classes & Closures
    MAKE_FUNCTION    = 70
    CALL_FUNCTION    = 71
    CALL_FUNCTION_KW = 72
    BUILD_CLASS      = 73
    IMPORT_NAME      = 74
    IMPORT_FROM      = 75
    CALL_FUNCTION_EX = 76
    LOAD_DEREF       = 77
    STORE_DEREF      = 78

    # Iteration & Exceptions
    GET_ITER         = 80
    FOR_ITER         = 81
    SETUP_FINALLY    = 82
    POP_BLOCK        = 83
    RAISE_VARARGS    = 84
    CHECK_EXC_MATCH  = 85

    # Termination / NOP / Trap
    HALT             = 99
    NOP              = 100
    TRAP             = 101

    # Generators (resumable frames)
    YIELD_VALUE      = 102
    YIELD_FROM       = 103


class _TVMCodeObject:
    """Represents a virtualized code block (Module, Function, Class, or Generator)."""
    def __init__(self, name: str, arg_names: List[str], kwarg_name: Optional[str] = None, vararg_name: Optional[str] = None, kwonly_names: Optional[List[str]] = None, defaults: Optional[Dict[str, Any]] = None):
        self.name = name
        self.arg_names = list(arg_names)
        self.kwonly_names = list(kwonly_names or [])
        self.kwarg_name = kwarg_name
        self.vararg_name = vararg_name
        self.defaults = defaults or {}
        self.instructions: List[Tuple[int, int]] = []
        self.constants: List[Any] = []
        self.names: List[str] = []
        locs = list(arg_names) + list(self.kwonly_names)
        if vararg_name and vararg_name not in locs:
            locs.append(vararg_name)
        if kwarg_name and kwarg_name not in locs:
            locs.append(kwarg_name)
        self.local_names: List[str] = locs
        # Kwonly params that carry defaults (late-bound via body preamble);
        # serialized so the runtime binder can exempt them from the strict
        # missing-argument check (TVM 4.0 GAP-27 refinement).
        self.kwonly_default_names: Tuple[str, ...] = ()

    def get_const_idx(self, val: Any) -> int:
        for idx, c in enumerate(self.constants):
            if type(c) == type(val) and c == val:
                return idx
        self.constants.append(val)
        return len(self.constants) - 1

    def get_name_idx(self, name: str) -> int:
        if name not in self.names:
            self.names.append(name)
        return self.names.index(name)

    def get_local_idx(self, name: str) -> int:
        if name not in self.local_names:
            self.local_names.append(name)
        return self.local_names.index(name)


class _TVMASTCompiler(ast.NodeVisitor):
    """Compiles Python AST statements and expressions into TVM-IR and custom virtual bytecode."""
    def __init__(self, name: str = '<module>', arg_names: List[str] = None, kwonly_names: Optional[List[str]] = None, kwarg_name: Optional[str] = None, vararg_name: Optional[str] = None, defaults: Optional[Dict[str, Any]] = None, is_function: bool = False, is_class: bool = False, vm_level: int = 1, rng: Optional[random.Random] = None):
        self.code_obj = _TVMCodeObject(name, arg_names or [], kwarg_name=kwarg_name, vararg_name=vararg_name, kwonly_names=kwonly_names, defaults=defaults)
        self.is_function = is_function
        self.is_class = is_class
        self.vm_level = vm_level
        self.rng = rng or random.Random()
        self.labels: Dict[int, int] = {}
        self.label_fixups: Dict[int, List[int]] = {}
        self.next_label_id = 0
        self.loop_stack: List[Tuple[int, int]] = []
        # Depth of enclosing SETUP_FINALLY frames (try / with). break/continue
        # crossing these boundaries MUST pop the handler first or the frame's
        # exc_handlers stack retains a stale entry that hijacks a later,
        # unrelated exception (TVM GAP-01/03).
        self.exc_frame_depth = 0
        self.loop_depth = 0
        self.explicit_globals: Set[str] = set()
        self.explicit_nonlocals: Set[str] = set()

    def new_label(self) -> int:
        lbl = self.next_label_id
        self.next_label_id += 1
        return lbl

    def mark_label(self, label_id: int):
        self.labels[label_id] = len(self.code_obj.instructions)

    def emit(self, op: int, arg: int = 0):
        # FIX (TVM P0): the 3-byte serializer silently truncated args > 0xFFFF,
        # corrupting jump targets / pool indices in large functions.
        if not isinstance(arg, int) or arg < 0 or arg > 0xFFFF:
            raise TVMEmitError(f"opcode {op}: argument out of 16-bit range: {arg!r}")
        self.code_obj.instructions.append((op, arg))

    def emit_jump(self, op: int, target_label_id: int):
        idx = len(self.code_obj.instructions)
        self.code_obj.instructions.append((op, 0))
        if target_label_id not in self.label_fixups:
            self.label_fixups[target_label_id] = []
        self.label_fixups[target_label_id].append(idx)

    def _scan_scope(self, body_nodes: List[ast.stmt]):
        """Pre-scans the lexical scope for global/nonlocal declarations and local assignment targets."""
        for node in body_nodes:
            self._scan_scope_decls(node)
        if self.is_function or self.is_class:
            for node in body_nodes:
                self._scan_scope_stores(node)

    def _scan_scope_decls(self, node: ast.AST):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, ast.Global):
            for name in node.names:
                self.explicit_globals.add(name)
        elif isinstance(node, ast.Nonlocal):
            for name in node.names:
                self.explicit_nonlocals.add(name)
        for child in ast.iter_child_nodes(node):
            self._scan_scope_decls(child)

    def _scan_scope_stores(self, node: ast.AST):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name not in self.explicit_globals and node.name not in self.explicit_nonlocals:
                self.code_obj.get_local_idx(node.name)
            return

        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            if node.id not in self.explicit_globals and node.id not in self.explicit_nonlocals:
                self.code_obj.get_local_idx(node.id)
        elif isinstance(node, ast.NamedExpr):
            if isinstance(node.target, ast.Name):
                if node.target.id not in self.explicit_globals and node.target.id not in self.explicit_nonlocals:
                    self.code_obj.get_local_idx(node.target.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            if node.name not in self.explicit_globals and node.name not in self.explicit_nonlocals:
                self.code_obj.get_local_idx(node.name)

        for child in ast.iter_child_nodes(node):
            self._scan_scope_stores(child)

    def _store_target(self, target: ast.AST):
        """Helper to lower assignment targets into appropriate STORE opcodes."""
        if isinstance(target, ast.Name):
            if target.id in self.explicit_globals:
                self.emit(_TVMOpcodes.STORE_GLOBAL, self.code_obj.get_name_idx(target.id))
            elif target.id in self.explicit_nonlocals:
                self.emit(_TVMOpcodes.STORE_DEREF, self.code_obj.get_name_idx(target.id))
            elif self.is_class:
                self.emit(_TVMOpcodes.STORE_FAST, self.code_obj.get_local_idx(target.id))
            elif self.is_function and target.id in self.code_obj.local_names:
                self.emit(_TVMOpcodes.STORE_FAST, self.code_obj.get_local_idx(target.id))
            else:
                self.emit(_TVMOpcodes.STORE_GLOBAL, self.code_obj.get_name_idx(target.id))
        elif isinstance(target, ast.Attribute):
            self.visit(target.value)
            idx = self.code_obj.get_name_idx(target.attr)
            self.emit(_TVMOpcodes.SET_ATTR, idx)
        elif isinstance(target, ast.Subscript):
            self.visit(target.value)
            self.visit(target.slice)
            self.emit(_TVMOpcodes.SET_ITEM)
        elif isinstance(target, (ast.Tuple, ast.List)):
            # Check for starred unpacking
            starred_idx = -1
            for idx, elt in enumerate(target.elts):
                if isinstance(elt, ast.Starred):
                    starred_idx = idx
                    break
            if starred_idx >= 0:
                before_cnt = starred_idx
                after_cnt = len(target.elts) - 1 - starred_idx
                self.emit(_TVMOpcodes.UNPACK_EX, before_cnt | (after_cnt << 8))
                for elt in target.elts:
                    if isinstance(elt, ast.Starred):
                        self._store_target(elt.value)
                    else:
                        self._store_target(elt)
            else:
                self.emit(_TVMOpcodes.UNPACK_SEQUENCE, len(target.elts))
                for elt in target.elts:
                    self._store_target(elt)

    # --- Expressions ---

    def visit_Constant(self, node: ast.Constant):
        idx = self.code_obj.get_const_idx(node.value)
        self.emit(_TVMOpcodes.LOAD_CONST, idx)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self._store_target(node)
        elif isinstance(node.ctx, ast.Del):
            if node.id in self.explicit_globals:
                self.emit(_TVMOpcodes.DEL_GLOBAL, self.code_obj.get_name_idx(node.id))
            elif node.id in self.explicit_nonlocals:
                self.emit(_TVMOpcodes.DEL_FAST, self.code_obj.get_local_idx(node.id))
            elif (self.is_class or self.is_function) and node.id in self.code_obj.local_names:
                self.emit(_TVMOpcodes.DEL_FAST, self.code_obj.get_local_idx(node.id))
            else:
                self.emit(_TVMOpcodes.DEL_GLOBAL, self.code_obj.get_name_idx(node.id))
        else:
            # Load context
            if node.id in self.explicit_globals:
                self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(node.id))
            elif node.id in self.explicit_nonlocals:
                self.emit(_TVMOpcodes.LOAD_DEREF, self.code_obj.get_name_idx(node.id))
            elif (self.is_class or self.is_function) and node.id in self.code_obj.local_names:
                self.emit(_TVMOpcodes.LOAD_FAST, self.code_obj.get_local_idx(node.id))
            else:
                self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(node.id))

    def visit_BinOp(self, node: ast.BinOp):
        self.visit(node.left)
        self.visit(node.right)
        op_map = {
            ast.Add: _TVMOpcodes.BINARY_ADD,
            ast.Sub: _TVMOpcodes.BINARY_SUB,
            ast.Mult: _TVMOpcodes.BINARY_MUL,
            ast.Div: _TVMOpcodes.BINARY_DIV,
            ast.FloorDiv: _TVMOpcodes.BINARY_FLOORDIV,
            ast.Mod: _TVMOpcodes.BINARY_MOD,
            ast.Pow: _TVMOpcodes.BINARY_POW,
            ast.BitAnd: _TVMOpcodes.BINARY_AND,
            ast.BitOr: _TVMOpcodes.BINARY_OR,
            ast.BitXor: _TVMOpcodes.BINARY_XOR,
            ast.LShift: _TVMOpcodes.BINARY_LSHIFT,
            ast.RShift: _TVMOpcodes.BINARY_RSHIFT,
            ast.MatMult: _TVMOpcodes.BINARY_MATMUL,
        }
        self.emit(op_map.get(type(node.op), _TVMOpcodes.BINARY_ADD))

    def visit_UnaryOp(self, node: ast.UnaryOp):
        self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            self.emit(_TVMOpcodes.UNARY_NEG)
        elif isinstance(node.op, ast.Not):
            self.emit(_TVMOpcodes.UNARY_NOT)
        elif isinstance(node.op, ast.Invert):
            self.emit(_TVMOpcodes.UNARY_INVERT)
        elif isinstance(node.op, ast.UAdd):
            pass

    def visit_TypeAlias(self, node: ast.AST):
        if hasattr(node, 'value'):
            self.visit(node.value)
            if hasattr(node, 'name'):
                self._store_target(node.name)
            else:
                self.emit(_TVMOpcodes.POP_TOP)

    def visit_TryStar(self, node: ast.AST):
        # FIX (GAP-38): except* was silently compiled as a plain try, destroying
        # PEP 654 semantics (ExceptionGroup never split). Fail LOUD instead of
        # silent-wrong-output; stage wrapper logs it and --strict aborts.
        raise TVMEmitError("except* (PEP 654) is not supported by TVM virtualization")

    def visit_BoolOp(self, node: ast.BoolOp):
        # Short-circuiting boolean operations (And / Or)
        is_or = isinstance(node.op, ast.Or)
        lbl_end = self.new_label()
        for idx, val in enumerate(node.values):
            self.visit(val)
            if idx < len(node.values) - 1:
                if is_or:
                    self.emit_jump(_TVMOpcodes.JUMP_IF_TRUE_OR_POP, lbl_end)
                else:
                    self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE_OR_POP, lbl_end)
        self.mark_label(lbl_end)

    def visit_Compare(self, node: ast.Compare):
        cmp_map = {
            ast.Lt: 0, ast.LtE: 1, ast.Eq: 2, ast.NotEq: 3,
            ast.Gt: 4, ast.GtE: 5, ast.In: 6, ast.NotIn: 7,
            ast.Is: 8, ast.IsNot: 9
        }
        if len(node.ops) == 1:
            self.visit(node.left)
            self.visit(node.comparators[0])
            cmp_code = cmp_map.get(type(node.ops[0]), 2)
            self.emit(_TVMOpcodes.COMPARE_OP, cmp_code)
        else:
            # Chained comparison with short-circuiting: a < b < c
            lbl_fail = self.new_label()
            lbl_end = self.new_label()

            self.visit(node.left)
            for idx, (op, comp) in enumerate(zip(node.ops, node.comparators)):
                is_last = (idx == len(node.ops) - 1)
                cmp_code = cmp_map.get(type(op), 2)
                temp_slot = self.code_obj.get_local_idx(f'_$cmp_{self.new_label()}')

                self.visit(comp)
                if not is_last:
                    self.emit(_TVMOpcodes.STORE_FAST, temp_slot)
                    self.emit(_TVMOpcodes.LOAD_FAST, temp_slot)

                self.emit(_TVMOpcodes.COMPARE_OP, cmp_code)
                if not is_last:
                    self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
                    self.emit(_TVMOpcodes.LOAD_FAST, temp_slot)
                else:
                    self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

            self.mark_label(lbl_fail)
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(False))
            self.mark_label(lbl_end)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        for val in node.values:
            self.visit(val)
        self.emit(_TVMOpcodes.BUILD_LIST, len(node.values))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(''))
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('join'))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_FormattedValue(self, node: ast.FormattedValue):
        self.visit(node.value)
        # Handle conversion (!s=115, !r=114, !a=97)
        if node.conversion == 115:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('str'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        elif node.conversion == 114:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('repr'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        elif node.conversion == 97:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('ascii'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        # Handle format_spec
        if node.format_spec:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('format'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.visit(node.format_spec)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 2)
        elif node.conversion == -1:
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('str'))
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_NamedExpr(self, node: ast.NamedExpr):
        # Assignment expression (walrus operator :=)
        self.visit(node.value)
        self.emit(_TVMOpcodes.DUP_TOP)
        self._store_target(node.target)

    def visit_IfExp(self, node: ast.IfExp):
        # Ternary conditional expression: a if cond else b
        lbl_else = self.new_label()
        lbl_end = self.new_label()
        self.visit(node.test)
        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_else)
        self.visit(node.body)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)
        self.mark_label(lbl_else)
        self.visit(node.orelse)
        self.mark_label(lbl_end)

    def visit_Await(self, node: ast.Await):
        tmp_slot = self.code_obj.get_local_idx(f'_$await_tmp_{self.new_label()}')
        self.visit(node.value)
        self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.LOAD_FAST, tmp_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_Call(self, node: ast.Call):
        has_starred = any(isinstance(a, ast.Starred) for a in node.args)
        has_starred_kw = any(kw.arg is None for kw in node.keywords)
        if has_starred or has_starred_kw:
            self.emit(_TVMOpcodes.BUILD_LIST, 0)
            lst_idx = self.code_obj.get_local_idx(f'_$call_args_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, lst_idx)
            for a in node.args:
                if isinstance(a, ast.Starred):
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_idx)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('extend'))
                    self.visit(a.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_idx)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('append'))
                    self.visit(a)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)

            self.emit(_TVMOpcodes.BUILD_DICT, 0)
            kw_idx = self.code_obj.get_local_idx(f'_$call_kw_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, kw_idx)
            for kw in node.keywords:
                if kw.arg is None:
                    self.emit(_TVMOpcodes.LOAD_FAST, kw_idx)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('update'))
                    self.visit(kw.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.visit(kw.value)
                    self.emit(_TVMOpcodes.LOAD_FAST, kw_idx)
                    self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(kw.arg))
                    self.emit(_TVMOpcodes.SET_ITEM)

            self.visit(node.func)
            self.emit(_TVMOpcodes.LOAD_FAST, lst_idx)
            self.emit(_TVMOpcodes.LOAD_FAST, kw_idx)
            self.emit(_TVMOpcodes.CALL_FUNCTION_EX, 1)
        else:
            self.visit(node.func)
            for arg in node.args:
                self.visit(arg)
            if node.keywords:
                for kw in node.keywords:
                    k_idx = self.code_obj.get_const_idx(kw.arg)
                    self.emit(_TVMOpcodes.LOAD_CONST, k_idx)
                    self.visit(kw.value)
                self.emit(_TVMOpcodes.CALL_FUNCTION_KW, len(node.args) | (len(node.keywords) << 8))
            else:
                self.emit(_TVMOpcodes.CALL_FUNCTION, len(node.args))

    def visit_Attribute(self, node: ast.Attribute):
        self.visit(node.value)
        idx = self.code_obj.get_name_idx(node.attr)
        if isinstance(node.ctx, ast.Load):
            self.emit(_TVMOpcodes.GET_ATTR, idx)
        elif isinstance(node.ctx, ast.Store):
            self.emit(_TVMOpcodes.SET_ATTR, idx)
        elif isinstance(node.ctx, ast.Del):
            self.emit(_TVMOpcodes.DEL_ATTR, idx)

    def visit_Subscript(self, node: ast.Subscript):
        self.visit(node.value)
        self.visit(node.slice)
        if isinstance(node.ctx, ast.Load):
            self.emit(_TVMOpcodes.GET_ITEM)
        elif isinstance(node.ctx, ast.Store):
            self.emit(_TVMOpcodes.SET_ITEM)
        elif isinstance(node.ctx, ast.Del):
            self.emit(_TVMOpcodes.DEL_ITEM)

    def visit_List(self, node: ast.List):
        has_starred = any(isinstance(e, ast.Starred) for e in node.elts)
        if has_starred:
            self.emit(_TVMOpcodes.BUILD_LIST, 0)
            lst_slot = self.code_obj.get_local_idx(f'_$list_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, lst_slot)
            for e in node.elts:
                if isinstance(e, ast.Starred):
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('extend'))
                    self.visit(e.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('append'))
                    self.visit(e)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
            self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
        else:
            for elt in node.elts:
                self.visit(elt)
            self.emit(_TVMOpcodes.BUILD_LIST, len(node.elts))

    def visit_Tuple(self, node: ast.Tuple):
        has_starred = any(isinstance(e, ast.Starred) for e in node.elts)
        if has_starred:
            self.emit(_TVMOpcodes.BUILD_LIST, 0)
            lst_slot = self.code_obj.get_local_idx(f'_$tup_lst_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, lst_slot)
            for e in node.elts:
                if isinstance(e, ast.Starred):
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('extend'))
                    self.visit(e.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('append'))
                    self.visit(e)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('tuple'))
            self.emit(_TVMOpcodes.LOAD_FAST, lst_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        else:
            for elt in node.elts:
                self.visit(elt)
            self.emit(_TVMOpcodes.BUILD_TUPLE, len(node.elts))

    def visit_Set(self, node: ast.Set):
        has_starred = any(isinstance(e, ast.Starred) for e in node.elts)
        if has_starred:
            self.emit(_TVMOpcodes.BUILD_SET, 0)
            set_slot = self.code_obj.get_local_idx(f'_$set_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, set_slot)
            for e in node.elts:
                if isinstance(e, ast.Starred):
                    self.emit(_TVMOpcodes.LOAD_FAST, set_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('update'))
                    self.visit(e.value)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, set_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('add'))
                    self.visit(e)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
            self.emit(_TVMOpcodes.LOAD_FAST, set_slot)
        else:
            for elt in node.elts:
                self.visit(elt)
            self.emit(_TVMOpcodes.BUILD_SET, len(node.elts))

    def visit_Dict(self, node: ast.Dict):
        has_unpacking = any(k is None for k in node.keys)
        if has_unpacking:
            self.emit(_TVMOpcodes.BUILD_DICT, 0)
            dict_slot = self.code_obj.get_local_idx(f'_$dict_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, dict_slot)
            for k, v in zip(node.keys, node.values):
                if k is None:
                    self.emit(_TVMOpcodes.LOAD_FAST, dict_slot)
                    self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('update'))
                    self.visit(v)
                    self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
                    self.emit(_TVMOpcodes.POP_TOP)
                else:
                    self.visit(v)
                    self.emit(_TVMOpcodes.LOAD_FAST, dict_slot)
                    self.visit(k)
                    self.emit(_TVMOpcodes.SET_ITEM)
            self.emit(_TVMOpcodes.LOAD_FAST, dict_slot)
        else:
            for k, v in zip(node.keys, node.values):
                self.visit(k)
                self.visit(v)
            self.emit(_TVMOpcodes.BUILD_DICT, len(node.keys))

    def visit_Slice(self, node: ast.Slice):
        if node.lower: self.visit(node.lower)
        else: self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        if node.upper: self.visit(node.upper)
        else: self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        if node.step: self.visit(node.step)
        else: self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.BUILD_SLICE, 3)

    # --- Statements & Control Flow Lowering ---

    def visit_Expr(self, node: ast.Expr):
        self.visit(node.value)
        if not (getattr(self, 'is_generator', False) and isinstance(node.value, (ast.Yield, ast.YieldFrom))):
            self.emit(_TVMOpcodes.POP_TOP)

    def visit_Assign(self, node: ast.Assign):
        self.visit(node.value)
        if len(node.targets) > 1:
            for target in node.targets[:-1]:
                self.emit(_TVMOpcodes.DUP_TOP)
                self._store_target(target)
            self._store_target(node.targets[-1])
        else:
            self._store_target(node.targets[0])

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value:
            self.visit(node.value)
            self._store_target(node.target)

    def visit_AugAssign(self, node: ast.AugAssign):
        op_map = {
            ast.Add: _TVMOpcodes.BINARY_ADD,
            ast.Sub: _TVMOpcodes.BINARY_SUB,
            ast.Mult: _TVMOpcodes.BINARY_MUL,
            ast.Div: _TVMOpcodes.BINARY_DIV,
            ast.FloorDiv: _TVMOpcodes.BINARY_FLOORDIV,
            ast.Mod: _TVMOpcodes.BINARY_MOD,
            ast.Pow: _TVMOpcodes.BINARY_POW,
            ast.BitAnd: _TVMOpcodes.BINARY_AND,
            ast.BitOr: _TVMOpcodes.BINARY_OR,
            ast.BitXor: _TVMOpcodes.BINARY_XOR,
            ast.LShift: _TVMOpcodes.BINARY_LSHIFT,
            ast.RShift: _TVMOpcodes.BINARY_RSHIFT,
            ast.MatMult: _TVMOpcodes.BINARY_MATMUL,
        }
        bin_op = op_map.get(type(node.op), _TVMOpcodes.BINARY_ADD)

        if isinstance(node.target, ast.Name):
            self.visit(ast.Name(id=node.target.id, ctx=ast.Load()))
            self.visit(node.value)
            self.emit(bin_op)
            self._store_target(node.target)
        elif isinstance(node.target, ast.Attribute):
            # Evaluate target object ONCE and store in temp slot
            self.visit(node.target.value)
            obj_slot = self.code_obj.get_local_idx(f'_$aug_obj_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, obj_slot)

            self.emit(_TVMOpcodes.LOAD_FAST, obj_slot)
            attr_idx = self.code_obj.get_name_idx(node.target.attr)
            self.emit(_TVMOpcodes.GET_ATTR, attr_idx)

            self.visit(node.value)
            self.emit(bin_op)

            # SET_ATTR expects stack: [new_val, obj]
            self.emit(_TVMOpcodes.LOAD_FAST, obj_slot)
            self.emit(_TVMOpcodes.SET_ATTR, attr_idx)
        elif isinstance(node.target, ast.Subscript):
            # Evaluate container and slice ONCE
            self.visit(node.target.value)
            cnt_slot = self.code_obj.get_local_idx(f'_$aug_cnt_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, cnt_slot)

            self.visit(node.target.slice)
            idx_slot = self.code_obj.get_local_idx(f'_$aug_idx_{self.new_label()}')
            self.emit(_TVMOpcodes.STORE_FAST, idx_slot)

            self.emit(_TVMOpcodes.LOAD_FAST, cnt_slot)
            self.emit(_TVMOpcodes.LOAD_FAST, idx_slot)
            self.emit(_TVMOpcodes.GET_ITEM)

            self.visit(node.value)
            self.emit(bin_op)

            # SET_ITEM expects stack: [new_val, container, slice]
            self.emit(_TVMOpcodes.LOAD_FAST, cnt_slot)
            self.emit(_TVMOpcodes.LOAD_FAST, idx_slot)
            self.emit(_TVMOpcodes.SET_ITEM)

    def visit_Delete(self, node: ast.Delete):
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in self.explicit_globals:
                    self.emit(_TVMOpcodes.DEL_GLOBAL, self.code_obj.get_name_idx(target.id))
                elif target.id in self.explicit_nonlocals:
                    self.emit(_TVMOpcodes.DEL_FAST, self.code_obj.get_local_idx(target.id))
                elif self.is_class or (self.is_function and target.id in self.code_obj.local_names):
                    self.emit(_TVMOpcodes.DEL_FAST, self.code_obj.get_local_idx(target.id))
                else:
                    self.emit(_TVMOpcodes.DEL_GLOBAL, self.code_obj.get_name_idx(target.id))
            elif isinstance(target, ast.Subscript):
                self.visit(target.value)
                self.visit(target.slice)
                self.emit(_TVMOpcodes.DEL_ITEM)
            elif isinstance(target, ast.Attribute):
                self.visit(target.value)
                self.emit(_TVMOpcodes.DEL_ATTR, self.code_obj.get_name_idx(target.attr))

    def visit_Assert(self, node: ast.Assert):
        lbl_ok = self.new_label()
        self.visit(node.test)
        self.emit_jump(_TVMOpcodes.JUMP_IF_TRUE, lbl_ok)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('AssertionError'))
        if node.msg:
            self.visit(node.msg)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        else:
            self.emit(_TVMOpcodes.CALL_FUNCTION, 0)
        self.emit(_TVMOpcodes.RAISE_VARARGS)
        self.mark_label(lbl_ok)

    def visit_Global(self, node: ast.Global):
        for name in node.names:
            self.explicit_globals.add(name)

    def visit_Nonlocal(self, node: ast.Nonlocal):
        for name in node.names:
            self.explicit_nonlocals.add(name)

    def visit_Pass(self, node: ast.Pass):
        self.emit(_TVMOpcodes.NOP)

    def visit_Raise(self, node: ast.Raise):
        if node.cause:
            # handler pops cause first, then exc -> push exc first
            self.visit(node.exc)
            self.visit(node.cause)
            self.emit(_TVMOpcodes.RAISE_VARARGS, 2)
        elif node.exc:
            self.visit(node.exc)
            self.emit(_TVMOpcodes.RAISE_VARARGS)
        else:
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
            self.emit(_TVMOpcodes.RAISE_VARARGS)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        is_gen = self._contains_yield_in_scope(node.body)
        # FIX (TVM GAP-25): positional-only params were silently dropped from the
        # signature, misrouting positional binding and voiding the '/' constraint.
        arg_names = [a.arg for a in getattr(node.args, 'posonlyargs', [])] + [a.arg for a in node.args.args]
        kwonly_names = [a.arg for a in node.args.kwonlyargs] if hasattr(node.args, 'kwonlyargs') else []
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        sub_compiler = _TVMASTCompiler(name=node.name, arg_names=arg_names, kwonly_names=kwonly_names, kwarg_name=kwarg_name, vararg_name=vararg_name, is_function=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler._scan_scope(node.body)
        # Kwonly params WITH defaults: sentinel replaced by body preamble at
        # call time; the runtime binder must not treat them as missing.
        sub_compiler.code_obj.kwonly_default_names = tuple(
            a.arg for a, d in zip(getattr(node.args, 'kwonlyargs', []), getattr(node.args, 'kw_defaults', []))
            if d is not None
        )

        # Handle default arguments
        # Positional defaults are evaluated ONCE at function-creation time
        # (native CPython semantics) via the __vm_bind_defaults__ registry.
        if node.args.defaults:
            dfl_slot = self.code_obj.get_local_idx(f'_$dflt_{self.new_label()}')
            pos_names = [a.arg for a in node.args.args[-len(node.args.defaults):]]
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tuple(pos_names)))
            for d_expr in node.args.defaults:
                self.visit(d_expr)
            self.emit(_TVMOpcodes.BUILD_TUPLE, len(node.args.defaults))
            self.emit(_TVMOpcodes.BUILD_TUPLE, 2)
            self.emit(_TVMOpcodes.STORE_FAST, dfl_slot)

        if hasattr(node.args, 'kw_defaults') and node.args.kw_defaults:
            for arg_node, def_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if def_node is not None:
                    arg_idx = sub_compiler.code_obj.get_local_idx(arg_node.arg)
                    sub_compiler.emit(_TVMOpcodes.LOAD_FAST, arg_idx)
                    sub_compiler.emit(_TVMOpcodes.LOAD_GLOBAL, sub_compiler.code_obj.get_name_idx(_TVM_TOKENS['no_arg']))
                    sub_compiler.emit(_TVMOpcodes.COMPARE_OP, 8)
                    lbl_has_val = sub_compiler.new_label()
                    sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_has_val)
                    sub_compiler.visit(def_node)
                    sub_compiler.emit(_TVMOpcodes.STORE_FAST, arg_idx)
                    sub_compiler.mark_label(lbl_has_val)

        if is_gen:
            sub_compiler.is_generator = True
            for stmt in node.body:
                sub_compiler.visit(stmt)
        else:
            for stmt in node.body:
                sub_compiler.visit(stmt)
        sub_code = sub_compiler.finalize()

        idx = self.code_obj.get_const_idx(sub_code)
        if node.args.defaults:
            self.emit(_TVMOpcodes.LOAD_FAST, dfl_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, idx)
        self.emit(_TVMOpcodes.MAKE_FUNCTION, (2 if is_gen else 0) | (8 if node.args.defaults else 0))  # bit1(2)=gen bit3(8)=defaults

        # Apply decorators if present
        for dec in reversed(node.decorator_list):
            self.visit(dec)
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        self._store_target(ast.Name(id=node.name, ctx=ast.Store()))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # FIX (TVM P0): this visitor previously never finalized the sub compiler
        # nor stored the code object into constants -> UnboundLocalError on `idx`
        # for EVERY async def compiled under --vm-obf. Mirrors visit_FunctionDef.
        arg_names = [a.arg for a in getattr(node.args, 'posonlyargs', [])] + [a.arg for a in node.args.args]
        kwonly_names = [a.arg for a in node.args.kwonlyargs] if hasattr(node.args, 'kwonlyargs') else []
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        sub_compiler = _TVMASTCompiler(name=node.name, arg_names=arg_names, kwonly_names=kwonly_names, kwarg_name=kwarg_name, vararg_name=vararg_name, is_function=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler._scan_scope(node.body)
        sub_compiler.is_async = True
        # Detect async-generator BEFORE compiling so visit_Yield emits suspends.
        is_agen_pre = self._contains_yield_in_scope(node.body)
        if is_agen_pre:
            sub_compiler.is_generator = True

        if node.args.defaults:
            dfl_slot = self.code_obj.get_local_idx(f'_$dflt_{self.new_label()}')
            pos_names = [a.arg for a in node.args.args[-len(node.args.defaults):]]
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tuple(pos_names)))
            for d_expr in node.args.defaults:
                self.visit(d_expr)
            self.emit(_TVMOpcodes.BUILD_TUPLE, len(node.args.defaults))
            self.emit(_TVMOpcodes.BUILD_TUPLE, 2)
            self.emit(_TVMOpcodes.STORE_FAST, dfl_slot)

        if hasattr(node.args, 'kw_defaults') and node.args.kw_defaults:
            for arg_node, def_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if def_node is not None:
                    arg_idx = sub_compiler.code_obj.get_local_idx(arg_node.arg)
                    sub_compiler.emit(_TVMOpcodes.LOAD_FAST, arg_idx)
                    sub_compiler.emit(_TVMOpcodes.LOAD_GLOBAL, sub_compiler.code_obj.get_name_idx(_TVM_TOKENS['no_arg']))
                    sub_compiler.emit(_TVMOpcodes.COMPARE_OP, 8)
                    lbl_has_val_a = sub_compiler.new_label()
                    sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_has_val_a)
                    sub_compiler.visit(def_node)
                    sub_compiler.emit(_TVMOpcodes.STORE_FAST, arg_idx)
                    sub_compiler.mark_label(lbl_has_val_a)

        # Record which kwonly params carry defaults: their sentinel is replaced
        # by the body preamble (late-bound channel), so the binder's strict
        # missing-arg check must skip them (TVM 4.0 GAP-27 refinement).
        _fn_code.kwonly_default_names = tuple(
            a.arg for a, d in zip(getattr(node.args, 'kwonlyargs', []), getattr(node.args, 'kw_defaults', []))
            if d is not None
        )
        for stmt in node.body:
            sub_compiler.visit(stmt)
        sub_code = sub_compiler.finalize()

        idx = self.code_obj.get_const_idx(sub_code)
        mk_flags = (1 | 2) if is_agen_pre else 1
        if node.args.defaults:
            self.emit(_TVMOpcodes.LOAD_FAST, dfl_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, idx)
        self.emit(_TVMOpcodes.MAKE_FUNCTION, mk_flags | (8 if node.args.defaults else 0))

        for dec in reversed(node.decorator_list):
            self.visit(dec)
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        self._store_target(ast.Name(id=node.name, ctx=ast.Store()))

    def visit_Lambda(self, node: ast.Lambda):
        # FIX (TVM GAP-25): positional-only params included.
        arg_names = [a.arg for a in getattr(node.args, 'posonlyargs', [])] + [a.arg for a in node.args.args]
        kwonly_names = [a.arg for a in node.args.kwonlyargs] if hasattr(node.args, 'kwonlyargs') else []
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        sub_compiler = _TVMASTCompiler(name='<lambda>', arg_names=arg_names, kwonly_names=kwonly_names, kwarg_name=kwarg_name, vararg_name=vararg_name, is_function=True, vm_level=self.vm_level, rng=self.rng)

        if node.args.defaults:
            num_defaults = len(node.args.defaults)
            default_args = node.args.args[-num_defaults:]
            for arg_node, def_node in zip(default_args, node.args.defaults):
                arg_idx = sub_compiler.code_obj.get_local_idx(arg_node.arg)
                sub_compiler.emit(_TVMOpcodes.LOAD_FAST, arg_idx)
                sub_compiler.emit(_TVMOpcodes.LOAD_GLOBAL, sub_compiler.code_obj.get_name_idx(_TVM_TOKENS['no_arg']))
                sub_compiler.emit(_TVMOpcodes.COMPARE_OP, 8)
                lbl_has = sub_compiler.new_label()
                sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_has)
                sub_compiler.visit(def_node)
                sub_compiler.emit(_TVMOpcodes.STORE_FAST, arg_idx)
                sub_compiler.mark_label(lbl_has)

        if hasattr(node.args, 'kw_defaults') and node.args.kw_defaults:
            for arg_node, def_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if def_node is not None:
                    arg_idx = sub_compiler.code_obj.get_local_idx(arg_node.arg)
                    sub_compiler.emit(_TVMOpcodes.LOAD_FAST, arg_idx)
                    sub_compiler.emit(_TVMOpcodes.LOAD_GLOBAL, sub_compiler.code_obj.get_name_idx(_TVM_TOKENS['no_arg']))
                    sub_compiler.emit(_TVMOpcodes.COMPARE_OP, 8)
                    lbl_has = sub_compiler.new_label()
                    sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_has)
                    sub_compiler.visit(def_node)
                    sub_compiler.emit(_TVMOpcodes.STORE_FAST, arg_idx)
                    sub_compiler.mark_label(lbl_has)

        sub_compiler.visit(ast.Return(value=node.body))
        sub_code = sub_compiler.finalize()
        idx = self.code_obj.get_const_idx(sub_code)
        self.emit(_TVMOpcodes.LOAD_CONST, idx)
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)

    def _emit_comprehension(self, node, build_opname, acc_name, emit_element):
        """Shared multi-generator comprehension emitter (list/set/dict/genexpr).
        Correctly nests every generator clause instead of only generators[0]."""
        target_names = ['.0']
        for g in node.generators:
            for n in ast.walk(g.target):
                if isinstance(n, ast.Name) and n.id not in target_names:
                    target_names.append(n.id)

        sub_compiler = _TVMASTCompiler(name=f'<{acc_name[2:]}comp>', arg_names=target_names,
                                       is_function=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler.emit(getattr(_TVMOpcodes, build_opname), 0)
        acc_idx = sub_compiler.code_obj.get_local_idx(acc_name)
        sub_compiler.emit(_TVMOpcodes.STORE_FAST, acc_idx)

        heads = []
        exits = []
        for gi, gen in enumerate(node.generators):
            head = sub_compiler.new_label()
            exit_l = sub_compiler.new_label()
            heads.append(head)
            exits.append(exit_l)
            if gi == 0:
                sub_compiler.mark_label(head)
                sub_compiler.emit(_TVMOpcodes.LOAD_FAST, sub_compiler.code_obj.get_local_idx('.0'))
            else:
                slot_idx = sub_compiler.code_obj.get_local_idx(f'_$g{gi}')
                sub_compiler.visit(gen.iter)
                sub_compiler.emit(_TVMOpcodes.GET_ITER)
                sub_compiler.emit(_TVMOpcodes.STORE_FAST, slot_idx)
                sub_compiler.mark_label(head)
                sub_compiler.emit(_TVMOpcodes.LOAD_FAST, slot_idx)
            sub_compiler.emit_jump(_TVMOpcodes.FOR_ITER, exit_l)
            sub_compiler._store_target(gen.target)
            for if_expr in gen.ifs:
                sub_compiler.visit(if_expr)
                sub_compiler.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, head)

        emit_element(sub_compiler, acc_idx)

        for gi in range(len(node.generators) - 1, -1, -1):
            sub_compiler.emit_jump(_TVMOpcodes.JUMP, heads[gi])
            sub_compiler.mark_label(exits[gi])

        sub_compiler.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
        return sub_compiler

    def _emit_async_comprehension(self, node, kind):
        """Desugar `[x async for ...]`, `{...}`, dict/set/gen variants into an
        inline async helper function that the caller awaits. Returns after the
        resolved iterable has been pushed onto the stack."""
        lbl = self.new_label()
        fn_name = f'_$acomp_fn_{lbl}'
        acc_name = f'_$acomp_{lbl}'

        if kind == 'dict':
            acc_expr = ast.Dict(keys=[], values=[])
            append_call = ast.Call(
                func=ast.Attribute(value=ast.Name(id=acc_name, ctx=ast.Load()), attr='setitem', ctx=ast.Load()),
                args=[], keywords=[])
            # dict.append doesn't exist; build via setitem assignment instead
            body_appends = None
        else:
            method = {'list': 'append', 'set': 'add', 'gen': 'append'}[kind]
            acc_expr = ast.List(elts=[]) if kind in ('list', 'gen') else ast.Set(elts=[])

        # Build innermost append/emit statement(s)
        def make_emit():
            if kind == 'dict':
                return ast.Assign(
                    targets=[ast.Subscript(value=ast.Name(id=acc_name, ctx=ast.Load()),
                                           slice=self._clone_ctx(node.key), ctx=ast.Store())],
                    value=node.value)
            return ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id=acc_name, ctx=ast.Load()), attr=method, ctx=ast.Load()),
                args=[node.elt], keywords=[]))

        # Nest generators (first may be async; the rest are sync per grammar)
        g0 = node.generators[0]
        innermost = [make_emit()]
        for if_expr in reversed(g0.ifs):
            innermost = [ast.If(test=if_expr, body=innermost, orelse=[])]
        loop = ast.AsyncFor(target=g0.target, iter=g0.iter, body=innermost, orelse=[])
        current = [loop]
        for g in node.generators[1:]:
            inner2 = current
            for if_expr in reversed(g.ifs):
                inner2 = [ast.If(test=if_expr, body=inner2, orelse=[])]
            current = [ast.For(target=g.target, iter=g.iter, body=inner2, orelse=[])]

        fn_def = ast.AsyncFunctionDef(
            name=fn_name,
            args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                               kw_defaults=[], kwarg=None, defaults=[]),
            body=[ast.Assign(targets=[ast.Name(id=acc_name, ctx=ast.Store())], value=acc_expr)] + current +
                 [ast.Return(value=ast.Name(id=acc_name, ctx=ast.Load()))],
            decorator_list=[], returns=None, type_comment=None)

        # Compile the helper as an immediate async closure: MAKE_FUNCTION leaves
        # it on the stack; call it and await the returned coroutine.
        sub_compiler = _TVMASTCompiler(
            name=fn_name,
            arg_names=[], kwonly_names=[], kwarg_name=None, vararg_name=None,
            is_function=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler._scan_scope(fn_def.body)
        sub_compiler.is_async = True
        for stmt in fn_def.body:
            sub_compiler.visit(stmt)
        sub_code = sub_compiler.finalize()

        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 1)          # async
        self.emit(_TVMOpcodes.CALL_FUNCTION, 0)          # -> coroutine
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)          # -> resolved iterable

    @staticmethod
    def _clone_ctx(n):
        import copy as _c
        return _c.deepcopy(n)

    def visit_ListComp(self, node: ast.ListComp):
        if getattr(node.generators[0], 'is_async', False):
            return self._emit_async_comprehension(node, 'list')

        def emit_element(sc, acc_idx):
            sc.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
            sc.emit(_TVMOpcodes.GET_ATTR, sc.code_obj.get_name_idx('append'))
            sc.visit(node.elt)
            sc.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            sc.emit(_TVMOpcodes.POP_TOP)

        sub_compiler = self._emit_comprehension(node, 'BUILD_LIST', '_$lst', emit_element)
        sub_compiler.emit(_TVMOpcodes.RETURN_VALUE)
        sub_code = sub_compiler.finalize()
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)
        self.visit(node.generators[0].iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_SetComp(self, node: ast.SetComp):
        if getattr(node.generators[0], 'is_async', False):
            return self._emit_async_comprehension(node, 'set')

        def emit_element(sc, acc_idx):
            sc.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
            sc.emit(_TVMOpcodes.GET_ATTR, sc.code_obj.get_name_idx('add'))
            sc.visit(node.elt)
            sc.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            sc.emit(_TVMOpcodes.POP_TOP)

        sub_compiler = self._emit_comprehension(node, 'BUILD_SET', '_$set', emit_element)
        sub_compiler.emit(_TVMOpcodes.RETURN_VALUE)
        sub_code = sub_compiler.finalize()
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)
        self.visit(node.generators[0].iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_DictComp(self, node: ast.DictComp):
        if getattr(node.generators[0], 'is_async', False):
            return self._emit_async_comprehension(node, 'dict')

        def emit_element(sc, acc_idx):
            sc.visit(node.value)
            sc.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
            sc.visit(node.key)
            sc.emit(_TVMOpcodes.SET_ITEM)

        sub_compiler = self._emit_comprehension(node, 'BUILD_DICT', '_$dict', emit_element)
        sub_compiler.emit(_TVMOpcodes.RETURN_VALUE)
        sub_code = sub_compiler.finalize()
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)
        self.visit(node.generators[0].iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        if getattr(node.generators[0], 'is_async', False):
            return self._emit_async_comprehension(node, 'gen')

        def emit_element(sc, acc_idx):
            sc.emit(_TVMOpcodes.LOAD_FAST, acc_idx)
            sc.emit(_TVMOpcodes.GET_ATTR, sc.code_obj.get_name_idx('append'))
            sc.visit(node.elt)
            sc.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            sc.emit(_TVMOpcodes.POP_TOP)

        sub_compiler = self._emit_comprehension(node, 'BUILD_LIST', '_$lst', emit_element)
        sub_compiler.emit(_TVMOpcodes.GET_ITER)
        sub_compiler.emit(_TVMOpcodes.RETURN_VALUE)
        sub_code = sub_compiler.finalize()
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.MAKE_FUNCTION, 0)
        self.visit(node.generators[0].iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

    def visit_ClassDef(self, node: ast.ClassDef):
        sub_compiler = _TVMASTCompiler(name=node.name, arg_names=[], is_function=True, is_class=True, vm_level=self.vm_level, rng=self.rng)
        sub_compiler._scan_scope(node.body)
        for stmt in node.body:
            sub_compiler.visit(stmt)
        sub_code = sub_compiler.finalize()

        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(node.name))
        for b in node.bases:
            self.visit(b)
        self.emit(_TVMOpcodes.BUILD_TUPLE, len(node.bases))

        has_meta = False
        for kw in node.keywords:
            if kw.arg == 'metaclass':
                self.visit(kw.value)
                has_meta = True
                break
        if not has_meta:
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))

        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(sub_code))
        self.emit(_TVMOpcodes.BUILD_CLASS, 0)

        for dec in reversed(node.decorator_list):
            self.visit(dec)
            self.emit(_TVMOpcodes.ROT_TWO)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        self._store_target(ast.Name(id=node.name, ctx=ast.Store()))

    def visit_If(self, node: ast.If):
        lbl_else = self.new_label()
        lbl_end = self.new_label()

        self.visit(node.test)
        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_else)
        for stmt in node.body:
            self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        self.mark_label(lbl_else)
        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)
        self.mark_label(lbl_end)

    def visit_While(self, node: ast.While):
        lbl_head = self.new_label()
        lbl_break = self.new_label()
        lbl_exit = self.new_label()
        lbl_end = self.new_label()

        self.mark_label(lbl_head)
        self.visit(node.test)
        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_exit)

        self.loop_stack.append((lbl_head, lbl_break))
        for stmt in node.body:
            self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_head)
        self.loop_stack.pop()

        self.mark_label(lbl_exit)
        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        self.mark_label(lbl_break)
        self.mark_label(lbl_end)

    def visit_For(self, node: ast.For):
        self.loop_depth += 1
        iter_slot = self.code_obj.get_local_idx(f'_$iter_{self.loop_depth}')

        lbl_head = self.new_label()
        lbl_break = self.new_label()
        lbl_exit = self.new_label()
        lbl_end = self.new_label()

        self.visit(node.iter)
        self.emit(_TVMOpcodes.GET_ITER)
        self.emit(_TVMOpcodes.STORE_FAST, iter_slot)

        self.mark_label(lbl_head)
        self.emit(_TVMOpcodes.LOAD_FAST, iter_slot)
        self.emit_jump(_TVMOpcodes.FOR_ITER, lbl_exit)

        self._store_target(node.target)

        self.loop_stack.append((lbl_head, lbl_break))
        for stmt in node.body:
            self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_head)
        self.loop_stack.pop()

        self.mark_label(lbl_exit)
        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        self.mark_label(lbl_break)
        self.mark_label(lbl_end)

        self.loop_depth -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor):
        self.loop_depth += 1
        iter_slot = self.code_obj.get_local_idx(f'_$aiter_{self.loop_depth}')
        pair_slot = self.code_obj.get_local_idx(f'_$anext_pair_{self.loop_depth}')
        ok_slot = self.code_obj.get_local_idx(f'_$anext_ok_{self.loop_depth}')
        val_slot = self.code_obj.get_local_idx(f'_$anext_val_{self.loop_depth}')

        lbl_head = self.new_label()
        lbl_break = self.new_label()
        lbl_exit = self.new_label()
        lbl_end = self.new_label()

        # aiter = await obj.__aiter__()
        self.visit(node.iter)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__aiter__'))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 0)
        self.emit(_TVMOpcodes.STORE_FAST, iter_slot)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.LOAD_FAST, iter_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        self.emit(_TVMOpcodes.STORE_FAST, iter_slot)

        self.mark_label(lbl_head)
        # (ok, value) = __vm_anext__(aiter)  -- sentinel-free async iteration
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['anext_fn']))
        self.emit(_TVMOpcodes.LOAD_FAST, iter_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        self.emit(_TVMOpcodes.STORE_FAST, pair_slot)
        self.emit(_TVMOpcodes.LOAD_FAST, pair_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(0))
        self.emit(_TVMOpcodes.GET_ITEM)
        self.emit(_TVMOpcodes.STORE_FAST, ok_slot)
        self.emit(_TVMOpcodes.LOAD_FAST, pair_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(1))
        self.emit(_TVMOpcodes.GET_ITEM)
        self.emit(_TVMOpcodes.STORE_FAST, val_slot)
        self.emit(_TVMOpcodes.LOAD_FAST, ok_slot)
        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_exit)

        self.emit(_TVMOpcodes.LOAD_FAST, val_slot)
        self._store_target(node.target)

        self.loop_stack.append((lbl_head, lbl_break))
        for stmt in node.body:
            self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_head)
        self.loop_stack.pop()

        self.mark_label(lbl_exit)
        if node.orelse:
            for stmt in node.orelse:
                self.visit(stmt)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        self.mark_label(lbl_break)
        self.mark_label(lbl_end)

        self.loop_depth -= 1

    def visit_With(self, node: ast.With):
        if len(node.items) > 1:
            inner_with = ast.With(items=node.items[1:], body=node.body)
            single_with = ast.With(items=[node.items[0]], body=[inner_with])
            self.visit(single_with)
            return

        item = node.items[0]
        ctx_slot = self.code_obj.get_local_idx(f'_$ctx_mgr_{self.new_label()}')
        self.visit(item.context_expr)
        self.emit(_TVMOpcodes.STORE_FAST, ctx_slot)

        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__enter__'))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 0)
        if item.optional_vars:
            self._store_target(item.optional_vars)
        else:
            self.emit(_TVMOpcodes.POP_TOP)

        lbl_handler = self.new_label()
        lbl_end = self.new_label()
        lbl_suppressed = self.new_label()

        self.emit_jump(_TVMOpcodes.SETUP_FINALLY, lbl_handler)
        self.exc_frame_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self.emit(_TVMOpcodes.POP_BLOCK)

        # Normal exit: __exit__(None, None, None)
        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__exit__'))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
        self.emit(_TVMOpcodes.POP_TOP)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        # Exception exit:
        self.mark_label(lbl_handler)
        exc_slot = self.code_obj.get_local_idx(f'_$with_exc_{self.new_label()}')
        self.emit(_TVMOpcodes.STORE_FAST, exc_slot)

        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__exit__'))

        # Arg 1: type(e)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('type'))
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        # Arg 2: e
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)

        # Arg 3: getattr(e, '__traceback__', None)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('getattr'))
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx('__traceback__'))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)

        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
        self.emit_jump(_TVMOpcodes.JUMP_IF_TRUE, lbl_suppressed)

        # Re-raise if __exit__ returned falsy
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.RAISE_VARARGS)

        self.mark_label(lbl_suppressed)
        self.mark_label(lbl_end)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        if len(node.items) > 1:
            inner_with = ast.AsyncWith(items=node.items[1:], body=node.body)
            single_with = ast.AsyncWith(items=[node.items[0]], body=[inner_with])
            self.visit(single_with)
            return

        item = node.items[0]
        ctx_slot = self.code_obj.get_local_idx(f'_$actx_mgr_{self.new_label()}')
        self.visit(item.context_expr)
        self.emit(_TVMOpcodes.STORE_FAST, ctx_slot)

        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__aenter__'))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 0)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        if item.optional_vars:
            self._store_target(item.optional_vars)
        else:
            self.emit(_TVMOpcodes.POP_TOP)

        lbl_handler = self.new_label()
        lbl_end = self.new_label()
        lbl_suppressed = self.new_label()

        self.emit_jump(_TVMOpcodes.SETUP_FINALLY, lbl_handler)
        self.exc_frame_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self.emit(_TVMOpcodes.POP_BLOCK)
        self.exc_frame_depth -= 1

        # Normal exit: __aexit__(None, None, None)
        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__aexit__'))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
        self.emit(_TVMOpcodes.POP_TOP)
        self.emit_jump(_TVMOpcodes.JUMP, lbl_end)

        # Exception handler
        self.mark_label(lbl_handler)
        exc_slot = self.code_obj.get_local_idx(f'_$awith_exc_{self.new_label()}')
        self.emit(_TVMOpcodes.STORE_FAST, exc_slot)

        self.emit(_TVMOpcodes.LOAD_FAST, ctx_slot)
        self.emit(_TVMOpcodes.GET_ATTR, self.code_obj.get_name_idx('__aexit__'))

        # Arg 1: type(e)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('type'))
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        # Arg 2: e
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)

        # Arg 3: getattr(e, '__traceback__', None)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('getattr'))
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx('__traceback__'))
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)

        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
        self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['await_fn']))
        self.emit(_TVMOpcodes.ROT_TWO)
        self.emit(_TVMOpcodes.CALL_FUNCTION, 1)

        self.emit_jump(_TVMOpcodes.JUMP_IF_TRUE, lbl_suppressed)

        # Re-raise if __aexit__ returned falsy
        self.emit(_TVMOpcodes.LOAD_FAST, exc_slot)
        self.emit(_TVMOpcodes.RAISE_VARARGS)

        self.mark_label(lbl_suppressed)
        self.mark_label(lbl_end)

    def visit_Try(self, node: ast.Try):
        has_finally = bool(node.finalbody)
        has_handlers = bool(node.handlers)

        if has_finally:
            lbl_fin_handler = self.new_label()
            lbl_fin_end = self.new_label()
            fin_exc_slot = self.code_obj.get_local_idx(f'_$fin_exc_{self.new_label()}')
            self.emit_jump(_TVMOpcodes.SETUP_FINALLY, lbl_fin_handler)
            self.exc_frame_depth += 1

        if has_handlers:
            lbl_exc_dispatcher = self.new_label()
            lbl_try_end = self.new_label()

            self.emit_jump(_TVMOpcodes.SETUP_FINALLY, lbl_exc_dispatcher)
            self.exc_frame_depth += 1
            for stmt in node.body:
                self.visit(stmt)
            self.emit(_TVMOpcodes.POP_BLOCK)
            self.exc_frame_depth -= 1

            # Try body succeeded with no exception -> execute orelse
            if node.orelse:
                for stmt in node.orelse:
                    self.visit(stmt)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_try_end)

            # Exception dispatcher
            self.mark_label(lbl_exc_dispatcher)
            for h in node.handlers:
                lbl_next_h = self.new_label()
                if h.type:
                    self.emit(_TVMOpcodes.DUP_TOP)
                    self.visit(h.type)
                    self.emit(_TVMOpcodes.CHECK_EXC_MATCH)
                    self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_next_h)

                if h.name:
                    self.emit(_TVMOpcodes.DUP_TOP)
                    target_node = ast.Name(id=h.name, ctx=ast.Store())
                    self._store_target(target_node)

                self.emit(_TVMOpcodes.POP_TOP)
                for stmt in h.body:
                    self.visit(stmt)
                self.emit_jump(_TVMOpcodes.JUMP, lbl_try_end)

                self.mark_label(lbl_next_h)

            # Re-raise if no handler matched
            self.emit(_TVMOpcodes.RAISE_VARARGS)
            self.mark_label(lbl_try_end)
        else:
            for stmt in node.body:
                self.visit(stmt)

        if has_finally:
            self.emit(_TVMOpcodes.POP_BLOCK)
            self.exc_frame_depth -= 1
            for stmt in node.finalbody:
                self.visit(stmt)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_fin_end)

            self.mark_label(lbl_fin_handler)
            self.emit(_TVMOpcodes.STORE_FAST, fin_exc_slot)
            for stmt in node.finalbody:
                self.visit(stmt)
            self.emit(_TVMOpcodes.LOAD_FAST, fin_exc_slot)
            self.emit(_TVMOpcodes.RAISE_VARARGS)

            self.mark_label(lbl_fin_end)

    def visit_Break(self, node: ast.Break):
        if self.loop_stack:
            _, lbl_break = self.loop_stack[-1]
            for _ in range(self.exc_frame_depth):
                self.emit(_TVMOpcodes.POP_BLOCK)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_break)

    def visit_Continue(self, node: ast.Continue):
        if self.loop_stack:
            lbl_head, _ = self.loop_stack[-1]
            for _ in range(self.exc_frame_depth):
                self.emit(_TVMOpcodes.POP_BLOCK)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_head)

    @staticmethod
    def _contains_yield_in_scope(body):
        """True if any Yield/YieldFrom appears directly in this scope
        (does NOT descend into nested function/lambda scopes)."""
        stack = list(body)
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(n, (ast.Yield, ast.YieldFrom)):
                return True
            for child in ast.iter_child_nodes(n):
                stack.append(child)
        return False

    def visit_Yield(self, node: ast.Yield):
        if getattr(self, 'is_generator', False):
            if node.value:
                self.visit(node.value)
            else:
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
            self.emit(_TVMOpcodes.YIELD_VALUE)
        else:
            # yield outside a generator is illegal; keep legacy fallback
            if node.value:
                self.visit(node.value)
            else:
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
            self.emit(_TVMOpcodes.RETURN_VALUE)

    def visit_YieldFrom(self, node: ast.YieldFrom):
        # NOTE: CPython itself forbids `yield from` inside async functions
        # (SyntaxError), so only the sync path is reachable for valid sources.
        self.visit(node.value)
        self.emit(_TVMOpcodes.YIELD_FROM)

    def _capture_target(self, name: str) -> ast.Name:
        """Registers a match capture as a proper local (inside functions) and returns a Store target."""
        if self.is_function and name not in self.explicit_globals and name not in self.explicit_nonlocals:
            self.code_obj.get_local_idx(name)
        return ast.Name(id=name, ctx=ast.Store())

    def _match_pattern(self, pat, subj_slot: int, lbl_fail: int):
        """Emits bytecode matching `pat` against the subject held in local slot `subj_slot`.
        Jumps to `lbl_fail` on mismatch; stores capture bindings on success."""
        if isinstance(pat, ast.MatchValue):
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            if isinstance(pat.value, ast.AST):
                self.visit(pat.value)
            else:
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(pat.value))
            self.emit(_TVMOpcodes.COMPARE_OP, 2)  # ==
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
        elif isinstance(pat, ast.MatchSingleton):
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(pat.value))
            self.emit(_TVMOpcodes.COMPARE_OP, 8)  # is
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
        elif isinstance(pat, ast.MatchAs):
            if pat.pattern is not None:
                # `case <pattern> as name:` must FIRST match the inner pattern,
                # then bind. The old code skipped the match entirely, so
                # `str() as s` captured any subject (bools, floats, ints...).
                self._match_pattern(pat.pattern, subj_slot, lbl_fail)
            if pat.name is not None:
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                self._store_target(self._capture_target(pat.name))
        elif isinstance(pat, ast.MatchClass):
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('isinstance'))
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.visit(pat.cls)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 2)
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
            # FIX (GAP-35): missing kwd attr must FAIL the pattern (CPython),
            # not raise AttributeError through user code. getattr-3-arg +
            # _NO_ARG sentinel comparison.
            _no_arg_gi = self.code_obj.get_name_idx(_TVM_TOKENS['no_arg'])
            for attr_name, kp_node in zip(pat.kwd_attrs, pat.kwd_patterns):
                self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('getattr'))
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(attr_name))
                self.emit(_TVMOpcodes.LOAD_GLOBAL, _no_arg_gi)
                self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
                tmp_slot = self.code_obj.get_local_idx(f'_$mk_{self.new_label()}')
                self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
                self.emit(_TVMOpcodes.LOAD_FAST, tmp_slot)
                self.emit(_TVMOpcodes.LOAD_GLOBAL, _no_arg_gi)
                self.emit(_TVMOpcodes.COMPARE_OP, 9)  # is not
                self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
                self._match_pattern(kp_node, tmp_slot, lbl_fail)
            if pat.patterns:
                if len(pat.patterns) == 1 and isinstance(pat.patterns[0], ast.MatchAs):
                    cap = pat.patterns[0]
                    if cap.name is not None:
                        self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                        self._store_target(self._capture_target(cap.name))
                else:
                    _ma_gi = self.code_obj.get_name_idx('__tvm_margs')
                    for p_idx, pp_node in enumerate(pat.patterns):
                        # FIX (GAP-35b): positional index beyond __match_args__
                        # must fail the pattern, not raise IndexError.
                        self.emit(_TVMOpcodes.LOAD_GLOBAL, _ma_gi)
                        self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                        self.visit(pat.cls)
                        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(p_idx))
                        self.emit(_TVMOpcodes.CALL_FUNCTION, 3)
                        tmp_slot = self.code_obj.get_local_idx(f'_$mk_{self.new_label()}')
                        self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
                        self.emit(_TVMOpcodes.LOAD_FAST, tmp_slot)
                        self.emit(_TVMOpcodes.LOAD_GLOBAL, _no_arg_gi)
                        self.emit(_TVMOpcodes.COMPARE_OP, 9)  # is not
                        self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
                        self._match_pattern(pp_node, tmp_slot, lbl_fail)
        elif isinstance(pat, ast.MatchMapping):
            # FIX (GAP-34): match ANY collections.abc.Mapping (os.environ,
            # defaultdict, MappingProxyType...), not only exact dict.
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('__tvm_is_map'))
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
            for key_node, pat_node in zip(pat.keys, pat.patterns):
                self.visit(key_node)
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                self.emit(_TVMOpcodes.COMPARE_OP, 6)  # in
                self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                self.visit(key_node)
                self.emit(_TVMOpcodes.GET_ITEM)
                tmp_slot = self.code_obj.get_local_idx(f'_$mm_{self.new_label()}')
                self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
                self._match_pattern(pat_node, tmp_slot, lbl_fail)
            if pat.rest is not None:
                self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx(_TVM_TOKENS['match_rest']))
                self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                for key_node in pat.keys:
                    self.visit(key_node)
                self.emit(_TVMOpcodes.BUILD_TUPLE, len(pat.keys))
                self.emit(_TVMOpcodes.CALL_FUNCTION, 2)
                self._store_target(self._capture_target(pat.rest))
        elif isinstance(pat, ast.MatchSequence):
            has_star = any(isinstance(p, ast.MatchStar) for p in pat.patterns)
            # FIX (GAP-33): CPython sequence patterns match ANY object with
            # __len__/__getitem__ (range, deque, array, numpy 1-D...) except
            # str/bytes/bytearray. Use a runtime protocol helper instead of an
            # exact (tuple, list) isinstance that silently skipped custom containers.
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('__tvm_is_seq'))
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('len'))
            self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(len(pat.patterns)))
            if has_star:
                self.emit(_TVMOpcodes.COMPARE_OP, 5)  # >=
            else:
                self.emit(_TVMOpcodes.COMPARE_OP, 2)  # ==
            self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_fail)
            for p_idx, p_node in enumerate(pat.patterns):
                if isinstance(p_node, ast.MatchStar):
                    if p_node.name is not None:
                        n_after = len(pat.patterns) - p_idx - 1
                        upper_val = None if n_after == 0 else -n_after
                        self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(p_idx))
                        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(upper_val))
                        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
                        self.emit(_TVMOpcodes.BUILD_SLICE, 3)
                        self.emit(_TVMOpcodes.GET_ITEM)
                        self._store_target(self._capture_target(p_node.name))
                else:
                    self.emit(_TVMOpcodes.LOAD_FAST, subj_slot)
                    self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(p_idx))
                    self.emit(_TVMOpcodes.GET_ITEM)
                    tmp_slot = self.code_obj.get_local_idx(f'_$ms_{self.new_label()}')
                    self.emit(_TVMOpcodes.STORE_FAST, tmp_slot)
                    self._match_pattern(p_node, tmp_slot, lbl_fail)
        elif isinstance(pat, ast.MatchOr):
            # FIX (GAP-36): a partially-matched alternative must NOT leave its
            # captures installed when it fails. Snapshot every capture slot the
            # alternatives can write, restore on failure.
            cap_slots = []
            def _collect_caps(p):
                for ch in ast.walk(p):
                    if isinstance(ch, ast.MatchAs) and ch.name:
                        cap_slots.append(self._capture_target(ch.name).id)
                    elif isinstance(ch, ast.MatchStar) and ch.name:
                        cap_slots.append(self._capture_target(ch.name).id)
                    elif isinstance(ch, ast.MatchMapping) and ch.rest:
                        cap_slots.append(self._capture_target(ch.rest).id)
            for alt in pat.patterns:
                _collect_caps(alt)
            uniq_slots = list(dict.fromkeys(cap_slots))
            snap_slot = self.code_obj.get_local_idx(f'_$orsnap_{self.new_label()}')
            # snapshot current values of every possible capture binding
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('__tvm_snap'))
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tuple(uniq_slots)))
            self.emit(_TVMOpcodes.CALL_FUNCTION, 1)
            self.emit(_TVMOpcodes.STORE_FAST, snap_slot)
            lbl_ok = self.new_label()
            for alt in pat.patterns:
                lbl_alt_fail = self.new_label()
                self._match_pattern(alt, subj_slot, lbl_alt_fail)
                self.emit_jump(_TVMOpcodes.JUMP, lbl_ok)
                self.mark_label(lbl_alt_fail)
            # all failed -> rollback captures then fail upward
            self.emit(_TVMOpcodes.LOAD_GLOBAL, self.code_obj.get_name_idx('__tvm_restore'))
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(tuple(uniq_slots)))
            self.emit(_TVMOpcodes.LOAD_FAST, snap_slot)
            self.emit(_TVMOpcodes.CALL_FUNCTION, 2)
            self.emit(_TVMOpcodes.POP_TOP)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_fail)
            self.mark_label(lbl_ok)
        # Unknown/unsupported pattern kinds: emit no constraint (always matches).

    def visit_Match(self, node: ast.Match):
        lbl_match_end = self.new_label()
        self.visit(node.subject)
        subj_slot = self.code_obj.get_local_idx(f'_$subj_{self.new_label()}')
        self.emit(_TVMOpcodes.STORE_FAST, subj_slot)

        for case_clause in node.cases:
            lbl_next_case = self.new_label()
            self._match_pattern(case_clause.pattern, subj_slot, lbl_next_case)

            if case_clause.guard:
                self.visit(case_clause.guard)
                self.emit_jump(_TVMOpcodes.JUMP_IF_FALSE, lbl_next_case)

            for stmt in case_clause.body:
                self.visit(stmt)
            self.emit_jump(_TVMOpcodes.JUMP, lbl_match_end)
            self.mark_label(lbl_next_case)

        self.mark_label(lbl_match_end)

    def visit_Return(self, node: ast.Return):
        if node.value:
            self.visit(node.value)
        else:
            self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.RETURN_VALUE)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            idx = self.code_obj.get_name_idx(alias.name)
            self.emit(_TVMOpcodes.IMPORT_NAME, idx)
            if alias.asname:
                # `import a.b as c` must bind c = a.b (the submodule), not a.
                # FIX (GAP-30): route through the fromlist sentinel so the
                # SUBMODULE is returned directly - the old IMPORT_NAME(root)
                # + IMPORT_FROM(sub) + POP_TOP sequence popped the WRONG item
                # and bound the root package to the alias.
                if '.' in alias.name:
                    last_part = alias.name.split('.')[-1]
                    fl_sentinel = _TVM_TOKENS['fl_prefix'] + alias.name + '\x00' + last_part
                    idx = self.code_obj.get_name_idx(fl_sentinel)
                    self.emit(_TVMOpcodes.IMPORT_NAME, idx)
                target_name = alias.asname
            else:
                # plain `import a.b` binds the root package 'a'
                target_name = alias.name.split('.')[0]
            store_idx = self.code_obj.get_name_idx(target_name)
            self.emit(_TVMOpcodes.STORE_GLOBAL, store_idx)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # FIX (GAP-31): star + relative imports are unsupported by the VM
        # runtime; previously they crashed at RUNTIME with opaque errors.
        # Fail LOUD at compile time instead.
        if any(alias.name == '*' for alias in node.names):
            raise TVMEmitError("from-module import * is not supported by TVM virtualization")
        if node.level and node.level > 0:
            raise TVMEmitError("relative imports are not supported by TVM virtualization")
        # FIX (GAP-29): `from pkg.sub import name` previously called
        # __import__('pkg.sub') WITHOUT fromlist -> returned the ROOT package
        # -> getattr failed. The handler recognizes this sentinel name form
        # and re-imports with fromlist so the SUBMODULE is returned.
        names_csv = ','.join(a.name for a in node.names)
        sentinel = _TVM_TOKENS['fl_prefix'] + (node.module or '') + '\x00' + names_csv
        mod_idx = self.code_obj.get_name_idx(sentinel)
        self.emit(_TVMOpcodes.IMPORT_NAME, mod_idx)
        for alias in node.names:
            attr_idx = self.code_obj.get_name_idx(alias.name)
            self.emit(_TVMOpcodes.IMPORT_FROM, attr_idx)
            target_name = alias.asname or alias.name
            store_idx = self.code_obj.get_name_idx(target_name)
            self.emit(_TVMOpcodes.STORE_GLOBAL, store_idx)
        self.emit(_TVMOpcodes.POP_TOP)

    def finalize(self) -> _TVMCodeObject:
        self.emit(_TVMOpcodes.LOAD_CONST, self.code_obj.get_const_idx(None))
        self.emit(_TVMOpcodes.RETURN_VALUE)

        if self.vm_level >= 2:
            old_insts = self.code_obj.instructions
            new_insts = []
            target_pos_map = {}
            inst_pos_map = {}
            for old_idx, (op, arg) in enumerate(old_insts):
                target_pos_map[old_idx] = len(new_insts)
                # Level 2 & 3: Randomized NOP insertion
                if self.rng.random() < 0.15:
                    new_insts.append((_TVMOpcodes.NOP, 0))
                # Level 3: Dummy Invariant Push/Pop cycle insertion
                if self.vm_level >= 3 and self.rng.random() < 0.10:
                    d_idx = self.code_obj.get_const_idx(0)
                    new_insts.append((_TVMOpcodes.LOAD_CONST, d_idx))
                    new_insts.append((_TVMOpcodes.POP_TOP, 0))
                inst_pos_map[old_idx] = len(new_insts)
                new_insts.append((op, arg))
                # After unconditional exits, insert unreachable Dead Traps
                if op in (_TVMOpcodes.RETURN_VALUE, _TVMOpcodes.HALT, _TVMOpcodes.RAISE_VARARGS):
                    num_traps = self.rng.randint(1, 3)
                    for _ in range(num_traps):
                        new_insts.append((_TVMOpcodes.TRAP, self.rng.randint(0, 65535)))

            target_pos_map[len(old_insts)] = len(new_insts)
            inst_pos_map[len(old_insts)] = len(new_insts)
            self.labels = {lbl_id: target_pos_map.get(old_t, len(new_insts) - 1) for lbl_id, old_t in self.labels.items()}
            self.label_fixups = {lbl_id: [inst_pos_map.get(old_f, 0) for old_f in fix_list] for lbl_id, fix_list in self.label_fixups.items()}
            self.code_obj.instructions = new_insts

        for lbl_id, fixup_indices in self.label_fixups.items():
            target_ip = self.labels.get(lbl_id, len(self.code_obj.instructions) - 1)
            for fix_idx in fixup_indices:
                op, _ = self.code_obj.instructions[fix_idx]
                self.code_obj.instructions[fix_idx] = (op, target_ip)
        return self.code_obj


_TVM_MAGIC = b"TVM1"
_TVM_VERSION = 4

# Tamper response modes for the emitted runtime.
#   'exit'   - process terminates on any integrity failure (default)
#   'poison' - keys are silently degraded and execution continues inert
_TVM_TAMPER_MODES = ("exit", "poison")


def _tvm_derive_runtime_keys(seed_bytes: bytes, salt_bytes: bytes = b'') -> Tuple[bytes, bytes]:
    """
    Derives dynamic cryptographic keystream and HMAC keys using iterative SHA-256 expansion with domain separation.
    Returns (k_enc, k_mac).
    """
    k_enc = hashlib.sha256(b"TRX_TVM_ENC_KEY_V3:" + seed_bytes + salt_bytes).digest()
    k_mac = hashlib.sha256(b"TRX_TVM_MAC_KEY_V3:" + seed_bytes + salt_bytes).digest()
    return k_enc, k_mac


def _tvm_aead_encrypt(payload: bytes, k_enc: bytes, k_mac: bytes) -> bytes:
    """
    Encrypts payload using counter-mode keystream XOR + HMAC-SHA256 authenticated envelope.
    Envelope format: [Nonce: 16B] + [HMAC Tag: 32B] + [Ciphertext: NB]
    """
    nonce = secrets.token_bytes(16)
    plen = len(payload)
    num_blocks = (plen + 31) // 32
    ks = bytearray()
    for i in range(num_blocks):
        ctr = i.to_bytes(4, 'big')
        ks.extend(hashlib.sha256(k_enc + nonce + ctr).digest())
    ciphertext = bytes(p ^ k for p, k in zip(payload, ks[:plen]))
    tag = hmac.new(k_mac, nonce + ciphertext, hashlib.sha256).digest()
    return nonce + tag + ciphertext


def _serialize_tvm_code_object(code: _TVMCodeObject, isa_map: Dict[int, int], k_enc: bytes, k_mac: bytes, perm_get=None) -> bytes:
    """
    Recursively serializes a _TVMCodeObject and nested code objects into an authenticated AEAD structure.
    Nested code objects inside constants are encrypted with unique child salts and stored as lazy records.
    perm_get(name) -> optional per-code-object substitution list applied AFTER isa_map
    (level-4 per-function ISA divergence).
    """
    inv = perm_get(code.name) if perm_get else None
    bytecode_ba = bytearray()
    for op, arg in code.instructions:
        mapped_op = isa_map.get(op, op)
        if inv is not None:
            mapped_op = inv[mapped_op & 0xFF]
        bytecode_ba.append(mapped_op & 0xFF)
        bytecode_ba.append((arg >> 8) & 0xFF)
        bytecode_ba.append(arg & 0xFF)

    serialized_consts = []
    for c in code.constants:
        if isinstance(c, _TVMCodeObject):
            child_salt = secrets.token_bytes(16)
            child_k_enc, child_k_mac = _tvm_derive_runtime_keys(k_enc, child_salt)
            child_encrypted = _serialize_tvm_code_object(c, isa_map, child_k_enc, child_k_mac, perm_get)
            serialized_consts.append((_TVM_TOKENS['lazy'], child_salt, child_encrypted))
        else:
            serialized_consts.append(c)

    raw_payload = marshal.dumps((
        code.name,
        code.arg_names,
        getattr(code, 'kwonly_names', []),
        code.vararg_name,
        code.kwarg_name,
        code.local_names,
        bytes(bytecode_ba),
        tuple(serialized_consts),
        tuple(code.names),
        tuple(getattr(code, 'kwonly_default_names', ()))
    ))

    import zlib as _zlib_mod
    compressed_payload = _zlib_mod.compress(raw_payload, level=9)
    return _tvm_aead_encrypt(compressed_payload, k_enc, k_mac)


def _vm_emit_runtime_interpreter_v2(root_code: _TVMCodeObject, isa_map: Dict[int, int], vm_level: int, rng: random.Random, vm_debug: bool = False) -> str:
    """Emits the pure Python Polymorphic Virtual Machine Runtime Interpreter 2.0 with AEAD decryption and dynamic affine dispatch."""
    # Deterministic per-name 256-byte permutation (level 4 ISA divergence).
    def _perm_from_seed(name: str, seed: bytes):
        import hashlib as _hlib
        data = b"TRX_PERM:" + seed + name.encode('utf-8', 'replace')
        perm = list(range(256))
        i = 255
        counter = 0
        while i > 0:
            blk = _hlib.sha256(data + counter.to_bytes(4, 'big')).digest()
            counter += 1
            for b in blk:
                if i == 0:
                    break
                j = b % (i + 1)
                perm[i], perm[j] = perm[j], perm[i]
                i -= 1
        return perm

    master_seed = secrets.token_bytes(32)
    runtime_salt = secrets.token_bytes(16)
    k_enc, k_mac = _tvm_derive_runtime_keys(master_seed, runtime_salt)

    if vm_level >= 4 and getattr(__import__('os').environ.get('TRX_VM_L4_PERM', '0'), '__class__', str) is not type:
        pass  # placeholder keeps linters calm

    if vm_level >= 4 and os.environ.get("TRX_VM_L4_PERM") == "1":
        _perm_cache = {}

        def _perm_inv_for(name: str):
            p = _perm_cache.get(name)
            if p is None:
                fwd = _perm_from_seed(name, master_seed)
                inv = [0] * 256
                for stored, mapped in enumerate(fwd):
                    inv[mapped] = stored
                p = (fwd, inv)
                _perm_cache[name] = p
            return p

        def _perm_get(name: str):
            return _perm_inv_for(name)[1]
    else:
        def _perm_get(name: str):
            return None

    serialized_root_packet = _serialize_tvm_code_object(root_code, isa_map, k_enc, k_mac, _perm_get)

    v = {k: rd() for k in [
        'code_obj_cls', 'frame_cls', 'interp_fn', 'call_vm_fn', 'eval_frame_fn',
        'eval_frame_async_fn', 'call_vm_async_fn', 'lazy_decode_fn',
        'derive_keys_fn', 'decrypt_packet_fn', 'decode_code_fn',
        'root_packet', 'master_seed', 'runtime_salt', 'dispatch_tbl',
        'dispatch_tbl_async', 'ret_sig', 'await_sig', 'halt_sig',
        'yield_sig', 'no_arg_sig', 'active_frames', 'vm_super_fn', 'vm_await_fn',
        'vm_anext_fn', 'bind_frame_fn', 'gen_cls', 'agen_cls', 'async_depth',
        'attach_isa_fn', 'perm_rt_fn',
        'trap_fn'
    ]}

    # Level-4 per-function ISA divergence is implemented (serializer + runtime
    # inverse-dispatch) but DISABLED pending a unique-per-code-object salt:
    # keying the permutation by bare name let same-named code objects share a
    # mapping, which produced cross-frame semantic subtleties. Flip once isa
    # salts are threaded through serialization.
    _TVM_L4_PERM_ENABLED = False

    odd_multipliers = [m for m in range(3, 256, 2)]
    M = rng.choice(odd_multipliers)
    _trap_delay = round(rng.uniform(0.01, 0.15), 4)
    A = rng.randint(0, 255)
    tok = _TVM_TOKENS

    _DBG_AE = "pass"
    _DBG_CALLA = "pass"
    if vm_debug:
        _DBG_AE = ("import sys as _vdbg\n        "
                   f"_vdbg.stderr.write('AE+ depth=%r\\n' % ({v['async_depth']}[0]))")
        _DBG_CALLA = ("import sys as _vdbg2\n        "
                      f"_vdbg2.stderr.write('CALLA fn=%r depth=%r\\n' % (getattr(_fn, '__name__', '?'), {v['async_depth']}[0]))")

    def affine_slot(std_op: int) -> int:
        mapped_op = isa_map.get(std_op, std_op)
        return (mapped_op * M + A) % 256

    slot_ld_c    = affine_slot(_TVMOpcodes.LOAD_CONST)
    slot_ld_g    = affine_slot(_TVMOpcodes.LOAD_GLOBAL)
    slot_st_g    = affine_slot(_TVMOpcodes.STORE_GLOBAL)
    slot_ld_f    = affine_slot(_TVMOpcodes.LOAD_FAST)
    slot_st_f    = affine_slot(_TVMOpcodes.STORE_FAST)
    slot_dup     = affine_slot(_TVMOpcodes.DUP_TOP)
    slot_pop     = affine_slot(_TVMOpcodes.POP_TOP)
    slot_rot2    = affine_slot(_TVMOpcodes.ROT_TWO)
    slot_rot3    = affine_slot(_TVMOpcodes.ROT_THREE)

    slot_add     = affine_slot(_TVMOpcodes.BINARY_ADD)
    slot_sub     = affine_slot(_TVMOpcodes.BINARY_SUB)
    slot_mul     = affine_slot(_TVMOpcodes.BINARY_MUL)
    slot_div     = affine_slot(_TVMOpcodes.BINARY_DIV)
    slot_fdiv    = affine_slot(_TVMOpcodes.BINARY_FLOORDIV)
    slot_mod     = affine_slot(_TVMOpcodes.BINARY_MOD)
    slot_pow     = affine_slot(_TVMOpcodes.BINARY_POW)
    slot_and     = affine_slot(_TVMOpcodes.BINARY_AND)
    slot_or      = affine_slot(_TVMOpcodes.BINARY_OR)
    slot_xor     = affine_slot(_TVMOpcodes.BINARY_XOR)
    slot_lsh     = affine_slot(_TVMOpcodes.BINARY_LSHIFT)
    slot_rsh     = affine_slot(_TVMOpcodes.BINARY_RSHIFT)
    slot_neg     = affine_slot(_TVMOpcodes.UNARY_NEG)
    slot_not     = affine_slot(_TVMOpcodes.UNARY_NOT)
    slot_inv     = affine_slot(_TVMOpcodes.UNARY_INVERT)
    slot_matmul  = affine_slot(_TVMOpcodes.BINARY_MATMUL)

    slot_cmp     = affine_slot(_TVMOpcodes.COMPARE_OP)

    slot_jmp     = affine_slot(_TVMOpcodes.JUMP)
    slot_jmp_t   = affine_slot(_TVMOpcodes.JUMP_IF_TRUE)
    slot_jmp_f   = affine_slot(_TVMOpcodes.JUMP_IF_FALSE)
    slot_jmp_f_p = affine_slot(_TVMOpcodes.JUMP_IF_FALSE_OR_POP)
    slot_jmp_t_p = affine_slot(_TVMOpcodes.JUMP_IF_TRUE_OR_POP)
    slot_ret     = affine_slot(_TVMOpcodes.RETURN_VALUE)

    slot_g_attr  = affine_slot(_TVMOpcodes.GET_ATTR)
    slot_s_attr  = affine_slot(_TVMOpcodes.SET_ATTR)
    slot_d_attr  = affine_slot(_TVMOpcodes.DEL_ATTR)
    slot_g_item  = affine_slot(_TVMOpcodes.GET_ITEM)
    slot_s_item  = affine_slot(_TVMOpcodes.SET_ITEM)
    slot_d_item  = affine_slot(_TVMOpcodes.DEL_ITEM)
    slot_d_fast  = affine_slot(_TVMOpcodes.DEL_FAST)
    slot_d_glob  = affine_slot(_TVMOpcodes.DEL_GLOBAL)

    slot_b_list  = affine_slot(_TVMOpcodes.BUILD_LIST)
    slot_b_tup   = affine_slot(_TVMOpcodes.BUILD_TUPLE)
    slot_b_set   = affine_slot(_TVMOpcodes.BUILD_SET)
    slot_b_dict  = affine_slot(_TVMOpcodes.BUILD_DICT)
    slot_unp_seq = affine_slot(_TVMOpcodes.UNPACK_SEQUENCE)
    slot_unp_ex  = affine_slot(_TVMOpcodes.UNPACK_EX)
    slot_b_slice = affine_slot(_TVMOpcodes.BUILD_SLICE)

    slot_mk_fn   = affine_slot(_TVMOpcodes.MAKE_FUNCTION)
    slot_call_fn = affine_slot(_TVMOpcodes.CALL_FUNCTION)
    slot_call_kw = affine_slot(_TVMOpcodes.CALL_FUNCTION_KW)
    slot_call_ex = affine_slot(_TVMOpcodes.CALL_FUNCTION_EX)
    slot_b_cls   = affine_slot(_TVMOpcodes.BUILD_CLASS)
    slot_imp_n   = affine_slot(_TVMOpcodes.IMPORT_NAME)
    slot_imp_f   = affine_slot(_TVMOpcodes.IMPORT_FROM)
    slot_ld_drf  = affine_slot(_TVMOpcodes.LOAD_DEREF)
    slot_st_drf  = affine_slot(_TVMOpcodes.STORE_DEREF)

    slot_g_iter  = affine_slot(_TVMOpcodes.GET_ITER)
    slot_for_it  = affine_slot(_TVMOpcodes.FOR_ITER)
    slot_st_fin  = affine_slot(_TVMOpcodes.SETUP_FINALLY)
    slot_pop_blk = affine_slot(_TVMOpcodes.POP_BLOCK)
    slot_raise   = affine_slot(_TVMOpcodes.RAISE_VARARGS)
    slot_chk_exc = affine_slot(_TVMOpcodes.CHECK_EXC_MATCH)

    slot_halt    = affine_slot(_TVMOpcodes.HALT)
    slot_nop     = affine_slot(_TVMOpcodes.NOP)
    slot_trap    = affine_slot(_TVMOpcodes.TRAP)
    slot_yield   = affine_slot(_TVMOpcodes.YIELD_VALUE)
    slot_yfrom   = affine_slot(_TVMOpcodes.YIELD_FROM)

    reg_entries = [
        (slot_ld_c, '_h_ld_c'),
        (slot_ld_g, '_h_ld_g'),
        (slot_st_g, '_h_st_g'),
        (slot_ld_f, '_h_ld_f'),
        (slot_st_f, '_h_st_f'),
        (slot_dup, '_h_dup'),
        (slot_pop, '_h_pop'),
        (slot_rot2, '_h_rot2'),
        (slot_rot3, '_h_rot3'),
        (slot_add, '_h_add'),
        (slot_sub, '_h_sub'),
        (slot_mul, '_h_mul'),
        (slot_div, '_h_div'),
        (slot_fdiv, '_h_fdiv'),
        (slot_mod, '_h_mod'),
        (slot_pow, '_h_pow'),
        (slot_and, '_h_and'),
        (slot_or, '_h_or'),
        (slot_xor, '_h_xor'),
        (slot_lsh, '_h_lsh'),
        (slot_rsh, '_h_rsh'),
        (slot_neg, '_h_neg'),
        (slot_not, '_h_not'),
        (slot_inv, '_h_inv'),
        (slot_matmul, '_h_matmul'),
        (slot_cmp, '_h_cmp'),
        (slot_jmp, '_h_jmp'),
        (slot_jmp_t, '_h_jmp_t'),
        (slot_jmp_f, '_h_jmp_f'),
        (slot_jmp_f_p, '_h_jmp_f_p'),
        (slot_jmp_t_p, '_h_jmp_t_p'),
        (slot_ret, '_h_ret'),
        (slot_g_attr, '_h_g_attr'),
        (slot_s_attr, '_h_s_attr'),
        (slot_d_attr, '_h_d_attr'),
        (slot_g_item, '_h_g_item'),
        (slot_s_item, '_h_s_item'),
        (slot_d_item, '_h_d_item'),
        (slot_d_fast, '_h_d_fast'),
        (slot_d_glob, '_h_d_glob'),
        (slot_b_list, '_h_b_list'),
        (slot_b_tup, '_h_b_tup'),
        (slot_b_set, '_h_b_set'),
        (slot_b_dict, '_h_b_dict'),
        (slot_unp_seq, '_h_unp_seq'),
        (slot_unp_ex, '_h_unp_ex'),
        (slot_b_slice, '_h_b_slice'),
        (slot_mk_fn, '_h_mk_fn'),
        (slot_call_fn, '_h_call_fn'),
        (slot_call_kw, '_h_call_kw'),
        (slot_call_ex, '_h_call_ex'),
        (slot_b_cls, '_h_b_cls'),
        (slot_imp_n, '_h_imp_n'),
        (slot_imp_f, '_h_imp_f'),
        (slot_ld_drf, '_h_ld_drf'),
        (slot_st_drf, '_h_st_drf'),
        (slot_g_iter, '_h_g_iter'),
        (slot_for_it, '_h_for_it'),
        (slot_st_fin, '_h_st_fin'),
        (slot_pop_blk, '_h_pop_blk'),
        (slot_raise, '_h_raise'),
        (slot_chk_exc, '_h_chk_exc'),
        (slot_nop, '_h_nop'),
        (slot_halt, '_h_halt'),
        (slot_trap, v['trap_fn']),
        (slot_yield, '_h_yield'),
        (slot_yfrom, '_h_yield_from')
    ]
    rng.shuffle(reg_entries)
    reg_stmts = "\n    ".join([f"{v['dispatch_tbl']}[{s}] = {fn}; {v['dispatch_tbl_async']}[{s}] = {fn}" for s, fn in reg_entries])

    src = f"""
def {v['interp_fn']}(_root_packet, _master_seed, _runtime_salt):
    import hashlib as _hashlib
    import hmac as _hmac
    import marshal as _marshal
    import os as _os
    import sys as _sys
    import zlib as _zlib
    _sys_len = len

    if hasattr(_sys, 'monitoring'):
        try:
            _ttag = 'tx' + _hashlib.sha256(_root_packet[:9]).hexdigest()[:6]
            for _tool_id in range(6):
                try:
                    if _sys.monitoring.get_tool(_tool_id) is None:
                        try:
                            _sys.monitoring.use_tool_id(_tool_id, _ttag)
                            _sys.monitoring.set_events(_tool_id, 0)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def {v['derive_keys_fn']}(_seed, _salt=b''):
        _k1 = _hashlib.sha256(b"TRX_TVM_ENC_KEY_V3:" + _seed + _salt).digest()
        _k2 = _hashlib.sha256(b"TRX_TVM_MAC_KEY_V3:" + _seed + _salt).digest()
        return _k1, _k2

    def {v['decrypt_packet_fn']}(_packet, _k_enc, _k_mac):
        if _sys_len(_packet) < 48:
            _os._exit(1)
        _nonce = _packet[:16]
        _tag = _packet[16:48]
        _ciphertext = _packet[48:]
        _expected_tag = _hmac.new(_k_mac, _nonce + _ciphertext, _hashlib.sha256).digest()
        if not _hmac.compare_digest(_tag, _expected_tag):
            _os._exit(1)
        _plen = _sys_len(_ciphertext)
        _num_blocks = (_plen + 31) // 32
        _ks = bytearray()
        for _i in range(_num_blocks):
            _ctr = _i.to_bytes(4, 'big')
            _ks.extend(_hashlib.sha256(_k_enc + _nonce + _ctr).digest())
        return bytes(_c ^ _k for _c, _k in zip(_ciphertext, _ks[:_plen]))

    def {v['decode_code_fn']}(_packet, _k_enc, _k_mac):
        _compressed_bytes = {v['decrypt_packet_fn']}(_packet, _k_enc, _k_mac)
        _raw_bytes = _zlib.decompress(_compressed_bytes)
        _data = _marshal.loads(_raw_bytes)
        return {v['code_obj_cls']}(_data, _k_enc)

    class {v['code_obj_cls']}:
        def __init__(self, data, parent_k_enc):
            self.name = data[0]
            self.arg_names = data[1]
            self.kwonly_names = data[2]
            self.vararg_name = data[3]
            self.kwarg_name = data[4]
            self.local_names = data[5]
            self.code = data[6]
            self.constants = list(data[7])
            self.names = data[8]
            self.kwonly_default_names = tuple(data[9]) if _sys_len(data) > 9 else ()
            self.defining_class = None
            self._k_enc = parent_k_enc

        def resolve_const(self, idx):
            c = self.constants[idx]
            if isinstance(c, tuple) and _sys_len(c) == 3 and c[0] == {repr(tok['lazy'])}:
                child_salt, child_packet = c[1], c[2]
                child_k_enc, child_k_mac = {v['derive_keys_fn']}(self._k_enc, child_salt)
                decoded = {v['decode_code_fn']}(child_packet, child_k_enc, child_k_mac)
                self.constants[idx] = decoded
                return decoded
            return c

    class {v['frame_cls']}:
        def __init__(self, code_obj, locals_dict, global_env):
            self.code_obj = code_obj
            self.pc = 0
            self.stack = []
            self.locals = locals_dict
            self.global_env = global_env
            self.exc_handlers = []
            self.current_exception = None
            self.captured_env = None
            self.defining_class = None
            self.is_generator = False
            self.just_resumed = False
            self.dele = None
            self.injected_exc = None
            self._m = 1
            self._a = 0

    def {v['lazy_decode_fn']}(c, parent_k_enc=None):
        if isinstance(c, tuple) and _sys_len(c) == 3 and c[0] == {repr(tok['lazy'])}:
            child_salt, child_packet = c[1], c[2]
            child_k_enc, child_k_mac = {v['derive_keys_fn']}(parent_k_enc or _root_k_enc, child_salt)
            return {v['decode_code_fn']}(child_packet, child_k_enc, child_k_mac)
        return c

    _root_k_enc, _root_k_mac = {v['derive_keys_fn']}(_master_seed, _runtime_salt)
    _root_code = {v['decode_code_fn']}(_root_packet, _root_k_enc, _root_k_mac)

    _g_env = globals()
    {v['active_frames']} = []
    {v['no_arg_sig']} = object()
    _g_env[{repr(tok['no_arg'])}] = {v['no_arg_sig']}
    {v['ret_sig']} = object()
    {v['await_sig']} = object()
    {v['yield_sig']} = object()
    {v['halt_sig']} = object()
    {v['async_depth']} = [0]

    def {v['perm_rt_fn']}(_nm, _sd):
        _data = b"TRX_PERM:" + _sd + _nm.encode('utf-8', 'replace')
        _perm = list(range(256))
        _i = 255
        _ctr = 0
        while _i > 0:
            _blk = _hashlib.sha256(_data + _ctr.to_bytes(4, 'big')).digest()
            _ctr += 1
            for _b in _blk:
                if _i == 0:
                    break
                _j = _b % (_i + 1)
                _perm[_i], _perm[_j] = _perm[_j], _perm[_i]
                _i -= 1
        return _perm

    def {v['trap_fn']}(_f, _a):
        import time as _time_mod
        _time_mod.sleep({_trap_delay})
        _os._exit(1)

    # Dynamic Opcode Handlers
    def _h_ld_c(_f, _a):
        _f.stack.append(_f.code_obj.resolve_const(_a))

    def _h_ld_g(_f, _a):
        _n = _f.code_obj.names[_a]
        if _f.captured_env and _n in _f.captured_env:
            _f.stack.append(_f.captured_env[_n])
            return
        if {v['active_frames']}:
            for _pf in reversed({v['active_frames']}[:-1]):
                if _n in _pf.locals and _pf.locals[_n] is not {v['no_arg_sig']}:
                    _f.stack.append(_pf.locals[_n])
                    return
        if _n in _f.global_env:
            _f.stack.append(_f.global_env[_n])
        elif hasattr(__builtins__, _n):
            _f.stack.append(getattr(__builtins__, _n))
        elif isinstance(__builtins__, dict) and _n in __builtins__:
            _f.stack.append(__builtins__[_n])
        else:
            raise NameError(f"name '{{_n}}' is not defined")

    def _h_st_g(_f, _a):
        _f.global_env[_f.code_obj.names[_a]] = _f.stack.pop()

    def _h_ld_f(_f, _a):
        _f.stack.append(_f.locals.get(_f.code_obj.local_names[_a], None))

    def _h_st_f(_f, _a):
        _f.locals[_f.code_obj.local_names[_a]] = _f.stack.pop()

    def _h_dup(_f, _a):
        _f.stack.append(_f.stack[-1])

    def _h_pop(_f, _a):
        if _f.stack: _f.stack.pop()

    def _h_rot2(_f, _a):
        _top = _f.stack.pop(); _sec = _f.stack.pop()
        _f.stack.append(_top); _f.stack.append(_sec)

    def _h_rot3(_f, _a):
        _top = _f.stack.pop(); _sec = _f.stack.pop(); _thd = _f.stack.pop()
        _f.stack.append(_top); _f.stack.append(_thd); _f.stack.append(_sec)

    def _h_add(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val + _b)

    def _h_sub(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val - _b)

    def _h_mul(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val * _b)

    def _h_div(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val / _b)

    def _h_fdiv(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val // _b)

    def _h_mod(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val % _b)

    def _h_pow(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val ** _b)

    def _h_and(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val & _b)

    def _h_or(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val | _b)

    def _h_xor(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val ^ _b)

    def _h_lsh(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val << _b)

    def _h_rsh(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val >> _b)

    def _h_neg(_f, _a):
        _f.stack.append(-_f.stack.pop())

    def _h_not(_f, _a):
        _f.stack.append(not _f.stack.pop())

    def _h_inv(_f, _a):
        _f.stack.append(~_f.stack.pop())

    def _h_matmul(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop(); _f.stack.append(_a_val @ _b)

    def _h_cmp(_f, _a):
        _b = _f.stack.pop(); _a_val = _f.stack.pop()
        if _a == 0: _f.stack.append(_a_val < _b)
        elif _a == 1: _f.stack.append(_a_val <= _b)
        elif _a == 2: _f.stack.append(_a_val == _b)
        elif _a == 3: _f.stack.append(_a_val != _b)
        elif _a == 4: _f.stack.append(_a_val > _b)
        elif _a == 5: _f.stack.append(_a_val >= _b)
        elif _a == 6: _f.stack.append(_a_val in _b)
        elif _a == 7: _f.stack.append(_a_val not in _b)
        elif _a == 8: _f.stack.append(_a_val is _b)
        elif _a == 9: _f.stack.append(_a_val is not _b)
        else: _f.stack.append(False)

    def _h_chk_exc(_f, _a):
        _exc_type = _f.stack.pop()
        _exc_val = _f.stack.pop()
        if isinstance(_exc_val, type):
            _f.stack.append(issubclass(_exc_val, _exc_type))
        else:
            _f.stack.append(isinstance(_exc_val, _exc_type))

    def _h_jmp(_f, _a):
        _f.pc = _a * 3

    def _h_jmp_t(_f, _a):
        if _f.stack.pop(): _f.pc = _a * 3

    def _h_jmp_f(_f, _a):
        if not _f.stack.pop(): _f.pc = _a * 3

    def _h_jmp_f_p(_f, _a):
        if not _f.stack[-1]: _f.pc = _a * 3
        else: _f.stack.pop()

    def _h_jmp_t_p(_f, _a):
        if _f.stack[-1]: _f.pc = _a * 3
        else: _f.stack.pop()

    def _h_ret(_f, _a):
        return ({v['ret_sig']}, _f.stack.pop() if _f.stack else None)

    def _h_g_attr(_f, _a):
        _f.stack.append(getattr(_f.stack.pop(), _f.code_obj.names[_a]))

    def _h_s_attr(_f, _a):
        _obj = _f.stack.pop(); _val = _f.stack.pop()
        setattr(_obj, _f.code_obj.names[_a], _val)

    def _h_d_attr(_f, _a):
        delattr(_f.stack.pop(), _f.code_obj.names[_a])

    def _h_g_item(_f, _a):
        _k = _f.stack.pop(); _c = _f.stack.pop()
        _f.stack.append(_c[_k])

    def _h_s_item(_f, _a):
        _k = _f.stack.pop(); _c = _f.stack.pop(); _v = _f.stack.pop()
        _c[_k] = _v

    def _h_d_item(_f, _a):
        _k = _f.stack.pop(); _c = _f.stack.pop(); del _c[_k]

    def _h_d_fast(_f, _a):
        _k = _f.code_obj.local_names[_a]
        if _k in _f.locals: del _f.locals[_k]

    def _h_d_glob(_f, _a):
        _k = _f.code_obj.names[_a]
        if _k in _f.global_env: del _f.global_env[_k]

    def _h_b_list(_f, _a):
        _elts = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _f.stack.append(_elts)

    def _h_b_tup(_f, _a):
        _elts = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _f.stack.append(tuple(_elts))

    def _h_b_set(_f, _a):
        _elts = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _f.stack.append(set(_elts))

    def _h_b_dict(_f, _a):
        _d = {{}}
        _items = []
        for _ in range(_a):
            _dv = _f.stack.pop(); _dk = _f.stack.pop()
            _items.append((_dk, _dv))
        for _dk, _dv in reversed(_items):
            _d[_dk] = _dv
        _f.stack.append(_d)

    def _h_unp_seq(_f, _a):
        _seq = list(_f.stack.pop())
        for _item in reversed(_seq):
            _f.stack.append(_item)

    def _h_unp_ex(_f, _a):
        _before = _a & 0xFF
        _after = (_a >> 8) & 0xFF
        _seq = list(_f.stack.pop())
        _total = _sys_len(_seq)
        for _item in reversed(_seq[_total - _after:] if _after else []):
            _f.stack.append(_item)
        _f.stack.append(_seq[_before : _total - _after])
        for _item in reversed(_seq[:_before]):
            _f.stack.append(_item)

    def _h_b_slice(_f, _a):
        _step = _f.stack.pop(); _upper = _f.stack.pop(); _lower = _f.stack.pop()
        _f.stack.append(slice(_lower, _upper, _step))

    def _h_ld_drf(_f, _a):
        _n = _f.code_obj.names[_a]
        if _f.captured_env and _n in _f.captured_env:
            _f.stack.append(_f.captured_env[_n])
            return
        if {v['active_frames']}:
            for _pf in reversed({v['active_frames']}[:-1]):
                if _n in _pf.locals:
                    _f.stack.append(_pf.locals[_n])
                    return
        if _n in _f.global_env:
            _f.stack.append(_f.global_env[_n])
        elif hasattr(__builtins__, _n):
            _f.stack.append(getattr(__builtins__, _n))
        elif isinstance(__builtins__, dict) and _n in __builtins__:
            _f.stack.append(__builtins__[_n])
        else:
            raise NameError(f"free variable '{{_n}}' referenced before assignment in enclosing scope")

    def _h_st_drf(_f, _a):
        _n = _f.code_obj.names[_a]
        _val = _f.stack.pop()
        _updated = False
        if {v['active_frames']}:
            for _pf in reversed({v['active_frames']}[:-1]):
                if _n in _pf.locals:
                    _pf.locals[_n] = _val
                    _updated = True
                    break
        if _f.captured_env and _n in _f.captured_env:
            _f.captured_env[_n] = _val
            _updated = True
        if not _updated:
            _f.global_env[_n] = _val

    def _h_mk_fn(_f, _a):
        _fn_code_obj = _f.stack.pop()
        if isinstance(_fn_code_obj, tuple) and len(_fn_code_obj) == 3 and _fn_code_obj[0] == {repr(tok['lazy'])}:
            _fn_code_obj = {v['lazy_decode_fn']}(_fn_code_obj, _f.code_obj._k_enc)
        _dmap = None
        if bool(_a & 8):
            # (names_tuple, values_tuple) was pushed beneath the code const.
            # Kept per-closure: sharing a map on the shared code object would
            # give every instance the LAST evaluated defaults.
            _pair = _f.stack.pop()
            _names, _vals = _pair
            _dmap = dict(zip(_names, _vals))
        _is_async = bool(_a & 1)
        _is_gen = bool(_a & 2)
        _captured_env = dict(_f.locals)
        if _f.captured_env:
            _merged = dict(_f.captured_env)
            _merged.update(_captured_env)
            _captured_env = _merged
        if _is_gen and _is_async:
            def _make_agen(_fco, _cenv, _dfl):
                def _agfactory(*_args, **_kwargs):
                    _d_cls = getattr(_agfactory, '_vm_def_cls', getattr(_fco, 'defining_class', None))
                    return {v['agen_cls']}(_fco, _args, _kwargs, _cenv, _d_cls, _dfl)
                _agfactory._fco = _fco
                _agfactory.__name__ = _fco.name
                return _agfactory
            _f.stack.append(_make_agen(_fn_code_obj, _captured_env, _dmap))
        elif _is_gen:
            def _make_gen(_fco, _cenv, _dfl):
                def _gfactory(*_args, **_kwargs):
                    _d_cls = getattr(_gfactory, '_vm_def_cls', getattr(_fco, 'defining_class', None))
                    return {v['gen_cls']}(_fco, _args, _kwargs, _cenv, _d_cls, _dfl)
                _gfactory._fco = _fco
                _gfactory.__name__ = _fco.name
                return _gfactory
            _f.stack.append(_make_gen(_fn_code_obj, _captured_env, _dmap))
        elif _is_async:
            def _make_wrapped_async(_fco, _cenv, _dfl):
                async def _wrapped_async(*_args, **_kwargs):
                    _d_cls = getattr(_wrapped_async, '_vm_def_cls', getattr(_fco, 'defining_class', None))
                    return await {v['call_vm_async_fn']}(_fco, _args, _kwargs, _cenv, _def_cls=_d_cls, _defaults=_dfl)
                _wrapped_async._fco = _fco
                _wrapped_async.__name__ = _fco.name
                return _wrapped_async
            _f.stack.append(_make_wrapped_async(_fn_code_obj, _captured_env, _dmap))
        else:
            def _make_wrapped(_fco, _cenv, _dfl):
                def _wrapped(*_args, **_kwargs):
                    _d_cls = getattr(_wrapped, '_vm_def_cls', getattr(_fco, 'defining_class', None))
                    return {v['call_vm_fn']}(_fco, _args, _kwargs, _cenv, _def_cls=_d_cls, _defaults=_dfl)
                _wrapped._fco = _fco
                _wrapped.__name__ = _fco.name
                return _wrapped
            _f.stack.append(_make_wrapped(_fn_code_obj, _captured_env, _dmap))

    def _h_call_fn(_f, _a):
        _args = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _fn = _f.stack.pop()
        _f.stack.append(_fn(*_args))

    def _wrap_anext_coro(_coro):
        async def _runner():
            try:
                return (True, await _coro)
            except StopAsyncIteration:
                return (False, None)
        return _runner()

    def _h_call_fn_async(_f, _a):
        _args = [_f.stack.pop() for _ in range(_a)][::-1] if _a else []
        _fn = _f.stack.pop()
        # Identity-only await detection. The old name-table heuristic
        # legacy detection misfired on any global whose name index
        # collided with the await slot, hijacking plain calls like worker([7,8]).
        in_async = {v['async_depth']}[0] > 0
        {_DBG_CALLA}
        if _fn is _g_env.get({repr(tok['await_fn'])}):
            import inspect
            if _args and (inspect.iscoroutine(_args[0]) or inspect.isawaitable(_args[0])):
                if in_async:
                    # Native hand-off onto the running loop (no nested pools).
                    return ({v['await_sig']}, _args[0])
                _f.stack.append({v['vm_await_fn']}(_args[0]))
            else:
                _f.stack.append(_args[0] if _args else None)
        elif _fn is _g_env.get({repr(tok['anext_fn'])}):
            if in_async and _args:
                try:
                    _coro = _args[0].__anext__()
                except StopAsyncIteration:
                    _f.stack.append((False, None))
                    return
                return ({v['await_sig']}, _wrap_anext_coro(_coro))
            _f.stack.append({v['vm_anext_fn']}(*_args))
        elif hasattr(_fn, '__name__') and _fn.__name__ == '_vm_await':
            import inspect
            if _args and (inspect.iscoroutine(_args[0]) or inspect.isawaitable(_args[0])):
                return ({v['await_sig']}, _args[0])
            else:
                _f.stack.append(_args[0] if _args else None)
        else:
            _f.stack.append(_fn(*_args))

    def _h_call_kw(_f, _a):
        _n_args = _a & 0xFF
        _n_kw = (_a >> 8) & 0xFF
        _kw = {{}}
        for _ in range(_n_kw):
            _v = _f.stack.pop(); _k = _f.stack.pop(); _kw[_k] = _v
        _args = [_f.stack.pop() for _ in range(_n_args)][::-1] if _n_args else []
        _fn = _f.stack.pop()
        _f.stack.append(_fn(*_args, **_kw))

    def _h_call_ex(_f, _a):
        _kw = _f.stack.pop() if (_a & 1) else {{}}
        _star_args = list(_f.stack.pop())
        _fn = _f.stack.pop()
        _f.stack.append(_fn(*_star_args, **_kw))

    def _h_b_cls(_f, _a):
        _cls_code = _f.stack.pop()
        if isinstance(_cls_code, tuple) and _sys_len(_cls_code) == 3 and _cls_code[0] == {repr(tok['lazy'])}:
            _cls_code = {v['lazy_decode_fn']}(_cls_code, _f.code_obj._k_enc)
        _meta_param = _f.stack.pop()
        _bases = _f.stack.pop()
        _cname = _f.stack.pop()
        _cls_loc = {{}}
        _cls_frame = {v['attach_isa_fn']}({v['frame_cls']}(_cls_code, _cls_loc, _g_env))
        {v['eval_frame_fn']}(_cls_frame)
        _meta = _meta_param
        if _meta is None and hasattr(_bases, '__iter__'):
            for _b in _bases:
                if isinstance(_b, type) and _b is not object and issubclass(_b, type):
                    _meta = _b
                    break
        if _meta is None:
            _meta = type
        _new_class = _meta(_cname, tuple(_bases), _cls_loc)
        for _c in getattr(_cls_code, 'constants', []):
            if hasattr(_c, 'defining_class'):
                _c.defining_class = _new_class
        for _k, _v in _cls_loc.items():
            if callable(_v):
                try:
                    setattr(_v, '__class__', _new_class)
                    setattr(_v, '_vm_def_cls', _new_class)
                    if hasattr(_v, '_fco'):
                        setattr(_v._fco, 'defining_class', _new_class)
                except Exception:
                    pass
        _f.stack.append(_new_class)

    def _h_imp_n(_f, _a):
        _n = _f.code_obj.names[_a]
        if _n.startswith({repr(tok['fl_prefix'])}):
            # fromlist sentinel emitted by visit_ImportFrom:
            # sentinel-prefix lookup -> return SUBMODULE.
            _rest = _n[len({repr(tok['fl_prefix'])}):]
            _mod, _, _csv = _rest.partition(chr(0))
            _f.stack.append(__import__(_mod, fromlist=tuple(_csv.split(','))))
        else:
            _f.stack.append(__import__(_n))

    def _h_imp_f(_f, _a):
        _m = _f.stack[-1]
        _f.stack.append(getattr(_m, _f.code_obj.names[_a]))

    def _h_g_iter(_f, _a):
        _f.stack.append(iter(_f.stack.pop()))

    def _h_for_it(_f, _a):
        _it = _f.stack.pop()
        try:
            _next_val = next(_it)
            _f.stack.append(_next_val)
        except StopIteration:
            _f.pc = _a * 3

    def _h_st_fin(_f, _a):
        _f.exc_handlers.append(_a * 3)

    def _h_pop_blk(_f, _a):
        if _f.exc_handlers: _f.exc_handlers.pop()

    def _h_raise(_f, _a):
        if _a >= 2:
            # raise EXC from CAUSE  (arg bit 2 = cause present)
            _cause = _f.stack.pop() if _f.stack else None
            _exc = _f.stack.pop() if _f.stack else None
            if _exc is None:
                _exc = _f.current_exception or RuntimeError("Exception raised")
            if _cause is not None:
                try:
                    _exc.__cause__ = _cause
                    _exc.__suppress_context__ = True
                except Exception:
                    pass
            raise _exc
        _exc = _f.stack.pop() if _f.stack else None
        if _exc is None:
            _exc = _f.current_exception or RuntimeError("Exception raised")
        raise _exc

    def _h_nop(_f, _a):
        pass

    def _h_yield(_f, _a):
        _v = _f.stack.pop()
        return ({v['yield_sig']}, _v)

    def _h_yield_from(_f, _a):
        if _f.dele is None:
            # First entry: stack top is the sub-iterable/generator
            _sub = _f.stack.pop()
            _f.last_sent = None
            if hasattr(_sub, 'send'):
                _f.dele = _sub
            else:
                _f.dele = iter(_sub)
        else:
            # Resumed: wrapper pushed the value sent() into this generator;
            # forward it into the delegated generator.
            _f.last_sent = _f.stack.pop()
        try:
            if hasattr(_f.dele, 'send'):
                _item = _f.dele.send(_f.last_sent)
            else:
                _item = next(_f.dele)
            # Rewind PC so the resume re-enters THIS instruction (it drives the
            # whole delegation loop across suspensions).
            _f.pc -= 3
            return ({v['yield_sig']}, _item)
        except StopIteration as _e:
            _f.dele = None
            _f.stack.append(getattr(_e, 'value', None))
        except BaseException:
            if _f.dele is not None and hasattr(_f.dele, 'close'):
                try:
                    _f.dele.close()
                except Exception:
                    pass
            _d = _f.dele
            _f.dele = None
            raise

    def _h_halt(_f, _a):
        return {v['halt_sig']}

    {v['dispatch_tbl']} = [{v['trap_fn']}] * 256
    {v['dispatch_tbl_async']} = [{v['trap_fn']}] * 256
    {reg_stmts}
    {v['dispatch_tbl_async']}[{slot_call_fn}] = _h_call_fn_async

    # Level >= 4: per-function affine ISA keys derived from master seed + code
    # object name. Levels < 4 share the single build-wide (M, A) pair.

    def {v['bind_frame_fn']}(_fn_code, _passed_args, _passed_kwargs=None, _captured_env=None, _def_cls=None, _defaults=None):
        _loc = {{_aname: {v['no_arg_sig']} for _aname in _fn_code.local_names}}
        _rem_kwargs = dict(_passed_kwargs or {{}})
        _pos_count = _sys_len(_fn_code.arg_names)
        for _idx, _aname in enumerate(_fn_code.arg_names):
            if _idx < _sys_len(_passed_args):
                _loc[_aname] = _passed_args[_idx]
            elif _aname in _rem_kwargs:
                _loc[_aname] = _rem_kwargs.pop(_aname)
        if _fn_code.vararg_name:
            _loc[_fn_code.vararg_name] = tuple(_passed_args[_pos_count:])
        elif _sys_len(_passed_args) > _pos_count and not _fn_code.name.startswith('<'):
            # FIX (GAP-26): CPython raises on surplus positionals without *args;
            # the old binder silently discarded them. Synthetic comps exempt.
            raise TypeError(f"{{_fn_code.name}}() takes {{_pos_count}} positional arguments but {{_sys_len(_passed_args)}} were given")
        for _kname in getattr(_fn_code, 'kwonly_names', []):
            if _kname in _rem_kwargs:
                _loc[_kname] = _rem_kwargs.pop(_kname)
        if _fn_code.kwarg_name:
            _loc[_fn_code.kwarg_name] = _rem_kwargs
        elif _rem_kwargs and not _fn_code.name.startswith('<'):
            # FIX (GAP-26b): keyword-typo masking - reject unknown kwargs.
            # Synthetic functions (comprehensions <listcomp> etc.) are exempt:
            # their compiler emits synthetic params bound by the comp loop.
            raise TypeError(f"{{_fn_code.name}}() got an unexpected keyword argument '{{next(iter(_rem_kwargs))}}'")
        _f = {v['frame_cls']}(_fn_code, _loc, _g_env)
        _f.captured_env = _captured_env or {{}}
        _f.defining_class = _def_cls
        if _defaults:
            for _dn, _dv in _defaults.items():
                if _loc.get(_dn) is {v['no_arg_sig']}:
                    _loc[_dn] = _dv
        for _an in list(_fn_code.arg_names) + list(getattr(_fn_code, 'kwonly_names', [])):
            if _loc.get(_an) is {v['no_arg_sig']} and not _fn_code.name.startswith('<') and _an not in getattr(_fn_code, 'kwonly_default_names', ()):
                # FIX (GAP-27): native-shaped missing-argument error instead of
                # leaking the internal sentinel into user code. Runs AFTER
                # default application; ONLY real parameters checked. Kwonly
                # params WITH defaults are exempt: their default is applied by
                # the function-body preamble at call time (late-bound channel).
                raise TypeError(f"{{_fn_code.name}}() missing required argument '{{_an}}'")
        {v['attach_isa_fn']}(_f)
        return _f

    def {v['call_vm_fn']}(_fn_code, _passed_args, _passed_kwargs=None, _captured_env=None, _def_cls=None, _defaults=None):
        _f = {v['bind_frame_fn']}(_fn_code, _passed_args, _passed_kwargs, _captured_env, _def_cls, _defaults)
        {v['active_frames']}.append(_f)
        try:
            return {v['eval_frame_fn']}(_f)
        finally:
            if {v['active_frames']}: {v['active_frames']}.pop()

    _orig_super = __builtins__.super if hasattr(__builtins__, 'super') else __builtins__['super']

    class {v['gen_cls']}:
        def __init__(self, _fco, _args, _kwargs, _cenv, _dcls, _dfl=None):
            self._fco = _fco
            self._args = _args
            self._kwargs = _kwargs
            self._cenv = _cenv
            self._dcls = _dcls
            self._dfl = _dfl
            self._fr = None
            self._done = False
        def __iter__(self):
            return self
        def __next__(self):
            return self.send(None)
        def _start(self):
            self._fr = {v['bind_frame_fn']}(self._fco, self._args, self._kwargs, self._cenv, self._dcls, self._dfl)
            self._fr.is_generator = True
            {v['active_frames']}.append(self._fr)
        def send(self, _v):
            if self._done:
                raise StopIteration
            if self._fr is None:
                if _v is not None:
                    raise TypeError("can't send non-None value to a just-started generator")
                self._start()
            else:
                self._fr.stack.append(_v)
            try:
                _r = {v['eval_frame_fn']}(self._fr)
            except BaseException:
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise
            if isinstance(_r, tuple) and _sys_len(_r) == 2 and _r[0] is {v['yield_sig']}:
                return _r[1]
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
            raise StopIteration(_r)
        def throw(self, _e, _val=None):
            if self._done or self._fr is None:
                if self._done:
                    raise _e
                self._start()
            self._fr.injected_exc = _e
            try:
                return self.send(None)
            except StopIteration:
                raise StopIteration from None
        def close(self):
            if self._done:
                return
            if self._fr is None:
                self._done = True
                return
            self._fr.injected_exc = GeneratorExit()
            try:
                _r = {v['eval_frame_fn']}(self._fr)
            except (GeneratorExit, StopIteration):
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                return
            except BaseException:
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
            if isinstance(_r, tuple) and _sys_len(_r) == 2 and _r[0] is {v['yield_sig']}:
                raise RuntimeError("generator ignored GeneratorExit")

    class {v['agen_cls']}:
        def __init__(self, _fco, _args, _kwargs, _cenv, _dcls, _dfl=None):
            self._fco = _fco
            self._args = _args
            self._kwargs = _kwargs
            self._cenv = _cenv
            self._dcls = _dcls
            self._dfl = _dfl
            self._fr = None
            self._done = False
        def __aiter__(self):
            return self
        def _start(self):
            self._fr = {v['bind_frame_fn']}(self._fco, self._args, self._kwargs, self._cenv, self._dcls, self._dfl)
            self._fr.is_generator = True
            {v['active_frames']}.append(self._fr)
        async def __anext__(self):
            if self._done:
                raise StopAsyncIteration
            if self._fr is None:
                self._start()
            try:
                _r = await {v['eval_frame_async_fn']}(self._fr)
            except (StopAsyncIteration, StopIteration):
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise StopAsyncIteration
            except BaseException:
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise
            if isinstance(_r, tuple) and _sys_len(_r) == 2 and _r[0] is {v['yield_sig']}:
                return _r[1]
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
            raise StopAsyncIteration
        async def asend(self, _v):
            if self._done:
                raise StopAsyncIteration
            if self._fr is None:
                self._start()
            else:
                self._fr.stack.append(_v)
            try:
                _r = await {v['eval_frame_async_fn']}(self._fr)
            except BaseException:
                self._done = True
                if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
                raise
            if isinstance(_r, tuple) and _sys_len(_r) == 2 and _r[0] is {v['yield_sig']}:
                return _r[1]
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)
            raise StopAsyncIteration
        async def aclose(self):
            if self._done or self._fr is None:
                self._done = True
                return
            self._fr.injected_exc = GeneratorExit()
            try:
                await {v['eval_frame_async_fn']}(self._fr)
            except BaseException:
                pass
            self._done = True
            if self._fr in {v['active_frames']}: {v['active_frames']}.remove(self._fr)

    def __vm_ayieldfrom___helper(_sub):
        async def _agen_delegate():
            if hasattr(_sub, '__aiter__'):
                async for _x in _sub:
                    yield _x
            else:
                for _x in iter(_sub):
                    yield _x
        return _agen_delegate()

    _g_env['__vm_ayieldfrom__'] = __vm_ayieldfrom___helper

    def {v['vm_super_fn']}(*_sargs):
        if _sys_len(_sargs) == 0 and {v['active_frames']}:
            _cur = {v['active_frames']}[-1]
            _self_obj = None
            for _k in _cur.code_obj.arg_names:
                _val = _cur.locals.get(_k)
                if _val is not None and _val is not {v['no_arg_sig']}:
                    _self_obj = _val
                    break
            if _self_obj is not None:
                _def_cls = getattr(_cur, 'defining_class', None)
                if _def_cls is None and hasattr(_cur.code_obj, 'defining_class'):
                    _def_cls = _cur.code_obj.defining_class
                if _def_cls is not None:
                    return _orig_super(_def_cls, _self_obj)
                if isinstance(_self_obj, type):
                    return _orig_super(_self_obj, _self_obj)
                return _orig_super(type(_self_obj), _self_obj)
        return _orig_super(*_sargs)

    _g_env['super'] = {v['vm_super_fn']}

    def {v['vm_await_fn']}(_val):
        import inspect, asyncio
        if inspect.iscoroutine(_val) or inspect.isawaitable(_val):
            try:
                _loop = asyncio.get_event_loop()
                if _loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pool:
                        return _pool.submit(asyncio.run, _val).result()
                return _loop.run_until_complete(_val)
            except Exception:
                return asyncio.run(_val)
        return _val

    _g_env[{repr(tok['await_fn'])}] = {v['vm_await_fn']}

    def {v['vm_anext_fn']}(_aiter):
        import inspect, asyncio
        try:
            _coro = _aiter.__anext__()
        except StopAsyncIteration:
            return (False, None)
        if inspect.iscoroutine(_coro) or inspect.isawaitable(_coro):
            try:
                _loop = asyncio.get_event_loop()
                if _loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pool:
                        return (True, _pool.submit(asyncio.run, _coro).result())
                return (True, _loop.run_until_complete(_coro))
            except StopAsyncIteration:
                return (False, None)
        return (True, _coro)

    _g_env[{repr(tok['anext_fn'])}] = {v['vm_anext_fn']}
    _g_env[{repr(tok['match_rest'])}] = (lambda _subj, _excl: {{k: v for k, v in _subj.items() if k not in _excl}})
    # Match-case protocol helpers (TVM 4.0 GAP-33/35):
    def __tvm_is_seq__(_o):
        if isinstance(_o, (str, bytes, bytearray)):
            return False
        # Exclude mappings (dict has __len__/__getitem__ but is NOT a sequence
        # under PEP 634) - mirrors collections.abc.Sequence semantics closely.
        if hasattr(_o, 'keys'):
            return False
        return hasattr(_o, '__len__') and hasattr(_o, '__getitem__')
    def __tvm_is_map__(_o):
        return hasattr(_o, 'keys') and hasattr(_o, '__getitem__')
    def __tvm_margs__(_subj, _cls, _idx):
        try:
            _ma = getattr(_cls, '__match_args__', None)
        except Exception:
            return {v['no_arg_sig']}
        if _ma is None or _idx >= _sys_len(tuple(_ma)):
            return {v['no_arg_sig']}
        return getattr(_subj, tuple(_ma)[_idx], {v['no_arg_sig']})
    _g_env['__tvm_is_seq'] = __tvm_is_seq__
    _g_env['__tvm_is_map'] = __tvm_is_map__
    _g_env['__tvm_margs'] = __tvm_margs__

    def __tvm_snap__(_names):
        # Captures may be frame LOCALS (function scope) or module globals;
        # resolve against the innermost active frame first.
        _sent = _g_env.get({repr(tok['no_arg'])})
        _src = {v['active_frames']}[-1].locals if {v['active_frames']} else _g_env
        return {{_n: _src.get(_n, _sent) for _n in _names}}
    def __tvm_restore__(_names, _snap):
        _tgt = {v['active_frames']}[-1].locals if {v['active_frames']} else _g_env
        for _n in _names:
            _v = _snap.get(_n)
            if _v is _g_env.get({repr(tok['no_arg'])}):
                _tgt.pop(_n, None)
            else:
                _tgt[_n] = _v
    _g_env['__tvm_snap'] = __tvm_snap__
    _g_env['__tvm_restore'] = __tvm_restore__

    def {tok['bind_defaults']}(_co, _pair):
        return _co

    _g_env[{repr(tok['bind_defaults'])}] = {tok['bind_defaults']}

    # Level-4 per-function ISA divergence infrastructure lives below; the
    # enable flag is interpolated from the emitter scope.
    _isa_fwd_cache = {{}}
    def {v['attach_isa_fn']}(_fr):
        if {int(vm_level >= 4)} and {int(_TVM_L4_PERM_ENABLED)}:
            _n = _fr.code_obj.name
            _p = _isa_fwd_cache.get(_n)
            if _p is None:
                _p = {v['perm_rt_fn']}(_n, _master_seed)
                _isa_fwd_cache[_n] = _p
            _fr._perm = _p
        else:
            _fr._perm = None
        return _fr

    async def {v['eval_frame_async_fn']}(_frame):
        _c_arr = _frame.code_obj.code
        _c_len = _sys_len(_c_arr)
        {v['async_depth']}[0] += 1
        {_DBG_AE}
        try:
            while _frame.pc < _c_len:
                try:
                    if _frame.injected_exc is not None:
                        _inj = _frame.injected_exc
                        _frame.injected_exc = None
                        raise _inj
                    _op = _c_arr[_frame.pc]
                    _arg = (_c_arr[_frame.pc+1] << 8) | _c_arr[_frame.pc+2]
                    _frame.pc += 3

                    _h = {v['dispatch_tbl_async']}[(((_frame._perm[_op]) if _frame._perm is not None else _op) * {M} + {A}) & 0xFF]
                    _sig = _h(_frame, _arg)
                    if _sig is not None:
                        if _sig is {v['halt_sig']}:
                            break
                        if isinstance(_sig, tuple) and _sys_len(_sig) == 2:
                            if _sig[0] is {v['ret_sig']}:
                                return _sig[1]
                            elif _sig[0] is {v['await_sig']}:
                                _res = await _sig[1]
                                _frame.stack.append(_res)
                            elif _sig[0] is {v['yield_sig']}:
                                return _sig
                except BaseException as _e:
                    _frame.current_exception = _e
                    if _frame.exc_handlers:
                        _handler_pc = _frame.exc_handlers.pop()
                        _frame.pc = _handler_pc
                        _frame.stack.append(_e)
                    else:
                        raise _e
            return _frame.stack.pop() if _frame.stack else None
        finally:
            {v['async_depth']}[0] -= 1
            if {int(vm_level >= 3)} and not _frame.is_generator:
                _frame.stack.clear()
                _frame.exc_handlers.clear()
                _frame.current_exception = None

    async def {v['call_vm_async_fn']}(_fn_code, _passed_args, _passed_kwargs=None, _captured_env=None, _def_cls=None, _defaults=None):
        _f = {v['bind_frame_fn']}(_fn_code, _passed_args, _passed_kwargs, _captured_env, _def_cls, _defaults)
        {v['active_frames']}.append(_f)
        try:
            return await {v['eval_frame_async_fn']}(_f)
        finally:
            if {v['active_frames']}: {v['active_frames']}.pop()

    def {v['eval_frame_fn']}(_frame):
        _c_arr = _frame.code_obj.code
        _c_len = _sys_len(_c_arr)
        try:
            while _frame.pc < _c_len:
                try:
                    if _frame.injected_exc is not None:
                        _inj = _frame.injected_exc
                        _frame.injected_exc = None
                        raise _inj
                    _op = _c_arr[_frame.pc]
                    _arg = (_c_arr[_frame.pc+1] << 8) | _c_arr[_frame.pc+2]
                    _frame.pc += 3

                    _h = {v['dispatch_tbl']}[(((_frame._perm[_op]) if _frame._perm is not None else _op) * {M} + {A}) & 0xFF]
                    _sig = _h(_frame, _arg)
                    if _sig is not None:
                        if _sig is {v['halt_sig']}:
                            break
                        if isinstance(_sig, tuple) and _sys_len(_sig) == 2 and _sig[0] is {v['ret_sig']}:
                            return _sig[1]
                        if isinstance(_sig, tuple) and _sys_len(_sig) == 2 and _sig[0] is {v['yield_sig']}:
                            return _sig
                except BaseException as _e:
                    _frame.current_exception = _e
                    if _frame.exc_handlers:
                        _handler_pc = _frame.exc_handlers.pop()
                        _frame.pc = _handler_pc
                        _frame.stack.append(_e)
                    else:
                        raise _e
            return _frame.stack.pop() if _frame.stack else None
        finally:
            if {int(vm_level >= 3)} and not _frame.is_generator:
                _frame.stack.clear()
                _frame.exc_handlers.clear()
                _frame.current_exception = None

    _initial_frame = {v['attach_isa_fn']}({v['frame_cls']}(_root_code, {{}}, _g_env))
    {v['eval_frame_fn']}(_initial_frame)

{v['interp_fn']}({repr(serialized_root_packet)}, {repr(master_seed)}, {repr(runtime_salt)})
"""
    return src.strip()


def _vm_obfuscate(code_str: str, seed=None, vm_level: int = 1) -> str:
    """
    Tr0ngX True Virtual Machine (TVM 2.0) Obfuscation Engine.
    100% Zero-exec full virtualization. Directly compiles Python AST into Custom ISA Bytecode
    and executes via a Polymorphic Frame-Based Virtual Machine Interpreter with dynamic AEAD stream encryption.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return code_str

    build_seed = seed if seed is not None else secrets.randbits(64)
    rng = random.Random(build_seed)

    # 1. Generate per-build Polymorphic ISA Mapping (0..255)
    all_opcodes = list(range(1, 255))
    rng.shuffle(all_opcodes)
    isa_map = {}
    standard_opcodes = [
        _TVMOpcodes.LOAD_CONST, _TVMOpcodes.LOAD_GLOBAL, _TVMOpcodes.STORE_GLOBAL,
        _TVMOpcodes.LOAD_FAST, _TVMOpcodes.STORE_FAST, _TVMOpcodes.DUP_TOP, _TVMOpcodes.POP_TOP,
        _TVMOpcodes.ROT_TWO, _TVMOpcodes.ROT_THREE,
        _TVMOpcodes.BINARY_ADD, _TVMOpcodes.BINARY_SUB, _TVMOpcodes.BINARY_MUL,
        _TVMOpcodes.BINARY_DIV, _TVMOpcodes.BINARY_FLOORDIV, _TVMOpcodes.BINARY_MOD,
        _TVMOpcodes.BINARY_POW, _TVMOpcodes.BINARY_AND, _TVMOpcodes.BINARY_OR,
        _TVMOpcodes.BINARY_XOR, _TVMOpcodes.BINARY_LSHIFT, _TVMOpcodes.BINARY_RSHIFT,
        _TVMOpcodes.UNARY_NEG, _TVMOpcodes.UNARY_NOT, _TVMOpcodes.UNARY_INVERT,
        _TVMOpcodes.BINARY_MATMUL,
        _TVMOpcodes.COMPARE_OP, _TVMOpcodes.JUMP, _TVMOpcodes.JUMP_IF_TRUE,
        _TVMOpcodes.JUMP_IF_FALSE, _TVMOpcodes.JUMP_IF_FALSE_OR_POP, _TVMOpcodes.JUMP_IF_TRUE_OR_POP,
        _TVMOpcodes.RETURN_VALUE, _TVMOpcodes.GET_ATTR, _TVMOpcodes.SET_ATTR,
        _TVMOpcodes.GET_ITEM, _TVMOpcodes.SET_ITEM, _TVMOpcodes.DEL_ITEM,
        _TVMOpcodes.DEL_ATTR, _TVMOpcodes.DEL_FAST, _TVMOpcodes.DEL_GLOBAL,
        _TVMOpcodes.BUILD_LIST, _TVMOpcodes.BUILD_TUPLE, _TVMOpcodes.BUILD_SET, _TVMOpcodes.BUILD_DICT,
        _TVMOpcodes.UNPACK_SEQUENCE, _TVMOpcodes.BUILD_SLICE, _TVMOpcodes.UNPACK_EX,
        _TVMOpcodes.MAKE_FUNCTION, _TVMOpcodes.CALL_FUNCTION, _TVMOpcodes.CALL_FUNCTION_KW,
        _TVMOpcodes.BUILD_CLASS, _TVMOpcodes.IMPORT_NAME, _TVMOpcodes.IMPORT_FROM,
        _TVMOpcodes.CALL_FUNCTION_EX, _TVMOpcodes.LOAD_DEREF, _TVMOpcodes.STORE_DEREF,
        _TVMOpcodes.GET_ITER, _TVMOpcodes.FOR_ITER, _TVMOpcodes.SETUP_FINALLY,
        _TVMOpcodes.POP_BLOCK, _TVMOpcodes.RAISE_VARARGS, _TVMOpcodes.CHECK_EXC_MATCH,
        _TVMOpcodes.HALT, _TVMOpcodes.NOP, _TVMOpcodes.TRAP,
        _TVMOpcodes.YIELD_VALUE, _TVMOpcodes.YIELD_FROM
    ]
    for idx, std_op in enumerate(standard_opcodes):
        isa_map[std_op] = all_opcodes[idx]

    # 2. Lower AST into Custom TVM Instructions with VM-level hardening
    _TVM_TOKENS.clear()
    _TVM_TOKENS.update({
        'lazy': '__' + rd()[:14],
        'no_arg': '_' + rd()[:12],
        'await_fn': '__' + rd()[:14],
        'anext_fn': '__' + rd()[:14],
        'match_rest': '__' + rd()[:14],
        'bind_defaults': '__' + rd()[:14],
        'fl_prefix': '__' + rd()[:14],
    })
    compiler = _TVMASTCompiler(name='<module>', is_function=False, vm_level=vm_level, rng=rng)
    compiler._scan_scope(tree.body)
    for stmt in tree.body:
        compiler.visit(stmt)
    root_code = compiler.finalize()

    # 3. Emit Polymorphic Runtime Interpreter 2.0 with AEAD & Dynamic Dispatch
    runtime = _vm_emit_runtime_interpreter_v2(root_code, isa_map, vm_level, rng,
                                              vm_debug=False)
    return runtime



# ΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉ
# KRAMER ENGINE - KYRIE ELEISON & OBFUSCATED CLASS WRAPPER
# ΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉ

_kramer_alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
Kyrie_ROT_FWD = str.maketrans(_kramer_alphabet, _kramer_alphabet[1:] + _kramer_alphabet[:1])

class Kyrie:
    _ZETA = "\u03b6"
    _ESC = "\uE000"
    _ROT_FWD = Kyrie_ROT_FWD

    @staticmethod
    def _ekyrie(text: str):
        return text.translate(Kyrie._ROT_FWD)

    @staticmethod
    def _encrypt(text: str, key: int = 0):
        t = [chr(ord(t) + key) if t != "\n" else Kyrie._ZETA for t in text]
        return "".join(t)

    @staticmethod
    def encrypt(content: str, key: int):
        e1 = Kyrie._ekyrie(content.replace(Kyrie._ZETA, Kyrie._ESC))
        return Kyrie._encrypt(e1, key=key)

    @staticmethod
    def _xor_stream_encrypt(text: str, key: int):
        """XOR stream cipher with key-derived keystream (replaces simple Caesar)."""
        keystream_seed = key
        result = []
        for i, ch in enumerate(text):
            # LCG keystream generator
            keystream_seed = (keystream_seed * 1664525 + 1013904223) & 0xFFFFFFFF
            xor_byte = keystream_seed & 0xFF
            if ch == "\n":
                result.append(Kyrie._ZETA)
            else:
                result.append(chr(ord(ch) ^ xor_byte))
        return "".join(result)

    @staticmethod
    def encrypt_v2(content: str, key: int):
        """Enhanced encryption: alphabet rotation + XOR stream cipher."""
        e1 = Kyrie._ekyrie(content.replace(Kyrie._ZETA, Kyrie._ESC))
        return Kyrie._xor_stream_encrypt(e1, key=key)

    @staticmethod
    def encrypt_v3(content: str, key: int) -> str:
        """Byte-level XOR with HMAC-SHA256 keystream (cryptographically strong).
        Returns hex-encoded string safe for embedding in source code."""
        import hashlib, hmac
        data = content.encode('utf-8')
        key_bytes = key.to_bytes(4, 'big')
        
        # Generate keystream using HMAC-SHA256 in counter mode
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(data):
            block = hmac.new(key_bytes, counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        
        # XOR encrypt
        encrypted = bytes(a ^ b for a, b in zip(data, keystream[:len(data)]))
        return encrypted.hex()

    @staticmethod
    def decrypt_v3(hex_str: str, key: int) -> str:
        """Decrypt hex-encoded XOR-encrypted content."""
        import hashlib, hmac
        data = bytes.fromhex(hex_str)
        key_bytes = key.to_bytes(4, 'big')
        
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(data):
            block = hmac.new(key_bytes, counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        
        decrypted = bytes(a ^ b for a, b in zip(data, keystream[:len(data)]))
        return decrypted.decode('utf-8')

# ═══════════════════════════════════════════════════════════════
# EMOJI OBFUSCATION - ENCODE ENTIRE CODE AS EMOJI SEQUENCE
# ═══════════════════════════════════════════════════════════════

def _emoji_encode(code_str):
    """Encode Python code as a sequence of emoji characters with a compact loader.
    Each byte of compressed code maps to an emoji from U+1F400-U+1F4FF range.
    The result looks like a wall of 🐀🐁🐂🐃... animal/object emoji."""
    compressed = zlib.compress(code_str.encode('utf-8'), 9)
    # Use U+1F400 as base — Animals & Nature + Objects block (256 chars)
    _EMOJI_BASE = 0x1F400
    emoji_data = ''.join(chr(_EMOJI_BASE + b) for b in compressed)
    # Build compact loader with literal UTF-8 emoji stream
    loader = (
        f"# -*- coding: utf-8 -*-\n"
        f"import zlib as _z\n"
        f"exec(_z.decompress(bytes(ord(_c)-{_EMOJI_BASE} for _c in \"\"\"{emoji_data}\"\"\")).decode('utf-8'))\n"
    )
    return loader


def _emoji_encode_v2(code_str):
    """Advanced emoji encoding: marshal+compress+emoji with obfuscated loader."""
    try:
        compiled = marshal.dumps(compile(code_str, '<emoji>', 'exec'))
    except SyntaxError:
        compiled = code_str.encode('utf-8')
    compressed = zlib.compress(compiled, 9)
    _EMOJI_BASE = 0x1F400
    emoji_data = ''.join(chr(_EMOJI_BASE + b) for b in compressed)
    v1 = rd() if not _EngineState.use_cjk_names and not _EngineState.use_homoglyph_names and not _EngineState.use_rare_unicode_names else '_e'
    v2 = rd() if not _EngineState.use_cjk_names and not _EngineState.use_homoglyph_names and not _EngineState.use_rare_unicode_names else '_d'
    loader = (
        f"# -*- coding: utf-8 -*-\n"
        f"import zlib as _z, marshal as _m, sys as _s\n"
        f"{v1} = \"\"\"{emoji_data}\"\"\"\n"
        f"{v2} = _z.decompress(bytes(ord(_c)-{_EMOJI_BASE} for _c in {v1}))\n"
        f"try:\n"
        f" _code = _m.loads({v2})\n"
        f"except ValueError:\n"
        f" raise SystemExit('[-] Marshal/bytecode version mismatch: payload built for Python ' + {_PYVER_TAG!r} + ', running on ' + '.'.join(map(str, _s.version_info[:2])))\n"
        f"exec(_code)\n"
        f"del {v1}, {v2}\n"
    )
    return loader


# ═══════════════════════════════════════════════════════════════
# WHITESPACE OBFUSCATION - ENCODE CODE AS SPACES & TABS
# ═══════════════════════════════════════════════════════════════

def _whitespace_encode(code_str):
    """Encode Python code as invisible whitespace (space=0, tab=1) with loader.
    The resulting file appears nearly empty — only whitespace is visible."""
    compressed = zlib.compress(code_str.encode('utf-8'), 9)
    # Each byte → 8 whitespace chars (space=0, tab=1)
    ws_bits = []
    for b in compressed:
        for bit_pos in range(7, -1, -1):
            ws_bits.append('\t' if (b >> bit_pos) & 1 else ' ')
    ws_data = ''.join(ws_bits)
    # Build self-decoding loader with literal tabs and spaces
    loader = (
        f"# -*- coding: utf-8 -*-\n"
        f"import zlib as _z\n"
        f"_w = \"\"\"{ws_data}\"\"\"\n"
        f"exec(_z.decompress(bytes("
        f"int(''.join('1' if c == '\\t' else '0' for c in _w[i:i+8]), 2) "
        f"for i in range(0, len(_w), 8))).decode('utf-8'))\n"
    )
    return loader


def _whitespace_encode_v2(code_str):
    """Advanced whitespace encoding with marshal compilation."""
    try:
        compiled = marshal.dumps(compile(code_str, '<ws>', 'exec'))
    except SyntaxError:
        compiled = code_str.encode('utf-8')
    compressed = zlib.compress(compiled, 9)
    ws_bits = []
    for b in compressed:
        for bit_pos in range(7, -1, -1):
            ws_bits.append('\t' if (b >> bit_pos) & 1 else ' ')
    ws_data = ''.join(ws_bits)
    loader = (
        f"# -*- coding: utf-8 -*-\n"
        f"import zlib as _z, marshal as _m, sys as _s\n"
        f"_w = \"\"\"{ws_data}\"\"\"\n"
        f"try:\n"
        f" _code = _m.loads(_z.decompress(bytes(\n"
        f" int(''.join('1' if c == '\\t' else '0' for c in _w[i:i+8]), 2) \n"
        f" for i in range(0, len(_w), 8))))\n"
        f"except ValueError:\n"
        f" raise SystemExit('[-] Marshal/bytecode version mismatch: payload built for Python ' + {_PYVER_TAG!r} + ', running on ' + '.'.join(map(str, _s.version_info[:2])))\n"
        f"exec(_code)\n"
    )
    return loader
# ═══════════════════════════════════════════════════════════════
# HYPERION ULTIMATE ENGINE (AST + TOKEN + CAMOUFLAGE SUITE)
# Based on Hyperion by billythegoat356 & BlueRed
# Integrated & Harmonized for Tr0ngX Ultimate AST Obfuscator
# ═══════════════════════════════════════════════════════════════

import builtins as _builtins_mod
import tokenize as _tokenize_mod
import io as _io_mod

_HYPERION_BUILTGLOB = [k for k in dir(_builtins_mod) if not k.startswith('__') and k not in ('None', 'True', 'False')]

class HyperionEngine:
    """Hyperion Obfuscator Engine: Token-level remapper, Math/Str mutator,
       Decoy line injector, Chunk shell encapsulator & Scientific class camouflage.
    """
    def __init__(self, content: str, clean=True, obfcontent=True, renlibs=True, renvars=True,
                 addbuiltins=True, randlines=True, shell=True, camouflage=False, safemode=True):
        self.content = content.lstrip('\ufeff')
        self.clean = clean
        self.obfcontent = obfcontent
        self.renlibs = renlibs
        self.renvars = renvars
        self.addbuiltins = addbuiltins
        self.randlines = randlines
        self.shell = shell
        self.camouflage = camouflage
        self.safemode = safemode

        self.add_imports = []
        self.impcontent = []
        self.impcontent2 = []
        self.strings = {}
        self.ostrings = {}
        self.lambdas = []
        self.imports = {}

    def transform(self) -> str:
        code = self.content
        if self.addbuiltins:
            code = self._add_builtins(code)

        self._create_vars()

        if self.renlibs:
            code = self._rename_imports(code)

        if self.renvars:
            code = self._rename_vars(code)

        if self.obfcontent:
            code = self._obf_content(code)

        if self.clean:
            code = self._clean_code(code)

        if self.randlines:
            code = self._rand_lines(code)

        if self.shell:
            code = self._chunk_shell(code)

        code = self._organise(code)

        if self.clean:
            code = self._clean_code(code)

        if self.camouflage:
            code = _hyperion_camouflage(code)

        return code

    def _add_builtins(self, code: str) -> str:
        used_builtins = []
        for var in _HYPERION_BUILTGLOB:
            if f"{var}(" in code or f" {var} " in code or f",{var}" in code:
                used_builtins.append(var)
        if used_builtins:
            # Inject explicit imports for used builtins (chunked, no truncation)
            imp_lines = []
            for i in range(0, len(used_builtins), 40):
                chunk = used_builtins[i:i + 40]
                imp_lines.append("from builtins import " + ",".join(chunk))
            return "\n".join(imp_lines) + "\n" + code
        return code

    def _create_vars(self):
        self.globals_var = rd()
        self.locals_var = rd()
        self.vars_var = rd()
        self.__import__var = rd()
        self.unhexlify_var = rd()
        self.dir_var = rd()
        self.getattr_var = rd()
        self.exec_var = rd()
        self.eval_var = rd()
        self.compile_var = rd()
        self.join_var = rd()
        self.true_var = rd()
        self.false_var = rd()
        self.bool_var = rd()
        self.str_var = rd()
        self.float_var = rd()

        self.local_import = f"locals()['{self.globals_var}'] = globals"
        
        self.impcontent = [
            f"{self.globals_var}()['{self.locals_var}'] = locals",
            f"{self.locals_var}()['{self.__import__var}'] = __import__",
            f"{self.globals_var}()['{self.vars_var}'] = {self.__import__var}('builtins').vars",
        ]

    def _rename_imports(self, code: str) -> str:
        lines = code.splitlines()
        self.imports = {}
        imp_setup = []

        for lin in lines:
            stripped = lin.strip()
            if (stripped.startswith(('import ', 'from ')) and
                '"' not in stripped and "'" not in stripped and
                ';' not in stripped and '*' not in stripped and
                not stripped.startswith('from builtins ')):
                if stripped.startswith('import '):
                    parts = stripped.removeprefix('import ').split(',')
                    for p in parts:
                        mod = p.strip().split(' as ')[0].strip()
                        if mod and mod.isidentifier() and mod not in self.imports:
                            alias = rd()
                            self.imports[mod] = alias
                            imp_setup.append(f"{self.globals_var}()['{mod}'] = {self.globals_var}()['{alias}'] = __import__('{mod}')")
                elif stripped.startswith('from '):
                    parts = stripped.removeprefix('from ').split(' import ')
                    mod = parts[0].strip()
                    if mod and mod.isidentifier() and mod not in self.imports:
                        alias = rd()
                        self.imports[mod] = alias
                        imp_setup.append(f"{self.globals_var}()['{mod}'] = {self.globals_var}()['{alias}'] = __import__('{mod}')")

        random.shuffle(imp_setup)
        self.impcontent2 = imp_setup
        return code

    def _rename_vars(self, code: str) -> str:
        try:
            tokens = list(_tokenize_mod.tokenize(_io_mod.BytesIO(code.encode('utf-8')).readline))
        except Exception:
            return code

        renamed = {}
        ntokens = []
        skip_keywords = {
            'def', 'class', 'import', 'from', 'as', 'return', 'yield', 'await', 'async',
            'if', 'elif', 'else', 'while', 'for', 'in', 'try', 'except', 'finally',
            'with', 'match', 'case', 'global', 'nonlocal', 'lambda', 'assert', 'del',
            'pass', 'break', 'continue', 'raise', 'True', 'False', 'None', 'self', 'cls'
        }

        in_case = False
        case_depth = 0
        in_def_sig = False
        in_class_sig = False

        for idx, token in enumerate(tokens):
            t_type, t_str = token.type, token.string
            if t_type == _tokenize_mod.NAME and t_str == 'case':
                in_case = True
                case_depth = 0
            elif in_case:
                if t_str in ('(', '[', '{'):
                    case_depth += 1
                elif t_str in (')', ']', '}'):
                    case_depth = max(0, case_depth - 1)
                elif case_depth == 0 and (t_str == ':' or t_str == 'if'):
                    in_case = False

            prev_tok = tokens[idx - 1].string if idx > 0 else ""
            next_tok = tokens[idx + 1].string if idx + 1 < len(tokens) else ""

            if t_type == _tokenize_mod.NAME and t_str == 'def':
                in_def_sig = True
            elif in_def_sig and t_str == ':' and prev_tok == ')':
                in_def_sig = False
            elif t_type == _tokenize_mod.NAME and t_str == 'class':
                in_class_sig = True
            elif in_class_sig and t_str == ':':
                in_class_sig = False

            if t_type == _tokenize_mod.NAME:
                if (not in_case and
                    not in_def_sig and
                    not in_class_sig and
                    t_str not in skip_keywords and
                    not t_str.startswith('__') and
                    prev_tok != '.' and
                    t_str not in self.imports):
                    if prev_tok in ('def', 'class') or next_tok == '=':
                        if t_str in _FROZEN_NAME_MAP:
                            renamed[t_str] = _FROZEN_NAME_MAP[t_str]
                        elif t_str not in renamed:
                            renamed[t_str] = rd()
                        t_str = renamed[t_str]
                    elif t_str in renamed:
                        t_str = renamed[t_str]
                elif prev_tok in ('def', 'class'):
                    if t_str not in skip_keywords and not t_str.startswith('__'):
                        if t_str in _FROZEN_NAME_MAP:
                            renamed[t_str] = _FROZEN_NAME_MAP[t_str]
                        elif t_str not in renamed:
                            renamed[t_str] = rd()
                        t_str = renamed[t_str]

            ntokens.append(_tokenize_mod.TokenInfo(t_type, t_str, token.start, token.end, token.line))

        try:
            return _tokenize_mod.untokenize(ntokens).decode('utf-8')
        except Exception:
            return code

    def _obf_content(self, code: str) -> str:
        try:
            tokens = list(_tokenize_mod.tokenize(_io_mod.BytesIO(code.encode('utf-8')).readline))
        except Exception:
            return code

        ntokens = []
        in_case = False
        case_depth = 0

        for token in tokens:
            t_type, t_str = token.type, token.string
            if t_type == _tokenize_mod.NAME and t_str == 'case':
                in_case = True
                case_depth = 0
            elif in_case:
                if t_str in ('(', '[', '{'):
                    case_depth += 1
                elif t_str in (')', ']', '}'):
                    case_depth = max(0, case_depth - 1)
                elif case_depth == 0 and (t_str == ':' or t_str == 'if'):
                    in_case = False

            if not in_case:
                if t_type == _tokenize_mod.NAME:
                    if t_str == 'True':
                        var_k = rd()
                        self.strings[var_k] = f"bool(~0 ^ ~1)"
                        t_str = f"globals()['{var_k}']"
                    elif t_str == 'False':
                        var_k = rd()
                        self.strings[var_k] = f"not bool(1)"
                        t_str = f"globals()['{var_k}']"
                elif t_type == _tokenize_mod.NUMBER:
                    if t_str.isdigit() and len(t_str) <= 6:
                        val = int(t_str)
                        rnum = random.randint(1000, 99999)
                        diff = rnum - val
                        t_str = f"({rnum} - {diff})"
            ntokens.append(_tokenize_mod.TokenInfo(t_type, t_str, token.start, token.end, token.line))

        try:
            return _tokenize_mod.untokenize(ntokens).decode('utf-8')
        except Exception:
            return code

    def _clean_code(self, code: str) -> str:
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
        except Exception:
            return code
        string_line_spans = []
        for tok in tokens:
            if tok.type == tokenize.STRING:
                string_line_spans.append((tok.start[0], tok.end[0]))
        in_string_span = lambda ln: any(a <= ln <= b for a, b in string_line_spans)
        kept_lines = []
        for lineno, lin in enumerate(code.splitlines(), start=1):
            s = lin.strip()
            if in_string_span(lineno):
                kept_lines.append(lin)
                continue
            if s and not s.startswith('#'):
                kept_lines.append(lin)
        return '\n'.join(kept_lines)

    def _rand_lines(self, code: str) -> str:
        lines = code.splitlines()
        res = []
        for idx, line in enumerate(lines):
            res.append(line)
            stripped = line.strip()
            if (idx == len(lines) - 1 or
                not stripped or
                stripped.endswith((':', ',', '\\')) or
                stripped.startswith(('@', 'def ', 'class ', 'elif ', 'else:', 'except', 'finally:'))):
                continue
            next_l = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            if next_l.startswith(('elif ', 'else:', 'except', 'finally:')):
                continue
            indent = len(line) - len(line.lstrip())
            if indent == 0 and random.random() < 0.25:
                res.append(f"{' ' * indent}if False: {rd()} = lambda: globals()")
        return '\n'.join(res)

    def _chunk_shell(self, code: str) -> str:
        lines = code.splitlines()
        chunks = []
        curr = []
        for idx, line in enumerate(lines):
            curr.append(line)
            next_l = lines[idx + 1] if idx + 1 < len(lines) else ""
            next_indent = len(next_l) - len(next_l.lstrip())
            next_strip = next_l.strip()
            if (next_indent == 0 and
                not next_strip.startswith(('elif', 'else', 'except', 'finally')) and
                not line.strip().endswith((':', ',', '\\')) and
                not line.strip().startswith('@')):
                c_code = '\n'.join(curr).strip()
                if c_code:
                    chunks.append(c_code)
                curr = []
        if curr:
            c_code = '\n'.join(curr).strip()
            if c_code:
                chunks.append(c_code)
        if not chunks:
            return code
        shell_lines = []
        for ch in chunks:
            shell_lines.append(f"eval(compile({repr(ch)}, {repr(rd())}, 'exec'))")
        return '\n'.join(shell_lines)

    def _organise(self, code: str) -> str:
        parts = [self.local_import]
        parts.extend(self.impcontent)
        parts.extend(self.impcontent2)
        for k, v in self.strings.items():
            parts.append(f"{self.globals_var}()['{k}'] = {v}")
        parts.append(code)
        return '\n'.join(parts)

def _hyperion_camouflage(content: str) -> str:
    """Hyperion Camouflage Engine: Encapsulates final payload inside realistic Fake Scientific/Math class architecture."""
    compressed_bytes = zlib.compress(content.encode("utf-8"))
    b85_payload = base64.b85encode(compressed_bytes).decode("ascii")

    chunk_size = 65536
    chunks = [b85_payload[i:i+chunk_size] for i in range(0, len(b85_payload), chunk_size)]

    gen_names = [
        'MemoryAccess', 'StackOverflow', 'System',
        'Divide', 'Product', 'CallFunction',
        'Math', 'Calculate', 'Hypothesis',
        'Frame', 'DetectVar', 'Substract',
        'Theory', 'Statistics', 'Random',
        'Round', 'Absolute', 'Negative',
        'Algorithm', 'Run', 'Builtins',
        'Positive', 'Invert', 'Square',
        'Add', 'Multiply', 'Modulo',
        'Power', 'Floor', 'Ceil',
        'Cube', 'Walk', 'While'
    ]
    random.shuffle(gen_names)
    gen = gen_names[:25]
    while len(gen) < 25:
        gen.append(rd())

    cls_name = gen[0]
    exec_alias = gen[11]
    str_alias = gen[12]
    tuple_alias = gen[13]
    map_alias = gen[14]
    ord_alias = gen[15]
    glob_alias = gen[17]
    type_alias = gen[24]

    bvars = {f"c_{i:05d}": c for i, c in enumerate(chunks)}
    vars_assignments = "\n".join(
        f"        {cls_name}.{gen[19]}({gen[20]}={repr(k)}, {gen[22]}={repr(v)})"
        for k, v in bvars.items()
    )
    bvar_keys = list(bvars.keys())

    rand_addr = f"0x00000{random.randint(1000, 9999)}BE{random.randint(10000, 99999)}"

    camo_code = f"""# ═════════════════════════════════════════════════════════════════
# HYPERION SCIENTIFIC SIMULATION LAYER (Camouflage Architecture)
# ═════════════════════════════════════════════════════════════════
import sys, os, time, math, zlib, base64

from math import prod as {gen[5]}

__obfuscator__ = 'Tr0ngX x Hyperion Ultimate'
__authors__ = ('Tr0ngX', 'billythegoat356', 'BlueRed')
__github__ = 'https://github.com/Tr0ngX/Tr0ngX-Ultimate-AST-Obfuscator'
__license__ = 'EPL-2.0'
__code__ = 'None'

{exec_alias}, {str_alias}, {tuple_alias}, {map_alias}, {ord_alias}, {glob_alias}, {type_alias} = exec, str, tuple, map, ord, globals, type

class {cls_name}:
    def __init__(self, {gen[4]}=100):
        self.{gen[3]} = {gen[5]}(({gen[4]}, {random.randint(10, 99)}))
        self.{gen[1]}({gen[6]}={random.randint(1, 50)})

    def {gen[1]}(self, {gen[6]}=int):
        self.{gen[3]} += {random.randint(1, 100)} + int({gen[6]} if isinstance({gen[6]}, int) else 1)
        try:
            return self.{gen[3]} % 777
        except Exception:
            return 0

    def {gen[2]}(self, {gen[7]}={random.randint(1, 50)}):
        {gen[7]} = ({gen[7]} * 2) ^ {random.randint(1, 255)}
        return {gen[7]}

    @staticmethod
    def {gen[18]}({gen[20]}=''):
        return {glob_alias}()[{gen[20]}]

    @staticmethod
    def {gen[19]}({gen[20]}='', {gen[22]}='', {gen[23]}={glob_alias}):
        {gen[23]}()[{gen[20]}] = {gen[22]}

    def execute(self, code=str):
        return {exec_alias}(code)

    @property
    def {gen[8]}(self):
        return ('<__main__.{cls_name} object at {rand_addr}>', {cls_name})

def _hyperion_bootstrap_payload():
    try:
        {gen[10]} = {cls_name}({gen[4]}={random.randint(100, 999)})
__VARS_ASSIGNMENTS__
        _reconstructed_b85 = ''.join([{cls_name}.{gen[18]}({gen[20]}=_k) for _k in {bvar_keys!r}])
        _decompressed_src = zlib.decompress(base64.b85decode(_reconstructed_b85.encode('ascii'))).decode('utf-8')
        {exec_alias}(_decompressed_src, globals(), globals())
    except Exception as _camo_err:
        raise _camo_err

if __name__ == '__main__':
    _hyperion_bootstrap_payload()
else:
    _hyperion_bootstrap_payload()
"""
    camo_code = camo_code.replace('__VARS_ASSIGNMENTS__', vars_assignments)
    return camo_code

def _hyperion_full_transform(code: str, camouflage: bool = False, shell: bool = False, randlines: bool = False) -> str:
    """Run complete Hyperion transformation suite."""
    engine = HyperionEngine(
        content=code,
        clean=True,
        obfcontent=True,
        renlibs=True,
        renvars=False,
        addbuiltins=True,
        randlines=randlines,
        shell=shell,
        camouflage=camouflage,
        safemode=True
    )
    return engine.transform()

# ═══════════════════════════════════════════════════════════════
# FUSED MATRIX SHIELD - 3-TRACK INTERLEAVED SYMBIOTIC LOADER
# ═══════════════════════════════════════════════════════════════

def _fused_matrix_wrap(payload_code: str, key: int = None) -> str:
    """Fuses Kramer Kyrie Caesar + Emoji Stream + Whitespace Bitfields
    into an interwoven symbiotic matrix loader. 100% Polymorphic & Disguised."""
    if key is None:
        key = _trx_rand(2**60 - 2**30) + 2**30
    try:
        compiled = marshal.dumps(compile(payload_code, '<fused_payload>', 'exec'))
    except SyntaxError:
        compiled = payload_code.encode('utf-8')

    compressed = zlib.compress(bz2.compress(compiled), 9)
    b85 = base64.b85encode(compressed).decode('ascii')

    _EMOJI_BASE = 0x1F400
    _n7_ = bytes(list(range(97, 123)) + list(range(48, 58))).decode('latin1')

    track_k = []
    track_e = []
    track_w = []

    # 64-Bit High-Entropy Knuth LCG Stream State (Period = 2^64)
    seed = (key ^ 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF

    for i, ch in enumerate(b85):
        seed = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        mod = (seed >> 32) % 3
        if mod == 0:
            # 1. Kyrie Alphabet Rotation + Dynamic Caesar Shift
            rot = _n7_[_n7_.index(ch) - 1] if ch in _n7_ else ch
            track_k.append(chr(ord(rot) + (key % 10000)))
        elif mod == 1:
            # 2. Masked Emoji Stream
            track_e.append(chr(_EMOJI_BASE + (ord(ch) ^ (key & 0x3F))))
        else:
            # 3. Pure Space/Tab Binary Bitfield
            b = ord(ch)
            for bit_pos in range(7, -1, -1):
                track_w.append('\t' if (b >> bit_pos) & 1 else ' ')

    sk = ''.join(track_k)
    se = ''.join(track_e)
    sw = ''.join(track_w)

    _types_ = ("str", "float", "bool", "int", "object", "bytes")

    # Generate 100% dynamic, randomized identifier tokens using active charset
    _names_ = [rd() for _ in range(16)]
    random.shuffle(_names_)
    glob = {f"n_{k+1}": _names_[k] for k in range(16)}

    # Dynamic imports disguised via bytes
    imp_b64 = fr"""__import__(bytes([98,97,115,101,54,52]).decode())"""
    imp_zlib = fr"""__import__(bytes([122,108,105,98]).decode())"""
    imp_bz2 = fr"""__import__(bytes([98,122,50]).decode())"""
    imp_m = fr"""__import__(bytes([109,97,114,115,104,97,108]).decode())"""
    imp_types = fr"""__import__(bytes([116,121,112,101,115]).decode())"""
    fn_name = fr"""bytes([70,117,110,99,116,105,111,110,84,121,112,101]).decode()"""
    eval_resolver = fr"""getattr(__import__(bytes([98,117,105,108,116,105,110,115]).decode()), bytes([101,118,97,108]).decode())"""

    v_k = rd()
    v_e = rd()
    v_w = rd()
    v_tot = rd()
    v_key = rd()
    v_eb = rd()
    v_dk = rd()
    v_de = rd()
    v_dw = rd()
    v_s = rd()
    v_ik = rd()
    v_ie = rd()
    v_iw = rd()
    v_res = rd()
    v_c = rd()
    v_j = rd()
    v_n1 = rd()

    ref_n7 = f"self.{glob['n_7']}"

    rec_lambda = (
        fr"""lambda {v_k},{v_e},{v_w},{v_tot}={len(b85)},{v_key}={key},{v_eb}={_EMOJI_BASE}: """
        fr"""(lambda {v_dk}=[{ref_n7}[{ref_n7}.index({v_c})+1 if {ref_n7}.index({v_c})+1<len({ref_n7}) else 0] if {v_c} in {ref_n7} else {v_c} """
        fr"""for {v_c} in [chr(ord({v_c})-({v_key}%10000)) for {v_c} in {v_k}]], """
        fr"""{v_de}=[chr((ord({v_c})-{v_eb})^({v_key}&0x3F)) for {v_c} in {v_e}], """
        fr"""{v_dw}=[chr(int(''.join('1' if ord({v_c})==9 else '0' for {v_c} in {v_w}[{v_j}:{v_j}+8]), 2)) for {v_j} in range(0, len({v_w}), 8)], """
        fr"""{v_s}=[(({v_key}^0x9E3779B97F4A7C15)&0xFFFFFFFFFFFFFFFF)], """
        fr"""{v_ik}=[0], {v_ie}=[0], {v_iw}=[0], {v_res}=[]: """
        fr"""[({v_res}.append({v_dk}[{v_ik}[0]]) or {v_ik}.__setitem__(0, {v_ik}[0]+1)) """
        fr"""if ([{v_s}.__setitem__(0, ({v_s}[0]*6364136223846793005+1442695040888963407)&0xFFFFFFFFFFFFFFFF), {v_s}[0]][1]>>32)%3==0 """
        fr"""else (({v_res}.append({v_de}[{v_ie}[0]]) or {v_ie}.__setitem__(0, {v_ie}[0]+1)) """
        fr"""if ({v_s}[0]>>32)%3==1 """
        fr"""else ({v_res}.append({v_dw}[{v_iw}[0]]) or {v_iw}.__setitem__(0, {v_iw}[0]+1))) """
        fr"""for _ in range({v_tot})] and ''.join({v_res}))()"""
    )

    _1_ = (fr"""self.{glob['n_5']}""", rec_lambda)
    _2_ = (fr"""self.{glob['n_6']}""", fr"""lambda {v_n1}:exec({imp_m}.loads({imp_bz2}.decompress({imp_zlib}.decompress({imp_b64}.b85decode({v_n1}.encode(bytes([97,115,99,105,105]).decode()))))), globals(), globals())""")
    _3_ = (fr"""_n4_['{glob['n_2']}']""", eval_resolver)
    _4_ = (fr"""self.{glob['n_1']}""", fr"""lambda {v_n1}:{v_n1}""")
    _5_ = (fr"""self.{glob['n_7']}""", fr"""bytes(list(range(97, 123)) + list(range(48, 58))).decode(bytes([108,97,116,105,110,49]).decode())""")
    _6_ = (fr"""self.{glob['n_8']}""", fr"""lambda _k,_e,_w: self.{glob['n_6']}(self.{glob['n_1']}(self.{glob['n_5']}(_k,_e,_w)))""")

    _all_ = [_1_, _2_, _3_, _4_, _5_, _6_]
    random.shuffle(_all_)

    _vars_content_ = ','.join(s[0] for s in _all_)
    _valors_content_ = ','.join(s[1] for s in _all_)
    _vars_ = _vars_content_ + '=' + _valors_content_

    # Dynamic Class & Method Identifiers from rd()
    c_name = rd()
    m_dec = rd()
    m_init = "__init__"
    m_decoy1 = rd()
    m_decoy2 = rd()

    tmpl = fr"""class {c_name}():
 def {m_decoy1}(self,*_a:{random.choice(_types_)},**_kw:{random.choice(_types_)})->{random.choice(_types_)}:
  return (_a[0] if _a else 0)
 def {m_dec}(self,*_n2_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  {_vars_}
  return self.{glob['n_8']}(_n2_[0], _n2_[1], _n2_[2])
 def {m_decoy2}(self,_x:{random.choice(_types_)}={random.randint(100,999)})->int:
  return (_x * (_x + 1)) ^ 0x55AA
 def {m_init}(self,*_n3_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  self.{m_dec}(*_n3_,**_n4_)
{c_name}(__SPK_DATA__,__EMJ_DATA__,__WSP_DATA__)""".strip()

    loader = tmpl.replace('__SPK_DATA__', repr(sk)).replace('__EMJ_DATA__', f'"""{se}"""').replace('__WSP_DATA__', f'"""{sw}"""')

    return loader.strip()


def _exotic_payload_wrap(code_str: str, use_bitmatrix: bool = True, use_base4096: bool = True) -> str:
    """Wrap payload with tr0ngx_exotic layers: BitMatrix byte transform and/or
    Base4096 astral glyph encoding. Generated loader embeds standalone decoders."""
    try:
        import tr0ngx_exotic as _tex
    except ImportError:
        _log_debug("tr0ngx_exotic module not found; exotic wrap skipped", level="ERROR")
        return code_str

    data = code_str.encode("utf-8")
    prelude = []

    if use_bitmatrix:
        data, key_material = _tex.bit_matrix_transform(data, random)
        fn_bmatrix = rd('state_machine')
        src = _tex.bit_matrix_decoder_source(key_material)
        src = src.replace("def tr0ngx_bmatrix_inverse(data):", f"def {fn_bmatrix}(data):", 1)
        prelude.append(src)

    if use_base4096:
        glyph_payload, meta = _tex.encode_base4096(data, random)
        fn_b4096 = rd('table')
        src = _tex.base4096_decoder_source(meta)
        src = src.replace("def tr0ngx_b4096_decode(payload):", f"def {fn_b4096}(payload):", 1)
        prelude.append(src)
        chain = f"{fn_b4096}({glyph_payload!r})"
        if use_bitmatrix:
            chain = f"{fn_bmatrix}({chain})"
    elif use_bitmatrix:
        chain = None

    prelude_src = "\n".join(prelude)
    if use_base4096:
        loader = (
            "# -*- coding: utf-8 -*-\n"
            f"{prelude_src}\n"
            f"_code_text = {chain}.decode('utf-8')\n"
            "exec(compile(_code_text, '<tr0ngx-exotic>', 'exec'))\n"
        )
    else:
        loader = (
            "# -*- coding: utf-8 -*-\n"
            f"{prelude_src}\n"
            f"_payload_bytes = {data!r}\n"
            f"_code_text = {fn_bmatrix}(_payload_bytes).decode('utf-8')\n"
            "exec(compile(_code_text, '<tr0ngx-exotic>', 'exec'))\n"
        )
    return loader


def _kramer_wrap(payload_code: str, key: int = None) -> str:
    """Wrap final payload into Kramer dynamic class with Kyrie encryption + fake type annotations + anti-dump."""
    from binascii import hexlify
    if key is None:
        key = _trx_rand(999000) + 1000

    _content_ = Kyrie.encrypt_v2(payload_code, key=key)
    content = hexlify(_content_.encode('utf-8')).decode('ascii')

    _types_ = ("str", "float", "bool", "int", "object", "bytes")

    # Generate 100% dynamic, randomized identifier tokens using active charset
    _names_ = [rd() for _ in range(16)]
    random.shuffle(_names_)
    glob = {f"n_{k+1}": _names_[k] for k in range(16)}

    # Dynamic imports & resolvers
    imp_bin = fr"""__import__(bytes([98,105,110,97,115,99,105,105]).decode())"""
    fn_unhex = fr"""getattr({imp_bin}, bytes([117,110,104,101,120,108,105,102,121]).decode())"""
    eval_resolver = fr"""getattr(__import__(bytes([98,117,105,108,116,105,110,115]).decode()), bytes([101,118,97,108]).decode())"""

    v_n9 = rd()
    v_n1 = rd()
    v_n12 = rd()
    v_t = rd()

    _dec_fn = rd('state_machine')
    _dec_src = (
        f"def {_dec_fn}(s, k):\n"
        f" out=[];st=k\n"
        f" for ch in s:\n"
        f"  st=(st*1664525+1013904223)&4294967295\n"
        f"  out.append('\\n' if ch=='\\u03b6' else chr(ord(ch)^(st&255)))\n"
        f" return ''.join(out)\n"
    )

    _1_ = (fr"""self.{glob['n_5']}""", fr"""lambda {v_n9}:{fn_unhex}(str({v_n9})).decode()""")
    _2_ = (fr"""self.{glob['n_6']}""", fr"""lambda {v_n1}:exec({v_n1}, globals(), globals())""")
    _3_ = (fr"""_n4_['{glob['n_2']}']""", eval_resolver)
    _4_ = (fr"""self.{glob['n_1']}""", fr"""lambda {v_n1}:{_dec_fn}(self.{glob['n_5']}({v_n1}),{key}).translate(str.maketrans(dict(zip(self.{glob['n_7']},self.{glob['n_7']}[-1:]+self.{glob['n_7']}[:-1])))).replace("\\uE000","\\u03b6")""")
    _5_ = (fr"""self.{glob['n_7']}""", fr"""bytes(list(range(97, 123)) + list(range(48, 58))).decode(bytes([108,97,116,105,110,49]).decode())""")
    _6_ = (fr"""self.{glob['n_8']}""", fr"""lambda {v_n12}:self.{glob['n_6']}(self.{glob['n_1']}({v_n12}))""")

    _all_ = [_1_, _2_, _3_, _4_, _5_, _6_]
    random.shuffle(_all_)

    _vars_content_ = ",".join(s[0] for s in _all_)
    _valors_content_ = ",".join(s[1] for s in _all_)
    _vars_ = _vars_content_ + "=" + _valors_content_

    c_name = rd()
    m_dec = rd()
    m_init = "__init__"
    m_decoy1 = rd()

    tmpl = _dec_src + fr"""class {c_name}():
 def {m_decoy1}(self,*_a:{random.choice(_types_)},**_kw:{random.choice(_types_)})->{random.choice(_types_)}:
  return (_a[0] if _a else None)
 def {m_dec}(self,_execute:str)->exec:
  return (None,self.{glob['n_8']}(_execute))[0]
 def {m_init}(self,*_n3_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  {_vars_}
  return self.{m_dec}(_n3_[0])
{c_name}('''{content}''')""".strip()

    return tmpl

# ═══════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════

dark = Col.dark_gray
light = Col.light_gray
purple = Colors.StaticMIX((Col.green, Col.yellow))
bpurple = Colors.StaticMIX((Col.pink, Col.blue, Col.blue))

text = f"""
  TR0NGX x VELIMATIX - ULTIMATE OBFUSCATOR
  AST ENGINE v4.0 - MAXIMUM POWER EDITION

 ══════════ TR0NGX CORE ENGINE ══════════
  • STRING    : 6 STRATEGIES (LAMBDA/XOR/SPLIT/REVERSE/SHUFFLE/BYTEWISE)
  • INTEGER   : 8 STRATEGIES (BYTE/OFFSET/XOR/ARITHMETIC/SHIFT/NESTED)
  • CONTROL   : STATE MACHINE + TRY-CATCH + MATCH-CASE + JUNK DECOYS

 ══════════ VELIMATIX AST ENGINE ══════════
  • BI-OPAQUE  : PREDICATE INJECTION + ROADLINE GENERATION
  • EXCEPTION  : WHILE-LOOP + EXCEPTION JUMP CONTROL FLOW
  • CONTROL    : MATCH-CASE STATE MACHINE + JUNK CASES
  • CALL OBF   : BUILTIN -> GETATTR CHAIN RECONSTRUCTION
  • MUTATOR    : XOR CHAIN + LAMBDA WRAP + STACK ELEMENTS
  • CLONE      : FAKE METHOD COPIES + DEAD CODE INJECTION
  • BUILTIN    : FULL BUILTIN RENAME (60+ FUNCTIONS)
  • STRING     : BYTEWISE XOR + SHIFT + NOT ENCODING

 ══════════ PROTECTION MATRIX ══════════
  • ANTI-DEBUG    : 6-VECTOR DETECTION + CONTINUOUS MONITOR
  • ANTI-HOOK     : VELIMATIX SHIELD + EXEC/EVAL GUARD
  • ANTI-IMPORT   : META_PATH BLOCKER (15+ TOOLS BLOCKED)
  • ANTI-DUMP     : CHUNKED EXECUTION + SELF-MODIFYING
  • ANTI-DECOMPILE: PYCDC/UNCOMPYLE BLOCKER (8000+ JUNK)
  • ANTI-MARSHAL  : TYPE VERIFY + CALLER CHECK + GUARD

 ══════════ AEAD COMPILER ══════════
  • PACKAGING     : MARSHAL + XOR(x2) + ZLIB(x2) + BZ2 + BASE85
  • DERIVATION    : 8-PART SPLIT + DYNAMIC KEY DERIVATION
  • DOUBLE COMPILE: TR0NGX INSIDE VELIMATIX LOADER

  • MODE 1 : LOW    (FAST, BASIC PROTECTION)
  • MODE 2 : MEDIUM (RECOMMENDED, FULL OBF)
  • MODE 3 : HIGH   (MAXIMUM, ALL LAYERS)

 ══════════ KRAMER & HYPERION ENGINES ══════════
  • KYRIE ELEISON  : INDEX SHIFT + ASCII CAESAR OFFSET
  • DYNAMIC CLASS  : RUNTIME OBFUSCATED CLASS + FAKE ANNOTATIONS
  • HYPERION TOKEN : BUILTINS / SCOPE / MATH / STR SPLITTING
  • CAMOUFLAGE     : FAKE SCIENTIFIC CLASS SIMULATION
  • FORCE PYTHON   : LOCK EXECUTION TO SPECIFIC PY VERSION (3.10 - 3.14)
  • CJK / PYCOOL   : CHINESE IDENTIFIERS + PYCOOL WATERMARKS

 ══════════ UNICODE MATRIX ENGINES ══════════
  • EMOJI-OBF     : CODE -> EMOJI SEQUENCE ENCODER (U+1F400 ANIMAL)
  • HOMOGLYPH     : CYRILLIC/GREEK LOOKALIKE NAMES (a/o/e)
  • RARE-UNICODE  : CJK EXTENSION B + KANGXI RADICALS (龘 鱻 𪚥)
  • ZALGO MARKS   : EXTREME PEP 3131 COMBINING DIACRITICS CASCADE
  • WHITESPACE    : INVISIBLE SPACE/TAB BINARY BITFIELD MATRIX
"""

banner = f"""

⠐⠀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⡀⠀⠀⠀⠀⠀⢀⣀⢀⠀⠀⣀⣀⣀⣀⠀⣀⣀⣀⣀⢀⡀⠀⠀⠀⠀⢀⡈⠢
⠀⠈⠭⣿⠏⠈⢻⣿⡿⠛⠉⠁⠀⠁⠀⠀⠀⠀⠀⢈⣈⣤⣤⣤⣀⡀⠀⠀⠀⠊⡊⠓⡦⡀⠀⠀⠀⠀⠀⠀⡇⠈
⠀⠀⠒⣧⣦⣠⠞⠁⠀⠀⠀⠀⠀⠀⢀⣀⣤⣶⣿⠯⠽⠧⠼⠷⢶⠿⢓⣀⣀⣆⡀⣠⣈⠻⣦⡀⣀⣠⡀⠀⡇⠀
⠀⠰⣟⣷⡟⠁⠀⠀⠀⠀⠀⢀⡤⠖⢫⣍⢀⣾⣯⠀⣞⡆⠀⣏⢻⣠⣄⡀⠉⠙⣻⣿⡻⣷⡈⢻⣿⣿⣷⣾⡇⠀
⠀⢠⣶⡟⠁⠀⠀⠀⣀⣴⠚⠉⠀⣠⣿⠞⠋⠻⣿⡀⠀⠀⠀⠈⠙⢻⣟⠳⣆⠀⠙⢯⡛⣿⢻⡇⡟⢩⢟⡟⡇⠀
⠀⢸⣿⠀⠀⠀⡠⣾⣿⢉⡀⢀⡆⡿⢃⣀⠀⠀⠘⣷⣀⢠⡄⠀⠀⠀⣙⠓⣿⣶⡀⠀⠛⠻⣾⣴⣱⣣⢖⣱⡇⠀
⠀⠸⣿⣧⢤⡎⣰⣣⣶⡏⡧⣄⣵⡿⠭⠻⠃⠀⠀⢣⣹⠸⣿⣤⡐⠛⠛⠷⡆⠈⠑⠢⠤⣀⠹⣿⡿⠿⣿⡿⡇⠀
⠀⢈⡿⣻⠉⡇⡿⠟⢉⡇⠱⣿⡁⡇⠀⠀⢀⣀⠀⠸⣧⠰⡇⢈⣙⡧⣄⡰⣤⣀⣠⣶⠒⠉⠀⠈⣧⣀⠀⣿⡇⠀
⠀⠀⣀⠈⠶⣿⠁⠀⠘⠣⢻⠇⣳⣷⣶⣶⣿⡟⠀⠀⠙⢷⣿⠘⣽⣿⣿⣿⣿⣄⠀⢻⠀⠀⠀⠀⡸⡿⠤⣷⡇⠀
⠀⠐⠋⠀⢀⡿⠀⠘⠀⢰⢸⣿⡿⢿⣿⠏⢉⣇⠀⠀⠀⠀⠙⠃⣾⣿⣁⣈⡻⣿⣯⣿⡄⠀⠀⣶⣇⢹⣧⣿⡇⠀
⠀⠀⠄⠀⡹⣧⠄⠀⠀⠸⣿⣿⡁⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⡇⠸⢻⠇⠀⠀⠀⡼⣿⣼⣿⣿⡇⠀
⠀⠐⣦⡤⡁⣿⠰⢠⠀⠀⢙⣇⠁⠻⣯⣍⡬⠏⠀⠀⠀⠠⠀⠀⠻⣧⣀⠼⢳⣠⣿⡄⢀⣠⡞⣴⣿⣿⠋⢨⡇⠀
⠀⠀⠿⠂⠄⡟⣇⢸⡄⠀⠘⠛⣷⢴⣺⣿⡍⠀⠀⠀⠀⠀⠀⠀⠀⢠⠠⣵⣾⢟⣃⡠⢾⡏⣼⠏⢸⡟⠛⣿⡇⠀
⠀⠐⣒⣀⣀⡟⠛⠾⢧⠀⠀⠀⢽⡙⠉⠐⠁⠀⠀⠀⢀⣴⣄⠀⠀⠀⠃⠛⣿⣹⠋⢀⣾⡼⠁⠀⢸⣿⣥⡿⡇⠀
⠀⠈⠛⣿⢟⢣⠀⠀⠨⣧⡀⠀⠏⣧⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣨⣼⣿⠀⢸⣿⠀⠀⠀⢸⡏⠀⣷⡇⠀
⠀⠠⡖⠀⠀⢸⠀⠀⢠⣿⣧⠀⠀⠸⣿⣟⡷⣶⣦⣤⠤⢤⣤⣤⣶⣶⢿⡟⢽⣏⠀⢸⣿⠀⠀⠀⠀⣷⠯⢿⡇⠀
⠀⢠⣶⣶⣦⣼⣰⠀⠀⡿⠹⣧⠀⠀⣿⣸⣧⣿⣨⢿⠷⠒⠚⠛⠛⠛⠚⠛⠺⠯⠤⠚⠛⠓⠚⠓⠒⠻⣦⠀⡇⠀
⠀⢸⣟⣿⣿⣿⠁⠀⠀⡇⠀⠞⣷⠀⠘⢿⣽⣿⣵⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⠁⡇⠀
⠀⢸⣿⣿⣿⣿⡆⠀⢀⣿⡷⡎⠉⢣⡀⠈⢿⡣⠻⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣖⡇⠀
⠀⢸⣿⣿⣿⣿⠀⢠⠾⠃⠁⢸⡄⠀⢷⠀⠀⠻⣤⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡇⠀
⠠⣈⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⢁⠄
"""


# ═══════════════════════════════════════════════════════════════
# ADVANCED PROFILER & REAL-TIME DIAGNOSTIC LOGGER
# ═══════════════════════════════════════════════════════════════

_EngineState.verbose_debug = False
_EngineState.profile_mode = False
_EngineState.strict_mode = False
_EngineState.log_file_path = None
_LOG_ENTRIES = []
_STAGE_ERRORS = []

def _get_current_ram_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0

def _log_debug(msg: str, stage: str = None, duration: float = None, error: Exception = None, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    dur_str = f" [took {duration:.4f}s]" if duration is not None else ""
    stg_str = f" [{stage}]" if stage else ""
    ram_mb = _get_current_ram_mb()
    ram_str = f" [RAM: {ram_mb:.1f}MB]" if ram_mb > 0 else ""
    entry = f"[{ts}][{level}]{stg_str}{ram_str} {msg}{dur_str}"
    _LOG_ENTRIES.append(entry)

    if _EngineState.verbose_debug or level in ("ERROR", "WARNING") or _EngineState.profile_mode:
        if level == "ERROR":
            _v(_gradient_text(f"  [ERROR]{stg_str} {msg}{dur_str}{ram_str}", (255, 60, 60), (255, 120, 60)))
            if error is not None:
                tb_lines = traceback.format_exc().strip()
                _LOG_ENTRIES.append(tb_lines)
                for l in tb_lines.splitlines():
                    _v(f"    │ {l}")
        elif level == "WARNING":
            _v(_gradient_text(f"  [WARNING]{stg_str} {msg}{dur_str}", (255, 180, 40), (255, 220, 80)))
        elif _EngineState.verbose_debug:
            _v(_gradient_text(f"  [DEBUG]{stg_str} {msg}{dur_str}{ram_str}", (80, 180, 255), (140, 220, 255)))

def _log_stage_error(stage_name: str, exc: Exception, extra_info: dict = None):
    tb = traceback.format_exc()
    tb_lines = [l for l in tb.strip().splitlines() if l.strip()]
    loc_str = tb_lines[-2] if len(tb_lines) >= 2 else "Unknown location"
    
    error_record = {
        "stage": stage_name,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "location": loc_str.strip(),
        "traceback": tb,
        "timestamp": time.time(),
        "ram_mb": round(_get_current_ram_mb(), 2),
        "extra_info": extra_info or {}
    }
    _STAGE_ERRORS.append(error_record)
    
    if "_DEBUG_MAP" in globals() and "errors" in _DEBUG_MAP:
        _DEBUG_MAP["errors"].append(error_record)

    _log_debug(f"{type(exc).__name__}: {exc} (at {loc_str.strip()})", stage=stage_name, error=exc, level="ERROR")
    
    if _EngineState.strict_mode:
        _v(_gradient_text(f"\n [STRICT MODE ABORT] Terminating immediately due to error in stage '{stage_name}'", (255, 30, 30), (255, 100, 30)))
        _v(f"  Exception: {type(exc).__name__}: {exc}")
        _v(f"  Traceback:\n{tb}\n")
        sys.exit(1)

def _print_profile_waterfall(total_elapsed: float, original_size: int, final_size: int):
    stages = _DEBUG_MAP.get("stages", [])
    if not stages and not _STAGE_ERRORS:
        return

    _v("")
    _v(" ══════════════════════ PERFORMANCE & BOTTLENECK PROFILE ══════════════════════")
    _v(f" {'STAGE':<34} {'TIME (s)':<12} {'% TOTAL':<10} {'SIZE DELTA':<14} {'STATUS'}")
    _v(" ─────────────────────────────────────────────────────────────────────────────")

    slowest_stage = None
    max_duration = -1.0

    for s in stages:
        stg_name = s.get("stage", "Unknown")
        dur = s.get("duration_seconds", 0.0)
        pct = (dur / total_elapsed * 100) if total_elapsed > 0 else 0
        delta = s.get("delta_bytes", 0)
        delta_str = f"+{delta:,} B" if delta >= 0 else f"-{abs(delta):,} B"
        status = "[OK]"

        if dur > max_duration:
            max_duration = dur
            slowest_stage = (stg_name, dur, pct)

        _v(f" {stg_name:<34} {dur:>8.4f}s    {pct:>6.1f}%    {delta_str:>12}    {status}")

    for err in _STAGE_ERRORS:
        _v(f" [ERROR] {err['stage']:<26} FAILED        --               --    [ERROR]")

    _v(" ─────────────────────────────────────────────────────────────────────────────")
    current_ram = _get_current_ram_mb()
    ram_str = f" | PEAK RAM: {current_ram:.1f} MB" if current_ram > 0 else ""
    _v(f" TOTAL TIME: {total_elapsed:.4f}s | EXPANSION: {original_size:,} B -> {final_size:,} B ({final_size/original_size if original_size>0 else 0:.1f}x){ram_str}")

    if slowest_stage and slowest_stage[1] > 0.1 and slowest_stage[2] >= 25.0:
        _v(f" [BOTTLENECK ADVISORY] Stage '{slowest_stage[0]}' took the longest ({slowest_stage[1]:.3f}s, {slowest_stage[2]:.1f}% of total).")
    if _STAGE_ERRORS:
        _v(f" [WARNING] Encountered {len(_STAGE_ERRORS)} stage exception(s). Run with --debug or inspect log file for tracebacks.")
    _v(" ═════════════════════════════════════════════════════════════════════════════")
    _v("")

def _export_log_file():
    if not _EngineState.log_file_path:
        return
    try:
        with open(_EngineState.log_file_path, "w", encoding="utf-8") as lf:
            lf.write(f"=== TR0NGX OBFUSCATOR EXECUTION & DIAGNOSTIC LOG ===\n")
            lf.write(f"Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            lf.write(f"Python    : {sys.version}\n")
            lf.write(f"Platform  : {platform.platform()}\n")
            lf.write(f"PID       : {os.getpid()}\n\n")
            lf.write("=== EXECUTION CHRONOLOGY ===\n")
            for entry in _LOG_ENTRIES:
                lf.write(entry + "\n")
            if _STAGE_ERRORS:
                lf.write("\n=== STAGE ERROR TRACEBACKS ===\n")
                for err in _STAGE_ERRORS:
                    lf.write(f"\n--- Stage: {err['stage']} ({err['exception_type']}) @ RAM {err['ram_mb']}MB ---\n")
                    lf.write(f"Message  : {err['message']}\n")
                    lf.write(f"Location : {err.get('location', '')}\n")
                    lf.write(f"Traceback:\n{err['traceback']}\n")
        _v(f" [DIAGNOSTIC LOG SAVED] {_EngineState.log_file_path}")
    except Exception as e:
        _v(f" WARNING: Failed to export log file: {e}")

_DEBUG_MAP = {
    "version": "4.0",
    "timestamp": None,
    "source_file": None,
    "output_file": None,
    "options": {},
    "renamed_functions": {},
    "renamed_builtins": {},
    "renamed_variables": {},
    "skipped_renames": [],
    "stages": [],
    "errors": []
}

def _track_debug_stage(name: str, duration_sec: float, initial_size: int, final_size: int, details: dict = None):
    delta = final_size - initial_size
    delta_str = f"+{delta:,} B" if delta >= 0 else f"-{abs(delta):,} B"
    _log_debug(f"Completed ({duration_sec:.4f}s, size: {initial_size:,} -> {final_size:,} B [{delta_str}])", stage=name, duration=duration_sec)
    _DEBUG_MAP["stages"].append({
        "stage": name,
        "duration_seconds": round(duration_sec, 4),
        "initial_size_bytes": initial_size,
        "final_size_bytes": final_size,
        "delta_bytes": delta,
        "ram_mb": round(_get_current_ram_mb(), 2),
        "details": details or {}
    })

def _is_agent_or_non_interactive():
    if os.environ.get("NO_COLOR") or os.environ.get("CI") or os.environ.get("ANTIGRAVITY_AGENT"):
        return True
    if any(k in os.environ for k in ("AGENT_ID", "CONTINUATION_ID", "AI_AGENT", "CLAUDE_CODE", "CRUSH_CLI")):
        return True
    try:
        if not sys.stdout.isatty():
            return True
    except Exception:
        return True
    return False

_EngineState.cli_quiet_mode = _is_agent_or_non_interactive()

def _clean_ansi(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
    # Strip standard ANSI escape sequences \x1b[...]
    cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    # Strip any leaked raw RGB color codes like [38;2;...m or [200;200;200m
    cleaned = re.sub(r'\[38;2;\d+;\d+;\d+m', '', cleaned)
    cleaned = re.sub(r'\[[0-9;]{2,}m', '', cleaned)
    return cleaned

def _gradient_text(text: str, start_rgb: tuple, end_rgb: tuple) -> str:
    """Tạo chuỗi màu gradient 2 màu mượt mà pha trộn qua 24-bit TrueColor ANSI escape codes."""
    if not isinstance(text, str) or not text:
        return str(text)
    if _EngineState.cli_quiet_mode:
        return text
    n = max(len(text) - 1, 1)
    res = []
    for i, ch in enumerate(text):
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * (i / n))
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * (i / n))
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * (i / n))
        res.append(f"\033[38;2;{r};{g};{b}m{ch}")
    return "".join(res) + "\033[0m"

def _format_symbol_tag(symbol: str) -> str:
    """Tạo tag [TR0NGX] / [STAGE] bằng bảng phối màu Neon Cyberpunk rực rỡ, sắc nét từng ký tự."""
    if _EngineState.cli_quiet_mode:
        return f"[{symbol}]"
    if symbol == 'TR0NGX':
        # Letter-by-letter Multi-Stop TrueColor Neon Gradient: Cyan -> Sky -> Indigo -> Violet -> Fuchsia -> Magenta
        return "\033[1;38;2;0;235;255m[\033[1;38;2;0;255;255mT\033[38;2;60;210;255mR\033[38;2;130;150;255m0\033[38;2;190;100;255mN\033[38;2;240;65;235mG\033[38;2;255;50;180mX\033[1;38;2;255;40;180m]\033[0m"
    elif symbol in ('ERROR', 'FAIL'):
        return f"\033[1;38;2;255;40;40m[\033[1;38;2;255;80;60m{symbol}\033[1;38;2;255;40;40m]\033[0m"
    elif symbol in ('WARN', 'WARNING'):
        return f"\033[1;38;2;255;180;20m[\033[1;38;2;255;220;40m{symbol}\033[1;38;2;255;180;20m]\033[0m"
    elif symbol in ('PASS', 'OK', 'SAVED'):
        return f"\033[1;38;2;0;240;255m[\033[1;38;2;50;255;130m{symbol}\033[1;38;2;0;240;255m]\033[0m"
    else:
        sym_grad = _gradient_text(symbol, (0, 240, 255), (240, 80, 255))
        return f"\033[1;38;2;0;240;255m[{sym_grad}\033[1;38;2;240;80;255m]\033[0m"

def stage(text: str, symbol: str = 'TR0NGX', col1=light, col2=None) -> str:
    text_str = str(text)
    # Extract clean core text without any prior ANSI codes or symbols
    clean_text = _clean_ansi(text_str).strip()
    if clean_text.startswith(f"[{symbol}]"):
        clean_text = clean_text[len(f"[{symbol}]"):].strip()
    
    if _EngineState.cli_quiet_mode:
        return f"[{symbol}] {clean_text}"

    upper_text = clean_text.upper()
    if "ENTER FILE" in upper_text:
        # Ultra-striking Amber Gold to Hot Neon Magenta gradient for file input prompts
        gradient_body = _gradient_text(clean_text, (255, 225, 30), (255, 40, 150))
    elif "SAVED:" in upper_text or "SUCCESS" in upper_text or "COMPLETE" in upper_text:
        # Electric Cyan to Neon Spring Green gradient
        gradient_body = _gradient_text(clean_text, (0, 240, 255), (50, 255, 130))
    elif any(kw in upper_text for kw in ["WARNING", "ERROR", "SYNTAX ERROR", "NOT FOUND", "FAILED"]):
        # Fiery Crimson Red to Radiant Gold-Orange gradient
        gradient_body = _gradient_text(clean_text, (255, 45, 45), (255, 185, 25))
    elif any(kw in upper_text for kw in ["MODE", "LEVEL", "CORES", "RAM", "LIMIT"]):
        # Neon Sunset Orange to Electric Purple gradient
        gradient_body = _gradient_text(clean_text, (255, 175, 40), (220, 75, 255))
    elif "? (Y/N)" in upper_text or "?" in upper_text:
        # Neon Turquoise to Orchid Violet gradient
        gradient_body = _gradient_text(clean_text, (40, 215, 255), (205, 105, 255))
    elif any(kw in upper_text for kw in ["ORIGINAL:", "OUTPUT:", "TIME:", "FUSION:", "DEBUG MAP", "OBF:", "ANTI:", "COMPILE:", "KRAMER:", "CJK"]):
        # Ice Cyan to Soft Magenta gradient
        gradient_body = _gradient_text(clean_text, (100, 220, 255), (180, 120, 255))
    else:
        # Bright Cyan to Vivid Purple default gradient
        gradient_body = _gradient_text(clean_text, (60, 210, 255), (210, 95, 255))

    tag = _format_symbol_tag(symbol)
    return f" {tag} {gradient_body} "

_raw_input = input

def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except (UnicodeEncodeError, Exception):
        enc = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
        safe_args = [
            a.encode(enc, errors='replace').decode(enc, errors='replace') if isinstance(a, str) else a
            for a in args
        ]
        print(*safe_args, **kwargs)

_raw_print = _safe_print

def _v_step(step, total, text):
    """Hiển thị log từng bước cực đẹp với màu sắc và căn lề chuẩn"""
    if _EngineState.cli_quiet_mode:
        _v(f" [{step}/{total}] {text}")
        return
    tag = _format_symbol_tag('TR0NGX')
    step_str = f"[{str(step):>{len(str(total))}}/{total}]"
    grad = _gradient_text(f"{step_str} {text}", (100, 220, 255), (180, 120, 255))
    _raw_print(f" {tag} {grad} ", flush=True)

def _v(x, *k):
    if isinstance(x, str) and ('\x1b' in x or x.startswith('[TR0NGX]')):
        return _raw_print(x, *k, flush=True)
    return _raw_print(stage(x), *k, flush=True)

def _prompt_input(x, secret: bool = False):
    formatted = stage(x)
    try:
        sys.stdout.write(formatted)
        sys.stdout.flush()
        if secret:
            return getpass("").strip().strip('"').strip("'")
        return _raw_input("").strip().strip('"').strip("'")
    except (UnicodeEncodeError, Exception):
        enc = sys.stdout.encoding or 'utf-8'
        safe_prompt = formatted.encode(enc, errors='replace').decode(enc, errors='replace')
        sys.stdout.write(safe_prompt)
        sys.stdout.flush()
        if secret:
            return getpass("").strip().strip('"').strip("'")
        return _raw_input("").strip().strip('"').strip("'")

def _show_banner():
    if _EngineState.cli_quiet_mode:
        return
    b = Add.Add(text, banner, center=True)
    _raw_print(Colorate.Diagonal(Colors.DynamicMIX((purple, light)), b))


# ═══════════════════════════════════════════════════════════════
# CLI PARSER & INTERACTIVE DISPATCHER
# ═══════════════════════════════════════════════════════════════

def _apply_resource_limits(max_ram_mb: int = None, max_cores: int = None):
    """Giới hạn tài nguyên RAM và CPU Cores để chống lag hệ thống."""
    if max_cores and max_cores > 0:
        try:
            # Set CPU Affinity on Windows/Linux
            if hasattr(os, "sched_setaffinity"):
                os.sched_setaffinity(0, set(range(min(max_cores, os.cpu_count() or 1))))
            elif sys.platform == "win32":
                import ctypes
                mask = (1 << min(max_cores, 64)) - 1
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.kernel32.SetProcessAffinityMask(handle, mask)
        except Exception:
            pass
        os.environ["OMP_NUM_THREADS"] = str(max_cores)
        os.environ["MKL_NUM_THREADS"] = str(max_cores)

    if max_ram_mb and max_ram_mb > 0:
        # Start a daemon thread to monitor RAM and trigger gc
        def _ram_watchdog():
            import gc, time
            while True:
                time.sleep(2)
                try:
                    import psutil
                    mem = psutil.Process().memory_info().rss / (1024 * 1024)
                    if mem > max_ram_mb:
                        gc.collect()
                except Exception:
                    gc.collect()
        import threading
        t = threading.Thread(target=_ram_watchdog, daemon=True)
        t.start()

def _parse_size_str(val):
    if val is None:
        return None
    if isinstance(val, int):
        return val
    val = str(val).strip().upper()
    if val.endswith("GB") or val.endswith("G"):
        return int(float(val.rstrip("GB").rstrip("G")) * 1024 * 1024 * 1024)
    if val.endswith("MB") or val.endswith("M"):
        return int(float(val.rstrip("MB").rstrip("M")) * 1024 * 1024)
    if val.endswith("KB") or val.endswith("K"):
        return int(float(val.rstrip("KB").rstrip("K")) * 1024)
    if val.isdigit():
        return int(val)
    return None

def _resolve_input_files(inputs=None, directory=None, recursive=False):
    """
    Discovers all target python files from list of inputs, glob patterns, or directory path.
    Returns list of dicts: [{'src': absolute_source_path, 'rel': relative_output_path}, ...]
    Excludes the tool's own outputs (tr0ngx-* files, tr0ngx_dist dirs, __pycache__) and
    preserves directory structure in 'rel' to prevent basename collisions in batch mode.
    """
    found = []
    seen = set()

    # Directory-name blacklist for batch walks. Source: Opy skip_path_fragments
    # rationale (Apache-2.0 research note) + pyminifier analyze.py unfiltered-walk
    # defect lesson - vendored/virtualenv trees must never enter the batch.
    _BATCH_DIR_BLACKLIST = frozenset({
        "__pycache__", "tr0ngx_dist", ".git", ".hg", ".svn",
        "venv", ".venv", "env", ".env", "virtualenv",
        "site-packages", "node_modules", ".tox", ".mypy_cache", ".pytest_cache",
        "dist", "build", "research_repos",
    })

    def _is_source_file(name: str) -> bool:
        # Case-insensitive extension match + .pyw support (audit fix: .PY was
        # silently skipped on case-sensitive comparison).
        low = name.lower()
        return low.endswith(".py") or low.endswith(".pyw")

    def _excluded(f_abs: str) -> bool:
        base = os.path.basename(f_abs)
        if base.startswith("tr0ngx-"):
            return True
        parts = f_abs.replace("/", os.sep).split(os.sep)
        return any(p.lower() in _BATCH_DIR_BLACKLIST for p in parts[:-1])

    def _add(f_path: str, rel_hint: str = None):
        f_abs = os.path.abspath(f_path)
        if f_abs in seen or _excluded(f_abs):
            return
        seen.add(f_abs)
        if rel_hint:
            found.append({"src": f_abs, "rel": rel_hint})
        else:
            try:
                found.append({"src": f_abs, "rel": os.path.relpath(f_abs, os.getcwd())})
            except ValueError:
                found.append({"src": f_abs, "rel": os.path.basename(f_abs)})

    if directory:
        d_abs = os.path.abspath(directory.strip().strip('"').strip("'"))
        if not os.path.isdir(d_abs):
            raise FileNotFoundError(f"Directory not found: {directory}")
        if recursive:
            for root, _, files in os.walk(d_abs):
                for f in files:
                    if _is_source_file(f):
                        f_abs = os.path.abspath(os.path.join(root, f))
                        rel = os.path.relpath(f_abs, d_abs)
                        if f_abs not in seen and not _excluded(f_abs):
                            seen.add(f_abs)
                            found.append({"src": f_abs, "rel": rel})
        else:
            for f in os.listdir(d_abs):
                if _is_source_file(f):
                    f_abs = os.path.abspath(os.path.join(d_abs, f))
                    if os.path.isfile(f_abs) and f_abs not in seen and not _excluded(f_abs):
                        seen.add(f_abs)
                        found.append({"src": f_abs, "rel": f})

    if inputs:
        raw_items = []
        if isinstance(inputs, str):
            if "," in inputs:
                raw_items = [p.strip() for p in inputs.split(",") if p.strip()]
            else:
                raw_items = inputs.split()
        elif isinstance(inputs, (list, tuple)):
            for it in inputs:
                if isinstance(it, str) and "," in it:
                    raw_items.extend([p.strip() for p in it.split(",") if p.strip()])
                else:
                    raw_items.append(str(it).strip())

        for item in raw_items:
            item_str = str(item).strip().strip('"').strip("'")
            if not item_str:
                continue
            if any(c in item_str for c in ("*", "?", "[", "]")):
                globbed = glob.glob(item_str, recursive=recursive)
                pattern_dir = os.path.dirname(os.path.abspath(item_str)) or os.getcwd()
                for g in sorted(globbed):
                    if _is_source_file(g) and os.path.isfile(g):
                        g_abs = os.path.abspath(g)
                        try:
                            rel_hint = os.path.relpath(g_abs, pattern_dir)
                        except ValueError:
                            rel_hint = os.path.basename(g_abs)
                        _add(g_abs, rel_hint)
            elif os.path.isdir(item_str):
                d_found = _resolve_input_files(directory=item_str, recursive=recursive)
                for df in d_found:
                    if df["src"] not in seen:
                        seen.add(df["src"])
                        found.append(df)
            elif os.path.isfile(item_str):
                _add(item_str)

    # Final collision guard: make every 'rel' unique by prefixing parent dirs
    rels_seen = {}
    for entry in found:
        r = entry["rel"].replace("\\", "/")
        if r in rels_seen:
            n = 2
            while f"{r}.{n}" in rels_seen:
                n += 1
            r = f"{r}.{n}"
        rels_seen[r] = True
        entry["rel"] = r

    return found

def get_args_or_prompt():
    parser = argparse.ArgumentParser(
        prog="procheck.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
╔══════════════════════════════════════════════════════════════════════════════╗
║        TR0NGX x VELIMATIX x KRAMER - ULTIMATE AST OBFUSCATOR        ║
║                    PYTHON CODE PROTECTION SUITE v4.0                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

CÔNG CỤ LÀM RỐI MÃ NGUỒN PYTHON ĐA TẦNG CỰC MẠNH:
  • Tầng 0: Hyperion Engine (Builtin remapping, token variable remap, math/str splitting)
  • Tầng 1: Tr0ngX AST Transformer (Biến đổi hằng số, chuỗi, số nguyên, logic)
  • Tầng 2: Velimatix Engine (BiOpaque predicates, Exception jump, Match-Case state machine)
  • Tầng 3: Trongdepzai Multi-Layer AST Obfuscation (Lớp 1..3)
  • Tầng 4: True VM Virtualization 2.0 (TVM: Polymorphic CPU, Randomized ISA & Encrypted V-Bytecode)
  • Tầng 5: Double Compile Bytecode Loader (marshal + XOR + zlib + bz2 + base85)
  • Tầng 6: Anti-Analysis Matrix (Anti-Debug, Anti-VM/Sandbox, In-Memory Anti-Dump, Self-Mod)
  • Tầng 7: Math Opaque & Dynamic Callsite XOR Strings
  • Tầng 8: Kramer Kyrie Eleison Outer Shield (Mã hóa dịch chuyển Caesar động + Class ảo)
  • Tầng 9: Tên biến tiếng Trung / CJK + Watermark bản quyền PyCool
  • Tầng 10: Emoji Obfuscation (Code → chuỗi emoji 🐀🐁🐂 + self-decoding loader)
  • Tầng 11: Homoglyph & Rare Unicode Names (Cyrillic/Greek & CJK Ext-B, Kangxi, Hieroglyphs)
  • Tầng 12: Whitespace Obfuscation (Code biến đổi thành không gian trắng space/tab binary)
  • Tầng 13: Extreme Zalgo Diacritics Shield (Chồng lớp dấu tổ hợp làm tê liệt decompiler GUI)
  • Tầng 14: Hyperion Scientific Class Camouflage (Ngụy trang lớp mô phỏng bộ nhớ khoa học)
  • Tầng 15: 3-Track Symbiotic Fused Matrix Shield (Kyrie + Emoji + Whitespace hợp nhất không phình dung lượng)
  • Tầng 16: Bedrock Decompiler Traps & Secret Sharing (Decompiler crash matrix, var-split XOR & string-frag pool)
  • Tầng 17: Deceptive Debug Poisoning & Metadata Spoofing (Trạng thái nhiễm độc ngầm & giả lập module stdlib)
        """,
        epilog="""
VÍ DỤ SỬ DỤNG:
  1. Chạy CLI đơn file:
     python tr0ngx_obfuscator.py -i script.py -o obf_script.py -m 3 --compile y --velimatix y --kramer y

  2. Chạy CLI nhiều file / Batch Obfuscation:
     python tr0ngx_obfuscator.py -i file1.py file2.py file3.py -o dist/ -m 2 --compile y -w 4

  3. Chạy CLI toàn bộ thư mục (đệ quy):
     python tr0ngx_obfuscator.py -d src/ -o dist/ -r -m 2 --compile y --matrix y

  4. Chạy giao diện tương tác TUI (hỗ trợ chọn 1 file hoặc hàng loạt):
     python tr0ngx_obfuscator.py
        """
    )
    # File & Batch options
    parser.add_argument("-i", "--input", nargs="*", help="Đường dẫn một hoặc nhiều file Python / pattern glob cần obfuscate", default=None)
    parser.add_argument("-D", "--dir", "--directory", help="Đường dẫn thư mục chứa các file Python cần obfuscate hàng loạt", default=None)
    parser.add_argument("-r", "--recursive", action="store_true", help="Quét đệ quy tất cả thư mục con khi obfuscate thư mục")
    parser.add_argument("-o", "--output", help="Đường dẫn file kết quả (nếu 1 file) hoặc thư mục kết quả (nếu nhiều file)", default=None)
    parser.add_argument("-w", "--workers", "--jobs", "-j", type=int, default=None, help="Số luồng CPU xử lý song song khi obfuscate nhiều file")
    
    # Engine modes
    parser.add_argument("-m", "--mode", type=int, choices=[1, 2, 3], help="Cấp độ làm rối Trongdepzai AST (1: Cơ bản, 2: Nâng cao, 3: Cực đại)", default=None)
    parser.add_argument("--moreobf", choices=["y", "n", "Y", "N"], help="Bơm mã rác AST junk & try-except dead code (y/n)", default=None)
    parser.add_argument("--antidebug", choices=["y", "n", "Y", "N"], help="Kích hoạt khiên chống debug & anti-hook (y/n)", default=None)
    parser.add_argument("--antivm", choices=["y", "n", "Y", "N"], help="Kích hoạt khiên phát hiện máy ảo (Anti-VM & Sandbox Detection) (y/n)", default=None)
    parser.add_argument("--selfmod", choices=["y", "n", "Y", "N"], help="Thêm tầng mã tự biến đổi chữ ký khi chạy (y/n)", default=None)
    parser.add_argument("--compile", choices=["y", "n", "Y", "N"], help="Biên dịch bytecode đa tầng (marshal + XOR + zlib + bz2) (y/n)", default=None)
    
    # Cryptographic Authentication & Passwords
    parser.add_argument("--password", type=str, default=None, help="Mật khẩu mã hóa payload chuẩn Argon2id + ChaCha20Poly1305 AEAD")
    parser.add_argument("--password-file", type=str, default=None, help="Đường dẫn file chứa mật khẩu mã hóa (tránh lộ password qua tiến trình)")
    parser.add_argument("--max-output-size", default=None, help="Giới hạn dung lượng file output tối đa (vd: 10MB, 50MB, 10485760)")
    parser.add_argument("--seed", type=int, default=None, help="Seed số nguyên để sinh mã định danh mang tính tái lập (Reproducible deterministic build)")

    # Velimatix engine
    parser.add_argument("--velimatix", choices=["y", "n", "Y", "N"], help="Kích hoạt động cơ Velimatix AST (y/n)", default=None)
    parser.add_argument("--veli-level", type=int, choices=[1, 2, 3], help="Cấp độ Velimatix (1: BiOpaque, 2: Exception Jump, 3: Match-Case State Machine)", default=None)
    parser.add_argument("--double-compile", choices=["y", "n", "Y", "N"], help="Đóng gói kép (Trongdepzai bytecode bên trong loader Velimatix) (y/n)", default=None)
    
    # Outer layers & variables
    parser.add_argument("--kramer", choices=["y", "n", "Y", "N"], help="Bọc ngoài bằng khiên Kramer Kyrie Eleison (y/n)", default=None)
    parser.add_argument("--cjk-vars", choices=["y", "n", "Y", "N"], help="Sử dụng biến ký tự chữ Hán / CJK & docstring PyCool (y/n)", default=None)
    parser.add_argument("--force-py", help="Khóa chỉ cho phép chạy trên phiên bản Python chỉ định (vd: 3.10, 3.11, 3.12, 3.14) hoặc 'off'", default=None)
    
    # Debug & Environment controls
    parser.add_argument("--debug-map", nargs="?", const="AUTO", default=None, help="Xuất bản đồ ánh xạ ký hiệu & thời gian từng stage ra file JSON (vd: --debug-map map.json)")
    parser.add_argument("--debug", "-d", action="store_true", help="Bật chế độ debug chi tiết (in log micro-stages, traceback và cảnh báo lỗi)")
    parser.add_argument("--profile", action="store_true", help="Hiển thị bảng phân tích chi tiết hiệu năng (Profiling Waterfall & Bottleneck Analysis)")
    parser.add_argument("--log-file", type=str, default=None, help="Ghi toàn bộ log và chẩn đoán chi tiết ra file riêng (vd: --log-file debug.log)")
    parser.add_argument("--strict", action="store_true", help="Dừng tiến trình ngay khi gặp lỗi ở bất kỳ stage nào thay vì âm thầm bỏ qua")
    parser.add_argument("--no-art", "--quiet", "-q", action="store_true", help="Tắt banner ASCII art và hiệu ứng màu để chạy sạch trong CLI/Agent")
    
    # Resource limiting (RAM & CPU Cores)
    parser.add_argument("--max-ram", "--ram-limit", type=int, default=None, help="Giới hạn dung lượng RAM tối đa (MB) cho tiến trình (vd: --max-ram 2048)")
    parser.add_argument("--cores", "--threads", type=int, default=None, help="Giới hạn số CPU Cores/Threads sử dụng (vd: --cores 2)")

    # New obfuscation modes
    parser.add_argument("--matrix", "--fused", choices=["y", "n", "Y", "N"], help="Kich hoat Ma Tran Hoa Quyen Da Tang (Hybrid Blended Variables + Fused 3-Track Shield) (y/n)", default=None)
    parser.add_argument("--emoji-obf", choices=["y", "n", "Y", "N"], help="Ma hoa output thanh chuoi emoji sequence (y/n)", default=None)
    parser.add_argument("--homoglyph", choices=["y", "n", "Y", "N"], help="Dung ten bien Cyrillic/Greek trong giong ASCII (a->а, o->о) (y/n)", default=None)
    parser.add_argument("--rare-unicode", choices=["y", "n", "Y", "N"], help="Dung ky tu Unicode sieu hiem (CJK Extension B, Kangxi) (y/n)", default=None)
    parser.add_argument("--zalgo", "--combining-marks", "-z", choices=["y", "n", "Y", "N"], help="Kich hoat khien Zalgo Combining Marks chong cuc nhieu dau lam lag engine render GUI/Decompiler (y/n)", default=None)
    parser.add_argument("--whitespace-obf", choices=["y", "n", "Y", "N"], help="Mã hóa output thành khoảng trắng vô hình (space=0, tab=1) (y/n)", default=None)
    parser.add_argument("--blank-padding", "--blank-lines", choices=["y", "n", "Y", "N"], help="Chèn hàng trăm dòng khoảng trống trắng tinh ở đầu file (Screen Blanker Padding) (y/n)", default=None)
    parser.add_argument("--hyperion", choices=["y", "n", "Y", "N"], help="Kích hoạt Hyperion Engine (Builtins remapping + token variable remapping + math/str obfuscation + chunk shell) (y/n)", default=None)
    parser.add_argument("--camouflage", "--camo", choices=["y", "n", "Y", "N"], help="Kích hoạt lớp ngụy trang Hyperion Camouflage (Fake Scientific/Algorithmic Class simulation) (y/n)", default=None)
    parser.add_argument("--math-opaque", choices=["y", "n", "Y", "N"], help="Kích hoạt vị từ toán học mờ (Mathematical Opaque Predicates - Quadratic Non-Residue mod 7 & Euler invariants) (y/n)", default=None)
    parser.add_argument("--dyn-strings", choices=["y", "n", "Y", "N"], help="Mã hóa chuỗi động XOR cục bộ từng vị trí gọi (Per-callsite dynamic XOR string encryption) (y/n)", default=None)
    parser.add_argument("--anti-dump", choices=["y", "n", "Y", "N"], help="Kích hoạt khiên chống memory dump & lọc đối tượng GC (In-Memory Anti-Dump & GC Object Scrubber) (y/n)", default=None)
    parser.add_argument("--vm-obf", choices=["y", "n", "Y", "N"], help="Kích hoạt VM Virtualization Engine - biến đổi code thành bytecode ảo thực thi bởi CPU ảo đa hình (y/n)", default=None)
    parser.add_argument("--vm-level", type=int, choices=[1, 2, 3, 4], help="Cấp độ VM Virtualization (1: Basic, 2: + Traps/NOP, 3: + Dummy/Scrub, 4: + Per-Function ISA Keys)", default=None)
    parser.add_argument("--dec-trap", "--dectrap", choices=["y", "n", "Y", "N"], help="Kích hoạt bẫy điều khiển luồng Decompiler Traps (làm sập uncompyle6, decompyle3, pycdc) (y/n)", default=None)
    parser.add_argument("--var-split", choices=["y", "n", "Y", "N"], help="Phân rã biến số nguyên thành các mảnh bí mật XOR (Variable Secret Sharing) (y/n)", default=None)
    parser.add_argument("--str-frag", choices=["y", "n", "Y", "N"], help="Băm nhỏ chuỗi và nạp mồi nhử trong const pool (String Fragmentation & Decoy Pool) (y/n)", default=None)
    parser.add_argument("--debug-poison", choices=["y", "n", "Y", "N"], help="Kích hoạt trạng thái nhiễm độc ngầm Deceptive Debug Poisoning State Machine (y/n)", default=None)
    parser.add_argument("--spoof-meta", choices=["y", "n", "Y", "N"], help="Ngụy trang siêu dữ liệu và đường dẫn module stdlib (Metadata & co_filename Spoofing) (y/n)", default=None)
    parser.add_argument("--exotic-pools", choices=["y", "n", "Y", "N"], help="Identifier từ các pool Unicode cực hiếm (Tangut, Egyptian Hieroglyphs, CJK Ext G/H, Anatolian, Bamum, Glagolitic, Miao) - XID + NFKC validated (y/n)", default=None)
    parser.add_argument("--base4096", choices=["y", "n", "Y", "N"], help="Encode payload thanh stream glyph 12-bit tu block Unicode hiem (Base4096 exotic alphabet) (y/n)", default=None)
    parser.add_argument("--bit-matrix", choices=["y", "n", "Y", "N"], help="Bien doi byte da vong: LCG-XOR / bit rotation / nibble swap / S-Box permutation (y/n)", default=None)
    parser.add_argument("--lzma-layer", choices=["y", "n", "Y", "N"], help="Them lop nen LZMA (preset 9) truoc ma hoa AEAD - giam 10-25%% kich thuoc payload (y/n)", default=None)
    parser.add_argument("--env-key", choices=["y", "n", "Y", "N"], help="Khoa payload theo fingerprint phan cung (MAC/host/arch) - che do khong mat khau; sai may = that bai xac thuc (y/n)", default=None)
    parser.add_argument("--verify", choices=["y", "n", "Y", "N"], help="Chay song song file goc vs file obfuscated va so sanh stdout sau khi build (y/n)", default=None)
    parser.add_argument("--shared-symbols", choices=["y", "n", "Y", "N"], help="Batch mode: dong bo rename symbol xuyen module (two-phase shared map, Opy-style) (y/n)", default=None)

    cli_args, unknown = parser.parse_known_args()
    if unknown:
        for _u in unknown:
            if not str(_u).startswith("-"):
                continue
            print(f"[-] ERROR: unrecognized argument: {_u}", file=sys.stderr)
        sys.exit(2)
    is_cli_mode = bool(cli_args.input is not None or cli_args.dir is not None)

    if getattr(cli_args, 'debug', False):
        _EngineState.verbose_debug = True
    if getattr(cli_args, 'profile', False):
        _EngineState.profile_mode = True
    if getattr(cli_args, 'strict', False):
        _EngineState.strict_mode = True
    if getattr(cli_args, 'log_file', None):
        _EngineState.log_file_path = cli_args.log_file.strip().strip('"').strip("'")

    if cli_args.no_art or is_cli_mode:
        _EngineState.cli_quiet_mode = True

    targets = []
    is_batch = False
    custom_out = cli_args.output

    if is_cli_mode:
        targets = _resolve_input_files(inputs=cli_args.input, directory=cli_args.dir, recursive=cli_args.recursive)
        if not targets:
            _v(" [ERROR] CLI: Không tìm thấy bất kỳ file Python (.py) hợp lệ nào.")
            sys.exit(1)
        if len(targets) > 1 or cli_args.dir is not None:
            is_batch = True
    else:
        _v(" [!] TR0NGX FILE SELECTION / CHỌN CHẾ ĐỘ NHẬP:")
        _v("  1. SINGLE FILE (Mã hóa 1 file .py đơn lẻ)")
        _v("  2. BATCH FILES / DIRECTORY (Mã hóa hàng loạt nhiều file / thư mục / pattern)")
        file_mode_choice = _prompt_input(" Choose (1/2, default 1): ").strip()
        if file_mode_choice == "2":
            is_batch = True
            while True:
                batch_inp = _prompt_input(" ENTER DIRECTORY, GLOB PATTERN OR FILES (vd: src/, *.py, a.py, b.py): ").strip().strip('"').strip("'")
                rec_inp = _prompt_input(" RECURSIVE SUBDIRECTORIES? (y/n, default n): ").strip().upper()
                is_rec = (rec_inp == "Y")
                try:
                    targets = _resolve_input_files(inputs=batch_inp, directory=batch_inp if os.path.isdir(batch_inp) else None, recursive=is_rec)
                    if targets:
                        _v(_gradient_text(f" [i] Đã tìm thấy {len(targets)} file Python để obfuscate hàng loạt.", (0, 240, 255), (140, 80, 255)))
                        for t_idx, t in enumerate(targets[:10], 1):
                            _v(f"     {t_idx}. {t['rel']}")
                        if len(targets) > 10:
                            _v(f"     ... và {len(targets) - 10} file khác.")
                        break
                    else:
                        _v(" [!] Không tìm thấy file .py nào phù hợp. Vui lòng nhập lại.")
                except Exception as e:
                    _v(f" [!] Lỗi tìm file: {e}. Vui lòng nhập lại.")
            
            out_dir_inp = _prompt_input(" ENTER DESTINATION OUTPUT DIRECTORY (default: tr0ngx_dist/): ").strip().strip('"').strip("'")
            custom_out = out_dir_inp if out_dir_inp else "tr0ngx_dist"
        else:
            _file = _prompt_input(" ENTER FILE: ").strip().strip('"').strip("'")
            while True:
                try:
                    if not os.path.isfile(_file):
                        raise FileNotFoundError(f"File not found: {_file}")
                    with open(_file, "r", encoding="utf-8-sig", errors="replace") as file:
                        raw_code = file.read().lstrip('\ufeff')
                    _validate_input_source(raw_code)
                    ast.parse(raw_code)
                    targets = [{"src": os.path.abspath(_file), "rel": os.path.basename(_file)}]
                    break
                except Exception as e:
                    _v(f" SYNTAX/SECURITY ERROR: {e}")
                    _file = _prompt_input(" ENTER FILE AGAIN: ").strip().strip('"').strip("'")

    _setup = None
    if not is_cli_mode:
        _v(_gradient_text(" ╔══════════════════════════════════════════════════════════════════════╗", (0, 240, 255), (140, 80, 255)))
        _v(_gradient_text(" ║        TR0NGX ULTIMATE TUI - CẤU HÌNH BẢO VỆ MÃ NGUỒN PYTHON        ║", (0, 240, 255), (140, 80, 255)))
        _v(_gradient_text(" ╚══════════════════════════════════════════════════════════════════════╝", (0, 240, 255), (140, 80, 255)))
        _v("  1. FAST LITE PRESET      -- (Mode 1 AST + Dynamic Strings)")
        _v("  2. BALANCED PRESET       -- (Mode 2 + AEAD Compile + Velimatix L2 + Fused Matrix + Anti-Debug)")
        _v("  3. MAXIMUM ARSENAL       -- (Mode 3 + TVM 2.0 L3 + Fused Matrix + Camouflage + Zalgo +")
        _v("                              Math Opaque + Dyn Strings + Dec Traps + Var Split + Str Frag +")
        _v("                              Debug Poison + Spoof Meta + In-Memory Anti-Dump)")
        _v("  4. CUSTOM STEP-BY-STEP   -- (Tùy chỉnh chi tiết từng bước toàn bộ 17 tầng bảo vệ)")
        _setup = _prompt_input(" Choose profile (1/2/3/4, default 2): ").strip()
        if not _setup:
            _setup = "2"

        if _setup == "1":
            cli_args.mode = 1
            cli_args.moreobf = "N"
            cli_args.antidebug = "N"
            cli_args.antivm = "N"
            cli_args.selfmod = "N"
            cli_args.compile = "N"
            cli_args.velimatix = "N"
            cli_args.veli_level = 1
            cli_args.double_compile = "N"
            cli_args.kramer = "N"
            cli_args.cjk_vars = "N"
            cli_args.matrix = "N"
            cli_args.emoji_obf = "N"
            cli_args.homoglyph = "N"
            cli_args.rare_unicode = "N"
            cli_args.zalgo = "N"
            cli_args.whitespace_obf = "N"
            cli_args.blank_padding = "N"
            cli_args.hyperion = "N"
            cli_args.camouflage = "N"
            cli_args.math_opaque = "N"
            cli_args.dyn_strings = "Y"
            cli_args.anti_dump = "N"
            cli_args.vm_obf = "N"
            cli_args.vm_level = 1
            cli_args.dec_trap = "N"
            cli_args.var_split = "N"
            cli_args.str_frag = "N"
            cli_args.debug_poison = "N"
            cli_args.spoof_meta = "N"
            cli_args.force_py = "off"
        elif _setup == "2":
            cli_args.mode = 2
            cli_args.moreobf = "Y"
            cli_args.antidebug = "Y"
            cli_args.antivm = "Y"
            cli_args.selfmod = "N"
            cli_args.compile = "Y"
            cli_args.velimatix = "Y"
            cli_args.veli_level = 2
            cli_args.double_compile = "Y"
            cli_args.kramer = "N"
            cli_args.cjk_vars = "N"
            cli_args.matrix = "Y"
            cli_args.emoji_obf = "N"
            cli_args.homoglyph = "N"
            cli_args.rare_unicode = "N"
            cli_args.zalgo = "N"
            cli_args.whitespace_obf = "N"
            cli_args.blank_padding = "N"
            cli_args.hyperion = "N"
            cli_args.camouflage = "N"
            cli_args.math_opaque = "Y"
            cli_args.dyn_strings = "Y"
            cli_args.anti_dump = "Y"
            cli_args.vm_obf = "N"
            cli_args.vm_level = 1
            cli_args.dec_trap = "Y"
            cli_args.var_split = "Y"
            cli_args.str_frag = "Y"
            cli_args.debug_poison = "Y"
            cli_args.spoof_meta = "Y"
            cli_args.force_py = "off"
        elif _setup == "3":
            cli_args.mode = 3
            cli_args.moreobf = "Y"
            cli_args.antidebug = "Y"
            cli_args.antivm = "Y"
            cli_args.selfmod = "Y"
            cli_args.compile = "Y"
            cli_args.velimatix = "Y"
            cli_args.veli_level = 2
            cli_args.double_compile = "Y"
            cli_args.kramer = "N"
            cli_args.cjk_vars = "N"
            cli_args.matrix = "Y"
            cli_args.emoji_obf = "N"
            cli_args.homoglyph = "N"
            cli_args.rare_unicode = "N"
            cli_args.zalgo = "Y"
            cli_args.whitespace_obf = "N"
            cli_args.blank_padding = "N"
            cli_args.hyperion = "Y"
            cli_args.camouflage = "Y"
            cli_args.math_opaque = "Y"
            cli_args.dyn_strings = "Y"
            cli_args.anti_dump = "Y"
            cli_args.vm_obf = "Y"
            cli_args.vm_level = 3
            cli_args.dec_trap = "Y"
            cli_args.var_split = "Y"
            cli_args.str_frag = "Y"
            cli_args.debug_poison = "Y"
            cli_args.spoof_meta = "Y"
            cli_args.force_py = "off"

    # Resource capping and workers
    max_ram = cli_args.max_ram
    max_cores = cli_args.cores
    # FIX (audit P1): -w 0 previously fell through the falsy-or chain to auto;
    # zero is now rejected exactly like negative values.
    if cli_args.workers is not None and cli_args.workers < 1:
        print(f"[-] ERROR: --workers must be a positive integer (got: {cli_args.workers}).", file=sys.stderr)
        sys.exit(2)
    workers = cli_args.workers or max_cores or max(2, min(8, (os.cpu_count() or 4)))
    if not isinstance(workers, int) or workers < 1:
        print(f"[-] ERROR: --workers must be a positive integer (got: {workers}).", file=sys.stderr)
        sys.exit(2)

    # In-memory scrubbing: overwrite sensitive password in sys.argv to prevent procfs inspection
    for idx, arg in enumerate(sys.argv):
        if arg == '--password' and idx + 1 < len(sys.argv):
            sys.argv[idx + 1] = '*' * len(sys.argv[idx + 1])
        elif arg.startswith('--password='):
            sys.argv[idx] = '--password=' + ('*' * (len(arg) - 11))

    # 2. Mode
    if cli_args.mode is not None:
        mode = cli_args.mode
    else:
        while True:
            try:
                mode = int(_prompt_input(" ENTER MODE (1-3): "))
                if 1 <= mode <= 3:
                    break
                _v(" ENTER 1, 2, OR 3")
            except ValueError:
                _v(" INVALID INPUT")

    # 3. Flags
    moreobf = cli_args.moreobf or ("N" if is_cli_mode else _prompt_input(" MORE OBF? (y/n): "))
    antidebug = cli_args.antidebug or ("N" if is_cli_mode else _prompt_input(" ANTI DEBUG? (y/n): "))
    antivm = getattr(cli_args, 'antivm', None) or ("N" if is_cli_mode else _prompt_input(" ANTI VM & SANDBOX? (y/n): "))
    selfmodify = cli_args.selfmod or ("N" if is_cli_mode else _prompt_input(" SELF-MODIFYING CODE? (y/n): "))
    method = cli_args.compile or ("N" if is_cli_mode else _prompt_input(" COMPILE? (y/n): "))
    velimatix = cli_args.velimatix or ("N" if is_cli_mode else _prompt_input(" VELIMATIX ENGINE? (y/n): "))

    veli_level = 1
    if velimatix.upper() == "Y":
        if cli_args.veli_level is not None:
            veli_level = cli_args.veli_level
        else:
            if is_cli_mode:
                veli_level = 3
            else:
                while True:
                    try:
                        veli_level = int(_prompt_input(" VELIMATIX LEVEL (1-3): "))
                        if 1 <= veli_level <= 3:
                            break
                        _v(" ENTER 1, 2, OR 3")
                    except ValueError:
                        _v(" INVALID")

    double_compile = "N"
    if method.upper() == "Y" and velimatix.upper() == "Y":
        double_compile = cli_args.double_compile or ("Y" if is_cli_mode else _prompt_input(" DOUBLE COMPILE (Veli wrap)? (y/n): "))

    kramer_wrap_choice = cli_args.kramer or ("N" if is_cli_mode else _prompt_input(" KRAMER OUTER SHIELD (Kyrie Eleison)? (y/n): "))
    cjk_choice = cli_args.cjk_vars or ("N" if is_cli_mode else _prompt_input(" CJK CHINESE IDENTIFIERS & PYCOOL DOCSTRINGS? (y/n): "))

    # New Obfuscation Modes
    matrix_choice = cli_args.matrix or ("N" if is_cli_mode else _prompt_input(" MATRIX DEEP FUSION (Hybrid Variables + Fused 3-Track Shield)? (y/n): "))
    emoji_obf_choice = cli_args.emoji_obf or ("N" if is_cli_mode else _prompt_input(" EMOJI OBFUSCATION (code -> Animal emoji stream)? (y/n): "))
    homoglyph_choice = cli_args.homoglyph or ("N" if is_cli_mode else _prompt_input(" HOMOGLYPH NAMES (Cyrillic/Greek lookalikes: a/o/e)? (y/n): "))
    rare_unicode_choice = cli_args.rare_unicode or ("N" if is_cli_mode else _prompt_input(" RARE UNICODE NAMES (CJK Ext-B Ancient glyphs)? (y/n): "))
    zalgo_choice = getattr(cli_args, 'zalgo', None) or ("N" if is_cli_mode else _prompt_input(" ZALGO COMBINING MARKS (Extreme Diacritics Cascade)? (y/n): "))
    whitespace_obf_choice = cli_args.whitespace_obf or ("N" if is_cli_mode else _prompt_input(" WHITESPACE OBFUSCATION (code -> Invisible space/tab)? (y/n): "))
    blank_padding_choice = getattr(cli_args, 'blank_padding', None) or getattr(cli_args, 'blank_lines', None) or ("N" if is_cli_mode else _prompt_input(" BLANK LINES PADDING (Screen Blanker 300+ empty lines)? (y/n): "))
    hyperion_choice = getattr(cli_args, 'hyperion', None) or ("N" if is_cli_mode else _prompt_input(" HYPERION ENGINE (Builtin/Import/Var token remap + Chunk shell)? (y/n): "))
    camouflage_choice = getattr(cli_args, 'camouflage', None) or ("N" if is_cli_mode else _prompt_input(" HYPERION CAMOUFLAGE (Fake Scientific Simulation Class)? (y/n): "))
    math_opaque_choice = getattr(cli_args, 'math_opaque', None) or ("N" if is_cli_mode else _prompt_input(" MATHEMATICAL OPAQUE PREDICATES (Number theory invariants)? (y/n): "))
    dyn_strings_choice = getattr(cli_args, 'dyn_strings', None) or ("N" if is_cli_mode else _prompt_input(" DYNAMIC PER-CALLSITE STRING XOR (Zero global table)? (y/n): "))
    antidump_choice = getattr(cli_args, 'anti_dump', None) or ("N" if is_cli_mode else _prompt_input(" IN-MEMORY ANTI-DUMP & GC SCRUBBER? (y/n): "))
    vm_obf_choice = getattr(cli_args, 'vm_obf', None) or ("N" if is_cli_mode else _prompt_input(" VM VIRTUALIZATION ENGINE? (y/n): "))
    vm_level_choice = getattr(cli_args, 'vm_level', None) or 1
    dectrap_choice = getattr(cli_args, 'dec_trap', None) or getattr(cli_args, 'dectrap', None) or ("N" if is_cli_mode else _prompt_input(" DECOMPILER TRAPS (Break uncompyle6/decompyle3/pycdc)? (y/n): "))
    varsplit_choice = getattr(cli_args, 'var_split', None) or ("N" if is_cli_mode else _prompt_input(" VARIABLE SECRET SHARING (XOR Split local ints)? (y/n): "))
    strfrag_choice = getattr(cli_args, 'str_frag', None) or ("N" if is_cli_mode else _prompt_input(" STRING FRAGMENTATION (Decoy pool + dynamic assembly)? (y/n): "))
    debugpoison_choice = getattr(cli_args, 'debug_poison', None) or ("N" if is_cli_mode else _prompt_input(" DECEPTIVE DEBUG POISONING (Silent key degradation)? (y/n): "))
    spoofmeta_choice = getattr(cli_args, 'spoof_meta', None) or ("N" if is_cli_mode else _prompt_input(" METADATA & CO_FILENAME SPOOFING? (y/n): "))
    exotic_pools_choice = getattr(cli_args, 'exotic_pools', None) or ("N" if is_cli_mode else _prompt_input(" EXOTIC UNICODE POOLS (Tangut/Egyptian/CJK-ExtG identifiers)? (y/n): "))
    base4096_choice = getattr(cli_args, 'base4096', None) or ("N" if is_cli_mode else _prompt_input(" BASE4096 GLYPH ENCODING (12-bit astral stream)? (y/n): "))
    bit_matrix_choice = getattr(cli_args, 'bit_matrix', None) or ("N" if is_cli_mode else _prompt_input(" BIT-MATRIX BYTE TRANSFORM (SBox/rotation/LCG)? (y/n): "))
    lzma_layer_choice = getattr(cli_args, 'lzma_layer', None) or "N"
    env_key_choice = getattr(cli_args, 'env_key', None) or "N"
    verify_mode_choice = getattr(cli_args, 'verify', None) or "N"
    _EngineState.lzma_layer = lzma_layer_choice.upper() == "Y"
    _EngineState.env_key_lock = env_key_choice.upper() == "Y"
    _EngineState.verify_mode = verify_mode_choice.upper() == "Y"

    # Force Python version
    if cli_args.force_py is not None:
        if cli_args.force_py.lower() in ["n", "no", "off", "none"]:
            force_py_choice = "N"
            forced_py_ver = ""
        else:
            # FIX (audit P1): invalid versions like 'banana' previously passed
            # through and made every runtime guard vacuously true.
            import re as _re_fp
            if not _re_fp.fullmatch(r"\d+\.\d+(\.\d+)?", cli_args.force_py.strip()):
                print(f"[-] ERROR: --force-py expects a version like 3.10 / 3.11.4 (got: {cli_args.force_py!r}).", file=sys.stderr)
                sys.exit(2)
            force_py_choice = "Y"
            forced_py_ver = cli_args.force_py.strip()
    else:
        if is_cli_mode:
            force_py_choice = "N"
            forced_py_ver = ""
        else:
            force_py_choice = _prompt_input(" FORCE PYTHON VERSION? (y/n): ")
            forced_py_ver = ""
            if force_py_choice.upper() == "Y":
                cur_v = f"{sys.version_info.major}.{sys.version_info.minor}"
                forced_py_ver = _prompt_input(f" ENTER PY VERSION (default {cur_v}): ").strip()
                if not forced_py_ver:
                    forced_py_ver = cur_v

    # Debug Map
    debug_map_arg = cli_args.debug_map
    if debug_map_arg is None and not is_cli_mode and _setup != "1":
        dbg_choice = _prompt_input(" GENERATE DEBUG MAP (.json)? (y/n): ")
        if dbg_choice.upper() == "Y":
            debug_map_arg = "AUTO"

    # Resource limits in interactive prompt if not passed
    if not is_cli_mode and max_ram is None and _setup != "1":
        ram_inp = _prompt_input(" MAX RAM LIMIT IN MB (press Enter for unlimited): ").strip()
        if ram_inp.isdigit():
            max_ram = int(ram_inp)
    if not is_cli_mode and max_cores is None and _setup != "1":
        core_inp = _prompt_input(" MAX CPU CORES (press Enter for auto): ").strip()
        if core_inp.isdigit():
            max_cores = int(core_inp)

    # Custom Output Path in interactive prompt if not passed and single file
    if not is_cli_mode and not is_batch and custom_out is None and _setup != "1":
        out_inp = _prompt_input(" CUSTOM OUTPUT PATH (press Enter for default): ").strip()
        if out_inp:
            custom_out = out_inp

    # Password resolution
    password = cli_args.password
    if cli_args.password_file:
        if not os.path.isfile(cli_args.password_file):
            print(f"[-] ERROR: --password-file not found: {cli_args.password_file}", file=sys.stderr)
            sys.exit(2)
        try:
            with open(cli_args.password_file, "r", encoding="utf-8") as pf:
                password = pf.read().strip()
        except Exception as e:
            print(f"[-] ERROR: cannot read --password-file: {e}", file=sys.stderr)
            sys.exit(2)
        if not password:
            print("[-] ERROR: --password-file is empty.", file=sys.stderr)
            sys.exit(2)
    if not password and os.environ.get("TR0NGX_PASSWORD"):
        password = os.environ.get("TR0NGX_PASSWORD")
    if not password and not is_cli_mode and method.upper() == "Y" and _setup != "1":
        pwd_inp = _prompt_input(" PASSWORD ENCRYPTION (press Enter for obfuscation-only): ", secret=True).strip()
        if pwd_inp:
            password = pwd_inp
    _EngineState.encryption_password = password
    if _EngineState.env_key_lock and password:
        # Mutually exclusive trust roots: password = portable secret, env-key =
        # machine-bound. Combining them silently would weaken the documented
        # semantics of both; prefer the stronger portable mode.
        print("[TR0NGX] [WARN] --env-key is incompatible with --password; hardware lock disabled.", flush=True)
        _EngineState.env_key_lock = False

    if cli_args.seed is not None:
        _EngineState.custom_seed = cli_args.seed
        random.seed(cli_args.seed)

    max_output_size_bytes = _parse_size_str(cli_args.max_output_size)
    _EngineState.max_output_size = max_output_size_bytes

    _apply_resource_limits(max_ram, max_cores)

    return {
        "targets": targets,
        "is_batch": is_batch,
        "mode": mode,
        "moreobf": moreobf,
        "antidebug": antidebug,
        "antivm": antivm,
        "selfmodify": selfmodify,
        "method": method,
        "password": password,
        "seed": cli_args.seed,
        "max_output_size": max_output_size_bytes,
        "velimatix": velimatix,
        "veli_level": veli_level,
        "double_compile": double_compile,
        "kramer": kramer_wrap_choice,
        "cjk": cjk_choice,
        "matrix": matrix_choice,
        "emoji_obf": emoji_obf_choice,
        "homoglyph": homoglyph_choice,
        "rare_unicode": rare_unicode_choice,
        "zalgo": zalgo_choice,
        "whitespace_obf": whitespace_obf_choice,
        "blank_padding": blank_padding_choice,
        "hyperion": hyperion_choice,
        "camouflage": camouflage_choice,
        "math_opaque": math_opaque_choice,
        "dyn_strings": dyn_strings_choice,
        "anti_dump": antidump_choice,
        "vm_obf": vm_obf_choice,
        "vm_level": vm_level_choice,
        "dec_trap": dectrap_choice,
        "var_split": varsplit_choice,
        "str_frag": strfrag_choice,
        "debug_poison": debugpoison_choice,
        "spoof_meta": spoofmeta_choice,
        "exotic_pools": exotic_pools_choice,
        "base4096": base4096_choice,
        "bit_matrix": bit_matrix_choice,
        "lzma_layer": lzma_layer_choice,
        "env_key": env_key_choice,
        "verify": verify_mode_choice,
        "shared_symbols": getattr(cli_args, 'shared_symbols', None) or "N",
        "force_py_choice": force_py_choice,
        "forced_py_ver": forced_py_ver,
        "debug_map": debug_map_arg,
        "max_ram": max_ram,
        "max_cores": max_cores,
        "workers": workers,
        "custom_out": custom_out
    }

def _reset_global_state():
    """Reset global state between runs."""
    global _used_names, _DEBUG_MAP, _LOG_ENTRIES, _STAGE_ERRORS
    with _used_names_lock:
        _used_names.clear()
    _RareChars.pool = None
    BiOpaqueUtils.possible_args = []
    BiOpaqueUtils.possible_functions = []
    BiOpaqueUtils.alphabet = ""
    BiOpaqueUtils.length = 16
    BiOpaqueUtils.safe_mode = False
    MutatorUtils.alphabet = ""
    MutatorUtils.length = 16
    ExceptionJumpUtils.alphabet = ""
    ExceptionJumpUtils.length = 16
    ControlFlowUtils.alphabet = ""
    ControlFlowUtils.length = 16
    _EngineState.use_cjk_names = False
    _EngineState.use_homoglyph_names = False
    _EngineState.use_rare_unicode_names = False
    _EngineState.use_zalgo_marks = False
    _EngineState.use_hyperion = False
    _EngineState.use_camouflage = False
    _EngineState.use_fused_names = False
    _EngineState.use_exotic_pools = None
    _LOG_ENTRIES.clear()
    _STAGE_ERRORS.clear()
    _DEBUG_MAP["renamed_functions"].clear()
    _DEBUG_MAP["renamed_builtins"].clear()
    _DEBUG_MAP["renamed_variables"].clear()
    _DEBUG_MAP["stages"].clear()
    _DEBUG_MAP["errors"].clear()

_EXOTIC_POOL_CACHE = []
_EngineState.use_fused_names = False
_EngineState.use_exotic_pools = None

_PYVER_TAG = f"{sys.version_info.major}.{sys.version_info.minor}"

def _gen_exotic_name(scope='general'):
    """Draw identifiers from rare Unicode script pools (Tangut, Egyptian Hieroglyphs,
    CJK Ext G/H, Anatolian, Bamum, Glagolitic, Miao, Vedic) with full XID + NFKC
    collision validation via tr0ngx_exotic."""
    global _EXOTIC_POOL_CACHE
    import unicodedata as _ud
    try:
        import tr0ngx_exotic as _tex
    except ImportError:
        return None
    if getattr(_EngineState, "used_nfkc", None) is None:
        _EngineState.used_nfkc = set()
    for _ in range(64):
        if not _EXOTIC_POOL_CACHE:
            kinds = _tex.pool_kinds()
            kind = _trx_choice(kinds)
            _EXOTIC_POOL_CACHE.extend(_tex.build_identifier_pool(kind, 128, random))
        name = _EXOTIC_POOL_CACHE.pop()
        norm = _ud.normalize("NFKC", name)
        with _used_names_lock:
            if name in _used_names or norm in _EngineState.used_nfkc:
                continue
            _used_names.add(name)
        _EngineState.used_nfkc.add(norm)
        return name
    return None

def obfuscate_single_target(src_file: str, output_file: str, options: dict, quiet_progress: bool = False) -> dict:
    """
    Core transformation engine that executes the entire Tr0ngX pipeline on a single file.
    Returns metrics dict with status, file sizes, ratio, and timing.
    """
    global _SEEDED_RNG
    with _obf_execution_lock:
        # Per-target isolation: reset cross-file global state so batch debug maps,
        # used-name pools and stage errors never contaminate between files.
        _DEBUG_MAP["stages"] = []
        _DEBUG_MAP["errors"] = []
        _DEBUG_MAP["renamed_functions"] = {}
        _DEBUG_MAP["renamed_builtins"] = {}
        _DEBUG_MAP["renamed_variables"] = {}
        _DEBUG_MAP["skipped_renames"] = []
        while _STAGE_ERRORS:
            _STAGE_ERRORS.pop()
        with _used_names_lock:
            _used_names.clear()
        # Cross-module shared-symbol contract (--shared-symbols): install the
        # frozen map for this target while holding the pipeline lock.
        _FROZEN_NAME_MAP.clear()
        _frozen = options.get("shared_symbol_map")
        if isinstance(_frozen, dict):
            _FROZEN_NAME_MAP.update(_frozen)
        if options.get("seed") is not None:
            # Deterministic per-file seeding (independent of worker scheduling)
            _s_seed = options["seed"] + sum(src_file.encode("utf-8"))
            random.seed(_s_seed)
            _SEEDED_RNG = random.Random(_s_seed ^ 0x5EED5EED)
            # Regenerate import-time helper names + global var-block template
            # under this file's seed so artifacts are reproducible (audit fix:
            # previously both baked OS entropy captured at module import).
            try:
                _refresh_runtime_symbols()
                _generate_var_block()
            except Exception:
                pass
        else:
            _SEEDED_RNG = None
        return _obfuscate_single_target_core(src_file, output_file, options, quiet_progress=quiet_progress)
        return _obfuscate_single_target_core(src_file, output_file, options, quiet_progress=quiet_progress)

def _obfuscate_single_target_core(src_file: str, output_file: str, options: dict, quiet_progress: bool = False) -> dict:
    start_time = time.time()
    try:
        with open(src_file, "r", encoding="utf-8-sig", errors="replace") as f:
            code = f.read().lstrip('\ufeff')
        _validate_input_source(code)
        original_size = len(code.encode('utf-8'))
    except Exception as e:
        _log_stage_error("0_read_source_file", e)
        return {
            "success": False,
            "src": src_file,
            "out": output_file,
            "original_size": 0,
            "output_size": 0,
            "ratio": 0.0,
            "elapsed": round(time.time() - start_time, 4),
            "error": str(e)
        }

    mode = options["mode"]
    moreobf = options.get("moreobf", "N")
    antidebug = options.get("antidebug", "N")
    antivm = options.get("antivm", "N")
    selfmodify = options.get("selfmodify", "N")
    method = options.get("method", "N")
    encryption_password = options.get("password")
    custom_seed = options.get("seed")
    max_output_size = options.get("max_output_size")
    velimatix = options.get("velimatix", "N")
    veli_level = options.get("veli_level", 1)
    double_compile = options.get("double_compile", "N")
    kramer_wrap_choice = options.get("kramer", "N")
    cjk_choice = options.get("cjk", "N")
    matrix_choice = options.get("matrix", "N")
    emoji_obf_choice = options.get("emoji_obf", "N")
    homoglyph_choice = options.get("homoglyph", "N")
    rare_unicode_choice = options.get("rare_unicode", "N")
    zalgo_choice = options.get("zalgo", "N")
    whitespace_obf_choice = options.get("whitespace_obf", "N")
    blank_padding_choice = options.get("blank_padding", "N")
    hyperion_choice = options.get("hyperion", "N")
    camouflage_choice = options.get("camouflage", "N")
    math_opaque_choice = options.get("math_opaque", "N")
    dyn_strings_choice = options.get("dyn_strings", "N")
    antidump_choice = options.get("anti_dump", "N")
    vm_obf_choice = options.get("vm_obf", "N")
    vm_level_choice = options.get("vm_level", 1)
    dectrap_choice = options.get("dec_trap", "N")
    varsplit_choice = options.get("var_split", "N")
    strfrag_choice = options.get("str_frag", "N")
    debugpoison_choice = options.get("debug_poison", "N")
    spoofmeta_choice = options.get("spoof_meta", "N")
    exotic_pools_choice = options.get("exotic_pools", "N")
    base4096_choice = options.get("base4096", "N")
    bit_matrix_choice = options.get("bit_matrix", "N")
    _EngineState.lzma_layer = str(options.get("lzma_layer", "N")).upper() == "Y"
    _EngineState.env_key_lock = str(options.get("env_key", "N")).upper() == "Y" and not options.get("password")
    force_py_choice = options.get("force_py_choice", "N")
    forced_py_ver = options.get("forced_py_ver", "")
    _debug_map_choice = options.get("debug_map")

    # Step 0: Hyperion AST & Token Engine
    if hyperion_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step(0, 8, "Hyperion Token & AST Remapping Engine...")
            code = _hyperion_full_transform(code, camouflage=False, shell=False, randlines=False)
            _track_debug_stage("0_hyperion_engine", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("0_hyperion_engine", e)

    # Step 1: Syntax transform
    try:
        t0 = time.time()
        sz0 = len(code)
        if not quiet_progress: _v_step(1, 8, "Syntax transformation...")
        code = _syntax(code)
        _track_debug_stage("1_syntax_transform", time.time() - t0, sz0, len(code))
    except Exception as e:
        _log_stage_error("1_syntax_transform", e)

    # Step 2: AST junk injection
    if moreobf.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step(2, 8, "AST junk injection...")
            code = __moreobf(code)
            _track_debug_stage("2_ast_junk_injection", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2_ast_junk_injection", e)

    # Step 2.3: Variable Secret Sharing (Var Split)
    if varsplit_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.3", 8, "Integer Variable Secret Sharing (XOR Split)...")
            code = _var_split_obf(code, seed=custom_seed)
            _track_debug_stage("2.3_var_split_secret_sharing", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.3_var_split_secret_sharing", e)

    # Step 2.4: Decompiler Trapping Matrix
    if dectrap_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.4", 8, "Decompiler Control Flow Traps (uncompyle6/decompyle3/pycdc breaker)...")
            code = _dec_trap_obf(code, density=0.6, seed=custom_seed)
            _track_debug_stage("2.4_decompiler_traps", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.4_decompiler_traps", e)

    # Step 2.5: Mathematical Opaque Predicates
    if math_opaque_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.5", 8, "Mathematical Opaque Predicates (Quadratic Non-Residue mod 7 & Euler invariants)...")
            code = _math_opaque_obf(code)
            _track_debug_stage("2.5_math_opaque_predicates", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.5_math_opaque_predicates", e)

    # Step 2.7: Dynamic Per-Callsite String XOR
    if dyn_strings_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.7", 8, "Dynamic Per-Callsite String XOR Encryption...")
            code = _dyn_strings_obf(code, seed=custom_seed)
            _track_debug_stage("2.7_dyn_strings_encryption", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.7_dyn_strings_encryption", e)

    # Step 2.8: String Fragmentation & Decoy Pool
    if strfrag_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            if not quiet_progress: _v_step("2.8", 8, "String Fragmentation & Decoy Pool (strfrag2)...")
            code = _str_frag_obf(code, seed=custom_seed)
            _track_debug_stage("2.8_str_frag_pool", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.8_str_frag_pool", e)

    # Step 3: Version check header
    target_ver_str = forced_py_ver if (force_py_choice.upper() == "Y" and forced_py_ver) else f"{sys.version_info.major}.{sys.version_info.minor}"
    checkver = _generate_strict_version_guard(target_ver_str)

    if cjk_choice.upper() == "Y":
        pycool_hdr = _gen_pycool_header()
        author = pycool_hdr + f"""((
    ((([["TR0NGX x VELIMATIX x PYCOOL MAXIMUM POWER"],
    ["https://github.com/Tr0ngX"],
    ["PYTHON AST OBFUSCATOR v4.0 - PYCOOL CJK EDITION"],
    3.11
    ],
    [__import__("builtins").exec(
    {checkver.encode()})
    ])
    )
    )
    )
)
"""
    else:
        author = f"""((
    ((([["TR0NGX x VELIMATIX MAXIMUM POWER"],
    ["https://github.com/Tr0ngX"],
    ["PYTHON AST OBFUSCATOR v4.0"],
    3.11
    ],
    [__import__("builtins").exec(
    {checkver.encode()})
    ])
    )
    )
    )
)
"""

    # Step 4: Velimatix Engine
    if velimatix.upper() == "Y":
        if not quiet_progress: _v_step(3, 8, f"Velimatix engine (level {veli_level})...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _velimatix_obf(code, mode=veli_level)
            _track_debug_stage(f"3_velimatix_level_{veli_level}", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error(f"3_velimatix_level_{veli_level}", e)

    # Step 5: Main Obfuscation Layers
    if not quiet_progress: _v_step(4, 8, f"Applying {mode}-layer tr0ngx obfuscation...")
    for i in range(mode):
        try:
            t0 = time.time()
            sz0 = len(code)
            new_code = obf(code, layer=i + 1)
            code = new_code
            _track_debug_stage(f"4_tr0ngx_layer_{i+1}_of_{mode}", time.time() - t0, sz0, len(code))
            if not quiet_progress: _v(f"        - Layer {i + 1}/{mode} complete")
        except Exception as e:
            _log_stage_error(f"4_tr0ngx_layer_{i+1}_of_{mode}", e)
            break

    # Step 6: Anti-Debug, Anti-VM, Anti-Dump, Self-Mod
    if antidebug.upper() == "Y":
        if not quiet_progress: _v_step(5, 8, "Injecting anti-debug shield...")
        t0 = time.time()
        sz0 = len(code)
        if velimatix.upper() == "Y":
            code = velimatix_anti_hook + code
        code = anti + code
        _track_debug_stage("5_anti_debug_injection", time.time() - t0, sz0, len(code))

    if antivm.upper() == "Y":
        if not quiet_progress: _v_step("5.2", 8, "Injecting Anti-VM & Sandbox shield...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_anti_vm_shield() + code
        _track_debug_stage("5.2_anti_vm_injection", time.time() - t0, sz0, len(code))

    if antidump_choice.upper() == "Y":
        if not quiet_progress: _v_step("5.4", 8, "Injecting In-Memory Anti-Dump & GC Scrubber shield...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_anti_dump_shield() + code
        _track_debug_stage("5.4_anti_dump_shield", time.time() - t0, sz0, len(code))

    if selfmodify.upper() == "Y":
        if not quiet_progress: _v_step("5.5", 8, "Adding self-modifying layer...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_self_modify_wrapper() + code
        _track_debug_stage("5.5_self_modify_layer", time.time() - t0, sz0, len(code))

    if debugpoison_choice.upper() == "Y":
        if not quiet_progress: _v_step("5.6", 8, "Injecting Deceptive Debug Poison State Machine...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_debug_poison_shield() + code
        _track_debug_stage("5.6_debug_poison_shield", time.time() - t0, sz0, len(code))

    # Step 6.5: VM Virtualization Engine
    if vm_obf_choice.upper() == "Y":
        if not quiet_progress: _v_step("6.5", 8, f"VM Virtualization Engine (level {vm_level_choice})...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _vm_obfuscate(code, seed=custom_seed, vm_level=int(vm_level_choice))
            _track_debug_stage("6.5_optimization_pass", time.time() - t0, sz0, len(code), details={"tier": vm_level_choice})
        except Exception as e:
            _log_stage_error("6.5_optimization_pass", e)

    # Step 8: Packaging & Compilation
    if method.upper() != "Y":
        if not quiet_progress: _v_step(6, 8, "Building non-compiled output...")
        t0 = time.time()
        sz0 = len(code)
        code = author + var + code
        if moreobf.upper() == "Y":
            try: code = __moreobf(code)
            except Exception: pass
        if velimatix.upper() == "Y" and veli_level >= 2:
            try: code = OBF_Spam(code, level=min(veli_level, 2))
            except Exception: pass
        _track_debug_stage("6_non_compiled_packaging", time.time() - t0, sz0, len(code))
    else:
        if not quiet_progress: _v_step(6, 8, "Multi-layer compilation...")
        t0 = time.time()
        sz0 = len(code)
        if moreobf.upper() == "Y":
            try: code = __moreobf(code)
            except Exception: pass
        code = ANTI_PYCDC + code

        if double_compile.upper() == "Y":
            if not quiet_progress: _v_step(7, 8, "DOUBLE COMPILE (Tr0ngX + Velimatix)...")
            try:
                code = _double_compile(var + code, target_ver=target_ver_str, password=encryption_password)
                _track_debug_stage("7_double_compile_packaging", time.time() - t0, sz0, len(code))
            except Exception as e:
                _log_stage_error("7_double_compile_packaging", e)
                double_compile = "N"

        if double_compile.upper() != "Y":
            try:
                compiled_bytes = marshal.dumps(compile(code, "<tr0ngx>", "exec"))
            except SyntaxError as e:
                _log_stage_error("7_compile_syntax_error", e)
                code = var + code
                _safe_atomic_write(output_file, str(code), input_file=src_file)
                return {"success": True, "src": src_file, "out": output_file, "original_size": original_size, "output_size": len(code.encode('utf-8')), "ratio": 1.0, "elapsed": round(time.time()-start_time, 4), "error": None}

            encrypted_data, _salt, _armor = _multi_layer_encrypt(compiled_bytes, password=encryption_password)
            _armor_dec = _armor['dec']
            _armor_rev = "[::-1]" if _armor['rev'] else ""
            if _armor['lzma']:
                _lzma_import = ", lzma"
                _lzma_var = rd()
                _lzma_extra = f"{_lzma_var} = getattr({___import__}({obfstr('lzma')}), {obfstr('decompress')})" + chr(10) + f"    _step5 = {_lzma_var}(_step5)"
            else:
                _lzma_import = ""
                _lzma_extra = ""
            if _EngineState.env_key_lock and not encryption_password:
                _envkey_unmask_std = chr(10).join([
                    "    try:",
                    "        import uuid as _trx_u",
                    "        _trx_fp = hashlib.sha256(('|'.join([str(_trx_u.getnode()), _platform.system(), _platform.machine(), _platform.python_implementation(), str(sys.version_info.major) + '.' + str(sys.version_info.minor)])).encode()).digest()",
                    "        salt = bytes(salt[i] ^ _trx_fp[i] for i in range(16))",
                    "    except Exception:",
                    "        raise SystemExit(1)",
                ])
            else:
                _envkey_unmask_std = "# portable build: no hardware binding"
            l = len(encrypted_data)
            num_parts = 8
            parts = [repr(encrypted_data[(l*k)//num_parts : (l*(k+1))//num_parts]) for k in range(num_parts)]
            part_vars = [rd() for _ in range(num_parts)]
            part_assignments = '\n'.join(f"{part_vars[k]}  {'  '*500}={parts[k]}" for k in range(num_parts))
            part_concat = '+'.join(part_vars)

            _en_var, _july_var, _birth_var, _b85_var = rd(), rd(), rd(), rd()
            if encryption_password:
                _auth_dec_section = f"""
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

_pwd = __import__("os").environ.get("TR0NGX_PASSWORD")
if not _pwd:
    import getpass as _gp
    _pwd = _gp.getpass("[TR0NGX] Enter decryption password: ")
"""
                _auth_dec_call = "_auth_decrypt(_step3, _pwd)"
            else:
                _auth_dec_section = f"""
def _derive_runtime_keys(salt):
    _parts = []
    _parts.append(sys.version[:5].encode())
    _parts.append(_platform.python_implementation().encode())
    _parts.append(salt)
    _parts.append(str(sys.maxsize).encode())
    _parts.append(sys.byteorder.encode())
    _combined = b''.join(_parts)
    _enc_k = hashlib.sha256(_combined + b'__enc__').digest()
    return _enc_k

def _auth_decrypt(raw_bytes):
    magic = raw_bytes[:4]
    salt = raw_bytes[4:20]
{_envkey_unmask_std}
    _enc_k = _derive_runtime_keys(salt)
    ke = hashlib.pbkdf2_hmac('sha256', salt, _enc_k, 50000, 32)
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
"""
                _auth_dec_call = "_auth_decrypt(_step3)"

            code = author + var + f"""
import hashlib, hmac, platform as _platform, sys, os{_lzma_import}
sys.dont_write_bytecode = True
{_generate_strict_version_guard(target_ver_str)}

{_auth_dec_section}

{_en_var} = getattr({___import__}({obfstr("marshal")}), {obfstr("loads")})
{_july_var} = getattr({___import__}({obfstr("zlib")}), {obfstr("decompress")})
{_birth_var} = getattr({___import__}({obfstr("bz2")}), {obfstr("decompress")})
{_b85_var} = getattr({___import__}({obfstr("base64")}), {obfstr(_armor_dec)})

{part_assignments}

try:
    _payload = {part_concat}
    _step1 = {_b85_var}(_payload{_armor_rev})
    _step2 = {_july_var}(_step1)
    _step3 = {_birth_var}(_step2)
    _step4 = {_auth_dec_call}
    _step5 = {_july_var}(_step4)
    {_lzma_extra}
    exec({_en_var}(_step5), globals(), globals())
    del _payload, _step1, _step2, _step3, _step4, _step5
except Exception as _e:
    raise _e
"""
            if velimatix.upper() == "Y" and veli_level >= 2:
                try: code = OBF_Spam(code, level=1)
                except Exception: pass
            _track_debug_stage("7_standard_compile_packaging", time.time() - t0, sz0, len(code))

    # Outer Shield Matrix & Camouflage
    multi_shield_count = sum(1 for c in [kramer_wrap_choice, emoji_obf_choice, whitespace_obf_choice] if c.upper() == "Y")
    is_fused_shield = (matrix_choice.upper() == "Y") or (multi_shield_count >= 2)

    if camouflage_choice.upper() == "Y":
        if not quiet_progress: _v(" [12] Applying Hyperion Scientific Class Camouflage...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _hyperion_camouflage(code)
            _track_debug_stage("12_hyperion_camouflage", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("12_hyperion_camouflage", e)

    if bit_matrix_choice.upper() == "Y" or base4096_choice.upper() == "Y":
        if not quiet_progress: _v(" [11.5] Applying Exotic Byte/Glyph Encoding (BitMatrix + Base4096)...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _exotic_payload_wrap(code, use_bitmatrix=(bit_matrix_choice.upper() == "Y"), use_base4096=(base4096_choice.upper() == "Y"))
            _track_debug_stage("11.5_exotic_payload_wrap", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("11.5_exotic_payload_wrap", e)

    if is_fused_shield:
        if not quiet_progress: _v(" [9/9] Applying Fused Matrix Shield (Kyrie + Emoji + Whitespace Symbiotic)...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _fused_matrix_wrap(code)
            _track_debug_stage("8_fused_matrix_shield", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("8_fused_matrix_shield", e)
    else:
        if kramer_wrap_choice.upper() == "Y":
            if not quiet_progress: _v(" [9/9] Applying Kramer Outer Shield (Kyrie Eleison)...")
            try:
                t0 = time.time()
                sz0 = len(code)
                code = _kramer_wrap(code)
                _track_debug_stage("8_kramer_outer_shield", time.time() - t0, sz0, len(code))
            except Exception as e:
                _log_stage_error("8_kramer_outer_shield", e)

        if emoji_obf_choice.upper() == "Y":
            try:
                t0 = time.time()
                sz0 = len(code)
                code = _emoji_encode_v2(code) if method.upper() == "Y" else _emoji_encode(code)
                _track_debug_stage("9_emoji_obfuscation", time.time() - t0, sz0, len(code))
            except Exception as e:
                _log_stage_error("9_emoji_obfuscation", e)

        if whitespace_obf_choice.upper() == "Y":
            try:
                t0 = time.time()
                sz0 = len(code)
                code = _whitespace_encode_v2(code) if method.upper() == "Y" else _whitespace_encode(code)
                _track_debug_stage("10_whitespace_obfuscation", time.time() - t0, sz0, len(code))
            except Exception as e:
                _log_stage_error("10_whitespace_obfuscation", e)

    if spoofmeta_choice.upper() == "Y":
        if not quiet_progress: _v(" [12.5] Injecting Metadata Spoofing & Signature Debranding...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _generate_spoof_meta_shield() + code
            _track_debug_stage("12.5_spoof_meta_shield", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("12.5_spoof_meta_shield", e)

    _blank_pad = ("\n" * 300) if blank_padding_choice.upper() == "Y" else ""
    if zalgo_choice.upper() == "Y":
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + _gen_zalgo_cascade_docstring(paragraphs=1, lines_per_p=6, chars_per_line=12, marks_per_char=50) + "\n" + code + "\n" + _gen_zalgo_cascade_docstring(paragraphs=1, lines_per_p=4, chars_per_line=12, marks_per_char=50)
    elif cjk_choice.upper() == "Y" or matrix_choice.upper() == "Y" or rare_unicode_choice.upper() == "Y":
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + _gen_cjk_docstring(paragraphs=1, lines_per_p=5, chars_per_line=36) + "\n" + code + "\n" + _gen_cjk_docstring(paragraphs=1, lines_per_p=4, chars_per_line=36)
    else:
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + code

    # Write output atomically
    _safe_atomic_write(output_file, str(code), input_file=src_file)
    elapsed = time.time() - start_time
    file_size = os.path.getsize(output_file)
    ratio = file_size / original_size if original_size > 0 else 0

    if max_output_size and file_size > max_output_size:
        if os.path.isfile(output_file):
            try: os.remove(output_file)
            except Exception: pass
        raise ValueError(f"Output size ({file_size:,} B) exceeded limit ({max_output_size:,} B)")

    if _debug_map_choice is not None:
        dbg_map_file = (os.path.splitext(output_file)[0] + ".debug.json") if _debug_map_choice == "AUTO" else _debug_map_choice
        try:
            import json
            dbg_map_file = _validate_and_sanitize_output_path(dbg_map_file, input_file=src_file)
            _safe_atomic_write(dbg_map_file, json.dumps(_DEBUG_MAP, indent=2, ensure_ascii=False), input_file=src_file)
        except Exception as de:
            _log_stage_error("debug_map_export", de)

    # Built-in semantic verification (--verify y)
    if _EngineState.verify_mode:
        if not quiet_progress: _v(" [VERIFY] Semantic differential: original vs obfuscated...")
        t_v0 = time.time()
        vres = _verify_semantics(src_file, output_file)
        try:
            _track_debug_stage("13_verify_semantic", time.time() - t_v0, original_size, file_size, details=vres)
        except Exception:
            pass
        if not vres.get('ok'):
            try:
                _log_stage_error("13_verify_semantic", RuntimeError("obfuscated output diverged from original"), {"result": vres})
            except Exception:
                pass
            print("[TR0NGX] [WARNING] VERIFY FAILED: obfuscated output differs from original.", flush=True)

    return {
        "success": True,
        "src": src_file,
        "out": output_file,
        "original_size": original_size,
        "output_size": file_size,
        "ratio": ratio,
        "elapsed": round(elapsed, 4),
        "error": None
    }

def _verify_semantics(src_file: str, out_file: str, timeout: int = 60) -> dict:
    """Built-in semantic differential check (source: pyshield --verify mode, MIT
    research note; hardened to compare exit codes in addition to stdout)."""
    try:
        r1 = subprocess.run([sys.executable, src_file], capture_output=True, timeout=timeout)
        r2 = subprocess.run([sys.executable, out_file], capture_output=True, timeout=timeout)
        ok = (r1.stdout.strip() == r2.stdout.strip()) and (r1.returncode == r2.returncode)
        return {'ok': ok, 'rc_original': r1.returncode, 'rc_obfuscated': r2.returncode,
                'stdout_match': r1.stdout.strip() == r2.stdout.strip()}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def run_batch_obfuscation(targets: list, custom_out: str, options: dict):
    """
    Executes multi-threaded parallel batch obfuscation for multiple target files.
    """
    start_batch = time.time()
    total_files = len(targets)
    workers = options.get("workers") or max(2, min(8, os.cpu_count() or 4))
    
    # Destination directory resolution
    if custom_out:
        out_dir = custom_out.strip().strip('"').strip("'")
    else:
        first_dir = os.path.dirname(targets[0]["src"]) or "."
        out_dir = os.path.join(first_dir, "tr0ngx_dist")
    
    os.makedirs(out_dir, exist_ok=True)

    # Phase A: cross-module shared-symbol map (--shared-symbols y). Single-threaded
    # parse of all targets BEFORE any worker starts; workers consume the frozen
    # immutable map (Opy consistency model, hardened two-phase design).
    if str(options.get("shared_symbols", "N")).upper() == "Y" and len(targets) > 1:
        try:
            options["shared_symbol_map"] = _collect_shared_symbol_map(targets, seed=options.get("seed"))
            _v(f"  [SHARED-SYMBOLS] Frozen {len(options['shared_symbol_map'])} cross-module symbol(s)")
            try:
                import json as _json
                _safe_atomic_write(os.path.join(out_dir, "tr0ngx_shared_symbols.json"),
                                   _json.dumps(options["shared_symbol_map"], indent=2))
            except Exception:
                pass
        except Exception as _ss_err:
            _log_stage_error("shared_symbols_phase_a", _ss_err)
            options["shared_symbol_map"] = {}
    else:
        options.pop("shared_symbol_map", None)

    _v(_gradient_text(" ══════════════════════════════════════════════════════════════════════════════", (80, 180, 255), (200, 80, 255)))
    _v(f"  [TR0NGX BATCH ENGINE] Starting parallel batch obfuscation ({total_files} files, {workers} workers)")
    _v(f"  Destination Dir : {os.path.abspath(out_dir)}")
    _v(_gradient_text(" ══════════════════════════════════════════════════════════════════════════════", (80, 180, 255), (200, 80, 255)))

    results = []
    completed_lock = threading.Lock()
    completed_count = 0

    def _worker_task(t_info):
        nonlocal completed_count
        src = t_info["src"]
        rel = t_info["rel"]
        dest = os.path.join(out_dir, rel)
        dest_dir = os.path.dirname(dest)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)

        res = obfuscate_single_target(src, dest, options, quiet_progress=True)
        with completed_lock:
            completed_count += 1
            cur = completed_count
        
        status_tag = "\033[92m[OK]\033[0m" if res["success"] else "\033[91m[FAIL]\033[0m"
        rel_display = rel if len(rel) <= 35 else ("..." + rel[-32:])
        if res["success"]:
            _v(f"  [{cur:>{len(str(total_files))}}/{total_files}] {status_tag} {rel_display:<35} -> {res['output_size']:>10,} B ({res['ratio']:>5.1f}x | {res['elapsed']:>5.2f}s)")
        else:
            _v(f"  [{cur:>{len(str(total_files))}}/{total_files}] {status_tag} {rel_display:<35} -> ERROR: {res['error']}")
        return res

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=min(workers, total_files)) as executor:
        futures = [executor.submit(_worker_task, t) for t in targets]
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except SystemExit:
                raise
            except KeyboardInterrupt:
                raise
            except Exception as e:
                _log_debug(f"Worker crashed: {e}", level="ERROR")
                import traceback as _tb2
                _log_debug(_tb2.format_exc(), level="ERROR")
                results.append({"success": False, "src": "?", "out": "?", "original_size": 0, "output_size": 0, "ratio": 0.0, "elapsed": 0.0, "error": str(e)})

    total_batch_time = time.time() - start_batch
    success_count = sum(1 for r in results if r["success"])
    fail_count = total_files - success_count
    total_in_bytes = sum(r["original_size"] for r in results)
    total_out_bytes = sum(r["output_size"] for r in results if r["success"])
    overall_ratio = (total_out_bytes / total_in_bytes) if total_in_bytes > 0 else 0

    summary_lines = [
        f"Total Files Processed : {total_files}",
        f"Successful            : {success_count} / {total_files} ({success_count/total_files*100:.1f}%)",
        f"Failed                : {fail_count}",
        f"Total Original Size   : {total_in_bytes:,} bytes",
        f"Total Obfuscated Size : {total_out_bytes:,} bytes ({overall_ratio:.1f}x expansion)",
        f"Total Elapsed Time    : {total_batch_time:.2f}s (Avg: {total_batch_time/total_files:.2f}s/file)",
        f"Output Destination    : {os.path.abspath(out_dir)}"
    ]
    summary_text = "\n".join(summary_lines)

    _v(_gradient_text(" ══════════════════════ BATCH OBFUSCATION SUMMARY ══════════════════════", (85, 130, 255), (190, 85, 255)))
    if _EngineState.cli_quiet_mode:
        _v(summary_text)
    else:
        try:
            _boxed = Box.DoubleCube(summary_text)
            _raw_print(Colorate.Diagonal(Colors.StaticMIX((Col.cyan, Col.purple)), _boxed))
        except Exception:
            _v(summary_text)
    _v(_gradient_text(" ═══════════════════════════════════════════════════════════════════════", (85, 130, 255), (190, 85, 255)))
    _export_log_file()
    _v(" BATCH OBFUSCATION COMPLETE!")
    if fail_count > 0:
        sys.exit(1)
    return results

def main():
    # ═══════════════════════════════════════════════════════════════
    # MAIN EXECUTION (CLI + TUI DISPATCHER)
    # ═══════════════════════════════════════════════════════════════
    _reset_global_state()
    _show_banner()
    _cfg = get_args_or_prompt()
    targets = _cfg["targets"]
    is_batch = _cfg["is_batch"]
    custom_out = _cfg["custom_out"]

    matrix_choice = _cfg.get("matrix", "N")
    homoglyph_choice = _cfg.get("homoglyph", "N")
    rare_unicode_choice = _cfg.get("rare_unicode", "N")
    cjk_choice = _cfg.get("cjk", "N")
    zalgo_choice = _cfg.get("zalgo", "N")
    hyperion_choice = _cfg.get("hyperion", "N")
    camouflage_choice = _cfg.get("camouflage", "N")

    # Set name generation mode flags & Matrix fusion
    if matrix_choice.upper() == "Y" or (homoglyph_choice.upper() == "Y" and rare_unicode_choice.upper() == "Y"):
        _EngineState.use_fused_names = True
        _init_rare_chars()
        _init_combining_marks()
    if cjk_choice.upper() == "Y":
        _EngineState.use_cjk_names = True
    if homoglyph_choice.upper() == "Y":
        _EngineState.use_homoglyph_names = True
    if rare_unicode_choice.upper() == "Y":
        _EngineState.use_rare_unicode_names = True
        _init_rare_chars()
    if _cfg.get("exotic_pools", "N").upper() == "Y":
        _EngineState.use_exotic_pools = True
    if zalgo_choice.upper() == "Y":
        _EngineState.use_zalgo_marks = True
        _init_combining_marks()
    if hyperion_choice.upper() == "Y":
        _EngineState.use_hyperion = True
    if camouflage_choice.upper() == "Y":
        _EngineState.use_camouflage = True

    _refresh_runtime_symbols()

    # Dispatch to batch runner if multiple files, or single file pipeline if 1 file
    if is_batch or len(targets) > 1:
        run_batch_obfuscation(targets, custom_out, _cfg)
    else:
        src_target = targets[0]["src"]
        if custom_out:
            if os.path.isdir(custom_out) or custom_out.endswith("/") or custom_out.endswith("\\"):
                os.makedirs(custom_out, exist_ok=True)
                out_target = os.path.join(custom_out, os.path.basename(src_target))
            else:
                out_target = custom_out.strip().strip('"').strip("'")
        else:
            _dir_n, _base_n = os.path.split(src_target)
            out_target = os.path.join(_dir_n, "tr0ngx-" + _base_n) if _dir_n else ("tr0ngx-" + _base_n)

        _v(" ═══ STARTING OBFUSCATION ═══")
        res = obfuscate_single_target(src_target, out_target, _cfg, quiet_progress=False)
        if not res["success"]:
            _v(f" [ERROR] Obfuscation failed: {res['error']}")
            if _EngineState.strict_mode:
                sys.exit(1)
            return

        original_size = res["original_size"]
        file_size = res["output_size"]
        ratio = res["ratio"]
        elapsed = res["elapsed"]
        output_file = res["out"]

        _new_modes = []
        multi_shield_count = sum(1 for c in [_cfg.get("kramer","N"), _cfg.get("emoji_obf","N"), _cfg.get("whitespace_obf","N")] if c.upper() == "Y")
        if (matrix_choice.upper() == "Y") or (multi_shield_count >= 2):
            _new_modes.append("MATRIX-FUSED (3-Track Symbiotic)")
        else:
            if _cfg.get("emoji_obf", "N").upper() == "Y": _new_modes.append("EMOJI")
            if _cfg.get("whitespace_obf", "N").upper() == "Y": _new_modes.append("WHITESPACE")
        if _EngineState.use_fused_names:
            _new_modes.append("HYBRID-VARS")
        else:
            if homoglyph_choice.upper() == "Y": _new_modes.append("HOMOGLYPH")
            if rare_unicode_choice.upper() == "Y": _new_modes.append("RARE-UNI")
            if zalgo_choice.upper() == "Y": _new_modes.append("ZALGO-MARKS (Z͑͗͑͗... Diacritics)")
        if hyperion_choice.upper() == "Y": _new_modes.append("HYPERION-ENGINE")
        if camouflage_choice.upper() == "Y": _new_modes.append("HYPERION-CAMOUFLAGE")
        if _cfg.get("math_opaque", "N").upper() == "Y": _new_modes.append("MATH-OPAQUE (Quadratic/Euler Invariants)")
        if _cfg.get("dyn_strings", "N").upper() == "Y": _new_modes.append("DYN-STRINGS (Per-Callsite XOR)")
        if _cfg.get("anti_dump", "N").upper() == "Y": _new_modes.append("ANTI-DUMP (GC Scrubber)")

        _veli_suffix = f"(L{_cfg.get('veli_level', 1)})" if _cfg['velimatix'].upper() == 'Y' else ""
        _summary_lines = [
            f"File Saved   : {output_file}",
            f"Original Size: {original_size:,} bytes",
            f"Output Size  : {file_size:,} bytes ({ratio:.1f}x)",
            f"Time Taken   : {elapsed:.2f}s",
            f"Mode         : {_cfg['mode']} | Veli: {_cfg['velimatix'].upper()}{_veli_suffix}",
            f"Compile      : {_cfg['method'].upper()} | Double: {_cfg['double_compile'].upper() if _cfg['method'].upper()=='Y' else 'N'}",
            f"Protections  : Anti-Debug={_cfg['antidebug'].upper()} | Anti-VM={_cfg['antivm'].upper()} | Anti-Dump={_cfg['anti_dump'].upper()} | Self-Mod={_cfg['selfmodify'].upper()} | Kramer={_cfg['kramer'].upper()}"
        ]
        if _new_modes:
            _summary_lines.append(f"Layers       : {' + '.join(_new_modes)}")

        _summary_text = "\n".join(_summary_lines)

        _v(_gradient_text(" ═══════════════════════════════════════", (85, 130, 255), (190, 85, 255)))
        if _EngineState.cli_quiet_mode:
            _v(_summary_text)
        else:
            try:
                _boxed = Box.DoubleCube(_summary_text)
                _raw_print(Colorate.Diagonal(Colors.StaticMIX((Col.cyan, Col.purple)), _boxed))
            except Exception:
                _v(_summary_text)
        _v(_gradient_text(" ═══════════════════════════════════════", (85, 130, 255), (190, 85, 255)))
        if _EngineState.profile_mode or _EngineState.verbose_debug:
            _print_profile_waterfall(elapsed, original_size, file_size)
        _export_log_file()
        if _STAGE_ERRORS and not _EngineState.strict_mode:
            failed_stages = ", ".join(sorted({e["stage"] for e in _STAGE_ERRORS}))
            _v(f" [!] WARNING: {len(_STAGE_ERRORS)} pipeline stage(s) FAILED: {failed_stages}")
            _v(" [!] Output was still written but may be MISSING protection layers listed above.")
        _v(" OBFUSCATION COMPLETE!")

if __name__ == "__main__":
    main()
