import re
with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos = 132619
sub = text[pos:]
for m in re.finditer(r'"""', sub):
    print('triple-quote at offset', m.start(), 'line preview:', repr(sub[m.start()-20:m.start()+20]))
