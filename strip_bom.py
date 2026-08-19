with open('sample_complex.py', 'rb') as f:
    data = f.read()

# Strip BOM if present
if data.startswith(b'\xef\xbb\xbf'):
    data = data[3:]

with open('sample_complex.py', 'wb') as f:
    f.write(data)

print('BOM stripped successfully.')
