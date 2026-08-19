import binascii

with open('obf_final_fixed.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's extract and decode the sparkle step by step
idx1 = text.find(\"'''f383b\")
idx2 = text.find(\"'''\n'''\n\", idx1)
hex_payload = text[idx1+3:idx2]

# Let's check line 11 to get the key
lines = text.splitlines()
line11 = lines[10]
# Find key in: ord(t)-KEY
import re
m = re.search(r'ord\(t\)-(\d+)', line11)
key = int(m.group(1))
print('Extracted key:', key)

alpha = 'abcdefghijklmnopqrstuvwxyz0123456789'
s1 = binascii.unhexlify(hex_payload).decode('utf-8')
s2 = ''.join(chr(ord(t)-key) if t!='ζ' else '\n' for t in s1)
s3 = s2.translate(str.maketrans(dict(zip(alpha, alpha[1:]+alpha[:1]))))

print('Decoded first 500 chars of payload:')
print(s3[:500])
print('Decoded lines around line 28:')
payload_lines = s3.splitlines()
for i in range(max(0, 20), min(len(payload_lines), 35)):
    print(f'Line {i+1}: {payload_lines[i]}')
