import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
MANIFEST = HERE / "manifest.json"

CATEGORY_RANGES = [
    (1, 3, "closures_nonlocal"),
    (4, 6, "generators_yield_from"),
    (7, 9, "asyncio_coroutines_tasks"),
    (10, 12, "async_generators"),
    (13, 14, "metaclass_prepare"),
    (15, 16, "descriptors"),
    (17, 18, "dataclasses"),
    (19, 22, "match_case_guards"),
    (23, 24, "walrus_comprehension"),
    (25, 27, "decorators_wraps"),
    (28, 30, "exception_groups"),
    (31, 34, "context_managers_sync_async"),
    (35, 38, "recursion_math"),
    (39, 41, "string_building"),
    (42, 44, "dict_set_comprehensions"),
    (45, 47, "slots_properties"),
    (48, 50, "mro_multiple_inheritance"),
    (51, 53, "iterator_protocol"),
    (54, 56, "functools_lru_cache"),
    (57, 60, "typing_annotations_runtime"),
]


def category_for(name):
    num = int(name.split("_", 1)[0])
    for lo, hi, cat in CATEGORY_RANGES:
        if lo <= num <= hi:
            return cat
    raise SystemExit(f"no category range for {name}")


def run_case(path):
    proc = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        timeout=120,
        cwd=str(HERE),
    )
    return proc


def build():
    entries = []
    failures = []
    for path in sorted(CASES.glob("*.py")):
        try:
            proc = run_case(path)
        except subprocess.TimeoutExpired:
            failures.append((path.name, "TIMEOUT"))
            continue
        if proc.returncode != 0:
            failures.append((path.name, f"exit={proc.returncode} stderr={proc.stderr.decode(errors='replace')[:400]}"))
            continue
        if not proc.stdout:
            failures.append((path.name, "empty stdout"))
            continue
        digest = hashlib.sha256(proc.stdout).hexdigest()
        entries.append({
            "case": path.name,
            "category": category_for(path.name),
            "expect_stdout_sha256": digest,
        })
    if failures:
        for name, why in failures:
            print(f"FAIL {name}: {why}", file=sys.stderr)
        raise SystemExit(f"{len(failures)} case(s) failed native run")
    MANIFEST.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"manifest written: {len(entries)} cases")


def check():
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_name = {e["case"]: e for e in entries}
    bad = 0
    for path in sorted(CASES.glob("*.py")):
        entry = by_name.get(path.name)
        if entry is None:
            print(f"MISSING {path.name} not in manifest", file=sys.stderr)
            bad += 1
            continue
        proc = run_case(path)
        if proc.returncode != 0 or not proc.stdout:
            print(f"FAIL {path.name}: rc={proc.returncode}", file=sys.stderr)
            bad += 1
            continue
        digest = hashlib.sha256(proc.stdout).hexdigest()
        if digest != entry["expect_stdout_sha256"]:
            print(f"DIFF {path.name}: {digest} != {entry['expect_stdout_sha256']}", file=sys.stderr)
            bad += 1
    extra = set(by_name) - {p.name for p in CASES.glob("*.py")}
    if extra:
        print(f"STALE manifest entries: {sorted(extra)}", file=sys.stderr)
        bad += len(extra)
    if bad:
        raise SystemExit(f"verify FAILED: {bad} problem(s)")
    print(f"verify OK: {len(entries)}/{len(entries)} hashes match fresh re-runs")


def main():
    ap = argparse.ArgumentParser(description="Golden-Corpus manifest tool")
    ap.add_argument("--check", action="store_true", help="verify manifest against fresh runs")
    ns = ap.parse_args()
    if ns.check:
        check()
    else:
        build()


if __name__ == "__main__":
    main()
