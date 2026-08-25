"""TVM runtime wall-clock benchmark.

Measures median execution time of fixed, compute-bound workloads running as
TVM-virtualized artifacts (vm-level 3) versus native. Usage:

    python benchmarks/vm_bench.py --out benchmarks/baseline.json

Output JSON: per-case native/obf median ms (5 runs), speedup ratio, totals,
build seconds. Deterministic workloads; no randomness in the measured section.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = {
    "fib_recursive": (
        18,
        "def fib(n):\n"
        "    if n < 2:\n"
        "        return n\n"
        "    return fib(n-1) + fib(n-2)\n"
        "print(fib(18))\n",
    ),
    "loop_sum": (
        30,
        "total = 0\n"
        "for i in range(30000):\n"
        "    total += i * 3 - 7\n"
        "print(total)\n",
    ),
    "string_build": (
        12,
        "parts = []\n"
        "for i in range(4000):\n"
        "    parts.append(str(i % 97) + '-' + str(i))\n"
        "s = ''.join(parts)\n"
        "print(len(s))\n",
    ),
    "closure_counter": (
        25,
        "def make():\n"
        "    c = 0\n"
        "    def inc(d=1):\n"
        "        nonlocal c\n"
        "        c += d\n"
        "        return c\n"
        "    return inc\n"
        "inc = make()\n"
        "x = 0\n"
        "for _ in range(8000):\n"
        "    x = inc(2)\n"
        "print(x)\n",
    ),
    "miller_rabin": (
        10,
        "def is_prime(n):\n"
        "    if n < 2:\n"
        "        return False\n"
        "    for p in (2, 3, 5, 7, 11, 13):\n"
        "        if n % p == 0:\n"
        "            return n == p\n"
        "    d = n - 1\n"
        "    s = 0\n"
        "    while d % 2 == 0:\n"
        "        d //= 2\n"
        "        s += 1\n"
        "    for a in (2, 3, 5, 7, 11, 13, 17):\n"
        "        x = pow(a, d, n)\n"
        "        if x == 1 or x == n - 1:\n"
        "            continue\n"
        "        for _ in range(s - 1):\n"
        "            x = pow(x, 2, n)\n"
        "            if x == n - 1:\n"
        "                break\n"
        "        else:\n"
        "            return False\n"
        "    return True\n"
        "print(sum(1 for n in range(2, 700) if is_prime(n)))\n",
    ),
}

RUNS = 5


def median_run(cmd_list, expect_substr, cwd=None):
    times = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        r = subprocess.run(cmd_list, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=cwd)
        dt = (time.perf_counter() - t0) * 1000.0
        if r.returncode != 0 or expect_substr not in r.stdout:
            raise RuntimeError("run failed rc=%s out=%r err=%r" %
                               (r.returncode, r.stdout[:80], r.stderr[-200:]))
        times.append(dt)
    return statistics.median(times)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tmpdir = tempfile.mkdtemp(prefix="trx_vmbench_")
    results = {}
    total_native = total_obf = 0.0

    for name, (tag, src) in CASES.items():
        ipath = os.path.join(tmpdir, name + "_src.py")
        opath = os.path.join(tmpdir, name + "_obf.py")
        with open(ipath, "w", encoding="utf-8") as f:
            f.write(src)

        t0 = time.perf_counter()
        b = subprocess.run(
            [sys.executable, "main.py", "-i", ipath, "-o", opath,
             "-m", "1", "--compile", "y", "--double-compile", "n",
             "--vm-obf", "y", "--vm-level", "3", "--velimatix", "n",
             "--no-art"],
            capture_output=True, text=True, cwd=REPO)
        build_s = time.perf_counter() - t0
        if b.returncode != 0:
            raise RuntimeError("build failed for %s: %s" % (name, b.stderr[-300:]))

        expect = subprocess.run([sys.executable, ipath], capture_output=True,
                                text=True).stdout.strip()
        nat_ms = median_run([sys.executable, ipath], expect.strip().splitlines()[0])
        obf_ms = median_run([sys.executable, opath], expect.strip().splitlines()[0])

        results[name] = {
            "native_ms": round(nat_ms, 2),
            "tvm_ms": round(obf_ms, 2),
            "ratio": round(obf_ms / nat_ms, 2) if nat_ms else None,
            "build_s": round(build_s, 2),
        }
        total_native += nat_ms
        total_obf += obf_ms
        print("%-16s native %8.1f ms | tvm %8.1f ms | x%.2f" %
              (name, nat_ms, obf_ms, obf_ms / max(nat_ms, 0.001)))

    payload = {
        "python": sys.version.split()[0],
        "runs": RUNS,
        "vm_level": 3,
        "cases": results,
        "totals": {
            "native_ms": round(total_native, 2),
            "tvm_ms": round(total_obf, 2),
            "geomean_ratio": round(
                statistics.geometric_mean(
                    [results[c]["ratio"] for c in results if results[c]["ratio"]]), 2),
        },
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    print("TOTALS native %.0f ms | tvm %.0f ms | geomean slowdown x%s" %
          (total_native, total_obf, payload["totals"]["geomean_ratio"]))
    print("written:", args.out)


if __name__ == "__main__":
    main()
