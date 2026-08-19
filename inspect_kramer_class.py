with open('obf_final.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

print('Line 8:', lines[7].strip())
print('Line 9:', lines[8].strip())
print('Line 10:', lines[9].strip())
print('Line 11:', lines[10][:120].strip())
print('Line 12:', lines[11].strip())
print('Line 13 (prefix):', lines[12][:60].strip())
