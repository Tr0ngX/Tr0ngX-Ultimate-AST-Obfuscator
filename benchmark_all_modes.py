# -*- coding: utf-8 -*-
"""
Tr0ngX Comprehensive Benchmark & Matrix Stress Tester
Measures build time, output expansion ratio, execution latency, and semantic accuracy across all individual modes and combined defense tiers.
Single-threaded, zero crash, deterministic compatibility.
"""

import os
import sys
import time
import subprocess
import tempfile
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# Standard sample target script used for baseline benchmarking
SAMPLE_TARGET_CODE = '''# Benchmark Target Script
import math, hashlib

def is_prime(n):
    if n < 2: return False
    for i in range(2, math.isqrt(n) + 1):
        if n % i == 0: return False
    return True

def compute_hash_chain(iterations):
    val = b"TR0NGX_BENCHMARK_SEED_2026"
    for _ in range(iterations):
        val = hashlib.sha256(val).digest()
    return val.hex()

def run_suite():
    primes = [x for x in range(100) if is_prime(x)]
    h = compute_hash_chain(500)
    return {"prime_count": len(primes), "hash_head": h[:16]}

if __name__ == "__main__":
    res = run_suite()
    print(f"BENCHMARK_RESULT: prime_count={res['prime_count']}, hash_head={res['hash_head']}")
'''

EXPECTED_OUTPUT_SUBSTRING = "BENCHMARK_RESULT: prime_count=25, hash_head="

@dataclass
class BenchmarkModeConfig:
    name: str
    description: str
    cli_flags: List[str]

BENCHMARK_MODES: List[BenchmarkModeConfig] = [
    BenchmarkModeConfig(
        name="Mode 1 (Lite AST)",
        description="Fast AST transformation + String & Integer mutation",
        cli_flags=["-m", "1", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Mode 2 (Standard AST)",
        description="2-Layer Trongdepzai AST + Constant restructuring",
        cli_flags=["-m", "2", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Mode 3 (Maximum AST)",
        description="3-Layer Deep AST + Control Flow Mutation",
        cli_flags=["-m", "3", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="AST Junk (+MoreOBF)",
        description="Mode 2 + Dead code decoy injection & try-except traps",
        cli_flags=["-m", "2", "--moreobf", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Math Opaque Predicates",
        description="Mode 2 + Number-theoretic Quadratic Non-Residue mod 7 & Euler invariants",
        cli_flags=["-m", "2", "--math-opaque", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Dynamic XOR Strings",
        description="Mode 2 + Dynamic Per-Callsite AST-Coordinate Derived XOR Strings",
        cli_flags=["-m", "2", "--dyn-strings", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Velimatix Level 1",
        description="Velimatix BiOpaque AST Predicates",
        cli_flags=["-m", "1", "--velimatix", "y", "--veli-level", "1", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Velimatix Level 2",
        description="Velimatix ExceptionJump Structured Control Flow",
        cli_flags=["-m", "1", "--velimatix", "y", "--veli-level", "2", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Velimatix Level 3",
        description="Velimatix Match-Case State Machine Dispatcher",
        cli_flags=["-m", "1", "--velimatix", "y", "--veli-level", "3", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="TVM 2.0 Level 1 (Basic)",
        description="Polymorphic CPU + Custom ISA Bytecode Virtualization",
        cli_flags=["-m", "1", "--vm-obf", "y", "--vm-level", "1", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="TVM 2.0 Level 2 (+Traps)",
        description="TVM 2.0 with Rolling NOPs and Unassigned Opcode Traps",
        cli_flags=["-m", "1", "--vm-obf", "y", "--vm-level", "2", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="TVM 2.0 Level 3 (+Scrub)",
        description="TVM 2.0 with Dummy Invariants & Memory Scrubbing",
        cli_flags=["-m", "1", "--vm-obf", "y", "--vm-level", "3", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Compiled AEAD Payload",
        description="Multi-layer authenticated AEAD compilation (Marshal+2xXOR+2xZlib+Bz2)",
        cli_flags=["-m", "2", "--compile", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Double Compile AEAD",
        description="Inner AEAD compiled bytecode wrapped inside Velimatix Loader",
        cli_flags=["-m", "2", "--compile", "y", "--double-compile", "y", "--velimatix", "y", "--veli-level", "2", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Anti-VM & Sandbox",
        description="Hardware, Hypervisor, MAC OUI & Driver Detection Matrix",
        cli_flags=["-m", "2", "--antivm", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="In-Memory Anti-Dump",
        description="GC Object Scrubber, Linecache Neutralizer & Frame Cleaner",
        cli_flags=["-m", "2", "--anti-dump", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Self-Modifying Layer",
        description="Zero-width signature morphing & runtime hash recalculation",
        cli_flags=["-m", "2", "--selfmod", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Kramer Kyrie Shield",
        description="Dynamic Caesar Alphabet Rotation Class Loader",
        cli_flags=["-m", "2", "--kramer", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Emoji Stream Shield",
        description="Executable Unicode Animal Emoji sequence encoding",
        cli_flags=["-m", "2", "--emoji-obf", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Whitespace Bitfield",
        description="Invisible tab/space binary bitfield encoding",
        cli_flags=["-m", "2", "--whitespace-obf", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Extreme Zalgo Shield",
        description="Glitch diacritics stacking (Z͑͗͑͗...) to paralyze decompiler GUIs",
        cli_flags=["-m", "2", "--zalgo", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Hyperion Camouflage",
        description="Fake Scientific Computing Simulation Class (MemoryAccess/StackOverflow)",
        cli_flags=["-m", "2", "--camouflage", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="Fused 3-Track Matrix",
        description="Interwoven Symbiotic Matrix Loader (Kyrie + Emoji + Whitespace)",
        cli_flags=["-m", "2", "--matrix", "y", "--no-art"]
    ),
    BenchmarkModeConfig(
        name="FULL ARSENAL MAXIMUM",
        description="All 15 defense tiers combined: TVM 2.0 L3 + Camouflage + Matrix + Anti-Analysis Matrix",
        cli_flags=[
            "-m", "2",
            "--compile", "y",
            "--double-compile", "y",
            "--velimatix", "y",
            "--veli-level", "2",
            "--vm-obf", "y",
            "--vm-level", "3",
            "--matrix", "y",
            "--camouflage", "y",
            "--math-opaque", "y",
            "--dyn-strings", "y",
            "--moreobf", "y",
            "--antivm", "y",
            "--anti-dump", "y",
            "--selfmod", "y",
            "--no-art"
        ]
    )
]

def run_single_benchmark(mode: BenchmarkModeConfig, target_path: str, obf_engine_path: str) -> Dict[str, Any]:
    out_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    out_path = out_file.name
    out_file.close()

    try:
        # Step 1: Measure Obfuscation Build Time
        cmd_obf = [sys.executable, obf_engine_path, "-i", target_path, "-o", out_path] + mode.cli_flags
        t0_build = time.perf_counter()
        p_obf = subprocess.run(cmd_obf, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        t_build = time.perf_counter() - t0_build

        if p_obf.returncode != 0:
            return {
                "name": mode.name,
                "status": "BUILD_FAIL",
                "build_time": round(t_build, 3),
                "exec_time": 0.0,
                "size_bytes": 0,
                "expansion": 0.0,
                "error": p_obf.stderr.strip() or p_obf.stdout.strip()
            }

        out_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        src_size = os.path.getsize(target_path)
        expansion = round(out_size / src_size, 1) if src_size > 0 else 1.0

        # Step 2: Measure Execution Latency & Verify Correctness (Single-threaded)
        t0_exec = time.perf_counter()
        p_exec = subprocess.run([sys.executable, out_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        t_exec = time.perf_counter() - t0_exec

        if p_exec.returncode != 0:
            return {
                "name": mode.name,
                "status": "RUNTIME_FAIL",
                "build_time": round(t_build, 3),
                "exec_time": round(t_exec, 4),
                "size_bytes": out_size,
                "expansion": expansion,
                "error": p_exec.stderr.strip() or p_exec.stdout.strip()
            }

        # Step 3: Semantic Verification
        if EXPECTED_OUTPUT_SUBSTRING not in p_exec.stdout:
            return {
                "name": mode.name,
                "status": "SEMANTIC_MISMATCH",
                "build_time": round(t_build, 3),
                "exec_time": round(t_exec, 4),
                "size_bytes": out_size,
                "expansion": expansion,
                "error": f"Output mismatch. Received: {p_exec.stdout.strip()}"
            }

        return {
            "name": mode.name,
            "status": "PASS",
            "build_time": round(t_build, 3),
            "exec_time": round(t_exec, 4),
            "size_bytes": out_size,
            "expansion": expansion,
            "error": None
        }

    except Exception as e:
        return {
            "name": mode.name,
            "status": "EXCEPTION",
            "build_time": 0.0,
            "exec_time": 0.0,
            "size_bytes": 0,
            "expansion": 0.0,
            "error": str(e)
        }
    finally:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    obf_engine = os.path.join(root_dir, "tr0ngx_obfuscator.py")

    # Create temporary baseline script
    src_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8")
    src_file.write(SAMPLE_TARGET_CODE)
    src_path = src_file.name
    src_file.close()

    # Measure Baseline (Unobfuscated Execution Time)
    t0_base = time.perf_counter()
    p_base = subprocess.run([sys.executable, src_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    baseline_exec_time = time.perf_counter() - t0_base

    print("=" * 95)
    print("      TR0NGX ULTIMATE AST OBFUSCATOR - MODE-BY-MODE BENCHMARK HARNESS")
    print("=" * 95)
    print(f" Python Interpreter : {sys.version.split()[0]} ({sys.platform})")
    print(f" Benchmark Target   : Cryptographic Hash Chain + Sieve of Eratosthenes")
    print(f" Source Script Size : {os.path.getsize(src_path):,} bytes")
    print(f" Baseline Exec Time : {baseline_exec_time:.4f}s")
    print(f" Test Concurrency   : Single-threaded (1 worker, non-blocking serial execution)")
    print("-" * 95)
    print(f" {'#':<3} | {'Mode Name':<30} | {'Status':<8} | {'Build (s)':<9} | {'Exec (s)':<9} | {'Size (Bytes)':<12} | {'Ratio':<7}")
    print("-" * 95)

    results = []
    for idx, mode in enumerate(BENCHMARK_MODES, 1):
        res = run_single_benchmark(mode, src_path, obf_engine)
        results.append(res)

        status_str = f"\033[92m{res['status']}\033[0m" if res['status'] == "PASS" else f"\033[91m{res['status']}\033[0m"
        size_display = f"{res['size_bytes']:,}" if res['size_bytes'] > 0 else "-"
        ratio_display = f"{res['expansion']}x" if res['expansion'] > 0 else "-"

        print(f" {idx:<3} | {res['name']:<30} | {status_str:<17} | {res['build_time']:<9.3f} | {res['exec_time']:<9.4f} | {size_display:<12} | {ratio_display:<7}")
        if res['error']:
            print(f"     └─> ERROR: {res['error'][:100]}")

    # Cleanup temporary source
    if os.path.exists(src_path):
        try:
            os.remove(src_path)
        except Exception:
            pass

    # Summary Statistics
    total_modes = len(results)
    passed_modes = sum(1 for r in results if r["status"] == "PASS")
    pass_rate = (passed_modes / total_modes) * 100.0

    print("=" * 95)
    print(f" BENCHMARK SUMMARY: {passed_modes}/{total_modes} Modes Passed ({pass_rate:.1f}%)")
    print("=" * 95)

    # Export benchmark report if requested
    report_file = os.path.join(root_dir, "benchmark_report.json")
    with open(report_file, "w", encoding="utf-8") as rf:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "python_version": sys.version,
            "baseline_exec_time": round(baseline_exec_time, 4),
            "modes_count": total_modes,
            "passed_count": passed_modes,
            "pass_rate": round(pass_rate, 2),
            "details": results
        }, rf, indent=2)
    print(f" Detailed JSON Benchmark Report exported to: {report_file}")

if __name__ == "__main__":
    main()
