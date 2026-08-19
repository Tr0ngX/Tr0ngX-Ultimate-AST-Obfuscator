with open('obf_mode3_test.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's inspect the first 400 chars of obf_mode3_test.py
print(repr(text[:400]))
