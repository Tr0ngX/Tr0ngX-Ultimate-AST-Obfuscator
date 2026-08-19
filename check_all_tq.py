import ast
with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Let's inspect all triple-quote pairs in the entire file
import re
tqs = [m.start() for m in re.finditer(r'"""|\'\'\'', code)]
print('Total triple-quote tokens:', len(tqs))
if len(tqs) % 2 != 0:
    print('ODD NUMBER OF TRIPLE QUOTES! There is an unclosed triple quote!')
    # Find which one is unclosed
    for i in range(len(tqs)):
        start = tqs[i]
        line_no = code[:start].count('\n') + 1
        quote_type = code[start:start+3]
        print(f'Quote #{i}: line {line_no} ({quote_type})')
