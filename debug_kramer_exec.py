import time, binascii

# Let's inspect the Kramer execution step by step
with open('obf_final.py', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

# Extract hex sparkle
idx1 = text.find(\"'''f1868\")
idx2 = text.find(\"'''\n'''\n\", idx1)
hex_data = text[idx1+3:idx2]
print('Hex data length:', len(hex_data))

key = 12345 # wait, what was the key?
