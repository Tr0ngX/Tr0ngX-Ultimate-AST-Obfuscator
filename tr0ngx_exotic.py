"""
tr0ngx_exotic.py - Exotic obfuscation primitives library for Tr0ngX Ultimate AST Obfuscator.

Self-contained, stdlib-only (Python 3.10 - 3.14) toolkit exposing:

    Identifier pools (XID-safe, NFKC-deduplicated, compile-probed):
        build_identifier_pool(kind, count, rng) -> list[str]
        validate_identifier(name)               -> bool
        pool_kinds()                            -> tuple[str, ...]

    Payload codecs (bytes -> str, with standalone inline-able decoder sources):
        encode_base4096(data, rng)              -> (payload, meta)
        base4096_decoder_source(meta)           -> str   # pure-builtin decoder source
        encode_base256_exotic(data, rng)        -> (payload, meta)
        base256_exotic_decoder_source(meta)     -> str   # pure-builtin decoder source

    Invertible byte transforms:
        bit_matrix_transform(data, rng, rounds) -> (data, key_material)
        inverse_bit_matrix(data, key_material)  -> bytes
        bit_matrix_decoder_source(key_material) -> str   # pure-builtin inverse source

    Track interleaving:
        interleave_tracks(a, b, rng)            -> bytes
        deinterleave_tracks(blob)               -> (a, b)

Every encoder roundtrips losslessly; decoder sources execute without imports,
using only language builtins (ord, bytearray, arithmetic), so the main
obfuscator can inline them verbatim into generated loaders.

Determinism: all randomness flows through the caller-supplied random.Random
instance; identical seeds reproduce identical outputs byte-for-byte.

Made for the Tr0ngX anti-reverse engineering research pipeline.
"""

import random
import struct
import unicodedata
from typing import Dict, List, Tuple

__all__ = [
    "build_identifier_pool",
    "validate_identifier",
    "pool_kinds",
    "encode_base4096",
    "base4096_decoder_source",
    "encode_base256_exotic",
    "base256_exotic_decoder_source",
    "bit_matrix_transform",
    "inverse_bit_matrix",
    "bit_matrix_decoder_source",
    "interleave_tracks",
    "deinterleave_tracks",
]

# ---------------------------------------------------------------------------
# Exotic Unicode block maps (inclusive codepoint ranges)
# ---------------------------------------------------------------------------

R_TANGUT_IDEO: Tuple[int, int] = (0x17000, 0x187F7)
R_TANGUT_COMP: Tuple[int, int] = (0x18800, 0x18AFF)
R_TANGUT_SUPP: Tuple[int, int] = (0x18D00, 0x18D08)
R_EGYPT_BASE: Tuple[int, int] = (0x13000, 0x1342E)
R_EGYPT_EXT_A: Tuple[int, int] = (0x13460, 0x143FA)
R_CJK_EXT_G: Tuple[int, int] = (0x30000, 0x3134A)
R_CJK_EXT_H: Tuple[int, int] = (0x31350, 0x323AF)
R_VEDIC_MARKS: Tuple[int, int] = (0x1CD0, 0x1CFF)
R_ANATOLIAN: Tuple[int, int] = (0x14400, 0x1467F)
R_BAMUM_SUPP: Tuple[int, int] = (0x16800, 0x16A38)
R_GLAGOLITIC: Tuple[int, int] = (0x2C00, 0x2C5F)
R_GLAGOLITIC_MARKS: Tuple[int, int] = (0x1E000, 0x1E02A)
R_PAHAWH_HMONG: Tuple[int, int] = (0x16B00, 0x16B8F)
R_POLLARD_MIAO: Tuple[int, int] = (0x16F00, 0x16F9F)
R_NYIAKENG_HMONG: Tuple[int, int] = (0x1E100, 0x1E14F)
R_WANCHO: Tuple[int, int] = (0x1E2C0, 0x1E2FF)
R_TOTO: Tuple[int, int] = (0x1E290, 0x1E2BF)
R_OLD_UYGHUR: Tuple[int, int] = (0x10F70, 0x10FAF)
R_CYPRO_MINOAN: Tuple[int, int] = (0x12F90, 0x12FFF)
R_DEVANAGARI_LETTERS: Tuple[int, int] = (0x0904, 0x0939)
R_YI_SYLLABLES: Tuple[int, int] = (0xA000, 0xA48C)
R_YI_RADICALS: Tuple[int, int] = (0xA490, 0xA4C6)

# kind -> (stem_ranges usable as identifier start, tail_ranges usable as continuation)
POOL_SPECS: Dict[str, Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]] = {
    "tangut": ([R_TANGUT_IDEO, R_TANGUT_COMP, R_TANGUT_SUPP],
               [R_TANGUT_IDEO, R_TANGUT_COMP, R_TANGUT_SUPP]),
    "egyptian": ([R_EGYPT_BASE, R_EGYPT_EXT_A],
                 [R_EGYPT_BASE, R_EGYPT_EXT_A]),
    "cjk_ext": ([R_CJK_EXT_G, R_CJK_EXT_H],
                [R_CJK_EXT_G, R_CJK_EXT_H]),
    "vedic": ([R_DEVANAGARI_LETTERS],
              [R_DEVANAGARI_LETTERS, R_VEDIC_MARKS]),
    "anatolian": ([R_ANATOLIAN], [R_ANATOLIAN]),
    "bamum": ([R_BAMUM_SUPP], [R_BAMUM_SUPP]),
    "glagolitic": ([R_GLAGOLITIC],
                   [R_GLAGOLITIC, R_GLAGOLITIC_MARKS]),
    "miao": ([R_POLLARD_MIAO, R_PAHAWH_HMONG, R_NYIAKENG_HMONG,
              R_WANCHO, R_TOTO, R_OLD_UYGHUR, R_CYPRO_MINOAN],
             [R_POLLARD_MIAO, R_PAHAWH_HMONG, R_NYIAKENG_HMONG,
              R_WANCHO, R_TOTO, R_OLD_UYGHUR, R_CYPRO_MINOAN]),
}

# Graceful fallback chain when a primary kind starves (old Unicode DB, sparse block).
FALLBACK_STEMS: List[Tuple[int, int]] = [
    R_TANGUT_IDEO, R_TANGUT_COMP, R_CJK_EXT_G, R_EGYPT_BASE,
    R_ANATOLIAN, R_BAMUM_SUPP, R_GLAGOLITIC, R_PAHAWH_HMONG,
    R_POLLARD_MIAO, R_DEVANAGARI_LETTERS,
]
FALLBACK_TAILS: List[Tuple[int, int]] = FALLBACK_STEMS + [
    R_VEDIC_MARKS, R_GLAGOLITIC_MARKS,
]

_BAD_START_CATEGORIES = ("Mn", "Mc", "Me")


# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------

def validate_identifier(name: object) -> bool:
    """Return True iff name is a standalone-safe Python identifier.

    Gates: non-empty str, no surrogate codepoints, first char not Mn/Mc/Me,
    XID identifier semantics via isidentifier() plus the ('x'+name)
    continuation probe, NFKC self-stability, and a live compile() probe.
    """
    if not isinstance(name, str) or not name:
        return False
    for ch in name:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            return False
    if unicodedata.category(name[0]) in _BAD_START_CATEGORIES:
        return False
    if not name.isidentifier():
        return False
    if not ("x" + name).isidentifier():
        return False
    if unicodedata.normalize("NFKC", name) != name:
        return False
    try:
        compile("%s=1" % name, "<tr0ngx-probe>", "exec")
    except Exception:
        return False
    return True


def pool_kinds() -> Tuple[str, ...]:
    """Tuple of supported identifier pool kinds."""
    return tuple(sorted(POOL_SPECS))


def _pick_range(rng: random.Random, ranges: List[Tuple[int, int]]) -> int:
    spans = [hi - lo + 1 for lo, hi in ranges]
    total = sum(spans)
    roll = rng.randrange(total)
    for (lo, _hi), span in zip(ranges, spans):
        if roll < span:
            return rng.randrange(lo, lo + span)
        roll -= span
    lo, hi = ranges[-1]
    return rng.randrange(lo, hi + 1)


def _fill_pool(out: List[str], seen: set, nfkc_seen: set, count: int,
               stems: List[Tuple[int, int]], tails: List[Tuple[int, int]],
               rng: random.Random) -> None:
    attempts = count * 80 + 6000
    while len(out) < count and attempts > 0:
        attempts -= 1
        length = rng.randint(2, 4)
        chars = [chr(_pick_range(rng, stems))]
        mixed = stems + tails
        for _ in range(length - 1):
            chars.append(chr(_pick_range(rng, mixed)))
        cand = "".join(chars)
        if cand in seen:
            continue
        nfkc = unicodedata.normalize("NFKC", cand)
        if nfkc != cand or nfkc in nfkc_seen:
            continue
        if not validate_identifier(cand):
            continue
        seen.add(cand)
        nfkc_seen.add(nfkc)
        out.append(cand)


def build_identifier_pool(kind: str, count: int, rng: random.Random) -> List[str]:
    """Build up to `count` exotic validated identifiers for `kind`.

    Falls back across the global block chain when the primary kind cannot
    fill the quota (interpreter with an older Unicode DB). Never raises;
    returns whatever was collected if even the fallback chain starves.
    """
    if count <= 0:
        return []
    out: List[str] = []
    seen: set = set()
    nfkc_seen: set = set()
    spec = POOL_SPECS.get(kind)
    if spec is not None:
        _fill_pool(out, seen, nfkc_seen, count, spec[0], spec[1], rng)
    if len(out) < count:
        _fill_pool(out, seen, nfkc_seen, count, FALLBACK_STEMS, FALLBACK_TAILS, rng)
    return out[:count]


# ---------------------------------------------------------------------------
# Shared glyph collection / source escaping
# ---------------------------------------------------------------------------

def _collect_glyphs(count: int, ranges: List[Tuple[int, int]]) -> List[str]:
    """Collect `count` distinct letter glyphs: non-surrogate, NFKC-stable."""
    out: List[str] = []
    seen: set = set()
    for lo, hi in ranges:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            cat = unicodedata.category(ch)
            if cat[0] != "L":
                continue
            nfkc = unicodedata.normalize("NFKC", ch)
            if nfkc != ch or ch in seen:
                continue
            seen.add(ch)
            out.append(ch)
            if len(out) >= count:
                return out
    return out


def _escape_glyphs(text: str) -> str:
    """ASCII-safe \\uXXXX / \\UXXXXXXXX escapes for embedding into source."""
    pieces: List[str] = []
    for ch in text:
        cp = ord(ch)
        if cp <= 0xFFFF:
            pieces.append("\\u%04X" % cp)
        else:
            pieces.append("\\U%08X" % cp)
    return "".join(pieces)


BASE4096_ALPHABET_RANGES: List[Tuple[int, int]] = [
    R_TANGUT_IDEO, R_TANGUT_COMP, R_TANGUT_SUPP,
    R_CJK_EXT_G, R_CJK_EXT_H, R_EGYPT_BASE, R_EGYPT_EXT_A,
]

BASE256_ALPHABET_RANGES: List[Tuple[int, int]] = [
    R_YI_SYLLABLES, R_YI_RADICALS,
]


# ---------------------------------------------------------------------------
# Codec A: base-4096 astral glyph packing (12 bits per glyph)
# ---------------------------------------------------------------------------

def _build_alphabet(count: int, ranges: List[Tuple[int, int]],
                    rng: random.Random) -> str:
    glyphs = _collect_glyphs(count, ranges)
    if len(glyphs) < count:
        raise ValueError(
            "glyph starvation: requested %d, collected %d" % (count, len(glyphs)))
    rng.shuffle(glyphs)
    return "".join(glyphs)


def encode_base4096(data: bytes, rng: random.Random) -> Tuple[str, Dict[str, object]]:
    """Pack bytes into 12-bit groups mapped onto a 4096-glyph exotic alphabet.

    Returns (payload, meta); meta carries the shuffled alphabet and original
    size so base4096_decoder_source(meta) can rebuild a standalone decoder.
    """
    alphabet = _build_alphabet(4096, BASE4096_ALPHABET_RANGES, rng)
    size = len(data)
    group_count = (size * 8 + 11) // 12
    pad_bits = group_count * 12 - size * 8
    value = (int.from_bytes(data, "big") << pad_bits) if size else 0
    pieces: List[str] = []
    for i in range(group_count):
        shift = (group_count - 1 - i) * 12
        pieces.append(alphabet[(value >> shift) & 0xFFF])
    meta: Dict[str, object] = {"alphabet": alphabet, "size": size}
    return "".join(pieces), meta


def base4096_decoder_source(meta: Dict[str, object]) -> str:
    """Standalone pure-builtin decoder source reversing encode_base4096."""
    alphabet = _escape_glyphs(str(meta["alphabet"]))
    size = int(meta["size"])
    return (
        "def tr0ngx_b4096_decode(payload):\n"
        "    _A = \"%s\"\n"
        "    _map = {}\n"
        "    _i = 0\n"
        "    for _g in _A:\n"
        "        _map[ord(_g)] = _i\n"
        "        _i += 1\n"
        "    _size = %d\n"
        "    _acc = 0\n"
        "    _nb = 0\n"
        "    _out = bytearray()\n"
        "    for _ch in payload:\n"
        "        _acc = (_acc << 12) | _map[ord(_ch)]\n"
        "        _nb += 12\n"
        "        while _nb >= 8:\n"
        "            _nb -= 8\n"
        "            _out.append((_acc >> _nb) & 255)\n"
        "            if len(_out) >= _size:\n"
        "                return bytes(_out)\n"
        "    return bytes(_out)\n"
    ) % (alphabet, size)


# ---------------------------------------------------------------------------
# Codec B: base-256 Yi syllable mapping (1 byte -> 1 glyph)
# ---------------------------------------------------------------------------

def encode_base256_exotic(data: bytes, rng: random.Random) -> Tuple[str, Dict[str, object]]:
    """Map each byte onto one Yi Syllables glyph (U+A000..U+A6FF band).

    Returns (payload, meta) with the shuffled 256-glyph table in meta.
    """
    table = _build_alphabet(256, BASE256_ALPHABET_RANGES, rng)
    payload = "".join(table[b] for b in data)
    meta: Dict[str, object] = {"table": table, "size": len(data)}
    return payload, meta


def base256_exotic_decoder_source(meta: Dict[str, object]) -> str:
    """Standalone pure-builtin decoder source reversing encode_base256_exotic."""
    table = _escape_glyphs(str(meta["table"]))
    return (
        "def tr0ngx_yi256_decode(payload):\n"
        "    _T = \"%s\"\n"
        "    _map = {}\n"
        "    _i = 0\n"
        "    for _g in _T:\n"
        "        _map[ord(_g)] = _i\n"
        "        _i += 1\n"
        "    return bytes([_map[ord(_c)] for _c in payload])\n"
    ) % table


# ---------------------------------------------------------------------------
# Transform: invertible bit matrix op chain
# ---------------------------------------------------------------------------

def _op_lcg_xor(buf: bytearray, a: int, c: int, seed: int) -> None:
    state = seed
    for i in range(len(buf)):
        state = (state * a + c) & 0xFFFF
        buf[i] ^= state & 0xFF


def _op_rotl(buf: bytearray, amount: int) -> None:
    for i in range(len(buf)):
        v = buf[i]
        buf[i] = ((v << amount) | (v >> (8 - amount))) & 0xFF


def _op_rotr(buf: bytearray, amount: int) -> None:
    for i in range(len(buf)):
        v = buf[i]
        buf[i] = ((v >> amount) | (v << (8 - amount))) & 0xFF


def _op_nibble_swap(buf: bytearray) -> None:
    for i in range(len(buf)):
        v = buf[i]
        buf[i] = ((v & 0x0F) << 4) | (v >> 4)


def _op_sbox(buf: bytearray, table: List[int]) -> None:
    for i in range(len(buf)):
        buf[i] = table[buf[i]]


def _op_pos_mask(buf: bytearray, k1: int, k2: int) -> None:
    for i in range(len(buf)):
        buf[i] ^= (k1 * i + k2) & 0xFF


def _make_sbox(rng: random.Random) -> List[int]:
    table = list(range(256))
    for i in range(255, 0, -1):
        j = rng.randint(0, i)
        table[i], table[j] = table[j], table[i]
    return table


def _sbox_inverse(table: List[int]) -> List[int]:
    inv = [0] * 256
    for i, v in enumerate(table):
        inv[v] = i
    return inv


def bit_matrix_transform(data: bytes, rng: random.Random, rounds: int = 4
                         ) -> Tuple[bytes, Dict[str, object]]:
    """Chain `rounds` randomly-chosen invertible byte ops over `data`.

    Op menu: rolling LCG XOR stream, byte bit-rotation, odd-round nibble swap,
    Fisher-Yates SBOX permutation, position-dependent XOR mask. Returns
    (transformed_bytes, key_material) where key_material is a compact dict of
    ints plus the SBOX table.
    """
    if rounds < 0:
        rounds = 0
    buf = bytearray(data)
    ops: List[Dict[str, object]] = []
    for r in range(rounds):
        menu = ["lcg", "rotl", "sbox", "posmask"]
        if r % 2 == 1:
            menu.append("swap")
        choice = rng.choice(menu)
        if choice == "lcg":
            a = rng.randrange(3, 256) | 1
            c = rng.randrange(1, 256)
            seed = rng.randrange(256)
            _op_lcg_xor(buf, a, c, seed)
            ops.append({"op": "lcg", "a": a, "c": c, "seed": seed})
        elif choice == "rotl":
            amount = rng.randint(1, 7)
            _op_rotl(buf, amount)
            ops.append({"op": "rotl", "amount": amount})
        elif choice == "swap":
            _op_nibble_swap(buf)
            ops.append({"op": "swap"})
        elif choice == "sbox":
            table = _make_sbox(rng)
            _op_sbox(buf, table)
            ops.append({"op": "sbox", "table": table})
        else:
            k1 = rng.randrange(256)
            k2 = rng.randrange(256)
            _op_pos_mask(buf, k1, k2)
            ops.append({"op": "posmask", "k1": k1, "k2": k2})
    key: Dict[str, object] = {"ops": ops, "length": len(buf), "rounds": rounds}
    return bytes(buf), key


def inverse_bit_matrix(data: bytes, key_material: Dict[str, object]) -> bytes:
    """Exact inverse of bit_matrix_transform for the given key material."""
    buf = bytearray(data)
    for desc in reversed(key_material["ops"]):
        op = desc["op"]
        if op == "lcg":
            _op_lcg_xor(buf, int(desc["a"]), int(desc["c"]), int(desc["seed"]))
        elif op == "rotl":
            _op_rotr(buf, int(desc["amount"]))
        elif op == "swap":
            _op_nibble_swap(buf)
        elif op == "sbox":
            _op_sbox(buf, _sbox_inverse(list(desc["table"])))
        else:
            _op_pos_mask(buf, int(desc["k1"]), int(desc["k2"]))
    return bytes(buf)


def bit_matrix_decoder_source(key_material: Dict[str, object]) -> str:
    """Standalone pure-builtin inverse-function source for a bit matrix key."""
    lines: List[str] = [
        "def tr0ngx_bmatrix_inverse(data):",
        "    buf = bytearray(data)",
        "    n = len(buf)",
    ]
    for desc in reversed(key_material["ops"]):
        op = desc["op"]
        if op == "lcg":
            lines += [
                "    _s = %d" % int(desc["seed"]),
                "    for _i in range(n):",
                "        _s = (_s * %d + %d) & 0xFFFF" % (int(desc["a"]), int(desc["c"])),
                "        buf[_i] ^= _s & 255",
            ]
        elif op == "rotl":
            amt = int(desc["amount"])
            lines += [
                "    for _i in range(n):",
                "        _v = buf[_i]",
                "        buf[_i] = ((_v >> %d) | (_v << %d)) & 255" % (amt, 8 - amt),
            ]
        elif op == "swap":
            lines += [
                "    for _i in range(n):",
                "        _v = buf[_i]",
                "        buf[_i] = ((_v & 15) << 4) | (_v >> 4)",
            ]
        elif op == "sbox":
            inv = _sbox_inverse(list(desc["table"]))
            lit = "[" + ",".join(str(v) for v in inv) + "]"
            lines += [
                "    _inv = %s" % lit,
                "    for _i in range(n):",
                "        buf[_i] = _inv[buf[_i]]",
            ]
        else:
            lines += [
                "    for _i in range(n):",
                "        buf[_i] ^= (%d * _i + %d) & 255" % (int(desc["k1"]), int(desc["k2"])),
            ]
    lines.append("    return bytes(buf)")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Track interleaving
# ---------------------------------------------------------------------------

_INTERLEAVE_HEADER = struct.Struct(">BQQ")
_INTERLEAVE_HEADER_SIZE = _INTERLEAVE_HEADER.size
_TRACK_MARKER = 0x00


def interleave_tracks(a: bytes, b: bytes, rng: random.Random) -> bytes:
    """Zip-interleave two byte streams starting from a random track.

    Wire format: header (start flag, len(a), len(b)), strict alternating pair
    region over min(len(a), len(b)) slots, 0x00 tail marker separating the
    pair region from the remainder of the longer track. Deterministic given
    the rng instance.
    """
    start = rng.randrange(2)
    la, lb = len(a), len(b)
    m = la if la < lb else lb
    out = bytearray(_INTERLEAVE_HEADER.pack(start, la, lb))
    for i in range(m):
        if (i % 2 == 0) == (start == 0):
            out.append(a[i])
            out.append(b[i])
        else:
            out.append(b[i])
            out.append(a[i])
    out.append(_TRACK_MARKER)
    longer = a if la >= lb else b
    out.extend(longer[m:])
    return bytes(out)


def deinterleave_tracks(blob: bytes) -> Tuple[bytes, bytes]:
    """Exact inverse of interleave_tracks. Raises ValueError on malformed input."""
    if len(blob) < _INTERLEAVE_HEADER_SIZE + 1:
        raise ValueError("truncated interleave blob")
    start, la, lb = _INTERLEAVE_HEADER.unpack_from(blob, 0)
    if start > 1:
        raise ValueError("invalid start-track flag")
    m = la if la < lb else lb
    tail_len = (la if la >= lb else lb) - m
    body = blob[_INTERLEAVE_HEADER_SIZE:]
    expected = 2 * m + 1 + tail_len
    if len(body) != expected:
        raise ValueError("interleave length mismatch")
    pairs = body[:2 * m]
    if body[2 * m] != _TRACK_MARKER:
        raise ValueError("missing 0x00 tail marker")
    tail = body[2 * m + 1:]
    a = bytearray()
    b = bytearray()
    for i in range(m):
        if (i % 2 == 0) == (start == 0):
            a.append(pairs[2 * i])
            b.append(pairs[2 * i + 1])
        else:
            b.append(pairs[2 * i])
            a.append(pairs[2 * i + 1])
    longer = a if la >= lb else b
    longer.extend(tail)
    return bytes(a), bytes(b)


# ---------------------------------------------------------------------------
# Self-test entry point
# ---------------------------------------------------------------------------

_TEST_SIZES = (0, 1, 7, 255, 4096, 65536)
_POOL_TEST_COUNT = 500


def _run_self_test() -> int:
    failures: List[str] = []

    def check(label: str, cond: bool) -> bool:
        if cond:
            print("[PASS] %s" % label)
        else:
            failures.append(label)
            print("[FAIL] %s" % label)
        return cond

    master = random.Random(0x7E071D5E)

    for kind in pool_kinds():
        rng = random.Random(master.randrange(1 << 30))
        pool = build_identifier_pool(kind, _POOL_TEST_COUNT, rng)
        ok = len(pool) == _POOL_TEST_COUNT
        ok = ok and len(set(pool)) == len(pool)
        ok = ok and all(validate_identifier(n) for n in pool)
        nf = [unicodedata.normalize("NFKC", n) for n in pool]
        ok = ok and all(n == s for n, s in zip(pool, nf))
        ok = ok and len(set(nf)) == len(nf)
        check("pool kind=%s count=%d unique+valid=%d" %
              (kind, _POOL_TEST_COUNT, len(pool)), ok)

    for size in _TEST_SIZES:
        rng = random.Random(master.randrange(1 << 30))
        data = bytes(rng.randrange(256) for _ in range(size))
        payload, meta = encode_base4096(data, rng)
        ok = len(payload) == (size * 8 + 11) // 12
        ns: Dict[str, object] = {}
        src = base4096_decoder_source(meta)
        try:
            exec(compile(src, "<b4096-decoder>", "exec"), ns)
            decoded = ns["tr0ngx_b4096_decode"](payload)
            ok = ok and decoded == data
        except Exception as exc:
            ok = False
            print("       base4096 error size=%d: %r" % (size, exc))
        check("base4096 roundtrip size=%d" % size, ok)

    for size in _TEST_SIZES:
        rng = random.Random(master.randrange(1 << 30))
        data = bytes(rng.randrange(256) for _ in range(size))
        payload, meta = encode_base256_exotic(data, rng)
        ok = len(payload) == size
        ns = {}
        src = base256_exotic_decoder_source(meta)
        try:
            exec(compile(src, "<yi256-decoder>", "exec"), ns)
            decoded = ns["tr0ngx_yi256_decode"](payload)
            ok = ok and decoded == data
        except Exception as exc:
            ok = False
            print("       yi256 error size=%d: %r" % (size, exc))
        check("base256_exotic roundtrip size=%d" % size, ok)

    for size in _TEST_SIZES:
        for rounds in (1, 4, 7):
            rng = random.Random(master.randrange(1 << 30))
            data = bytes(rng.randrange(256) for _ in range(size))
            transformed, key = bit_matrix_transform(data, rng, rounds)
            ok = inverse_bit_matrix(transformed, key) == data
            ns = {}
            src = bit_matrix_decoder_source(key)
            try:
                exec(compile(src, "<bmatrix-decoder>", "exec"), ns)
                decoded = ns["tr0ngx_bmatrix_inverse"](transformed)
                ok = ok and decoded == data
            except Exception as exc:
                ok = False
                print("       bmatrix error size=%d rounds=%d: %r" % (size, rounds, exc))
            check("bit_matrix roundtrip size=%d rounds=%d" % (size, rounds), ok)

    for size in _TEST_SIZES:
        rng = random.Random(master.randrange(1 << 30))
        a = bytes(rng.randrange(256) for _ in range(size))
        b = bytes(rng.randrange(256) for _ in range(rng.randint(0, size)))
        blob = interleave_tracks(a, b, rng)
        ra, rb = deinterleave_tracks(blob)
        check("interleave roundtrip size=%d/%d" % (len(a), len(b)), ra == a and rb == b)

    edge_cases = ((b"", b""), (b"\x00", b""), (b"", b"\xff\xff"),
                  (b"\x00\x00", b"\x00"))
    for a, b in edge_cases:
        rng = random.Random(master.randrange(1 << 30))
        ra, rb = deinterleave_tracks(interleave_tracks(a, b, rng))
        check("interleave edge %r/%r" % (a, b), ra == a and rb == b)

    total = len(pool_kinds()) + len(_TEST_SIZES) * 2 + \
        len(_TEST_SIZES) * 3 + len(_TEST_SIZES) + len(edge_cases)
    if failures:
        print("RESULT: FAILED (%d/%d checks failed): %s" %
              (len(failures), total, ", ".join(failures)))
        return 1
    print("RESULT: ALL %d CHECKS PASSED" % total)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_run_self_test())
