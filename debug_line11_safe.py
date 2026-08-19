with open('obf_final.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
line11 = lines[10].encode('ascii', 'backslashreplace').decode('ascii')
print('Line 11 length:', len(line11))
print(line11)
