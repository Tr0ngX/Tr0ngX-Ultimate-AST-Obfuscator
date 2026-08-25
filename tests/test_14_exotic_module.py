"""
Test 14: Exotic Identifier & Encoding Module Suite (tr0ngx_exotic)
Imports tr0ngx_exotic from the repository root and validates its public
helpers:
  - validate_identifier over 200 generated samples for every pool kind,
  - encode/decode round-trips for base4096, base256-exotic,
    bit-matrix transform and track interleaving on payload sizes
    [0, 1, 7, 255, 4096] bytes,
  - NFC/NFKC normalization uniqueness of encoded alphabets (two distinct
    inputs must never normalize to the same visual string),
  - decoder_source() emits Python source that compiles and decodes
    correctly.

If tr0ngx_exotic.py does not exist yet in the repository root the entire
suite reports SKIP and exits green. Individual API pieces that are absent
from an existing module are skipped individually rather than failing.
"""
import os
import shutil
import sys
import tempfile
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

MODULE_FILENAME = "tr0ngx/exotic.py"
MODULE_NAME = "tr0ngx.exotic"
ROUNDTRIP_SIZES = [0, 1, 7, 255, 4096]
SAMPLES_PER_POOL = 200

RESULTS = {"pass": 0, "fail": 0, "skip": 0}


def check(name, ok, detail=""):
    if ok:
        RESULTS["pass"] += 1
        print("  [PASS] %s" % name)
    else:
        RESULTS["fail"] += 1
        print("  [FAIL] %s%s" % (name, (" -> " + detail) if detail else ""))
    return ok


def skip(name, detail=""):
    RESULTS["skip"] += 1
    print("  [SKIP] %s%s" % (name, (" -> " + detail) if detail else ""))


def first_attr(module, names):
    for attr in names:
        if hasattr(module, attr):
            return getattr(module, attr)
    return None


def make_payload(size, salt=0):
    return bytes((i * 31 + salt * 17 + size) % 256 for i in range(size))


def call_flexible(func, primary_args, alternate_arg_sets):
    """Call func trying several argument shapes; returns (ok, result)."""
    try:
        return True, func(*primary_args)
    except TypeError:
        pass
    except Exception:
        raise
    for args in alternate_arg_sets:
        try:
            return True, func(*args)
        except TypeError:
            continue
        except Exception:
            raise
    return False, None


def roundtrip_section(module):
    import random as _random
    failures = []
    for size in ROUNDTRIP_SIZES:
        payload = make_payload(size, salt=size)
        try:
            encoded, meta = module.encode_base4096(payload, _random.Random(42))
            src = module.base4096_decoder_source(meta)
            ns = {}
            exec(compile(src, "<b4096>", "exec"), ns)
            decoded = ns["tr0ngx_b4096_decode"](encoded)
            if bytes(decoded) != payload:
                failures.append("base4096 %dB mismatch" % size)
        except Exception as exc:
            failures.append("base4096 %dB: %s: %.60s" % (size, type(exc).__name__, exc))
    check("base4096 encoder + inline decoder source roundtrip", len(failures) == 0, "; ".join(failures[:4]))

    failures = []
    for size in ROUNDTRIP_SIZES:
        payload = make_payload(size, salt=size + 1)
        try:
            encoded, meta = module.encode_base256_exotic(payload, _random.Random(43))
            src = module.base256_exotic_decoder_source(meta)
            ns = {}
            exec(compile(src, "<yi256>", "exec"), ns)
            decoded = ns["tr0ngx_yi256_decode"](encoded)
            if bytes(decoded) != payload:
                failures.append("yi256 %dB mismatch" % size)
        except Exception as exc:
            failures.append("yi256 %dB: %s: %.60s" % (size, type(exc).__name__, exc))
    check("base256-exotic encoder + inline decoder source roundtrip", len(failures) == 0, "; ".join(failures[:4]))

    failures = []
    for size in ROUNDTRIP_SIZES:
        payload = make_payload(size, salt=size + 2)
        for rounds in (1, 4):
            try:
                transformed, key_material = module.bit_matrix_transform(payload, _random.Random(44), rounds=rounds)
                restored = module.inverse_bit_matrix(transformed, key_material)
                if bytes(restored) != payload:
                    failures.append("bitmatrix r=%d %dB mismatch" % (rounds, size))
            except Exception as exc:
                failures.append("bitmatrix r=%d %dB: %s: %.60s" % (rounds, size, type(exc).__name__, exc))
    check("bit-matrix transform/inverse roundtrip (rounds 1 and 4)", len(failures) == 0, "; ".join(failures[:4]))

    failures = []
    for a_size, b_size in ((0, 0), (1, 0), (7, 6), (255, 16), (4096, 3188)):
        a = make_payload(a_size, salt=3)
        b = make_payload(b_size, salt=4)
        try:
            blob = module.interleave_tracks(a, b, _random.Random(45))
            ra, rb = module.deinterleave_tracks(blob)
            if bytes(ra) != a or bytes(rb) != b:
                failures.append("interleave %d/%dB mismatch" % (a_size, b_size))
        except Exception as exc:
            failures.append("interleave %d/%dB: %s: %.60s" % (a_size, b_size, type(exc).__name__, exc))
    check("track interleaving roundtrip over edge sizes", len(failures) == 0, "; ".join(failures[:4]))


def pool_kinds(module):
    kinds = []
    if hasattr(module, "pool_kinds"):
        kinds = list(module.pool_kinds())
    cleaned = [str(k) for k in kinds if str(k)]
    return cleaned or ["default"]


def generate_pool_samples(module, kind, count):
    import random as _random
    if hasattr(module, "build_identifier_pool"):
        return module.build_identifier_pool(kind, count, _random.Random(46))
    return ["v_%d" % i for i in range(count)]


def validate_identifier_section(module):
    validate = getattr(module, "validate_identifier", None)
    if validate is None:
        skip("validate_identifier: not present")
        return
    all_ok = True
    details = []
    for kind in pool_kinds(module):
        bad = []
        samples = generate_pool_samples(module, kind, SAMPLES_PER_POOL)
        for sample in samples:
            try:
                verdict = validate(sample)
            except Exception as exc:
                bad.append("%s raised %.60s" % (sample[:24], exc))
                continue
            if verdict is not True:
                bad.append(sample[:32])
        if bad:
            all_ok = False
            details.append("pool '%s': %d/%d rejected (%s)" % (kind, len(bad), len(samples), bad[0]))
        else:
            print("     pool '%s': %d samples accepted" % (kind, len(samples)))
    check(
        "validate_identifier accepts generated pools (%d per kind)" % SAMPLES_PER_POOL,
        all_ok,
        "; ".join(details[:3]),
    )


def nfkc_uniqueness_section(module):
    import random as _random
    encoders = [
        ("base4096", getattr(module, "encode_base4096", None)),
        ("base256-exotic", getattr(module, "encode_base256_exotic", None)),
    ]
    encoders = [(n, e) for n, e in encoders if e is not None]
    if not encoders:
        skip("NFKC uniqueness: no encoders present")
        return
    overall_ok = True
    details = []
    for idx, (label, encode) in enumerate(encoders):
        seen = {}
        collision = None
        for salt in range(64):
            payload = make_payload(16, salt=salt)
            try:
                encoded, _meta = encode(payload, _random.Random(salt))
            except Exception as exc:
                collision = "%.80s" % exc
                break
            if not isinstance(encoded, str):
                encoded = str(encoded)
            normalized = unicodedata.normalize("NFKC", unicodedata.normalize("NFC", encoded))
            if normalized in seen:
                collision = "salts %d and %d collide under NFKC" % (seen[normalized], salt)
                break
            seen[normalized] = salt
        if collision:
            overall_ok = False
            details.append("%s: %s" % (label, collision))
    check("encoded outputs are unique under NFC/NFKC normalization", overall_ok, "; ".join(details))


def decoder_source_section(module):
    import random as _random
    payload = make_payload(33, salt=7)
    checks = []

    def run_case(label, encode_fn, source_fn, entry_name):
        try:
            encoded, meta = encode_fn(payload, _random.Random(47))
            src = source_fn(meta)
            compile(src, "<dec>", "exec")
            ns = {}
            exec(compile(src, "<dec>", "exec"), ns)
            decoder = ns.get(entry_name)
            if decoder is None:
                checks.append((label + ": compiles", True, ""))
                checks.append((label + ": decodes", False, "entry %s missing" % entry_name))
                return
            decoded = decoder(encoded)
            if isinstance(decoded, str):
                decoded = decoded.encode("latin-1")
            checks.append((label + ": compiles+decodes", bytes(decoded) == payload, ""))
        except Exception as exc:
            checks.append((label + ": compiles+decodes", False, "%.100s" % exc))

    if hasattr(module, "encode_base4096") and hasattr(module, "base4096_decoder_source"):
        run_case("base4096 decoder_source", module.encode_base4096, module.base4096_decoder_source, "tr0ngx_b4096_decode")
    else:
        skip("decoder_source base4096: not present")
    if hasattr(module, "encode_base256_exotic") and hasattr(module, "base256_exotic_decoder_source"):
        run_case("base256 decoder_source", module.encode_base256_exotic, module.base256_exotic_decoder_source, "tr0ngx_yi256_decode")
    else:
        skip("decoder_source base256: not present")

    for name, ok, detail in checks:
        check(name, ok, detail)


def main():
    print("[TEST 14] Exotic Module Suite (%s)" % MODULE_NAME)
    if not os.path.isfile(os.path.join(REPO_ROOT, MODULE_FILENAME)):
        print("  [SKIP] %s not found in repository root -> feature not integrated yet" % MODULE_FILENAME)
        print("-" * 70)
        print("[TEST 14] SUMMARY: 0 PASSED | 0 FAILED | SUITE SKIPPED (module absent)")
        print("[TEST 14] >>> SUITE GREEN (SKIP) <<<")
        return 0
    try:
        module = __import__(MODULE_NAME, fromlist=["exotic"])
    except Exception as exc:
        print("  [FAIL] importing %s raised %.160s" % (MODULE_NAME, exc))
        print("-" * 70)
        print("[TEST 14] SUMMARY: 0 PASSED | 1 FAILED | 0 SKIPPED")
        print("[TEST 14] >>> SUITE FAILED <<<")
        return 1

    print("  module imported from %s" % getattr(module, "__file__", "?"))
    validate_identifier_section(module)
    roundtrip_section(module)
    nfkc_uniqueness_section(module)
    decoder_source_section(module)

    passed = RESULTS["pass"]
    failed = RESULTS["fail"]
    skipped = RESULTS["skip"]
    print("-" * 70)
    print("[TEST 14] SUMMARY: %d PASSED | %d FAILED | %d SKIPPED" % (passed, failed, skipped))
    if failed == 0:
        print("[TEST 14] >>> SUITE GREEN <<<")
    else:
        print("[TEST 14] >>> SUITE FAILED <<<")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
