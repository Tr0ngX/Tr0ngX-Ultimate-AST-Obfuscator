with open('C:\\Users\\trong\\Downloads\\procheck.py', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f):
        if 'var =' in line or 'var=' in line:
            print(f'Line {idx+1}: {line.strip()[:100]}')
