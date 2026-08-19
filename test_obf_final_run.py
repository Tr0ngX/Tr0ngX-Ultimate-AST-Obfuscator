import subprocess, time

print('Testing python obf_final.py execution with timer...')
t0 = time.time()
try:
    res = subprocess.run(['python', 'obf_final.py'], capture_output=True, text=True, timeout=30)
    print(f'Done in {time.time()-t0:.2f}s! Exit code:', res.returncode)
    print('STDOUT:\n', res.stdout[:1500])
    if res.stderr:
        print('STDERR:\n', res.stderr[:1000])
except subprocess.TimeoutExpired:
    print(f'Timed out after 30s at {time.time()-t0:.2f}s!')
