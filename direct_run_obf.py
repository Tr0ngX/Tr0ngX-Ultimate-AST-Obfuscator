import subprocess, time

print('Testing test_obf_final_run.py without timeout...')
t0 = time.time()
p = subprocess.Popen(['python', 'obf_final.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
try:
    stdout, stderr = p.communicate(timeout=60)
    print(f'Done in {time.time()-t0:.2f}s! Returncode:', p.returncode)
    print('STDOUT:\n', stdout[:1000])
    if stderr:
        print('STDERR:\n', stderr[:1000])
except subprocess.TimeoutExpired:
    p.kill()
    print('Timed out!')
