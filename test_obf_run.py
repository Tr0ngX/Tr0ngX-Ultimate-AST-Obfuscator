import subprocess, time

print('Testing python obf_mode3_fast.py directly with timeout...')
t0 = time.time()
try:
    res = subprocess.run(['python', 'obf_mode3_fast.py'], capture_output=True, text=True, timeout=60)
    print(f'Done in {time.time()-t0:.2f}s! Exit code:', res.returncode)
    print('STDOUT:\n', res.stdout[:1000])
    if res.stderr:
        print('STDERR:\n', res.stderr[:1000])
except subprocess.TimeoutExpired:
    print(f'Timed out after 60s at {time.time()-t0:.2f}s!')
