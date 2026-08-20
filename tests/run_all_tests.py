"""
Tr0ngX Ultimate Obfuscator - High-Performance Multi-Threaded Test Runner & Verification Harness
Parallelizes test execution across multiple CPU workers with thread-safe live logging and strict runtime invariance checking.
"""
import os, sys, subprocess, tempfile, time, argparse, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    "tests/test_10_complex_realworld.py",
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
        "id": "cfg1",
        "name": "Standard Mode 1 (Fast AST + Strings)",
        "args": ["-m", "1", "--force-py", "off", "--no-art"]
    },
    {
        "id": "cfg2",
        "name": "Medium Mode 2 + Double Compile + Matrix Fused + Kramer",
        "args": ["-m", "2", "--compile", "y", "--velimatix", "y", "--veli-level", "2", "--double-compile", "y", "--matrix", "y", "--kramer", "y", "--cjk-vars", "y", "--force-py", "off", "--no-art"]
    },
    {
        "id": "cfg3",
        "name": "Argon2id / PBKDF2 Password AEAD + Double Compile + Kramer",
        "args": ["-m", "2", "--compile", "y", "--password", "Tr0ngX_SuitePass_2026", "--double-compile", "y", "--kramer", "y", "--force-py", "off", "--no-art"],
        "env": {"TR0NGX_PASSWORD": "Tr0ngX_SuitePass_2026"}
    },
    {
        "id": "cfg4",
        "name": "Modern Armor Mode 2: Math Opaque + Dynamic Strings XOR + In-Memory Anti-Dump",
        "args": ["-m", "2", "--compile", "y", "--math-opaque", "y", "--dyn-strings", "y", "--anti-dump", "y", "--force-py", "off", "--no-art"]
    },
    {
        "id": "cfg5",
        "name": "MAXIMUM POWER Mode 3 + Anti-Debug + Anti-VM + Anti-Dump + SelfMod + Math-Opaque + Dyn-Strings + Double Compile + Fused Matrix + Unicode",
        "args": ["-m", "3", "--moreobf", "y", "--antidebug", "y", "--antivm", "y", "--anti-dump", "y", "--selfmod", "y", "--math-opaque", "y", "--dyn-strings", "y", "--compile", "y", "--velimatix", "y", "--veli-level", "3", "--double-compile", "y", "--matrix", "y", "--kramer", "y", "--emoji-obf", "y", "--whitespace-obf", "y", "--cjk-vars", "y", "--rare-unicode", "y", "--homoglyph", "y", "--force-py", "off", "--no-art", "--max-ram", "2048", "--cores", "2"]
    }
]

_print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)
        sys.stdout.flush()

def run_single_obf_test(task):
    tf = task["file"]
    cfg = task["cfg"]
    task_num = task["num"]
    total_tasks = task["total"]
    obf_script = "tr0ngx_obfuscator.py"

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp_out:
        out_path = tmp_out.name

    try:
        # Step 1: Obfuscation
        t_obf0 = time.time()
        cmd = [sys.executable, obf_script, "-i", tf, "-o", out_path] + cfg["args"]
        p_obf = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        obf_dur = time.time() - t_obf0

        if p_obf.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            err = p_obf.stderr.strip() or p_obf.stdout.strip()
            return {
                "success": False,
                "file": tf,
                "cfg": cfg["name"],
                "task_num": task_num,
                "stage": "OBFUSCATION",
                "error": err,
                "obf_dur": obf_dur,
                "run_dur": 0.0,
                "size": 0
            }

        out_size = os.path.getsize(out_path)

        # Step 2: Runtime Execution Verification
        t_run0 = time.time()
        run_env = os.environ.copy()
        if "env" in cfg:
            run_env.update(cfg["env"])
        p_run = subprocess.run([sys.executable, out_path], env=run_env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        run_dur = time.time() - t_run0

        if p_run.returncode == 0:
            return {
                "success": True,
                "file": tf,
                "cfg": cfg["name"],
                "task_num": task_num,
                "obf_dur": obf_dur,
                "run_dur": run_dur,
                "size": out_size,
                "stdout": p_run.stdout.strip()
            }
        else:
            err = f"Exit Code {p_run.returncode}\nSTDERR: {p_run.stderr.strip()}\nSTDOUT: {p_run.stdout.strip()}"
            return {
                "success": False,
                "file": tf,
                "cfg": cfg["name"],
                "task_num": task_num,
                "stage": "RUNTIME_EXECUTION",
                "error": err,
                "obf_dur": obf_dur,
                "run_dur": run_dur,
                "size": out_size
            }
    except Exception as e:
        return {
            "success": False,
            "file": tf,
            "cfg": cfg["name"],
            "task_num": task_num,
            "stage": "EXCEPTION",
            "error": str(e),
            "obf_dur": 0.0,
            "run_dur": 0.0,
            "size": 0
        }
    finally:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(description="Tr0ngX Multi-Threaded Test Runner")
    parser.add_argument("-w", "--workers", type=int, default=max(2, min(8, (os.cpu_count() or 4))), help="Number of concurrent worker threads")
    parser.add_argument("--config", type=str, default="all", help="Target config (1-5 or all)")
    parser.add_argument("--file", type=str, default="all", help="Target test file substring filter")
    args = parser.parse_args()

    num_workers = args.workers
    selected_configs = OBF_CONFIGS
    if args.config != "all":
        try:
            cfg_idx = int(args.config) - 1
            if 0 <= cfg_idx < len(OBF_CONFIGS):
                selected_configs = [OBF_CONFIGS[cfg_idx]]
        except ValueError:
            pass

    selected_files = [f for f in TEST_FILES if os.path.exists(f)]
    if args.file != "all":
        selected_files = [f for f in selected_files if args.file in f]

    safe_print("=" * 85)
    safe_print(f" TR0NGX OBFUSCATOR - MULTI-THREADED TEST RUNNER ({num_workers} PARALLEL WORKERS)")
    safe_print("=" * 85)
    
    total_passed = 0
    total_failed = 0
    start_total = time.time()

    # 1. Native Execution Verification (Concurrent)
    safe_print(f"\n[PHASE 1] Concurrently Verifying Native Test Suites ({len(selected_files)} suites)...")
    def run_native(tf):
        t0 = time.time()
        p = subprocess.run([sys.executable, tf], capture_output=True, text=True, encoding="utf-8", errors="replace")
        dur = time.time() - t0
        return tf, p.returncode == 0, dur, p.stderr.strip()

    with ThreadPoolExecutor(max_workers=min(num_workers, len(selected_files))) as executor:
        futures = [executor.submit(run_native, tf) for tf in selected_files]
        for f in as_completed(futures):
            tf, ok, dur, err = f.result()
            if ok:
                safe_print(f"  [PASS] Native: {tf:<38} ({dur:.3f}s)")
                total_passed += 1
            else:
                safe_print(f"  [FAIL] Native: {tf}\n    [STDERR]: {err}")
                total_failed += 1

    # 2. Obfuscation and Post-Obfuscation Execution Verification (Multi-Threaded)
    task_list = []
    task_counter = 0
    for cfg in selected_configs:
        for tf in selected_files:
            task_counter += 1
            task_list.append({
                "num": task_counter,
                "total": 0,
                "file": tf,
                "cfg": cfg
            })
    for t in task_list:
        t["total"] = len(task_list)

    safe_print(f"\n[PHASE 2] Concurrently Obfuscating & Verifying {len(task_list)} Tasks across {num_workers} Workers...")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_task = {executor.submit(run_single_obf_test, t): t for t in task_list}
        completed_count = 0

        for future in as_completed(future_to_task):
            res = future.result()
            completed_count += 1
            progress_str = f"[{completed_count:>{len(str(len(task_list)))}}/{len(task_list)}]"
            
            if res["success"]:
                cfg_short = res["cfg"][:30] + "..." if len(res["cfg"]) > 33 else res["cfg"]
                safe_print(f"  {progress_str} [PASS] {res['file']:<35} | {cfg_short:<33} -> {res['size']:>10,} B (obf: {res['obf_dur']:>5.2f}s | run: {res['run_dur']:>5.2f}s)")
                total_passed += 1
            else:
                safe_print(f"\n  {progress_str} [FAIL] {res['file']} under '{res['cfg']}' [{res['stage']}]:\n    {res['error']}\n")
                total_failed += 1

    # 3. Standalone Security & Resilience Test Suites (Concurrent)
    standalone_files = [st for st in STANDALONE_TESTS if os.path.exists(st)]
    safe_print(f"\n[PHASE 3] Concurrently Running {len(standalone_files)} Standalone Security Suites...")
    
    with ThreadPoolExecutor(max_workers=min(num_workers, len(standalone_files))) as executor:
        futures = [executor.submit(run_native, st) for st in standalone_files]
        for f in as_completed(futures):
            st, ok, dur, err = f.result()
            if ok:
                safe_print(f"  [PASS] Standalone Suite: {st:<36} ({dur:.3f}s)")
                total_passed += 1
            else:
                safe_print(f"  [FAIL] Standalone Suite: {st}\n    [STDERR]: {err}")
                total_failed += 1

    total_dur = time.time() - start_total
    safe_print("\n" + "=" * 85)
    safe_print(f" MULTI-THREADED TEST RUN COMPLETED IN {total_dur:.2f}s: {total_passed} PASSED | {total_failed} FAILED")
    safe_print("=" * 85)
    
    if total_failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
