import subprocess, time

print('Testing python obf_final_fixed.py runtime execution...')
t0 = time.time()
res = subprocess.run(['python', 'obf_final_fixed.py'], capture_output=True, text=True, timeout=60)
print(f'Done in {time.time()-t0:.2f}s! Exit code:', res.returncode)
print('STDOUT:\n', res.stdout[:1500])
if res.stderr:
    print('STDERR:\n', res.stderr[:1000])
