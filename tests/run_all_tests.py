"""
Tr0ngX Ultimate Obfuscator - Automated End-to-End Test Runner
Obfuscates all test suites under multiple combinations and validates 100% semantic correctness.
"""
import os, sys, subprocess, tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEST_FILES = [
    "tests/test_01_core_features.py",
    "tests/test_02_crypto_math.py",
    "tests/test_03_data_structures.py",
    "tests/test_04_dynamic_reflection.py",
    "tests/test_05_edge_cases.py",
    "complex_benchmark.py"
]

STANDALONE_TESTS = [
    "tests/test_06_crypto_password.py",
    "tests/test_07_reproducible.py",
    "tests/test_08_dos_limits.py",
    "tests/test_09_antivm_antidebug.py"
]

OBF_CONFIGS = [
    {
        "name": "Standard Mode 1 (Fast AST + Strings)",
        "args": ["-m", "1", "--force-py", "off", "--no-art"]
    },
    {
        "name": "Medium Mode 2 + Double Compile + Matrix Fused",
        "args": ["-m", "2", "--compile", "y", "--velimatix", "y", "--veli-level", "2", "--double-compile", "y", "--matrix", "y", "--kramer", "y", "--cjk-vars", "y", "--force-py", "off", "--no-art"]
    },
    {
        "name": "Argon2id / PBKDF2 Password AEAD + Double Compile + Kramer",
        "args": ["-m", "2", "--compile", "y", "--password", "Tr0ngX_SuitePass_2026", "--double-compile", "y", "--kramer", "y", "--force-py", "off", "--no-art"],
        "env": {"TR0NGX_PASSWORD": "Tr0ngX_SuitePass_2026"}
    },
    {
        "name": "MAXIMUM POWER Mode 3 + Anti-Debug + Anti-VM + SelfMod + Double Compile + Fused Matrix + Unicode",
        "args": ["-m", "3", "--moreobf", "y", "--antidebug", "y", "--antivm", "y", "--selfmod", "y", "--compile", "y", "--velimatix", "y", "--veli-level", "3", "--double-compile", "y", "--matrix", "y", "--kramer", "y", "--emoji-obf", "y", "--whitespace-obf", "y", "--cjk-vars", "y", "--rare-unicode", "y", "--homoglyph", "y", "--force-py", "off", "--no-art", "--max-ram", "2048", "--cores", "2"]
    }
]

def main():
    print("=" * 70)
    print(" TR0NGX OBFUSCATOR - AUTOMATED INTEGRATION & STRESS TEST HARNESS")
    print("=" * 70)
    
    total_passed = 0
    total_failed = 0

    # 1. Native Execution Verification
    print("\n[PHASE 1] Verifying Native Test Suites Execution...", flush=True)
    for tf in TEST_FILES:
        if not os.path.exists(tf):
            print(f"  [!] Missing test file: {tf}", flush=True)
            continue
        p = subprocess.run([sys.executable, tf], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode == 0:
            print(f"  [PASS] Native: {tf}", flush=True)
            total_passed += 1
        else:
            print(f"  [FAIL] Native: {tf}\n    {p.stderr}", flush=True)
            total_failed += 1

    # 2. Obfuscation and Post-Obfuscation Execution Verification
    print("\n[PHASE 2] Obfuscating & Verifying Functional Invariance Across Matrix Configs...", flush=True)
    obf_script = "tr0ngx_obfuscator.py"
    
    for cfg in OBF_CONFIGS:
        print(f"\n---> Testing Configuration: {cfg['name']}", flush=True)
        for tf in TEST_FILES:
            if not os.path.exists(tf):
                continue
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp_out:
                out_path = tmp_out.name

            try:
                # Run obfuscation
                cmd = [sys.executable, obf_script, "-i", tf, "-o", out_path] + cfg["args"]
                p_obf = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                if p_obf.returncode != 0:
                    print(f"  [FAIL] OBFUSCATION ERROR on {tf}: {p_obf.stderr.strip() or p_obf.stdout.strip()}", flush=True)
                    total_failed += 1
                    continue

                # Run obfuscated file
                run_env = os.environ.copy()
                if "env" in cfg:
                    run_env.update(cfg["env"])
                p_run = subprocess.run([sys.executable, out_path], env=run_env, capture_output=True, text=True, encoding="utf-8", errors="replace")
                if p_run.returncode == 0:
                    print(f"  [PASS] VERIFIED: {tf} -> {os.path.basename(out_path)} ({os.path.getsize(out_path):,} bytes)", flush=True)
                    total_passed += 1
                else:
                    print(f"  [FAIL] EXECUTION FAILURE on {tf} [Return Code {p_run.returncode}]:\n{p_run.stderr.strip()}", flush=True)
                    total_failed += 1
            finally:
                if os.path.exists(out_path):
                    try:
                        os.remove(out_path)
                    except:
                        pass

    # 3. Standalone Security & Resilience Test Suites
    print("\n[PHASE 3] Running Standalone Security & Resilience Test Suites...", flush=True)
    for st in STANDALONE_TESTS:
        if not os.path.exists(st):
            print(f"  [!] Missing standalone test: {st}", flush=True)
            continue
        p = subprocess.run([sys.executable, st], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode == 0:
            print(f"  [PASS] Standalone Suite: {st}", flush=True)
            total_passed += 1
        else:
            print(f"  [FAIL] Standalone Suite: {st}\n    {p.stderr}", flush=True)
            total_failed += 1

    print("\n" + "=" * 70, flush=True)
    print(f" TEST RUN COMPLETED: {total_passed} PASSED | {total_failed} FAILED", flush=True)
    print("=" * 70, flush=True)
    
    if total_failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()

