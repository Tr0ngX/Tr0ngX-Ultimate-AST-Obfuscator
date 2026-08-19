with open('obf_final.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()
print('Total lines:', len(lines))
for i in range(min(18, len(lines))):
    print(f'Line {i+1}: {repr(lines[i][:60])}')
