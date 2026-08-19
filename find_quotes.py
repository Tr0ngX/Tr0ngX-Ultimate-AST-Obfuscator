with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's inspect where triple quotes are
import re
print('Occurrences of author + var + f\"\"\":')
for m in re.finditer(r'code\s*=\s*author\s*\+\s*var\s*\+\s*f\"\"\"', text):
    print('Match at char', m.start())
