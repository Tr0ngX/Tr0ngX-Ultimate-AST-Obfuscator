import binascii, re

with open('obf_final_fixed.py', 'r', encoding='utf-8') as f:
    text = f.read()

triple_quote = chr(39) * 3
idx1 = text.find(triple_quote)
idx1 = text.find(triple_quote, idx1 + 3)
idx1 = text.find(triple_quote, idx1 + 3) # start of sparkle
idx2 = text.find(triple_quote, idx1 + 3) # end of sparkle
hex_payload = text[idx1+3:idx2].strip()

lines = text.splitlines()
line11 = lines[10]
m = re.search(r'ord\(t\)-(\d+)', line11)
key = int(m.group(1))
print('Extracted key:', key, 'hex len:', len(hex_payload))

alpha = 'abcdefghijklmnopqrstuvwxyz0123456789'
s1 = binascii.unhexlify(hex_payload).decode('utf-8')
s2 = ''.join(chr(ord(t)-key) if t!='\u03b6' else '\n' for t in s1)
s3 = s2.translate(str.maketrans(dict(zip(alpha, alpha[1:]+alpha[:1]))))

payload_lines = s3.splitlines()
print('Total payload lines:', len(payload_lines))
for i in range(min(len(payload_lines), 35)):
    line_repr = payload_lines[i][:100].encode('ascii', 'backslashreplace').decode('ascii')
    print(f'Line {i+1}: {line_repr}')
