sample = 'sample_complex.py'
import subprocess

# Inputs:
# ENTER FILE: sample_complex.py
# ENTER MODE (1-3): 2
# MORE OBF? (y/n): y
# ANTI DEBUG? (y/n): n
# SELF-MODIFYING CODE? (y/n): n
# COMPILE? (y/n): y
# VELIMATIX ENGINE? (y/n): y
# VELIMATIX LEVEL (1-3): 2
# DOUBLE COMPILE (Veli wrap)? (y/n): y

inputs = \"sample_complex.py\n2\ny\nn\nn\ny\ny\n2\ny\n\"

p = subprocess.Popen(['python', 'C:\\Users\\trong\\Downloads\\procheck.py'],
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE,
                     text=True,
                     encoding='utf-8')
stdout, stderr = p.communicate(input=inputs, timeout=60)
print('STDOUT:\n', stdout[-1500:] if len(stdout) > 1500 else stdout)
print('STDERR:\n', stderr)
