import os, sys

def fix_standard_compile(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    bad_block = """            code = author + var + f\"\"\"

    import hashlib, hmac

    def _auth_decrypt(raw_bytes):
        salt = raw_bytes[:16]
        tag = raw_bytes[16:32]
        ct = raw_bytes[32:]
        ke = hashlib.pbkdf2_hmac('sha256', salt, {repr(enc_k)}, 1000, 32)
        km = hashlib.pbkdf2_hmac('sha256', salt, {repr(mac_k)}, 1000, 32)
        expected_tag = hmac.new(km, salt + ct, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected_tag):
            raise SystemExit(1)
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ct):
            block = hmac.new(ke, counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))

    {_en_var} = getattr({___import__}({obfstr("marshal")}), {obfstr("loads")})
    {_july_var} = getattr({___import__}({obfstr("zlib")}), {obfstr("decompress")})
    {_birth_var} = getattr({___import__}({obfstr("bz2")}), {obfstr("decompress")})
    {_b85_var} = getattr({___import__}({obfstr("base64")}), {obfstr("b85decode")})
    _types_mod = {___import__}({obfstr("types")})
    _fn_type = getattr(_types_mod, {obfstr("FunctionType")})

    {part_assignments}

    try:
        _payload = {part_concat}
        _step1 = {_b85_var}(_payload)
        _step2 = {_july_var}(_step1)
        _step3 = {_birth_var}(_step2)
        _step4 = _auth_decrypt(_step3)
        _step5 = {_july_var}(_step4)
        _fn_type({_en_var}(_step5), globals())()
        del _payload, _step1, _step2, _step3, _step4, _step5
    except Exception as _e:
        pass
\"\"\""""

    good_block = """            code = author + var + f\"\"\"
import hashlib, hmac, types

def _auth_decrypt(raw_bytes):
    salt = raw_bytes[:16]
    tag = raw_bytes[16:32]
    ct = raw_bytes[32:]
    ke = hashlib.pbkdf2_hmac('sha256', salt, {repr(enc_k)}, 1000, 32)
    km = hashlib.pbkdf2_hmac('sha256', salt, {repr(mac_k)}, 1000, 32)
    expected_tag = hmac.new(km, salt + ct, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected_tag):
        raise SystemExit(1)
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(ct):
        block = hmac.new(ke, counter.to_bytes(4, 'big'), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(ct, keystream[:len(ct)]))

{_en_var} = getattr({___import__}({obfstr("marshal")}), {obfstr("loads")})
{_july_var} = getattr({___import__}({obfstr("zlib")}), {obfstr("decompress")})
{_birth_var} = getattr({___import__}({obfstr("bz2")}), {obfstr("decompress")})
{_b85_var} = getattr({___import__}({obfstr("base64")}), {obfstr("b85decode")})
_types_mod = {___import__}({obfstr("types")})
_fn_type = getattr(_types_mod, {obfstr("FunctionType")})

{part_assignments}

try:
    _payload = {part_concat}
    _step1 = {_b85_var}(_payload)
    _step2 = {_july_var}(_step1)
    _step3 = {_birth_var}(_step2)
    _step4 = _auth_decrypt(_step3)
    _step5 = {_july_var}(_step4)
    _fn_type({_en_var}(_step5), globals())()
    del _payload, _step1, _step2, _step3, _step4, _step5
except Exception as _e:
    pass
\"\"\""""

    content = content.replace(bad_block, good_block)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_standard_compile(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_standard_compile(r"C:\Users\trong\Downloads\procheck.py")
print("Fixed standard compile indentation cleanly!")
