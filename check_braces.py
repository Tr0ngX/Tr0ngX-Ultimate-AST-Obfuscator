import sys
with open(r'C:\Users\trong\Downloads\procheck.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos = 132619
sub = text[pos+26:pos+1167]
# Let's count unescaped quotes or braces in sub
print('len of sub:', len(sub))
open_braces = sub.count('{')
close_braces = sub.count('}')
print('open braces:', open_braces, 'close braces:', close_braces)

# Check all expressions inside braces
idx = 0
while idx < len(sub):
    if sub[idx] == '{':
        end = sub.find('}', idx)
        if end != -1:
            expr = sub[idx+1:end]
            print('F-expr:', expr)
            idx = end + 1
        else:
            print('Unmatched { at', idx)
            break
    else:
        idx += 1
