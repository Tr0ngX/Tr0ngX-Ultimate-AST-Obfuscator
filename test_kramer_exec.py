test_code = 'print(100 + 200)'

# Run _kramer_wrap on test_code
import importlib.util
spec = importlib.util.spec_from_file_location('procheck', r'C:\Users\trong\Downloads\procheck.py')
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

wrapped = pc._kramer_wrap(test_code)
with open('test_kramer_small.py', 'w', encoding='utf-8') as f:
    f.write(wrapped)

print('Saved test_kramer_small.py, running...')
import subprocess
res = subprocess.run(['python', 'test_kramer_small.py'], capture_output=True, text=True)
print('Exit code:', res.returncode)
print('STDOUT:', repr(res.stdout))
print('STDERR:', repr(res.stderr))
