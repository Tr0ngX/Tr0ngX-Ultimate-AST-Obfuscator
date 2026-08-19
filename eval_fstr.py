with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos = 132619
full_fstring = text[pos:pos+1175]
print('Testing compile of full_fstring:')
try:
    eval(full_fstring, {'author': '', 'var': '', '_en_var': 'a', '___import__': '__import__', 'obfstr': lambda s: repr(s), '_july_var': 'b', '_birth_var': 'c', '_b85_var': 'd', '_exec_var': 'e', 'part_assignments': '', 'key1': 'k1', 'key2': 'k2', 'part_concat': 'x', 'try\u1160': print})
    print('F-string evaluated successfully!')
except Exception as e:
    print('F-string eval failed:', e)
