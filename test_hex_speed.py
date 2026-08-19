import binascii

raw_str = 'hello world test string 12345'
# Method 1 (Current Kramer): hexlify per character joined by '/'
m1 = '/'.join(binascii.hexlify(c.encode('utf-8')).decode('ascii') for c in raw_str)
# Unhexlify per char:
dec1 = ''.join(binascii.unhexlify(h).decode('utf-8') for h in m1.split('/'))

# Method 2 (Block hexlify): hexlify whole string once!
m2 = binascii.hexlify(raw_str.encode('utf-8')).decode('ascii')
# Unhexlify whole string once:
dec2 = binascii.unhexlify(m2).decode('utf-8')

print('Decoded match:', dec1 == raw_str, dec2 == raw_str)
print('Size m1:', len(m1), 'Size m2:', len(m2))
