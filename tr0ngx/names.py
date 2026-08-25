# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports pending repair)
# ═══════════════════════════════════════════════════════════════
# UNIQUE NAME GENERATORS - COLLISION-FREE
# ═══════════════════════════════════════════════════════════════

# stdlib imports restored post-split
import ast
import base64
import hashlib
import marshal
import os
import random
import secrets
import string
import sys
import tempfile
import threading
import zlib
from typing import Dict

# package-relative: config owns _EngineState (mutable shared state)
from . import config as _cfg
# error-path UI helpers (issue B fix: were referenced but never imported)
from .diagnostics import _v, _gradient_text

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

_cfg._EngineState.use_fused_names = False

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
        if _cfg._EngineState.use_exotic_pools and _trx_rand(100) < 70:
            _n = _gen_exotic_name(scope)
            if _n:
                return _n
        if _cfg._EngineState.use_zalgo_marks:
            return _gen_zalgo_name()
        if _cfg._EngineState.use_fused_names:
            return _gen_fused_name(scope)
        if _cfg._EngineState.use_rare_unicode_names:
            return _gen_rare_unicode_name()
        if _cfg._EngineState.use_homoglyph_names:
            return _gen_homoglyph_name()
        if _cfg._EngineState.use_cjk_names:
            return _gen_cjk_name()
        alphabet = string.ascii_lowercase + string.digits
        while True:
            k = _trx_rand(4) + 5
            name = "_" + "".join(_trx_choice(alphabet) for _ in range(k))
            if name not in _used_names:
                _used_names.add(name)
                return name

_EXOTIC_POOL_CACHE = []

def _gen_exotic_name(scope='general'):
    """Draw identifiers from rare Unicode script pools (Tangut, Egyptian Hieroglyphs,
    CJK Ext G/H, Anatolian, Bamum, Glagolitic, Miao, Vedic) with full XID + NFKC
    collision validation via tr0ngx_exotic."""
    global _EXOTIC_POOL_CACHE
    import unicodedata as _ud
    try:
        from . import exotic as _tex
    except ImportError:
        return None
    if getattr(_cfg._EngineState, "used_nfkc", None) is None:
        _cfg._EngineState.used_nfkc = set()
    for _ in range(64):
        if not _EXOTIC_POOL_CACHE:
            kinds = _tex.pool_kinds()
            kind = _trx_choice(kinds)
            _EXOTIC_POOL_CACHE.extend(_tex.build_identifier_pool(kind, 128, random))
        name = _EXOTIC_POOL_CACHE.pop()
        norm = _ud.normalize("NFKC", name)
        with _used_names_lock:
            if name in _used_names or norm in _cfg._EngineState.used_nfkc:
                continue
            _used_names.add(name)
        _cfg._EngineState.used_nfkc.add(norm)
        return name
    return None

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
_cfg._EngineState.use_cjk_names = False

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

_cfg._EngineState.use_homoglyph_names = False

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

_cfg._EngineState.use_rare_unicode_names = False

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

