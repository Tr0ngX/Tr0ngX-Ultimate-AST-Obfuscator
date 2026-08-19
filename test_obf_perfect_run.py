import subprocess, time

print('Testing python obf_mode3_perfect.py execution...')
t0 = time.time()
try:
    res = subprocess.run(['python', 'obf_mode3_perfect.py'], capture_output=True, text=True, timeout=60)
    print(f'Completed in {time.time()-t0:.2f}s! Exit code:', res.returncode)
    print('STDOUT:\n', res.stdout)
    if res.stderr:
        print('STDERR:\n', res.stderr)
except subprocess.TimeoutExpired:
    print(f'Timed out after 60s at {time.time()-t0:.2f}s!')
