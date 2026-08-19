with open('obf_final.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()
print('Total lines:', len(lines))
for i in range(len(lines)):
    line_bytes = lines[i][:60].encode('ascii', 'backslashreplace').decode('ascii')
    print(f'Line {i+1} (len {len(lines[i])}): {line_bytes}')
