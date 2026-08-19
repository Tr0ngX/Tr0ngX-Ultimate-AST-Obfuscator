import ast
with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(100, len(lines), 100):
    chunk = ''.join(lines[:i])
    try:
        ast.parse(chunk + '\n    pass\n')
    except SyntaxError as e:
        print(f'First failure at line {i}: {e}')
        # Now find exact line
        for j in range(i-100, i+1):
            try:
                ast.parse(''.join(lines[:j]) + '\n    pass\n')
            except SyntaxError as e2:
                print(f'Exact failure at line {j}: {e2}')
                break
        break
