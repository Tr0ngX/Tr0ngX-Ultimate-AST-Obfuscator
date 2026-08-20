import sys
import argparse
import ast
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
    encryption_password = None
    use_math_opaque = False
    use_dyn_strings = False
    use_anti_dump = False
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
    sys.exit()

__import__('sys').setrecursionlimit(15000)

# ═══════════════════════════════════════════════════════════════
# UNIQUE NAME GENERATORS - COLLISION-FREE
# ═══════════════════════════════════════════════════════════════

_used_names = set()
_used_names_lock = threading.Lock()

def _rd():
    alphabet = string.ascii_lowercase
    with _used_names_lock:
        while True:
            k = secrets.randbelow(5) + 6
            name = "".join(secrets.choice(alphabet) for _ in range(k))
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
        return _gen_homoglyph_name(secrets.randbelow(5) + 6)
    elif scope == 'biopaque':
        return _gen_rare_unicode_name(secrets.randbelow(3) + 3)
    elif scope == 'globals':
        return _gen_cjk_name(secrets.randbelow(5) + 6)
    else:
        picker = secrets.choice(['homo', 'rare', 'cjk', 'zalgo', 'invis'])
        if picker == 'homo':
            return _gen_homoglyph_name(secrets.randbelow(4) + 5)
        elif picker == 'rare':
            return _gen_rare_unicode_name(secrets.randbelow(3) + 3)
        elif picker == 'cjk':
            return _gen_cjk_name(secrets.randbelow(3) + 6)
        elif picker == 'zalgo':
            return _gen_zalgo_name(1, secrets.randbelow(21) + 25)
        else:
            return _gen_homoglyph_name(secrets.randbelow(5) + 6)

def rd(scope='general'):
    with _used_names_lock:
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
            k = secrets.randbelow(4) + 5
            name = "_" + "".join(secrets.choice(alphabet) for _ in range(k))
            if name not in _used_names:
                _used_names.add(name)
                return name

def randomint():
    return str(secrets.randbelow(900000) + 100000)

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

_FORBIDDEN_SYSTEM_PREFIXES = [
    '/etc', '/usr', '/bin', '/sbin', '/lib', '/lib64', '/boot', '/root', '/dev', '/proc', '/sys',
    'C:\\Windows', 'C:\\Program Files', 'C:\\Program Files (x86)', 'C:\\Windows\\System32'
]

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
    kind = secrets.randbelow(4)
    if kind == 0:
        k_val = secrets.randbelow(300) + 12
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
        n_val = secrets.randbelow(300) + 15
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
        x_val = secrets.randbelow(0xFFFF) + 200
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
        old_body = body
        body = []
        var_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        ex_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        body.append(ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=0), lineno=None))
        case = ast.While(
            test=ast.Compare(left=ast.Name(id=var_name), ops=[ast.NotEq()], comparators=[ast.Constant(value=len(old_body) + 1)]),
            body=[
                ast.AugAssign(target=ast.Name(id=var_name), op=ast.Add(), value=ast.Constant(value=1)),
                ast.Try(
                    body=[ast.Raise(exc=ast.Call(func=ast.Name(id='VELIMATIX'), args=[ast.Name(id=var_name)], keywords=[]))],
                    handlers=[ast.ExceptHandler(type=ast.Name(id='VELIMATIX'), name=ex_name, body=[])],
                    orelse=[], finalbody=[]
                )
            ], orelse=[]
        )
        line = 1
        for body_node in old_body:
            case.body[1].handlers[0].body.append(ast.If(
                test=ast.Compare(
                    left=ast.Subscript(value=ast.Attribute(value=ast.Name(id=ex_name), attr='args'), slice=ast.Constant(value=0)),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=line)]
                ),
                body=[body_node], orelse=[]
            ))
            line += 1
        junk = ExceptionJumpUtils.generate_junk(ex_name, len(old_body) + 1)
        case.body[1].handlers[0].body.extend(junk)
        random.shuffle(case.body[1].handlers[0].body)
        body.append(case)
        return body

    def generate_block(node):
        old_body = node.body
        node.body = []
        var_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        ex_name = Utils.randomize_name(ExceptionJumpUtils.alphabet, ExceptionJumpUtils.length)
        node.body.append(ast.Assign(targets=[ast.Name(id=var_name)], value=ast.Constant(value=0), lineno=None))
        case = ast.While(
            test=ast.Compare(left=ast.Name(id=var_name), ops=[ast.NotEq()], comparators=[ast.Constant(value=len(old_body) + 1)]),
            body=[
                ast.AugAssign(target=ast.Name(id=var_name), op=ast.Add(), value=ast.Constant(value=1)),
                ast.Try(
                    body=[ast.Raise(exc=ast.Call(func=ast.Name(id='VELIMATIX'), args=[ast.Name(id=var_name)], keywords=[]))],
                    handlers=[ast.ExceptHandler(type=ast.Name(id='VELIMATIX'), name=ex_name, body=[])],
                    orelse=[], finalbody=[]
                )
            ], orelse=[]
        )
        globals_list = []
        line = 1
        for body_node in old_body:
            if isinstance(body_node, ast.Global):
                globals_list.append(body_node)
                continue
            case.body[1].handlers[0].body.append(ast.If(
                test=ast.Compare(
                    left=ast.Subscript(value=ast.Attribute(value=ast.Name(id=ex_name), attr='args'), slice=ast.Constant(value=0)),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=line)]
                ),
                body=[body_node], orelse=[]
            ))
            line += 1
        junk = ExceptionJumpUtils.generate_junk(ex_name, len(old_body) + 1)
        case.body[1].handlers[0].body.extend(junk)
        random.shuffle(case.body[1].handlers[0].body)
        node.body.append(case)
        for global_obj in globals_list:
            node.body.insert(0, global_obj)
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
        def visit_FunctionDef(self, node: ast.FunctionDef):
            node = ExceptionJumpUtils.generate_block(node)
            return node

        def visit_If(self, node: ast.If):
            node = ExceptionJumpUtils.generate_block(node)
            return node

        def visit_Assign(self, node: ast.Assign):
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
        junk_cases = ControlFlowUtils.generate_junk_controlflow_block(maps, next_num, node)
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
        def visit_Call(self, node: ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ('super', 'locals', 'eval', 'exec', '__import__'):
                    return node
                is_builtin = str(node.func.id) in dir(__builtins__)
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

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if node.name.startswith('__'):
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

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in self.mapping:
                node.id = self.mapping[node.id]

        xor_key = secrets.randbelow(200) + 55
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
        """Generates an expression that is mathematically proven to be ALWAYS TRUE at runtime."""
        pick = secrets.randbelow(3)
        if pick == 0:
            x_val = secrets.randbelow(1000) + 11
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
            k_val = secrets.randbelow(500) + 13
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
        else:
            n_val = secrets.randbelow(500) + 9
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

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        if node.name.startswith("__") or len(node.body) < 2:
            return node
        
        new_body = []
        for stmt in node.body:
            if secrets.randbelow(100) < 60 and not isinstance(stmt, (ast.Return, ast.Yield, ast.YieldFrom, ast.Global, ast.Nonlocal, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                bogus_var = rd('biopaque')
                bogus_stmt = ast.Assign(
                    targets=[ast.Name(id=bogus_var)],
                    value=ast.BinOp(
                        left=ast.Constant(value=secrets.randbelow(0xFFFFFF)),
                        op=ast.BitXor(),
                        right=ast.Constant(value=secrets.randbelow(0xFFFFFF))
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
        self.master_seed = master_seed or (secrets.randbelow(0x7FFFFFFF) + 1000)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        # In Python AST, elements inside JoinedStr (f-strings) must stay as FormattedValue or Constant string.
        for idx, val in enumerate(node.values):
            if isinstance(val, ast.FormattedValue):
                node.values[idx] = self.visit(val)
        return node

    def visit_match_case(self, node: ast.match_case):
        # In Python 3.10+, match patterns cannot contain Call/Lambda expressions
        if node.guard:
            node.guard = self.visit(node.guard)
        node.body = [self.visit(stmt) for stmt in node.body]
        return node

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str) and len(node.value) > 0:
            if (node.value.startswith("__") and node.value.endswith("__")) or len(node.value) > 20000:
                return node
            
            val_bytes = node.value.encode('utf-8')
            lineno = getattr(node, 'lineno', 1) or 1
            col_offset = getattr(node, 'col_offset', 0) or 0
            
            site_key = (self.master_seed ^ (lineno * 31337) ^ (col_offset * 101) ^ len(val_bytes)) & 0xFFFFFFFF
            
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
        return node

def _dyn_strings_obf(code_str: str) -> str:
    """Apply Dynamic Per-Callsite String XOR Encryption."""
    tree = ast.parse(code_str)
    transformer = DynamicStringXORTransformer()
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


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
        return ast.Call(
            func=ast.Attribute(value=ast.Constant(value='{}' * len(node.values)), attr="format", ctx=ast.Load()),
            args=[value.value if isinstance(value, ast.FormattedValue) else value for value in node.values],
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
        magic = secrets.randbelow(9000000) + 1000000
        for char in v:
            logic = secrets.randbelow(5) + 1
            key = ord(char)
            key2 = magic
            if logic == 1:
                key3 = key ^ magic
                keys.append(f"(lambda: chr({key3} ^ {key2}))()")
            elif logic == 2:
                shift = secrets.randbelow(12) + 1
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
        secrets.SystemRandom().shuffle(shuffled)
        encoded = [(shuffled[i], ord(v[shuffled[i]]) + 0xFF78FF) for i in range(len(v))]
        pairs_str = str(encoded)
        return f"(lambda: ''.join(globals()['{_hexrun}'](c) for _, c in sorted({pairs_str})))()"

    else:
        # Multi-base encoding
        encoded_bytes = v.encode('utf-8')
        nums = [b for b in encoded_bytes]
        xor_val = secrets.randbelow(255) + 1
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
        strategy = secrets.randbelow(8) + 1
        val = int(v)

        # Strategy 1 (_byte) only works for non-negative integers
        if strategy == 1:
            if val >= 0:
                return f'(lambda: c2h6({_byte(val)}))()'
            else:
                # Fallback for negative numbers: use XOR strategy
                xor_key = secrets.randbelow(0xFFFFF - 0x1000) + 0x1000
                return f'(lambda: (lambda: {val ^ xor_key} ^ {xor_key})())()'

        elif strategy == 2:
            offset = secrets.randbelow(0xFFFFF - 0x5000) + 0x5000
            return f'(lambda: (lambda: {val + offset} - {offset})())()'

        elif strategy == 3:
            xor_key = secrets.randbelow(0xFFFFF - 0x1000) + 0x1000
            return f'(lambda: (lambda: {val ^ xor_key} ^ {xor_key})())()'

        elif strategy == 4:
            mult = secrets.choice([2, 3, 5, 7, 11, 13])
            remainder = val % mult
            base = val // mult
            return f'(lambda: (lambda: {base} * {mult} + {remainder})())()'

        elif strategy == 5:
            return f'(lambda: H2SbF7({(val + 0x7777)}))()'

        elif strategy == 6:
            return f'(lambda: ~~{val})()'

        elif strategy == 7:
            a = secrets.randbelow(10000) + 1
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

_generate_var_block()

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

    # Vector 11: Reversing & Disassembler window title inspection
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32'):
            _u32 = ctypes.windll.user32
            _buf = ctypes.create_unicode_buffer(512)
            _bad_titles = ('x64dbg', 'x32dbg', 'ida -', 'ida64', 'ghidra', 'dnspy', 'cheat engine', 'wireshark', 'process hacker', 'process explorer', 'http debugger', 'fiddler')
            def _enum_wnd_cb(hwnd, lparam):
                if _u32.IsWindowVisible(hwnd):
                    l = _u32.GetWindowTextW(hwnd, _buf, 512)
                    if l > 0:
                        t = _buf.value.lower()
                        if any(b in t for b in _bad_titles):
                            _obliterate()
                return True
            _WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            _u32.EnumWindows(_WNDPROC(_enum_wnd_cb), 0)
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

def fm(node: ast.JoinedStr) -> ast.Call:
    return ast.Call(
        func=ast.Attribute(
            value=ast.Constant(value="{}" * len(node.values)),
            attr="format",
            ctx=ast.Load(),
        ),
        args=[
            value.value if isinstance(value, ast.FormattedValue) else value
            for value in node.values
        ],
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
                        ast.parse(f"{_eval}('0/0')").body[0],
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
            body=[ast.parse(f"{_eval}('0/0')").body[0]],
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

    _DEBUG_MAP["renamed_functions"][ol] = nn
    if isinstance(node, str):
        node = ast.parse(node)
    for i in ast.walk(node):
        if isinstance(i, ast.FunctionDef) and i.name == ol:
            i.name = nn
        elif isinstance(i, ast.AsyncFunctionDef) and i.name == ol:
            i.name = nn
        elif isinstance(i, ast.Attribute) and isinstance(i.value, ast.Name) and i.value.id == ol:
            i.value.id = nn
        elif isinstance(i, ast.Call) and isinstance(i.func, ast.Name) and i.func.id == ol:
            i.func.id = nn
        elif isinstance(i, ast.Name) and i.id == ol:
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


def trycatch(body, loop):
    ar = []
    for x in body:
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
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

def obf(code):
    def ps(x):
        if isinstance(x, str):
            return ast.parse(x)
        return x

    code = rename_function(ps(code), "print", __print)
    code = rename_function(code, "input", __input)
    tree = ps(code)
    obfuscate(tree)
    tbd = trycatch(tree.body, 1)

    def ast_to_code(node):
        if isinstance(node, list):
            return '\n'.join(ast.unparse(n) for n in node)
        return ast.unparse(node)

    return ast_to_code(tbd)


# ═══════════════════════════════════════════════════════════════
# AUTHENTICATED STREAM ENCRYPTION (AEAD + PBKDF2-HMAC-SHA256)
# ═══════════════════════════════════════════════════════════════

def _derive_keys_argon2_or_pbkdf2(password: bytes, salt: bytes) -> tuple[bytes, bytes]:
    """Derive 256-bit encryption key and 256-bit MAC key using Argon2id (if available) or PBKDF2-HMAC-SHA256 (600,000 rounds)."""
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        ke = Argon2id(salt=salt + b'__enc__', length=32, iterations=4, lanes=4, memory_cost=131072).derive(password)
        km = Argon2id(salt=salt + b'__mac__', length=32, iterations=4, lanes=4, memory_cost=131072).derive(password)
        return ke, km
    except Exception:
        # Standard library high-entropy PBKDF2 (OWASP recommended 600,000 iterations)
        ke = hashlib.pbkdf2_hmac('sha256', password, salt + b'__enc__', 600000, 32)
        km = hashlib.pbkdf2_hmac('sha256', password, salt + b'__mac__', 600000, 32)
        return ke, km

def _derive_runtime_keys(salt: bytes):
    """Derive encryption and MAC keys from salt + runtime environment (for obfuscation-only mode)."""
    import platform
    parts = []
    parts.append(sys.version[:5].encode())
    parts.append(platform.python_implementation().encode())
    parts.append(salt)
    parts.append(str(sys.maxsize).encode())
    parts.append(sys.byteorder.encode())
    combined = b''.join(parts)
    enc_k = hashlib.sha256(combined + b'__enc__').digest()
    mac_k = hashlib.sha256(combined + b'__mac__').digest()
    ke = hashlib.pbkdf2_hmac('sha256', salt, enc_k, 50000, 32)
    km = hashlib.pbkdf2_hmac('sha256', salt, mac_k, 50000, 32)
    return ke, km

def _auth_stream_encrypt(data: bytes, salt: bytes, ke: bytes, km: bytes):
    """Authenticated Keystream Encryption with HMAC-CTR (Nonce + Counter) & Full HMAC-SHA256 Integrity Tag"""
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
    tag = hmac.new(km, salt + nonce + ciphertext, hashlib.sha256).digest()
    return ciphertext, tag, nonce

def _multi_layer_encrypt(data: bytes, password: str = None):
    """Apply Authenticated Stream Encryption with Argon2id/PBKDF2 (if password provided) or environment-derived keys."""
    data = zlib.compress(data, 9)
    salt = secrets.token_bytes(16)
    if password:
        ke, km = _derive_keys_argon2_or_pbkdf2(password.encode('utf-8'), salt)
    else:
        ke, km = _derive_runtime_keys(salt)

    ct, tag, nonce = _auth_stream_encrypt(data, salt, ke, km)
    # Payload format: salt(16) + nonce(12) + tag(32) + ciphertext
    payload_packed = salt + nonce + tag + ct
    payload_packed = bz2.compress(payload_packed, 9)
    payload_packed = zlib.compress(payload_packed, 9)
    return base64.b85encode(payload_packed).decode('ascii'), salt


def _velimatix_compile(code_str):
    """Velimatix-style marshal compilation with FunctionType Anti-Funnel loader and dynamic token randomization (TRX-OBF-006/DEOB-014)."""
    b = marshal.dumps(compile(code_str, "<velimatix>", "exec"))
    b = zlib.compress(b, 9)
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
except Exception:
    pass
"""


def _double_compile(code_str, target_ver=None, password=None):
    """Double compile: Authenticated AEAD Payload INSIDE Velimatix loader with Dynamic Keys."""
    if target_ver is None:
        target_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    try:
        compiled = marshal.dumps(compile(code_str, "<tr0ngx>", "exec"))
    except SyntaxError:
        return code_str

    enc_b85, salt = _multi_layer_encrypt(compiled, password=password)

    if password:
        inner_loader = f"""
import base64, zlib, bz2, marshal, hashlib, hmac, types, sys, os, getpass, gc

sys.dont_write_bytecode = True
_target_ver = {target_ver!r}
_curr_ver = sys.version.split()[0]
_curr_maj_min = f"{{sys.version_info.major}}.{{sys.version_info.minor}}"
if _curr_maj_min != _target_ver and not sys.version.startswith(_target_ver):
    print(f"[-] PYTHON VERSION MISMATCH! This obfuscated script requires Python {target_ver}.x (Current: {{_curr_ver}}). Please run with python{target_ver} or install Python {target_ver}.", flush=True)
    __import__("os")._exit(1)

def _auth_decrypt(raw_bytes, pwd_str):
    salt = raw_bytes[:16]
    nonce = raw_bytes[16:28]
    tag = raw_bytes[28:60]
    ct = raw_bytes[60:]
    p_bytes = pwd_str.encode('utf-8')
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        ke = Argon2id(salt=salt + b'__enc__', length=32, iterations=4, lanes=4, memory_cost=131072).derive(p_bytes)
        km = Argon2id(salt=salt + b'__mac__', length=32, iterations=4, lanes=4, memory_cost=131072).derive(p_bytes)
    except Exception:
        ke = hashlib.pbkdf2_hmac('sha256', p_bytes, salt + b'__enc__', 600000, 32)
        km = hashlib.pbkdf2_hmac('sha256', p_bytes, salt + b'__mac__', 600000, 32)
    expected_tag = hmac.new(km, salt + nonce + ct, hashlib.sha256).digest()
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

_pwd = os.environ.get("TR0NGX_PASSWORD")
if not _pwd:
    _pwd = getattr(__builtins__, 'input', lambda *a: "")("[TR0NGX] Enter decryption password: ")

_payload_b85 = {enc_b85!r}
_s1 = base64.b85decode(_payload_b85)
_s2 = zlib.decompress(_s1)
_s3 = bz2.decompress(_s2)
_s4 = _auth_decrypt(_s3, _pwd)
_s5 = zlib.decompress(_s4)
exec(marshal.loads(_s5), globals(), globals())
try:
    for _b_item in [_s1, _s2, _s3, _s4, _s5]:
        if isinstance(_b_item, (bytearray, bytes)):
            _ba = bytearray(_b_item)
            for _zi in range(len(_ba)): _ba[_zi] = 0
except Exception:
    pass
del _payload_b85, _s1, _s2, _s3, _s4, _s5, _pwd
gc.collect()
"""
    else:
        inner_loader = f"""
import base64, zlib, bz2, marshal, hashlib, hmac, types, sys, platform, gc

sys.dont_write_bytecode = True
_target_ver = {target_ver!r}
_curr_ver = sys.version.split()[0]
_curr_maj_min = f"{{sys.version_info.major}}.{{sys.version_info.minor}}"
if _curr_maj_min != _target_ver and not sys.version.startswith(_target_ver):
    print(f"[-] PYTHON VERSION MISMATCH! This obfuscated script requires Python {target_ver}.x (Current: {{_curr_ver}}). Please run with python{target_ver} or install Python {target_ver}.", flush=True)
    __import__("os")._exit(1)

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
    salt = raw_bytes[:16]
    nonce = raw_bytes[16:28]
    tag = raw_bytes[28:60]
    ct = raw_bytes[60:]
    enc_k, mac_k = _derive_runtime_keys(salt)
    ke = hashlib.pbkdf2_hmac('sha256', salt, enc_k, 50000, 32)
    km = hashlib.pbkdf2_hmac('sha256', salt, mac_k, 50000, 32)
    expected_tag = hmac.new(km, salt + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise SystemExit(1)
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(ct):
        block = hmac.new(ke, nonce + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))

_payload_b85 = {enc_b85!r}
_s1 = base64.b85decode(_payload_b85)
_s2 = zlib.decompress(_s1)
_s3 = bz2.decompress(_s2)
_s4 = _auth_decrypt(_s3)
_s5 = zlib.decompress(_s4)
exec(marshal.loads(_s5), globals(), globals())
try:
    for _b_item in [_s1, _s2, _s3, _s4, _s5]:
        if isinstance(_b_item, (bytearray, bytes)):
            _ba = bytearray(_b_item)
            for _zi in range(len(_ba)): _ba[_zi] = 0
except Exception:
    pass
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
    """Generate industrial-grade Anti-VM and Sandbox detection shield."""
    fn_name = rd('state_machine')
    abort_fn = rd('guard')
    cores_var = rd('biopaque')
    user_var = rd('state_machine')
    host_var = rd('guard')
    
    return f'''
# ═══ ANTI-VIRTUALIZATION & SANDBOX MATRIX ═══
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

    # 1. CPU Core Count Check (Automated analysis sandboxes often allocate <= 1 vCPU)
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
        _bad_identities = {{'SANDBOX', 'VIRUS', 'MALTEST', 'TEQUILABOOMBOOM', 'SAMPLE', 'CURRENTUSER', 'DESKTOP-ANALYSIS', 'USER-PC', 'JOHN-PC', 'TEST-PC', 'KLONE'}}
        if {user_var} in _bad_identities or {host_var} in _bad_identities:
            {abort_fn}()
    except Exception:
        pass

    # 3. Windows-Specific VM & Hypervisor Deep Inspection
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
            _vm_kw = (b'vmware', b'virtualbox', b'vbox', b'qemu', b'bochs', b'kvm', b'parallels', b'xen', b'hyper-v')
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

    # 4. Linux & POSIX Container / VM Deep Inspection
    if os.name == 'posix':
        try:
            _dmi_files = ['/sys/class/dmi/id/product_name', '/sys/class/dmi/id/sys_vendor', '/sys/class/dmi/id/board_vendor', '/sys/hypervisor/type']
            _vm_tags = ['virtualbox', 'vmware', 'qemu', 'kvm', 'bochs', 'xen', 'microsoft corporation', 'innotek', 'parallels', 'hyper-v']
            for _dpath in _dmi_files:
                if os.path.exists(_dpath):
                    with open(_dpath, 'r', errors='ignore') as _df:
                        _dcontent = _df.read().lower()
                        if any(_t in _dcontent for _t in _vm_tags):
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
'''




# ═══════════════════════════════════════════════════════════════
# KRAMER ENGINE - KYRIE ELEISON & OBFUSCATED CLASS WRAPPER
# ═══════════════════════════════════════════════════════════════

_kramer_alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"

class Kyrie:
    @staticmethod
    def _ekyrie(text: str):
        r = ""
        for a in text:
            if a in _kramer_alphabet:
                a = _kramer_alphabet[_kramer_alphabet.index(a)-1]
            r += a
        return r

    @staticmethod
    def _encrypt(text: str, key: int = 0):
        t = [chr(ord(t) + key) if t != "\n" else "ζ" for t in text]
        return "".join(t)

    @staticmethod
    def encrypt(content: str, key: int):
        e1 = Kyrie._ekyrie(content)
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
                result.append("ζ")
            else:
                result.append(chr(ord(ch) ^ xor_byte))
        return "".join(result)

    @staticmethod
    def encrypt_v2(content: str, key: int):
        """Enhanced encryption: alphabet rotation + XOR stream cipher."""
        e1 = Kyrie._ekyrie(content)
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
        f"import zlib as _z, marshal as _m\n"
        f"{v1} = \"\"\"{emoji_data}\"\"\"\n"
        f"{v2} = _z.decompress(bytes(ord(_c)-{_EMOJI_BASE} for _c in {v1}))\n"
        f"exec(_m.loads({v2}))\n"
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
        f"import zlib as _z, marshal as _m\n"
        f"_w = \"\"\"{ws_data}\"\"\"\n"
        f"exec(_m.loads(_z.decompress(bytes("
        f"int(''.join('1' if c == '\\t' else '0' for c in _w[i:i+8]), 2) "
        f"for i in range(0, len(_w), 8)))))\n"
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
            # Inject explicit imports for used builtins
            imp = "from builtins import " + ",".join(used_builtins[:40]) + "\n"
            return imp + code
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
                        if t_str not in renamed:
                            renamed[t_str] = rd()
                        t_str = renamed[t_str]
                    elif t_str in renamed:
                        t_str = renamed[t_str]
                elif prev_tok in ('def', 'class'):
                    if t_str not in skip_keywords and not t_str.startswith('__'):
                        if t_str not in renamed:
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
        lines = []
        for lin in code.splitlines():
            s = lin.strip()
            if s and not s.startswith('#'):
                lines.append(lin)
        return '\n'.join(lines)

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
__license__ = 'MIT / EPL-2.0'
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
        key = secrets.randbelow(2**60 - 2**30) + 2**30
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


def _kramer_wrap(payload_code: str, key: int = None) -> str:
    """Wrap final payload into Kramer dynamic class with Kyrie encryption + fake type annotations + anti-dump."""
    from binascii import hexlify
    if key is None:
        key = secrets.randbelow(999000) + 1000

    _content_ = Kyrie.encrypt(payload_code, key=key)
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

    _1_ = (fr"""self.{glob['n_5']}""", fr"""lambda {v_n9}:{fn_unhex}(str({v_n9})).decode()""")
    _2_ = (fr"""self.{glob['n_6']}""", fr"""lambda {v_n1}:exec({v_n1}, globals(), globals())""")
    _3_ = (fr"""_n4_['{glob['n_2']}']""", eval_resolver)
    _4_ = (fr"""self.{glob['n_1']}""", fr"""lambda {v_n1}:"".join(chr(ord({v_t})-{key})if {v_t}!="\u03b6"else"\n"for {v_t} in self.{glob['n_5']}({v_n1})).translate(str.maketrans(dict(zip(self.{glob['n_7']},self.{glob['n_7']}[1:]+self.{glob['n_7']}[:1]))))""")
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

    tmpl = fr"""class {c_name}():
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
    entry = f"[{ts}][{level}]{stg_str} {msg}{dur_str}"
    _LOG_ENTRIES.append(entry)

    if _EngineState.verbose_debug or level in ("ERROR", "WARNING") or _EngineState.profile_mode:
        if level == "ERROR":
            _v(f" [91m[ERROR]{stg_str} {msg}{dur_str}[0m")
            if error is not None:
                tb_lines = traceback.format_exc().strip()
                _LOG_ENTRIES.append(tb_lines)
                if _EngineState.verbose_debug:
                    for l in tb_lines.splitlines():
                        _v(f"   [90m│ {l}[0m")
        elif level == "WARNING":
            _v(f" [93m[WARNING]{stg_str} {msg}{dur_str}[0m")
        elif _EngineState.verbose_debug:
            _v(f" [96m[DEBUG]{stg_str} {msg}{dur_str}[0m")

def _log_stage_error(stage_name: str, exc: Exception):
    tb = traceback.format_exc()
    _STAGE_ERRORS.append({
        "stage": stage_name,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": tb,
        "timestamp": time.time()
    })
    _log_debug(f"{type(exc).__name__}: {exc}", stage=stage_name, error=exc, level="ERROR")
    if _EngineState.strict_mode:
        _v(f" [91m[STRICT MODE ABORT] Terminating due to error in stage '{stage_name}'[0m")
        sys.exit(1)

def _print_profile_waterfall(total_elapsed: float, original_size: int, final_size: int):
    stages = _DEBUG_MAP.get("stages", [])
    if not stages and not _STAGE_ERRORS:
        return

    _v("")
    _v(" ══════════════════════ PERFORMANCE & BOTTLENECK PROFILE ══════════════════════")
    _v(f" {'STAGE':<32} {'TIME (s)':<12} {'% TOTAL':<10} {'SIZE DELTA':<14} {'STATUS'}")
    _v(" ─────────────────────────────────────────────────────────────────────────────")

    slowest_stage = None
    max_duration = -1.0

    for s in stages:
        stg_name = s.get("stage", "Unknown")
        dur = s.get("duration_seconds", 0.0)
        pct = (dur / total_elapsed * 100) if total_elapsed > 0 else 0
        delta = s.get("delta_bytes", 0)
        delta_str = f"+{delta:,} B" if delta >= 0 else f"-{abs(delta):,} B"
        status = "[92m[OK][0m"

        if dur > max_duration:
            max_duration = dur
            slowest_stage = (stg_name, dur, pct)

        _v(f" {stg_name:<32} {dur:>8.4f}s    {pct:>6.1f}%    {delta_str:>12}    {status}")

    for err in _STAGE_ERRORS:
        _v(f" [91m{err['stage']:<32} {'FAILED':>8}        --               --    [ERROR][0m")

    _v(" ─────────────────────────────────────────────────────────────────────────────")
    current_ram = _get_current_ram_mb()
    ram_str = f" | PEAK RAM: {current_ram:.1f} MB" if current_ram > 0 else ""
    _v(f" TOTAL TIME: {total_elapsed:.4f}s | EXPANSION: {original_size:,} B -> {final_size:,} B ({final_size/original_size if original_size>0 else 0:.1f}x){ram_str}")

    if slowest_stage and slowest_stage[1] > 0.1 and slowest_stage[2] >= 25.0:
        _v(f" [93m[BOTTLENECK ADVISORY] Stage '{slowest_stage[0]}' took the longest ({slowest_stage[1]:.3f}s, {slowest_stage[2]:.1f}% of total).[0m")
    if _STAGE_ERRORS:
        _v(f" [91m[WARNING] Encountered {len(_STAGE_ERRORS)} stage exception(s). Run with --debug or inspect log file for tracebacks.[0m")
    _v(" ═════════════════════════════════════════════════════════════════════════════")
    _v("")

def _export_log_file():
    if not _EngineState.log_file_path:
        return
    try:
        with open(_EngineState.log_file_path, "w", encoding="utf-8") as lf:
            lf.write(f"=== TR0NGX OBFUSCATOR EXECUTION & DIAGNOSTIC LOG ===\n")
            lf.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for entry in _LOG_ENTRIES:
                lf.write(entry + "\n")
            if _STAGE_ERRORS:
                lf.write("\n=== STAGE ERROR TRACEBACKS ===\n")
                for err in _STAGE_ERRORS:
                    lf.write(f"\n--- Stage: {err['stage']} ({err['exception_type']}) ---\n")
                    lf.write(err['traceback'] + "\n")
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
    "stages": []
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

def _prompt_input(x):
    formatted = stage(x)
    try:
        sys.stdout.write(formatted)
        sys.stdout.flush()
        return _raw_input("").strip().strip('"').strip("'")
    except (UnicodeEncodeError, Exception):
        enc = sys.stdout.encoding or 'utf-8'
        safe_prompt = formatted.encode(enc, errors='replace').decode(enc, errors='replace')
        sys.stdout.write(safe_prompt)
        sys.stdout.flush()
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
  • Tầng 3: Double Compile Bytecode Loader (marshal + XOR + zlib + bz2 + base85)
  • Tầng 4: Kramer Kyrie Eleison Outer Shield (Mã hóa dịch chuyển Caesar động + Class ảo)
  • Tầng 5: Tên biến tiếng Trung / CJK + Watermark bản quyền PyCool
  • Tầng 6: Emoji Obfuscation (Code → chuỗi emoji 🐀🐁🐂 + self-decoding loader)
  • Tầng 7: Homoglyph Names (Tên biến Cyrillic/Greek trông giống ASCII: a->а, o->о)
  • Tầng 8: Rare Unicode Names (CJK Extension B, Kangxi Radicals: 龘 鱻 𪚥)
  • Tầng 9: Whitespace Obfuscation (Code biến đổi thành không gian trắng space/tab binary)
  • Tầng 10: Extreme Zalgo Diacritics Shield (Chồng lớp dấu tổ hợp làm tê liệt decompiler GUI)
  • Tầng 11: Hyperion Scientific Class Camouflage (Ngụy trang lớp mô phỏng bộ nhớ khoa học)
  • Tầng 12: 3-Track Symbiotic Fused Matrix Shield (Kyrie + Emoji + Whitespace hợp nhất không phình dung lượng)
        """,
        epilog="""
VÍ DỤ SỬ DỤNG:
  1. Chạy CLI đầy đủ tính năng:
     python tr0ngx_obfuscator.py -i script.py -o obf_script.py -m 3 --moreobf y --antidebug y --antivm y --selfmod y --compile y --velimatix y --veli-level 3 --double-compile y --kramer y --hyperion y --camouflage y --matrix y --zalgo y

  2. Chạy nhanh chế độ im lặng (không lag, không banner màu):
     python tr0ngx_obfuscator.py -i script.py -o obf_script.py -m 2 --compile y --kramer y --no-art

  3. Chạy giao diện tương tác TUI:
     python tr0ngx_obfuscator.py

  4. Bật Symbiotic Fused Matrix Shield:
     python tr0ngx_obfuscator.py -i script.py -m 2 --compile y --matrix y --no-art

  5. Bật Extreme Zalgo Diacritics + Homoglyph:
     python tr0ngx_obfuscator.py -i script.py -m 3 --compile y --zalgo y --homoglyph y --no-art

  6. ALL-IN MAXIMUM POWER (toàn bộ ma trận bảo vệ):
     python tr0ngx_obfuscator.py -i script.py -o max.py -m 3 --moreobf y --antidebug y --antivm y --selfmod y --compile y --velimatix y --veli-level 3 --double-compile y --kramer y --cjk-vars y --hyperion y --camouflage y --matrix y --zalgo y --no-art
        """
    )
    # File options
    parser.add_argument("-i", "--input", help="Đường dẫn file Python cần obfuscate", default=None)
    parser.add_argument("-o", "--output", help="Đường dẫn file kết quả xuất ra (mặc định: tr0ngx-<filename>)", default=None)
    
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

    cli_args, unknown = parser.parse_known_args()
    is_cli_mode = bool(cli_args.input is not None)

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

    _setup = None
    if not is_cli_mode:
        _v(" [!] TR0NGX INTERACTIVE SETUP")
        _v("  1. QUICK MODE (Mode 2, Compile, Velimatix L2, Kramer, Anti-Debug)")
        _v("  2. CUSTOM MODE (Cấu hình chi tiết từng bước)")
        _setup = _prompt_input(" Choose mode (1/2): ").strip()
        if _setup == "1":
            cli_args.mode = 2
            cli_args.moreobf = "Y"
            cli_args.antidebug = "Y"
            cli_args.antivm = "N"
            cli_args.selfmod = "N"
            cli_args.compile = "Y"
            cli_args.velimatix = "Y"
            cli_args.veli_level = 2
            cli_args.double_compile = "Y"
            cli_args.kramer = "Y"
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
            cli_args.dyn_strings = "N"
            cli_args.anti_dump = "N"
            cli_args.force_py = "off"

    # Resource capping and output destination
    max_ram = cli_args.max_ram
    max_cores = cli_args.cores
    custom_out = cli_args.output

    # 1. File input
    if is_cli_mode:
        _file = cli_args.input.strip().strip('"').strip("'")
        if not os.path.isfile(_file):
            _v(f" CLI ERROR: File not found: {_file}")
            sys.exit(1)
        with open(_file, "r", encoding="utf-8-sig", errors="replace") as file:
            raw_code = file.read().lstrip('\ufeff').lstrip('\ufeff')
        try:
            _validate_input_source(raw_code)
        except Exception as ve:
            _v(f" [INPUT SECURITY ERROR] {ve}")
            sys.exit(1)
    else:
        _file = _prompt_input(" ENTER FILE: ").strip().strip('"').strip("'")
        while True:
            try:
                with open(_file, "r", encoding="utf-8-sig", errors="replace") as file:
                    raw_code = file.read().lstrip('\ufeff').lstrip('\ufeff')
                try:
                    _validate_input_source(raw_code)
                    ast.parse(raw_code)
                except Exception as e:
                    _v(f" SYNTAX/SECURITY ERROR: {e}")
                    _file = _prompt_input(" ENTER FILE AGAIN: ").strip().strip('"').strip("'")
                    continue
                break
            except FileNotFoundError:
                _file = _prompt_input(" ENTER FILE AGAIN (not found): ").strip().strip('"').strip("'")

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

    # Force Python version
    if cli_args.force_py is not None:
        if cli_args.force_py.lower() in ["n", "no", "off", "none"]:
            force_py_choice = "N"
            forced_py_ver = ""
        else:
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

    # Custom Output Path in interactive prompt if not passed
    if not is_cli_mode and custom_out is None and _setup != "1":
        out_inp = _prompt_input(" CUSTOM OUTPUT PATH (press Enter for default): ").strip()
        if out_inp:
            custom_out = out_inp

    # Password resolution
    password = cli_args.password
    if cli_args.password_file and os.path.isfile(cli_args.password_file):
        try:
            with open(cli_args.password_file, "r", encoding="utf-8") as pf:
                password = pf.read().strip()
        except Exception:
            pass
    if not password and os.environ.get("TR0NGX_PASSWORD"):
        password = os.environ.get("TR0NGX_PASSWORD")
    if not password and not is_cli_mode and method.upper() == "Y" and _setup != "1":
        pwd_inp = _prompt_input(" PASSWORD ENCRYPTION (press Enter for obfuscation-only): ").strip()
        if pwd_inp:
            password = pwd_inp
    _EngineState.encryption_password = password

    if cli_args.seed is not None:
        _EngineState.custom_seed = cli_args.seed
        random.seed(cli_args.seed)

    max_output_size_bytes = _parse_size_str(cli_args.max_output_size)
    _EngineState.max_output_size = max_output_size_bytes

    # Apply resource capping
    _apply_resource_limits(max_ram, max_cores)

    return {
        "file": _file,
        "code": raw_code,
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
        "force_py_choice": force_py_choice,
        "forced_py_ver": forced_py_ver,
        "debug_map": debug_map_arg,
        "max_ram": max_ram,
        "max_cores": max_cores,
        "custom_out": custom_out
    }

def _reset_global_state():
    """Reset all global state to prevent cross-contamination between multiple obfuscation runs."""
    global _used_names, _DEBUG_MAP, _LOG_ENTRIES, _STAGE_ERRORS
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
    _LOG_ENTRIES.clear()
    _STAGE_ERRORS.clear()
    _DEBUG_MAP["renamed_functions"].clear()
    _DEBUG_MAP["renamed_builtins"].clear()
    _DEBUG_MAP["renamed_variables"].clear()
    _DEBUG_MAP["stages"].clear()

# ═══════════════════════════════════════════════════════════════
def main():
    # MAIN EXECUTION (CLI + TUI)
    # ═══════════════════════════════════════════════════════════════
    _reset_global_state()
    _show_banner()
    _cfg = get_args_or_prompt()
    _file = _cfg["file"]
    code = _cfg["code"]
    mode = _cfg["mode"]
    moreobf = _cfg["moreobf"]
    antidebug = _cfg["antidebug"]
    antivm = _cfg.get("antivm", "N")
    selfmodify = _cfg["selfmodify"]
    method = _cfg["method"]
    encryption_password = _cfg.get("password")
    custom_seed = _cfg.get("seed")
    max_output_size = _cfg.get("max_output_size")
    velimatix = _cfg["velimatix"]
    veli_level = _cfg["veli_level"]
    double_compile = _cfg["double_compile"]
    kramer_wrap_choice = _cfg["kramer"]
    cjk_choice = _cfg["cjk"]
    matrix_choice = _cfg.get("matrix", "N")
    emoji_obf_choice = _cfg.get("emoji_obf", "N")
    homoglyph_choice = _cfg.get("homoglyph", "N")
    rare_unicode_choice = _cfg.get("rare_unicode", "N")
    zalgo_choice = _cfg.get("zalgo", "N")
    whitespace_obf_choice = _cfg.get("whitespace_obf", "N")
    blank_padding_choice = _cfg.get("blank_padding", "N")
    hyperion_choice = _cfg.get("hyperion", "N")
    camouflage_choice = _cfg.get("camouflage", "N")
    math_opaque_choice = _cfg.get("math_opaque", "N")
    dyn_strings_choice = _cfg.get("dyn_strings", "N")
    antidump_choice = _cfg.get("anti_dump", "N")
    force_py_choice = _cfg["force_py_choice"]
    forced_py_ver = _cfg["forced_py_ver"]
    custom_out = _cfg["custom_out"]

    _debug_map_choice = _cfg.get("debug_map")

    _DEBUG_MAP["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _DEBUG_MAP["source_file"] = os.path.abspath(_file)
    _DEBUG_MAP["options"] = {
        "mode": mode,
        "moreobf": moreobf,
        "antidebug": antidebug,
        "antivm": antivm,
        "selfmodify": selfmodify,
        "compile": method,
        "password_protected": bool(encryption_password),
        "seed": custom_seed,
        "max_output_size": max_output_size,
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
        "force_py": forced_py_ver if force_py_choice.upper() == "Y" else "OFF"
    }

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
        _init_rare_chars()  # Pre-init the rare char pool
    if zalgo_choice.upper() == "Y":
        _EngineState.use_zalgo_marks = True
        _init_combining_marks()
    if hyperion_choice.upper() == "Y":
        _EngineState.use_hyperion = True
    if camouflage_choice.upper() == "Y":
        _EngineState.use_camouflage = True

    # Regenerate all runtime AST variable symbols using chosen character set
    _refresh_runtime_symbols()

    _v(" ═══ STARTING OBFUSCATION ═══")
    start_time = time.time()

    check = 0

    # ═══ Step 0: Hyperion AST & Token Engine (if enabled) ═══
    if hyperion_choice.upper() == "Y":
        try:
            t0 = time.time()
            sz0 = len(code)
            _v_step(0, 8, "Hyperion Token & AST Remapping Engine...")
            code = _hyperion_full_transform(code, camouflage=False, shell=False, randlines=False)
            _v("        - Dynamic Builtin Imports")
            _v("        - Variable & Import Scope Remapping")
            _v("        - Math & String Identifier Splitting")
            _v("        - Dynamic Globals/Locals Aliasing")
            _track_debug_stage("0_hyperion_engine", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("0_hyperion_engine", e)

    # ═══ Step 1: Syntax transform ═══
    try:
        t0 = time.time()
        sz0 = len(code)
        _v_step(1, 8, "Syntax transformation...")
        code = _syntax(code)
        _track_debug_stage("1_syntax_transform", time.time() - t0, sz0, len(code))
    except Exception as e:
        _log_stage_error("1_syntax_transform", e)

    # ═══ Step 2: AST junk injection ═══
    if moreobf.upper() == "Y":
        _v_step(2, 8, "AST junk injection...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = __moreobf(code)
            check = 5
            _track_debug_stage("2_ast_junk_injection", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2_ast_junk_injection", e)
            check = 5

    # ═══ Step 2.5: Mathematical Opaque Predicates (Module B) ═══
    if math_opaque_choice.upper() == "Y":
        _v_step("2.5", 8, "Mathematical Opaque Predicates (Quadratic Non-Residue mod 7 & Euler invariants)...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _math_opaque_obf(code)
            _track_debug_stage("2.5_math_opaque_predicates", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.5_math_opaque_predicates", e)

    # ═══ Step 2.7: Dynamic Per-Callsite String XOR Encryption (Module C) ═══
    if dyn_strings_choice.upper() == "Y":
        _v_step("2.7", 8, "Dynamic Per-Callsite String XOR Encryption...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _dyn_strings_obf(code)
            _track_debug_stage("2.7_dyn_strings_encryption", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("2.7_dyn_strings_encryption", e)

    # ═══ Step 3: Version check (Forced or Current) ═══
    target_ver_str = forced_py_ver if (force_py_choice.upper() == "Y" and forced_py_ver) else f"{sys.version_info.major}.{sys.version_info.minor}"
    checkver = f"""import sys
_target_ver = '{target_ver_str}'
_curr_ver = sys.version.split()[0]
_curr_maj_min = f"{{sys.version_info.major}}.{{sys.version_info.minor}}"
if _curr_maj_min != _target_ver and not sys.version.startswith(_target_ver):
    print(f"[-] PYTHON VERSION MISMATCH! This obfuscated script requires Python {target_ver_str}.x (Current: {{_curr_ver}}). Please run with python{target_ver_str} or install Python {target_ver_str}.", flush=True)
    __import__("os")._exit(1)
"""

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

    # ═══ Step 4: VELIMATIX ENGINE ═══
    if velimatix.upper() == "Y":
        _v_step(3, 8, f"Velimatix engine (level {veli_level})...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _velimatix_obf(code, mode=veli_level)
            _v("        - BiOpaque predicates")
            _v("        - Call obfuscation")
            _v("        - Dead code injection")
            if veli_level >= 2:
                _v("        - Exception jump flow")
                _v("        - Import obfuscation")
                _v("        - Builtin renaming")
            if veli_level >= 3:
                _v("        - Match-case control flow")
                _v("        - Constant mutation (XOR chain)")
                _v("        - Method cloning")
                _v("        - String bytewise encoding")
            _track_debug_stage(f"3_velimatix_level_{veli_level}", time.time() - t0, sz0, len(code))
        except Exception as e:
            _v(f" WARNING: Velimatix partial: {e}")

    # ═══ Step 5: Main obfuscation layers ═══
    _v_step(4, 8, f"Applying {mode}-layer tr0ngx obfuscation...")
    for i in range(mode):
        try:
            t0 = time.time()
            sz0 = len(code)
            new_code = obf(code)
            compile(new_code, "<test_layer>", "exec")
            code = new_code
            _track_debug_stage(f"4_tr0ngx_layer_{i+1}_of_{mode}", time.time() - t0, sz0, len(code))
            _v(f"        - Layer {i + 1}/{mode} complete")
        except Exception as e:
            _v(f" WARNING: Layer {i + 1} issue: {e}")
            break

    # ═══ Step 6: Anti-debug & Anti-Analysis Shield Matrix ═══
    if antidebug.upper() == "Y":
        _v_step(5, 8, "Injecting anti-debug shield...")
        t0 = time.time()
        sz0 = len(code)
        if velimatix.upper() == "Y":
            _v("        - Adding Velimatix anti-hook layer...")
            code = velimatix_anti_hook + code
        code = anti + code
        _track_debug_stage("5_anti_debug_injection", time.time() - t0, sz0, len(code))

    # ═══ Step 6.2: Anti-VM & Sandbox Detection ═══
    if antivm.upper() == "Y":
        _v_step("5.2", 8, "Injecting Anti-VM & Sandbox shield...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_anti_vm_shield() + code
        _track_debug_stage("5.2_anti_vm_injection", time.time() - t0, sz0, len(code))

    # ═══ Step 6.4: In-Memory Anti-Dump & GC Scrubber (Module D) ═══
    if antidump_choice.upper() == "Y":
        _v_step("5.4", 8, "Injecting In-Memory Anti-Dump & GC Scrubber shield...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_anti_dump_shield() + code
        _track_debug_stage("5.4_anti_dump_shield", time.time() - t0, sz0, len(code))

    # ═══ Step 6.5: Self-modifying ═══
    if selfmodify.upper() == "Y":
        _v_step("5.5", 8, "Adding self-modifying layer...")
        t0 = time.time()
        sz0 = len(code)
        code = _generate_self_modify_wrapper() + code
        _track_debug_stage("5.5_self_modify_layer", time.time() - t0, sz0, len(code))

    # ═══ Step 8: Compile or output ═══
    if method.upper() != "Y":
        _v_step(6, 8, "Building non-compiled output...")
        t0 = time.time()
        sz0 = len(code)
        code = author + var + code
        if check == 5:
            try:
                code = __moreobf(code)
            except Exception:
                try:
                    code = __moreobf(code)
                except Exception:
                    pass

        if velimatix.upper() == "Y" and veli_level >= 2:
            _v_step(7, 8, "Velimatix final pass...")
            try:
                code = OBF_Spam(code, level=min(veli_level, 2))
            except Exception:
                pass

        _track_debug_stage("6_non_compiled_packaging", time.time() - t0, sz0, len(code))
        _v_step(8, 8, "Finalizing...")
    else:
        _v_step(6, 8, "Multi-layer compilation...")
        t0 = time.time()
        sz0 = len(code)
        if check == 5:
            try:
                code = __moreobf(code)
            except Exception:
                try:
                    code = __moreobf(code)
                except Exception:
                    pass

        code = ANTI_PYCDC + code

        # ═══ Double compile path ═══
        if double_compile.upper() == "Y":
            _v_step(7, 8, "DOUBLE COMPILE (Tr0ngX + Velimatix)...")
            try:
                code = _double_compile(var + code, target_ver=target_ver_str, password=encryption_password)
                _v("        - Inner: marshal+XOR×2+zlib×2+bz2+base85")
                _v("        - Outer: Velimatix obfuscated loader")
                _v_step(8, 8, "Double compilation complete!")
                _track_debug_stage("7_double_compile_packaging", time.time() - t0, sz0, len(code))
            except Exception as e:
                _v(f" WARNING: Double compile failed: {e}")
                _v(" FALLBACK: Standard compilation...")
                double_compile = "N"

        # ═══ Standard compile path ═══
        if double_compile.upper() != "Y":
            try:
                compiled_bytes = marshal.dumps(compile(code, "<tr0ngx>", "exec"))
            except SyntaxError as e:
                _v(f" COMPILE ERROR: {e}")
                _v(" FALLBACK: Non-compiled mode")
                code = var + code
                _dir_n, _base_n = os.path.split(_file)
                output_file = os.path.join(_dir_n, "tr0ngx-" + _base_n) if _dir_n else ("tr0ngx-" + _base_n)
                _safe_atomic_write(output_file, str(code), input_file=_file)
                elapsed = time.time() - start_time
                _v(f" [SAVED] {output_file} ({elapsed:.2f}s)")
                sys.exit()

            if encryption_password:
                _v(" [6.5/8] Encrypting with Argon2id / PBKDF2 authenticated AEAD...")
            else:
                _v(" [6.5/8] Encrypting with authenticated multi-layer AEAD (Obfuscation-Only)...")
            encrypted_data, _salt = _multi_layer_encrypt(compiled_bytes, password=encryption_password)

            l = len(encrypted_data)
            parts = []
            num_parts = 8
            for i in range(num_parts):
                start = (l * i) // num_parts
                end = (l * (i + 1)) // num_parts
                parts.append(repr(encrypted_data[start:end]))

            _f = "for"
            _i = "in"
            _t = rd()

            part_vars = [rd() for _ in range(num_parts)]
            part_assignments = '\n'.join(
                f"{part_vars[i]}  {'  ' * 500}={parts[i]}" for i in range(num_parts)
            )
            part_concat = '+'.join(part_vars)

            _v_step(7, 8, "Building final authenticated payload...")

            _en_var = rd()
            _july_var = rd()
            _birth_var = rd()
            _b85_var = rd()
            _exec_var = rd()

            if encryption_password:
                _auth_dec_section = f"""
def _auth_decrypt(raw_bytes, pwd_str):
    salt = raw_bytes[:16]
    nonce = raw_bytes[16:28]
    tag = raw_bytes[28:60]
    ct = raw_bytes[60:]
    p_bytes = pwd_str.encode('utf-8')
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        ke = Argon2id(salt=salt + b'__enc__', length=32, iterations=4, lanes=4, memory_cost=131072).derive(p_bytes)
        km = Argon2id(salt=salt + b'__mac__', length=32, iterations=4, lanes=4, memory_cost=131072).derive(p_bytes)
    except Exception:
        ke = hashlib.pbkdf2_hmac('sha256', p_bytes, salt + b'__enc__', 600000, 32)
        km = hashlib.pbkdf2_hmac('sha256', p_bytes, salt + b'__mac__', 600000, 32)
    expected_tag = hmac.new(km, salt + nonce + ct, hashlib.sha256).digest()
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

_pwd = __import__("os").environ.get("TR0NGX_PASSWORD")
if not _pwd:
    _pwd = getattr(__builtins__, 'input', lambda *a: "")("[TR0NGX] Enter decryption password: ")
"""
                _auth_dec_call = "_auth_decrypt(_step3, _pwd)"
            else:
                _auth_dec_section = """
def _derive_runtime_keys(salt):
    _parts = []
    _parts.append(sys.version[:5].encode())
    _parts.append(_platform.python_implementation().encode())
    _parts.append(salt)
    _parts.append(str(sys.maxsize).encode())
    _parts.append(sys.byteorder.encode())
    _combined = b''.join(_parts)
    _enc_k = hashlib.sha256(_combined + b'__enc__').digest()
    _mac_k = hashlib.sha256(_combined + b'__mac__').digest()
    return _enc_k, _mac_k

def _auth_decrypt(raw_bytes):
    salt = raw_bytes[:16]
    nonce = raw_bytes[16:28]
    tag = raw_bytes[28:60]
    ct = raw_bytes[60:]
    _enc_k, _mac_k = _derive_runtime_keys(salt)
    ke = hashlib.pbkdf2_hmac('sha256', salt, _enc_k, 50000, 32)
    km = hashlib.pbkdf2_hmac('sha256', salt, _mac_k, 50000, 32)
    expected_tag = hmac.new(km, salt + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise SystemExit(1)
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(ct):
        block = hmac.new(ke, nonce + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))
"""
                _auth_dec_call = "_auth_decrypt(_step3)"

            code = author + var + f"""

import hashlib, hmac, platform as _platform, sys, os

sys.dont_write_bytecode = True
_target_ver = '{target_ver_str}'
_curr_ver = sys.version.split()[0]
_curr_maj_min = f"{{sys.version_info.major}}.{{sys.version_info.minor}}"
if _curr_maj_min != _target_ver and not sys.version.startswith(_target_ver):
    print(f"[-] PYTHON VERSION MISMATCH! This obfuscated script requires Python {target_ver_str}.x (Current: {{_curr_ver}}). Please run with python{target_ver_str} or install Python {target_ver_str}.", flush=True)
    __import__("os")._exit(1)

{_auth_dec_section}

{_en_var} = getattr({___import__}({obfstr("marshal")}), {obfstr("loads")})
{_july_var} = getattr({___import__}({obfstr("zlib")}), {obfstr("decompress")})
{_birth_var} = getattr({___import__}({obfstr("bz2")}), {obfstr("decompress")})
{_b85_var} = getattr({___import__}({obfstr("base64")}), {obfstr("b85decode")})

{part_assignments}

try:
    _payload = {part_concat}
    _step1 = {_b85_var}(_payload)
    _step2 = {_july_var}(_step1)
    _step3 = {_birth_var}(_step2)
    _step4 = {_auth_dec_call}
    _step5 = {_july_var}(_step4)
    exec({_en_var}(_step5), globals(), globals())
    del _payload, _step1, _step2, _step3, _step4, _step5
except Exception as _e:
    raise _e
"""

            if velimatix.upper() == "Y" and veli_level >= 2:
                _v_step(8, 8, "Velimatix final pass on loader...")
                try:
                    code = OBF_Spam(code, level=1)
                except Exception:
                    pass
            else:
                _v_step(8, 8, "Finalizing...")
            _track_debug_stage("7_standard_compile_packaging", time.time() - t0, sz0, len(code))

    # ═══════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════
    # SAVE OUTPUT & OUTER SHIELD MATRIX FUSION
    # ═══════════════════════════════════════════════════════════════

    multi_shield_count = sum(1 for c in [kramer_wrap_choice, emoji_obf_choice, whitespace_obf_choice] if c.upper() == "Y")
    is_fused_shield = (matrix_choice.upper() == "Y") or (multi_shield_count >= 2)

    # ═══ Intermediate Camouflage Layer (if enabled) ═══
    if camouflage_choice.upper() == "Y":
        _v(" [12] Applying Hyperion Scientific Class Camouflage...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _hyperion_camouflage(code)
            _v("        - Fake Simulation Class Generation")
            _v("        - Polymorphic Property & Memory Emulation")
            _v("        - Dynamic Payload Reconstructor")
            _track_debug_stage("12_hyperion_camouflage", time.time() - t0, sz0, len(code))
        except Exception as e:
            _v(f" WARNING: Camouflage error: {e}")

    # ═══ Outer Dynamic Shield Matrix ═══
    if is_fused_shield:
        _v(" [9/9] Applying Fused Matrix Shield (Kyrie + Emoji + Whitespace Symbiotic)...")
        try:
            t0 = time.time()
            sz0 = len(code)
            code = _fused_matrix_wrap(code)
            _v("        - 3-Track Interleaved Symbiotic Loader (Zero Bloat)")
            _v("        - Kyrie Caesar + Emoji Stream + Whitespace Bitfield Matrix")
            _v("        - Fast In-Memory Reconstruction Pipeline")
            _track_debug_stage("8_fused_matrix_shield", time.time() - t0, sz0, len(code))
        except Exception as e:
            _log_stage_error("8_fused_matrix_shield", e)
    else:
        # Single outer shield path
        if kramer_wrap_choice.upper() == "Y":
            _v(" [9/9] Applying Kramer Outer Shield (Kyrie Eleison)...")
            try:
                t0 = time.time()
                sz0 = len(code)
                code = _kramer_wrap(code)
                _v("        - Kyrie Eleison Caesar Index Shift")
                _v("        - Dynamic Obfuscated Kramer Class Wrapper")
                _v("        - Anti-Tamper String Inspection")
                _track_debug_stage("8_kramer_outer_shield", time.time() - t0, sz0, len(code))
            except Exception as e:
                _v(f" WARNING: Kramer wrap error: {e}")

        # ═══ Emoji Obfuscation Layer ═══
        if emoji_obf_choice.upper() == "Y":
            _v(" [10] Applying Emoji Obfuscation (U+1F400 Animal Block)...")
            try:
                t0 = time.time()
                sz0 = len(code)
                if method.upper() == "Y":
                    code = _emoji_encode_v2(code)
                else:
                    code = _emoji_encode(code)
                _v("        - Code -> Emoji Sequence Encoder")
                _v("        - Compact Self-Decoding Loader")
                _track_debug_stage("9_emoji_obfuscation", time.time() - t0, sz0, len(code))
            except Exception as e:
                _v(f" WARNING: Emoji encoding error: {e}")

        # ═══ Whitespace Obfuscation Layer ═══
        if whitespace_obf_choice.upper() == "Y":
            _v(" [11] Applying Whitespace Obfuscation (invisible code)...")
            try:
                t0 = time.time()
                sz0 = len(code)
                if method.upper() == "Y":
                    code = _whitespace_encode_v2(code)
                else:
                    code = _whitespace_encode(code)
                _v("        - Code -> Space/Tab Binary Encoding")
                _v("        - Self-Decoding Whitespace Loader")
                _track_debug_stage("10_whitespace_obfuscation", time.time() - t0, sz0, len(code))
            except Exception as e:
                _v(f" WARNING: Whitespace encoding error: {e}")

    _blank_pad = ("\n" * 300) if blank_padding_choice.upper() == "Y" else ""
    if zalgo_choice.upper() == "Y":
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + _gen_zalgo_cascade_docstring(paragraphs=1, lines_per_p=6, chars_per_line=12, marks_per_char=50) + "\n" + code + "\n" + _gen_zalgo_cascade_docstring(paragraphs=1, lines_per_p=4, chars_per_line=12, marks_per_char=50)
    elif cjk_choice.upper() == "Y" or matrix_choice.upper() == "Y" or rare_unicode_choice.upper() == "Y":
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + _gen_cjk_docstring(paragraphs=1, lines_per_p=5, chars_per_line=36) + "\n" + code + "\n" + _gen_cjk_docstring(paragraphs=1, lines_per_p=4, chars_per_line=36)
    else:
        code = _gen_tr0ngx_header() + "\n" + _blank_pad + code

    if custom_out:
        output_file = custom_out.strip().strip('"').strip("'")
    else:
        _dir_n, _base_n = os.path.split(_file)
        output_file = os.path.join(_dir_n, "tr0ngx-" + _base_n) if _dir_n else ("tr0ngx-" + _base_n)

    try:
        _safe_atomic_write(output_file, str(code), input_file=_file)

        elapsed = time.time() - start_time
        file_size = os.path.getsize(output_file)
        original_size = os.path.getsize(_file)
        ratio = file_size / original_size if original_size > 0 else 0

        # Enforce maximum output size limit (DoS prevention)
        if max_output_size and file_size > max_output_size:
            err_msg = f" [ERROR] Output size ({file_size:,} bytes) exceeded maximum limit ({max_output_size:,} bytes). Aborting."
            _v(_gradient_text(err_msg, (255, 40, 40), (255, 120, 40)))
            if os.path.isfile(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass
            sys.exit(1)

        # Warn if output is excessively large
        _SIZE_WARN_MB = 50
        if file_size > _SIZE_WARN_MB * 1024 * 1024:
            warn_str = f" WARNING: Output is {file_size / (1024*1024):.1f} MB (>{_SIZE_WARN_MB}MB). Consider using lower mode or fewer layers."
            tip_str = f"   Tip: Mode 2 + compile + kramer gives good protection with much smaller output."
            _v(_gradient_text(warn_str, (255, 45, 45), (255, 195, 20)))
            _v(_gradient_text(tip_str, (255, 95, 25), (255, 220, 45)))

        _DEBUG_MAP["output_file"] = os.path.abspath(output_file)
        _DEBUG_MAP["original_size_bytes"] = original_size
        _DEBUG_MAP["output_size_bytes"] = file_size
        _DEBUG_MAP["expansion_ratio"] = round(ratio, 2)
        _DEBUG_MAP["total_time_seconds"] = round(elapsed, 4)

        # ── Write Debug Map JSON if requested ──
        if _debug_map_choice is not None:
            if _debug_map_choice == "AUTO":
                dbg_map_file = os.path.splitext(output_file)[0] + ".debug.json"
            else:
                dbg_map_file = _debug_map_choice.strip().strip('"').strip("'")
            try:
                import json
                dbg_map_file = _validate_and_sanitize_output_path(dbg_map_file, input_file=_file)
                _safe_atomic_write(dbg_map_file, json.dumps(_DEBUG_MAP, indent=2, ensure_ascii=False), input_file=_file)
                _v(f" [DEBUG MAP] {dbg_map_file}")
            except Exception as de:
                _v(f" WARNING: Debug map export failed: {de}")

        # New modes summary
        _new_modes = []
        if is_fused_shield:
            _new_modes.append("MATRIX-FUSED (3-Track Symbiotic)")
        else:
            if emoji_obf_choice.upper() == "Y":
                _new_modes.append("EMOJI")
            if whitespace_obf_choice.upper() == "Y":
                _new_modes.append("WHITESPACE")
        if _EngineState.use_fused_names:
            _new_modes.append("HYBRID-VARS")
        else:
            if homoglyph_choice.upper() == "Y":
                _new_modes.append("HOMOGLYPH")
            if rare_unicode_choice.upper() == "Y":
                _new_modes.append("RARE-UNI")
            if zalgo_choice.upper() == "Y":
                _new_modes.append("ZALGO-MARKS (Z͑͗͑͗... Diacritics)")
        if hyperion_choice.upper() == "Y":
            _new_modes.append("HYPERION-ENGINE")
        if camouflage_choice.upper() == "Y":
            _new_modes.append("HYPERION-CAMOUFLAGE")
        if math_opaque_choice.upper() == "Y":
            _new_modes.append("MATH-OPAQUE (Quadratic/Euler Invariants)")
        if dyn_strings_choice.upper() == "Y":
            _new_modes.append("DYN-STRINGS (Per-Callsite XOR)")
        if antidump_choice.upper() == "Y":
            _new_modes.append("ANTI-DUMP (GC Scrubber)")

        _summary_lines = [
            f"File Saved   : {output_file}",
            f"Original Size: {original_size:,} bytes",
            f"Output Size  : {file_size:,} bytes ({ratio:.1f}x)",
            f"Time Taken   : {elapsed:.2f}s",
            f"Mode         : {mode} | Veli: {velimatix.upper()}{f'(L{veli_level})' if velimatix.upper()=='Y' else ''}",
            f"Compile      : {method.upper()} | Double: {double_compile.upper() if method.upper()=='Y' else 'N'}",
            f"Protections  : Anti-Debug={antidebug.upper()} | Anti-VM={antivm.upper()} | Anti-Dump={antidump_choice.upper()} | Self-Mod={selfmodify.upper()} | Kramer={kramer_wrap_choice.upper()}"
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
        _v(" OBFUSCATION COMPLETE!")
    except Exception as e:
        _v(f" ERROR SAVING: {e}")

if __name__ == "__main__":
    main()
