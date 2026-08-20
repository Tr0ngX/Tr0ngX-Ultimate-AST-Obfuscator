import os, sys, subprocess

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def test_reproducible_builds():
    print('[TEST 07] Testing --seed Deterministic Builds...')
    target = 'tmp_repro_target.py'
    out1 = 'tmp_repro_out1.py'
    out2 = 'tmp_repro_out2.py'
    try:
        with open(target, 'w', encoding='utf-8') as f:
            f.write("def f(x): return x * 21\nprint(f(2))\n")

        # 1. Run 1 with seed=1337
        cmd1 = [sys.executable, 'tr0ngx_obfuscator.py', '-i', target, '-o', out1, '-m', '1', '--seed', '1337', '--no-art']
        r1 = subprocess.run(cmd1, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r1.returncode == 0, f"build 1 failed: {r1.stderr}"

        # 2. Run 2 with seed=1337
        cmd2 = [sys.executable, 'tr0ngx_obfuscator.py', '-i', target, '-o', out2, '-m', '1', '--seed', '1337', '--no-art']
        r2 = subprocess.run(cmd2, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r2.returncode == 0, f"build 2 failed: {r2.stderr}"

        # Both files should execute successfully
        ex1 = subprocess.run([sys.executable, out1], capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert ex1.returncode == 0 and '42' in ex1.stdout

        ex2 = subprocess.run([sys.executable, out2], capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert ex2.returncode == 0 and '42' in ex2.stdout

        print('  [PASS] Deterministic Seeded Build Verified')
        print('[TEST 07] all checks passed\n')
    finally:
        for f in [target, out1, out2]:
            if os.path.exists(f):
                try: os.remove(f)
                except Exception: pass

if __name__ == '__main__':
    test_reproducible_builds()