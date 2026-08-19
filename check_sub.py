with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos = 132619
sub = text[pos:pos+1500]
print(sub.encode('ascii', errors='backslashreplace').decode('ascii'))
