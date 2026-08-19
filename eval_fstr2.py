with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos = 132619
eq = text.find('=', pos)
rhs = text[eq+1:pos+1175].strip()
print('Testing compile of rhs:')
try:
    compile(rhs, '<test>', 'eval')
    print('RHS compiled successfully!')
except SyntaxError as e:
    print('RHS SyntaxError:', e)
