import os, sys, subprocess

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def test_password_encryption_roundtrip():
    print('[TEST 06] Testing Argon2id + PBKDF2 Password AEAD Encryption...')
    target_code = "def secret_computation(x, y):\n    return (x * 42) ^ (y + 1337)\n\nassert secret_computation(10, 20) == (420 ! 1357)\nprint('PAYLOAD_EXECUTION_SUCCESS_KEY')\n"
    target_code = target_code.replace('!', '^')
    tmp_in = 'tmp_pwd_target.py'
    tmp_out = 'tmp_pwd_obf.py'
    try:
        with open(tmp_in, 'w', encoding='utf-8') as f:
            f.write(target_code)

        pwd = 'Tr0ngX_MasterKey_2026!'
        # 1. Obfuscate with password
        cmd = [sys.executable, 'main.py', '-i', tmp_in, '-o', tmp_out, '-m', '2', '--compile', 'y', '--password', pwd, '--no-art']
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert res.returncode == 0, f'Obfuscation failed: {res.stderr}'
        assert os.path.exists(tmp_out), 'Output file not generated'
        print('  [PASS] Password Compilation Succeeded')

        # 2. Verify execution with correct password in env
        env_correct = os.environ.copy()
        env_correct['PYTHONIOENCODING'] = 'utf-8'
        env_correct['TR0NGX_PASSWORD'] = pwd
        run_res = subprocess.run([sys.executable, tmp_out], env=env_correct, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert run_res.returncode == 0, f'Execution failed: {run_res.stderr}'
        assert 'PAYLOAD_EXECUTION_SUCCESS_KEY' in run_res.stdout
        print('  [PASS] Correct Password Execution Verified')

        # 3. Verify rejection with incorrect password
        env_wrong = os.environ.copy()
        env_wrong['TR0NGX_PASSWORD'] = 'IncorrectPassword!'
        run_wrong = subprocess.run([sys.executable, tmp_out], env=env_wrong, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert run_wrong.returncode != 0, 'Script did not fail with wrong password'
        print('  [PASS] Wrong Password Rejection Verified')

        print('[TEST 06] all checks passed\n')
    finally:
        for f in [tmp_in, tmp_out]:
            if os.path.exists(f):
                try: os.remove(f)
                except Exception: pass

if __name__ == '__main__':
    test_password_encryption_roundtrip()