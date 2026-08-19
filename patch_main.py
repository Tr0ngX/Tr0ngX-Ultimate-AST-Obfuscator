with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    text = f.read()

marker = '# MAIN EXECUTION (CLI + TUI)'
idx = text.find(marker)
print('Marker idx:', idx)
if idx != -1:
    before = text[:idx]
    after = text[idx:]
    
    lines = after.splitlines()
    main_func = ['def main():']
    for l in lines:
        main_func.append('    ' + l if l.strip() else '')
    main_func.append('\nif __name__ == "__main__":\n    main()\n')
    
    new_text = before + '\n'.join(main_func)
    with open(r'C:\Users\trong\Downloads\procheck.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Successfully wrapped main in __main__!')
