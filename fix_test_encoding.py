import os, glob

for p in glob.glob('tests/*.py'):
    with open(p, 'r', encoding='utf-8') as f:
        t = f.read()
    t = t.replace('✓', '[PASS]').replace('✗', '[FAIL]').replace('→', '->')
    prefix = (
        'import sys\n'
        'try:\n'
        '    sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
        'except Exception:\n'
        '    pass\n'
    )
    if 'sys.stdout.reconfigure' not in t:
        t = prefix + t
    with open(p, 'w', encoding='utf-8') as f:
        f.write(t)

print("Updated all test files cleanly!")
