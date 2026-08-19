import os, sys

def fix_inner_loader_formatting(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    old_loader = """    inner_loader = f\"\"\"
import base64, zlib, bz2, marshal, hashlib, hmac, types

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

_payload_b85 = {enc_b85!r}
_s1 = base64.b85decode(_payload_b85)
_s2 = zlib.decompress(_s1)
_s3 = bz2.decompress(_s2)
_s4 = _auth_decrypt(_s3)
_s5 = zlib.decompress(_s4)
types.FunctionType(marshal.loads(_s5), globals())()
del _payload_b85, _s1, _s2, _s3, _s4, _s5
\"\"\""""

    new_loader = """    inner_loader = \"\"\"
import base64, zlib, bz2, marshal, hashlib, hmac, types

def _auth_decrypt(raw_bytes):
    salt = raw_bytes[:16]
    tag = raw_bytes[16:32]
    ct = raw_bytes[32:]
    ke = hashlib.pbkdf2_hmac('sha256', salt, %s, 1000, 32)
    km = hashlib.pbkdf2_hmac('sha256', salt, %s, 1000, 32)
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

_payload_b85 = %s
_s1 = base64.b85decode(_payload_b85)
_s2 = zlib.decompress(_s1)
_s3 = bz2.decompress(_s2)
_s4 = _auth_decrypt(_s3)
_s5 = zlib.decompress(_s4)
types.FunctionType(marshal.loads(_s5), globals())()
del _payload_b85, _s1, _s2, _s3, _s4, _s5
\"\"\" % (repr(enc_k), repr(mac_k), repr(enc_b85))"""

    content = content.replace(old_loader, new_loader)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_inner_loader_formatting(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_inner_loader_formatting(r"C:\Users\trong\Downloads\procheck.py")
print("Replaced inner_loader f-strings with %s formatting cleanly!")
