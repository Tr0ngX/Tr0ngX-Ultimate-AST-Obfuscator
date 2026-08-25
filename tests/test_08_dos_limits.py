import os, sys, subprocess

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def test_dos_output_limits():
    print('[TEST 08] Testing --max-output-size DoS Limit Enforcement...')
    target = 'tmp_dos_target.py'
    out_small = 'tmp_dos_small.py'
    out_large = 'tmp_dos_large.py'
    try:
        with open(target, 'w', encoding='utf-8') as f:
            f.write("x = 100\nprint(x)\n")

        # 1. Should abort when limit is exceeded (100 bytes)
        cmd1_res = subprocess.run(
            [sys.executable, 'main.py', '-i', target, '-o', out_small, '-m', '1', '--max-output-size', '100', '--no-art'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        assert cmd1_res.returncode != 0, 'Expected abort when output exceeded max size'
        assert not os.path.exists(out_small), 'Output file was not cleaned up'
        print('  [PASS] Output Size Exceeded Abort Verified')

        # 2. Should pass when limit is large enough (10MB)
        cmd2_res = subprocess.run(
            [sys.executable, 'main.py', '-i', target, '-o', out_large, '-m', '1', '--max-output-size', '10MB', '--no-art'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        assert cmd2_res.returncode == 0, f"Expected success with 10MB limit: {cmd2_res.stderr}"
        assert os.path.exists(out_large), 'Output file should exist'
        print('  [PASS] Within Size Limit Build Verified')
        print('[TEST 08] all checks passed\n')
    finally:
        for f in [target, out_small, out_large]:
            if os.path.exists(f):
                try: os.remove(f)
                except Exception: pass

if __name__ == '__main__':
    test_dos_output_limits()