# AUTO-SPLIT from tr0ngx_obfuscator.py (mechanical slice, imports pending repair)
import sys
import random
import zlib
import bz2
import marshal
import base64

from . import config as _cfg
from .diagnostics import _log_debug
from .names import _FROZEN_NAME_MAP, _trx_rand, rd

_PYVER_TAG = f"{sys.version_info.major}.{sys.version_info.minor}"

# ═══════════════════════════════════════════════════════════════
# KRAMER ENGINE - KYRIE ELEISON & OBFUSCATED CLASS WRAPPER
# ═══════════════════════════════════════════════════════════════

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


def _emoji_encode_v2(code_str, already_packaged: bool = False):
    """Advanced emoji encoding: marshal+compress+emoji with obfuscated loader.

    PERF (2026-08): already_packaged=True skips the redundant compile() when the
    payload is an already-sealed loader; the emoji stream still encodes the full
    text, so protection is unchanged."""
    if already_packaged:
        compiled = code_str.encode('utf-8')
    else:
        try:
            compiled = marshal.dumps(compile(code_str, '<emoji>', 'exec'))
        except SyntaxError:
            compiled = code_str.encode('utf-8')
    compressed = zlib.compress(compiled, 9)
    _EMOJI_BASE = 0x1F400
    emoji_data = ''.join(chr(_EMOJI_BASE + b) for b in compressed)
    v1 = rd() if not _cfg._EngineState.use_cjk_names and not _cfg._EngineState.use_homoglyph_names and not _cfg._EngineState.use_rare_unicode_names else '_e'
    v2 = rd() if not _cfg._EngineState.use_cjk_names and not _cfg._EngineState.use_homoglyph_names and not _cfg._EngineState.use_rare_unicode_names else '_d'
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


def _whitespace_encode_v2(code_str, already_packaged: bool = False):
    """Advanced whitespace encoding with marshal compilation.

    PERF (2026-08): already_packaged=True skips the redundant compile(); the
    whitespace bitfield still encodes the full text byte-for-byte."""
    if already_packaged:
        compiled = code_str.encode('utf-8')
    else:
        try:
            compiled = marshal.dumps(compile(code_str, '<ws>', 'exec'))
        except SyntaxError:
            compiled = code_str.encode('utf-8')
    compressed = zlib.compress(compiled, 9)
    # PERF: table-driven bit expansion (identical output to per-bit appends)
    _ws_byte_map = {
        b: ''.join('\t' if (b >> bp) & 1 else ' ' for bp in range(7, -1, -1))
        for b in range(256)
    }
    ws_data = ''.join(map(_ws_byte_map.__getitem__, compressed))
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

def _fused_matrix_wrap(payload_code: str, key: int = None, already_packaged: bool = False) -> str:
    """Fuses Kramer Kyrie Caesar + Emoji Stream + Whitespace Bitfields
    into an interwoven symbiotic matrix loader. 100% Polymorphic & Disguised.

    PERF (2026-08): already_packaged=True skips the redundant CPython compile()
    pass when the payload is already a sealed loader produced by double-compile.
    The 3-track matrix still encrypts the ENTIRE text byte-for-byte, so the
    protection surface is identical - only wasted parser arena is removed
    (measured peak-RSS reduction from ~8.6GB to <2GB on full-option builds).
    """
    if key is None:
        key = _trx_rand(2**60 - 2**30) + 2**30
    if already_packaged:
        compiled = payload_code.encode('utf-8')
    else:
        try:
            compiled = marshal.dumps(compile(payload_code, '<fused_payload>', 'exec'))
        except SyntaxError:
            compiled = payload_code.encode('utf-8')

    compressed = zlib.compress(bz2.compress(compiled), 9)
    del compiled
    b85 = base64.b85encode(compressed).decode('ascii')
    del compressed

    _EMOJI_BASE = 0x1F400
    _n7_ = bytes(list(range(97, 123)) + list(range(48, 58))).decode('latin1')

    track_k = []
    track_e = []
    track_w = []

    # PERF (2026-08): precomputed per-symbol tables replace per-char
    # str.index()/membership scans and 8x per-bit list appends. Every table is
    # derived from the EXACT same formulas as the original loop, so sk/se/sw
    # are bit-identical to the previous implementation for any (b85, key) pair
    # and the runtime decoder lambda stays valid unchanged.
    _k_shift = key % 10000
    _k_low6 = key & 0x3F
    # original formula: rot = _n7_[_n7_.index(ch) - 1]; then chr(ord(rot) + shift)
    _n7_len = len(_n7_)
    _kyrie_map = {c: chr(ord(_n7_[(i - 1) % _n7_len]) + _k_shift) for i, c in enumerate(_n7_)}
    _kyrie_plain_map = {}
    _emoji_map = {}
    _ws_map = {
        b: ''.join('\t' if (b >> bp) & 1 else ' ' for bp in range(7, -1, -1))
        for b in range(256)
    }

    # 64-Bit High-Entropy Knuth LCG Stream State (Period = 2^64)
    seed = (key ^ 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    _LCG_MUL = 6364136223846793005
    _LCG_ADD = 1442695040888963407
    _U64_MASK = 0xFFFFFFFFFFFFFFFF

    for ch in b85:
        seed = (seed * _LCG_MUL + _LCG_ADD) & _U64_MASK
        mod = (seed >> 32) % 3
        if mod == 0:
            # 1. Kyrie Alphabet Rotation + Dynamic Caesar Shift
            t = _kyrie_map.get(ch)
            if t is None:
                t = _kyrie_plain_map.get(ch)
                if t is None:
                    t = chr(ord(ch) + _k_shift)
                    _kyrie_plain_map[ch] = t
            track_k.append(t)
        elif mod == 1:
            # 2. Masked Emoji Stream
            t = _emoji_map.get(ch)
            if t is None:
                t = chr(_EMOJI_BASE + (ord(ch) ^ _k_low6))
                _emoji_map[ch] = t
            track_e.append(t)
        else:
            # 3. Pure Space/Tab Binary Bitfield
            track_w.append(_ws_map[ord(ch)])

    sk = ''.join(track_k)
    del track_k
    se = ''.join(track_e)
    del track_e
    sw = ''.join(track_w)
    del track_w
    _b85_len = len(b85)
    del b85

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
        fr"""lambda {v_k},{v_e},{v_w},{v_tot}={_b85_len},{v_key}={key},{v_eb}={_EMOJI_BASE}: """
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
    if already_packaged:
        # TEXT-MODE finalizer: the payload is sealed loader SOURCE (not raw
        # marshal), so after the identical 3-track decode we exec the
        # decompressed utf-8 text directly. Track encoding/interleaving is
        # byte-identical to marshal mode - only the terminal step differs.
        _2_ = (fr"""self.{glob['n_6']}""", fr"""lambda {v_n1}:exec({imp_bz2}.decompress({imp_zlib}.decompress({imp_b64}.b85decode({v_n1}.encode(bytes([97,115,99,105,105]).decode())))).decode(bytes([117,116,102,45,56]).decode()), globals(), globals())""")
    else:
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

    # PERF (2026-08): literals are interpolated directly instead of three
    # full-string .replace() passes - identical output, no 3x whole-payload
    # copies/scans on multi-hundred-MB builds.
    _spk_lit = repr(sk)
    del sk
    _emj_lit = '"""' + se + '"""'
    del se
    _wsp_lit = '"""' + sw + '"""'
    del sw

    loader = fr"""class {c_name}():
 def {m_decoy1}(self,*_a:{random.choice(_types_)},**_kw:{random.choice(_types_)})->{random.choice(_types_)}:
  return (_a[0] if _a else 0)
 def {m_dec}(self,*_n2_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  {_vars_}
  return self.{glob['n_8']}(_n2_[0], _n2_[1], _n2_[2])
 def {m_decoy2}(self,_x:{random.choice(_types_)}={random.randint(100,999)})->int:
  return (_x * (_x + 1)) ^ 0x55AA
 def {m_init}(self,*_n3_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  self.{m_dec}(*_n3_,**_n4_)
{c_name}({_spk_lit},{_emj_lit},{_wsp_lit})""".strip()

    return loader


def _exotic_payload_wrap(code_str: str, use_bitmatrix: bool = True, use_base4096: bool = True) -> str:
    """Wrap payload with tr0ngx_exotic layers: BitMatrix byte transform and/or
    Base4096 astral glyph encoding. Generated loader embeds standalone decoders."""
    try:
        from . import exotic as _tex
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

