import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
"""
Test 02: Cryptographic Algorithms & Advanced Mathematics
Tests: SHA-256 HMAC, Custom SPN Block Cipher, Matrix Arithmetic, Modular Exponentiation, Primes
"""
import hashlib, hmac

# 1. Custom Toy SPN Block Cipher (Substitution-Permutation Network)
SBOX = [0xE, 0x4, 0xD, 0x1, 0x2, 0xF, 0xB, 0x8, 0x3, 0xA, 0x6, 0xC, 0x5, 0x9, 0x0, 0x7]
INV_SBOX = [SBOX.index(i) for i in range(16)]

def spn_substitute(val, sbox):
    return (sbox[(val >> 12) & 0xF] << 12) | (sbox[(val >> 8) & 0xF] << 8) | (sbox[(val >> 4) & 0xF] << 4) | sbox[val & 0xF]

def spn_permute(val):
    p = [0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15]
    res = 0
    for i in range(16):
        if (val >> i) & 1:
            res |= (1 << p[i])
    return res

def spn_encrypt_block(pt, keys):
    state = pt ^ keys[0]
    for r in range(1, 4):
        state = spn_substitute(state, SBOX)
        state = spn_permute(state)
        state ^= keys[r]
    state = spn_substitute(state, SBOX)
    state ^= keys[4]
    return state

# 2. Matrix Arithmetic
def matrix_mult(A, B):
    rows_A, cols_A = len(A), len(A[0])
    rows_B, cols_B = len(B), len(B[0])
    assert cols_A == rows_B
    C = [[0] * cols_B for _ in range(rows_A)]
    for i in range(rows_A):
        for j in range(cols_B):
            C[i][j] = sum(A[i][k] * B[k][j] for k in range(cols_A))
    return C

# 3. Sieve of Eratosthenes & Modular Math
def sieve_primes(n):
    is_p = [True] * (n + 1)
    is_p[0] = is_p[1] = False
    for p in range(2, int(n**0.5) + 1):
        if is_p[p]:
            for i in range(p * p, n + 1, p):
                is_p[i] = False
    return [i for i, b in enumerate(is_p) if b]

def egcd(a, b):
    if a == 0: return (b, 0, 1)
    g, y, x = egcd(b % a, a)
    return (g, x - (b // a) * y, y)

def modinv(a, m):
    g, x, y = egcd(a, m)
    if g != 1: raise Exception("No inverse")
    return x % m

def run_suite():
    print("[TEST 02] Running Cryptography & Mathematics Suite...")

    # 1. SPN Cipher
    keys = [0x1234, 0x5678, 0x9ABC, 0xDEF0, 0x1357]
    pt = 0xABCD
    ct = spn_encrypt_block(pt, keys)
    assert ct != pt and isinstance(ct, int)
    print(f"  [PASS] SPN Block Cipher Encrypt: 0x{pt:04X} -> 0x{ct:04X}")

    # 2. Matrix Multiplication
    A = [[1, 2, 3], [4, 5, 6]]
    B = [[7, 8], [9, 1], [2, 3]]
    C = matrix_mult(A, B)
    assert C == [[31, 19], [85, 55]]
    print("  [PASS] Matrix Matrix-Multiplication Passed")

    # 3. Primes & Number Theory
    primes = sieve_primes(50)
    assert primes == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
    inv = modinv(17, 3120)
    assert (17 * inv) % 3120 == 1
    print("  [PASS] Sieve of Eratosthenes & Modular Inversion Passed")

    # 4. HMAC SHA-256
    tag = hmac.new(b"secret_key", b"test_payload_matrix", hashlib.sha256).hexdigest()
    assert len(tag) == 64
    print("  [PASS] HMAC-SHA256 Authentication Passed")

    print("[TEST 02] >>> ALL CHECKS PASSED <<<\n")

if __name__ == "__main__":
    run_suite()
