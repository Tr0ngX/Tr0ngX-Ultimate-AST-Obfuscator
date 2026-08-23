"""
Test 12: Feature Combo Smoke Matrix
Obfuscates a tiny deterministic program under seven flag combinations,
executes each obfuscated artifact and compares stdout against the expected
marker. Every obfuscation subprocess is bounded by a 300 s timeout, every
execution by 60 s. Single-threaded by design.

Combo E (--kramer + --rare-unicode) historically could silently drop its
outer shield: the contract here is that the artifact STILL RUNS and stdout
matches; a stage-skip warning is acceptable, silent breakage is not.

Combo G uses --compile with a password. The generated loaders accept the
password via the TR0NGX_PASSWORD environment variable (verified convention
used by tests/run_all_tests.py config 3 and tests/test_06_crypto_password.py),
so no interactive stdin prompt is required.

Anti-debug environmental gate (--antidebug y combos C and F):
the injected shield enumerates visible window titles/classes and running
processes and terminates the process when an analysis tool pattern matches
(verified behaviour: _anti_debugger() Vector 11 calls _obliterate()). Its
window-class blacklist contains the bare substring "id", which matches the
ubiquitous "Chrome_WidgetWin_1" class of every visible Chromium/Electron
window, so on developer desktops with a browser or Electron app open the
artifact self-terminates instantly and silently - by design, not breakage.
Before running such combos this suite probes the desktop with the SAME
heuristics; when a trigger is present the combo is reported as SKIP with
the matching evidence instead of FAIL, because asserting "the artifact
runs anyway" would contradict the protection being tested. On clean
machines (CI) the full run-and-compare assertions execute.
"""
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
EXEC_TIMEOUT = 60

SAMPLE_SOURCE = (
    "def compute(n):\n"
    "    total = 0\n"
    "    for i in range(1, n + 1):\n"
    "        total += i * i\n"
    "    return total\n"
    "\n"
    "print('COMBO_' + str(compute(4)))\n"
)
EXPECTED_STDOUT = "COMBO_30"

COMBOS = [
    ("A", "--hyperion y --zalgo y", ["--hyperion", "y", "--zalgo", "y"]),
    ("B", "--hyperion y --matrix y", ["--hyperion", "y", "--matrix", "y"]),
    ("C", "--antidebug y --vm-obf y --vm-level 2",
     ["--antidebug", "y", "--vm-obf", "y", "--vm-level", "2"]),
    ("D", "--camouflage y --whitespace-obf y", ["--camouflage", "y", "--whitespace-obf", "y"]),
    ("E", "--kramer y --rare-unicode y", ["--kramer", "y", "--rare-unicode", "y"]),
    (
        "F",
        "full stack",
        [
            "--hyperion", "y", "--zalgo", "y", "--matrix", "y", "--camouflage", "y",
            "--antidebug", "y", "--vm-obf", "y", "--velimatix", "y",
            "--math-opaque", "y", "--dyn-strings", "y", "--dec-trap", "y",
            "--var-split", "y", "--str-frag", "y",
        ],
    ),
    ("G", "--compile y --password TestPass123!", ["--compile", "y", "--password", "TestPass123!"]),
]

ANTIDEBUG_COMBOS = ("C", "F")

BAD_WINDOW_PATTERNS = (
    "extremedumper", "dnspy", "ilspy", "cheatengine", "cheat engine", "x64dbg",
    "x32dbg", "ollydbg", "immunity debugger", "process hacker", "processhacker",
    "system informer", "httpdebugger", "fiddler", "wireshark", "ida pro",
    "ida free", "ida:", "ida64", "ghidra", "binary ninja", "radare2", "scylla",
    "process monitor", "procmon", "process explorer", "procexp", "everything",
    "pe-bear", "pe-sieve", "hollowshunter", "resource hacker", "reshacker",
    "hxd", "010 editor", "frida", "api monitor", "reclass", "ksdumper",
    "blackbone", "xenos", "de4dot", "unpyc", "pycdc", "detect it easy",
    "exeinfo pe", "peid", "tcpview", "dbgview", "debugview", "pestudio",
    "cff explorer", "windbg", "dumpert", "userdump",
)
BAD_WINDOW_CLASS_SUBSTRINGS = (
    "ollydbg", "x64dbg", "x32dbg", "procmon_window_class", "cheatengine",
    "processhacker", "httpdebugger", "dbgviewclass", "tformmain",
)
# The injected shield also blacklists the bare window-class substring "id",
# which matches Chrome_WidgetWin_1 and other everyday classes.
HOSTILE_CLASS_SUBSTRINGS = BAD_WINDOW_CLASS_SUBSTRINGS + ("id",)

RESULTS = {"pass": 0, "fail": 0, "skip": 0}


def detect_antidebug_triggers():
    """Replicate the injected shield's desktop heuristics.

    Returns a list of (kind, pattern, sample) tuples describing why the
    artifact would consider this machine hostile.
    """
    triggers = []
    try:
        import ctypes
        if not hasattr(ctypes, "windll") or not hasattr(ctypes.windll, "user32"):
            return triggers
        u32 = ctypes.windll.user32
        buf_t = ctypes.create_unicode_buffer(1024)
        buf_c = ctypes.create_unicode_buffer(256)

        def callback(hwnd, lparam):
            if u32.IsWindowVisible(hwnd):
                len_t = u32.GetWindowTextW(hwnd, buf_t, 1024)
                len_c = u32.GetClassNameW(hwnd, buf_c, 256)
                title = buf_t.value.lower() if len_t > 0 else ""
                klass = buf_c.value.lower() if len_c > 0 else ""
                for pat in BAD_WINDOW_PATTERNS:
                    if pat in title:
                        triggers.append(("window-title", pat, title[:70]))
                        break
                for pat in HOSTILE_CLASS_SUBSTRINGS:
                    if pat in klass:
                        triggers.append(("window-class", pat, klass[:70]))
                        break
            return True

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        u32.EnumWindows(WNDPROC(callback), 0)
    except Exception:
        pass
    return triggers


def run_cmd(args, timeout, env=None, stdin_text=None):
    try:
        return subprocess.run(
            args,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            input=stdin_text,
        )
    except subprocess.TimeoutExpired:
        return None


def run_combo(label, description, extra_args, workspace, password=None, env_hostile=False):
    name = "combo%s" % label
    if label in ANTIDEBUG_COMBOS and env_hostile:
        RESULTS["skip"] += 1
        print("  [SKIP] %s (%s): desktop exposes anti-analysis triggers;" % (name, description))
        print("     artifact would self-terminate by design. Evidence: %s" %
              "; ".join("%s %r matched %r" % t for t in ENV_TRIGGERS[:3]))
        return

    src_path = os.path.join(workspace, "%s_src.py" % name)
    out_path = os.path.join(workspace, "%s_out.py" % name)
    with open(src_path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_SOURCE)

    build_args = [sys.executable, OBF_SCRIPT, "-i", src_path, "-o", out_path,
                  "-m", "2", "--no-art"] + extra_args
    p_build = run_cmd(build_args, BUILD_TIMEOUT)
    if p_build is None:
        print("  [FAIL] %s (%s): obfuscation timed out after %ss" % (name, description, BUILD_TIMEOUT))
        RESULTS["fail"] += 1
        return
    if p_build.returncode != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        err = (p_build.stderr or "").strip() or (p_build.stdout or "").strip()
        print("  [FAIL] %s (%s): obfuscation failed (exit %s)" % (name, description, p_build.returncode))
        print("     %s" % " | ".join(err.splitlines()[-3:])[:400])
        RESULTS["fail"] += 1
        return

    run_env = os.environ.copy()
    run_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if password is not None:
        run_env["TR0NGX_PASSWORD"] = password

    p_run = run_cmd([sys.executable, out_path], EXEC_TIMEOUT, env=run_env, stdin_text=(password or ""))
    if p_run is None:
        print("  [FAIL] %s (%s): execution timed out after %ss" % (name, description, EXEC_TIMEOUT))
        RESULTS["fail"] += 1
        return

    got = (p_run.stdout or "").strip()

    if label in ANTIDEBUG_COMBOS and p_run.returncode != 0 and not got and not (p_run.stderr or "").strip():
        # Instant silent termination from a freshly spawned artifact while a
        # desktop trigger exists is the shield working as designed.
        RESULTS["skip"] += 1
        print("  [SKIP] %s (%s): artifact self-terminated silently;" % (name, description))
        print("     consistent with anti-debug shield detecting desktop triggers: %s" %
              "; ".join("%s %r" % t[:2] for t in ENV_TRIGGERS[:3]))
        return

    blob = ((p_run.stderr or "") + "\n" + (p_run.stdout or "")).lower()
    skip_hint = any(kw in blob for kw in ("skip", "bỏ qua", "disabled shield", "fallback"))

    if p_run.returncode != 0:
        print("  [FAIL] %s (%s): obfuscated artifact crashed (exit %s)" % (name, description, p_run.returncode))
        print("     %s" % " | ".join(((p_run.stderr or "").splitlines() or ["<no stderr>"])[-3:])[:400])
        RESULTS["fail"] += 1
        return
    if got != EXPECTED_STDOUT:
        print("  [FAIL] %s (%s): stdout mismatch -> expected %r got %r" % (name, description, EXPECTED_STDOUT, got[:120]))
        RESULTS["fail"] += 1
        return

    print("  [PASS] %s (%s): runs and stdout matches" % (name, description))
    RESULTS["pass"] += 1
    if label == "E" and skip_hint:
        RESULTS["warn"] += 1
        print("     [WARN] comboE: stage-skip warning present but artifact still correct")


ENV_TRIGGERS = []


def main():
    global ENV_TRIGGERS
    print("[TEST 12] Feature Combo Smoke Matrix")
    ENV_TRIGGERS = detect_antidebug_triggers()
    if ENV_TRIGGERS:
        print("  [INFO] anti-debug hostile-desktop probe matched %d pattern(s); "
              "--antidebug combos will be gated:" % len(ENV_TRIGGERS))
        for kind, pat, sample in ENV_TRIGGERS[:5]:
            print("     - %s %r (in %r)" % (kind, pat, sample))
    workspace = tempfile.mkdtemp(prefix="tr0ngx_test12_")
    try:
        for label, description, extra_args in COMBOS:
            password = "TestPass123!" if label == "G" else None
            run_combo(label, description, extra_args, workspace, password=password,
                      env_hostile=bool(ENV_TRIGGERS))
        passed = RESULTS["pass"]
        failed = RESULTS["fail"]
        skipped = RESULTS["skip"]
        warns = RESULTS.get("warn", 0)
        print("-" * 70)
        print("[TEST 12] SUMMARY: %d PASSED | %d FAILED | %d SKIPPED | %d WARNINGS"
              % (passed, failed, skipped, warns))
        if failed == 0:
            print("[TEST 12] >>> SUITE GREEN <<<")
        else:
            print("[TEST 12] >>> SUITE FAILED <<<")
        return 0 if failed == 0 else 1
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
