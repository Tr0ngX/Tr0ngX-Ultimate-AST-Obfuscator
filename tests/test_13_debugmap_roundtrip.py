"""
Test 13: --debug-map JSON Round-Trip Suite
Runs an obfuscation with --debug-map, loads the exported JSON map and
verifies:
  1. the file parses as JSON,
  2. expected top-level structure is present (stage list with stage names
     and durations; renamed-symbol dictionaries when populated),
  3. every renamed-symbol entry maps an original name to a DISTINCT new
     name (original != new),
  4. the document re-dumps deterministically (json.dumps of the loaded
     data is byte-stable across repeated serializations and a full
     load/dump/load cycle).

A second quick run exercises the AUTO path: --debug-map AUTO must write
"<output_stem>.debug.json" next to the output file.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBF_SCRIPT = os.path.join(REPO_ROOT, "tr0ngx_obfuscator.py")
BUILD_TIMEOUT = 300

SAMPLE_SOURCE = (
    "import math\n"
    "\n"
    "def area(radius):\n"
    "    return math.pi * radius * radius\n"
    "\n"
    "def perimeter(radius):\n"
    "    return 2 * math.pi * radius\n"
    "\n"
    "print('DEBUGMAP_SAMPLE_OK', round(area(2), 2), round(perimeter(2), 2))\n"
)

RENAMED_MAP_KEYS = ("renamed_functions", "renamed_builtins", "renamed_variables")

RESULTS = {"pass": 0, "fail": 0}


def check(name, ok, detail=""):
    if ok:
        RESULTS["pass"] += 1
        print("  [PASS] %s" % name)
    else:
        RESULTS["fail"] += 1
        print("  [FAIL] %s%s" % (name, (" -> " + detail) if detail else ""))
    return ok


def build(src_path, out_path, extra_args):
    cmd = [sys.executable, OBF_SCRIPT, "-i", src_path, "-o", out_path,
           "--force-py", "off", "--no-art"] + extra_args
    try:
        return subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=BUILD_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None


def validate_stage_metrics(data):
    stages = data.get("stages")
    ok = check("debug map contains a non-empty 'stages' list", isinstance(stages, list) and len(stages) > 0)
    if not ok or not isinstance(stages, list):
        return
    malformed = []
    for entry in stages:
        if not isinstance(entry, dict):
            malformed.append("non-dict stage entry")
            continue
        stage_name = entry.get("stage")
        duration = entry.get("duration_seconds")
        if not isinstance(stage_name, str) or not stage_name:
            malformed.append("stage entry missing 'stage' name")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
            malformed.append("stage %r has invalid duration %r" % (stage_name, duration))
    check(
        "every stage entry carries a name and non-negative duration",
        len(malformed) == 0,
        "; ".join(malformed[:5]),
    )


def validate_renamed_maps(data):
    any_map_present = False
    for key in RENAMED_MAP_KEYS:
        mapping = data.get(key)
        if mapping is None:
            continue
        if not isinstance(mapping, dict):
            check("renamed map '%s' is a dict when present" % key, False, type(mapping).__name__)
            continue
        if not mapping:
            continue
        any_map_present = True
        collisions = [orig for orig, new in mapping.items() if orig == new]
        check(
            "renamed map '%s': all %d entries have original != new" % (key, len(mapping)),
            len(collisions) == 0,
            "identity collisions: %s" % collisions[:8],
        )
    if not any_map_present:
        print("  [INFO] no renamed-symbol maps were populated for this configuration (allowed)")


def validate_deterministic_dump(data):
    dump_one = json.dumps(data, sort_keys=True, ensure_ascii=False)
    dump_two = json.dumps(data, sort_keys=True, ensure_ascii=False)
    check("re-dump of loaded JSON is byte-identical (twice)", dump_one == dump_two)
    reparsed = json.loads(dump_one)
    dump_three = json.dumps(reparsed, sort_keys=True, ensure_ascii=False)
    check("load -> dump -> load -> dump cycle is stable", dump_three == dump_one)


def main():
    print("[TEST 13] Debug Map Export & Round-Trip Suite")
    workspace = tempfile.mkdtemp(prefix="tr0ngx_test13_")
    try:
        src_path = os.path.join(workspace, "sample_src.py")
        out_path = os.path.join(workspace, "sample_out.py")
        map_path = os.path.join(workspace, "explicit_map.json")
        with open(src_path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE_SOURCE)

        p = build(src_path, out_path, ["-m", "2", "--hyperion", "y", "--debug-map", map_path])
        if p is None:
            check("obfuscation with --debug-map terminates within timeout", False, "TimeoutExpired")
        elif p.returncode != 0 or not artifact_exists(map_path):
            err = ((p.stderr or "") + (p.stdout or "")).strip()
            check("obfuscation with --debug-map succeeds and writes the map", False,
                  "exit=%s; %s" % (p.returncode, " | ".join(err.splitlines()[-3:])[:300]))
        else:
            check("obfuscation with --debug-map succeeds and writes the map", True)

            raw = ""
            with open(map_path, "r", encoding="utf-8") as fh:
                raw = fh.read()
            try:
                data = json.loads(raw)
                check("debug map parses as valid JSON", True)
            except ValueError as exc:
                data = None
                check("debug map parses as valid JSON", False, str(exc))

            if isinstance(data, dict):
                validate_stage_metrics(data)
                validate_renamed_maps(data)
                validate_deterministic_dump(data)
            elif data is not None:
                check("debug map root is a JSON object", False, type(data).__name__)

        # ---- AUTO naming convention -------------------------------------
        auto_out = os.path.join(workspace, "auto_out.py")
        auto_map = os.path.splitext(auto_out)[0] + ".debug.json"
        p_auto = build(src_path, auto_out, ["-m", "1", "--debug-map", "AUTO"])
        if p_auto is None:
            check("--debug-map AUTO run terminates within timeout", False, "TimeoutExpired")
        elif p_auto.returncode == 0 and artifact_exists(auto_map):
            try:
                json.loads(open(auto_map, "r", encoding="utf-8").read())
                check("--debug-map AUTO writes parseable <stem>.debug.json beside output", True)
            except ValueError as exc:
                check("--debug-map AUTO writes parseable <stem>.debug.json beside output", False, str(exc))
        else:
            check("--debug-map AUTO writes parseable <stem>.debug.json beside output", False,
                  "exit=%s, map exists=%s" % (p_auto.returncode, os.path.exists(auto_map)))

        passed = RESULTS["pass"]
        failed = RESULTS["fail"]
        print("-" * 70)
        print("[TEST 13] SUMMARY: %d PASSED | %d FAILED" % (passed, failed))
        if failed == 0:
            print("[TEST 13] >>> SUITE GREEN <<<")
        else:
            print("[TEST 13] >>> SUITE FAILED <<<")
        return 0 if failed == 0 else 1
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def artifact_exists(path):
    return os.path.isfile(path) and os.path.getsize(path) > 0


if __name__ == "__main__":
    sys.exit(main())
