# -*- coding: utf-8 -*-
"""
Native Payload Extraction Regression Suite (F-01 .. F-08 hardening)
===================================================================
Proves that the native loader cannot be unlocked offline the way the
2026-10-20 reverse-engineering report did (tier-1 PoC: read the AEAD key from
.rdata -> de-interleave -> ChaCha20-Poly1305 decrypt -> marshal.loads).

Checks implemented here:
  F-01  the AEAD key is NEVER part of the artifact (it is derived from the password)
  F-02  the marshal descramble seed is bound to the runtime key (no static seed)
  F-03  the API hash parameters are derived at runtime (no static literals)
  F-04  the CFF dispatcher state is stored under a runtime-only opaque mask
  F-05  the payload framing filler has no periodic structure
  F-07  no plaintext author banner / metadata in the image
  F-08  no plaintext payload-length constants in the image
Plus the functional contract: the artifact runs with the password and refuses to run without it.
"""

import os
import re
import struct
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import tr0ngx.packagers_native as pn

TEST_PASSWORD = "Tr0ngX-Regression-Pass!42"
TEST_SALT = bytes(range(16))

SRC = """import sys
print("TR0NGX_EXTRACT_PROBE_OK")
sys.exit(0)
"""


def _build(tmpdir, name="probe", password=TEST_PASSWORD, salt=TEST_SALT, stealth=True):
    out = os.path.join(tmpdir, f"{name}.exe")
    path = pn.package_native_exe(SRC, out, app_name=name, stealth_pe=stealth,
                                 password=password, salt=salt)
    assert os.path.isfile(path)
    return path


def _run(path, password=None, timeout=90):
    env = dict(os.environ)
    env.pop("TR0NGX_PASSWORD", None)
    if password is not None:
        env["TR0NGX_PASSWORD"] = password
    return subprocess.run([path], capture_output=True, text=True, timeout=timeout,
                          env=env, stdin=subprocess.DEVNULL)


# ---------------------------------------------------------------------------
# F-01 - the AEAD key must not exist in the artifact
# ---------------------------------------------------------------------------
def test_native_aead_key_is_not_embedded():
    """The key used by the native loader must be absent from the produced binary."""
    with tempfile.TemporaryDirectory(prefix="trx_extract_") as tmpdir:
        path = _build(tmpdir)
        with open(path, "rb") as fh:
            data = fh.read()

        key = pn.native_derive_key(TEST_PASSWORD, TEST_SALT, pn.native_kdf_id())
        assert len(key) == 32
        assert key not in data, "AEAD key leaked into the artifact - tier-1 extraction is possible again"

        # The key must not be recoverable through any trivial transform of embedded blobs either:
        # the derivation is a KDF over the password, so no XOR/rotation of image bytes yields it.
        for shift in (1, 8, 16, 32):
            rotated = key[shift:] + key[:shift]
            assert rotated not in data


def test_native_requires_password_and_unlocks_with_it():
    """The artifact must refuse to run without the password and run correctly with it."""
    with tempfile.TemporaryDirectory(prefix="trx_extract_") as tmpdir:
        path = _build(tmpdir)

        good = _run(path, password=TEST_PASSWORD)
        assert good.returncode == 0, good.stderr
        assert "TR0NGX_EXTRACT_PROBE_OK" in good.stdout

        missing = _run(path, password=None)
        assert missing.returncode != 0
        assert "TR0NGX_EXTRACT_PROBE_OK" not in missing.stdout

        wrong = _run(path, password="definitely-not-the-password")
        assert wrong.returncode != 0
        assert "TR0NGX_EXTRACT_PROBE_OK" not in wrong.stdout
        # a wrong password must not leak a distinguishable diagnostic
        assert "TR0NGX_EXTRACT_PROBE_OK" not in wrong.stderr


def test_native_without_password_is_integrity_only(capsys):
    """A password-less native build must still work, but it cannot provide confidentiality.

    The key then lives in the artifact (masked), so an analyst can recover the payload -
    that mode is explicitly labelled as integrity-only by the packager.
    """
    with tempfile.TemporaryDirectory(prefix="trx_extract_") as tmpdir:
        out = os.path.join(tmpdir, "nopass.exe")
        path = pn.package_native_exe(SRC, out, app_name="nopass", stealth_pe=False)
        assert os.path.isfile(path)

        warning = capsys.readouterr().out
        assert "integrity only" in warning.lower()

        run = _run(path, password=None)
        assert run.returncode == 0, run.stderr
        assert "TR0NGX_EXTRACT_PROBE_OK" in run.stdout


# ---------------------------------------------------------------------------
# F-02 / F-03 / F-04 / F-08 - static material must be gone
# ---------------------------------------------------------------------------
def test_native_source_has_no_static_key_or_hash_constants():
    """Locks the structural invariants of the generated C template."""
    src = pn.__file__
    with open(src, encoding="utf-8") as fh:
        text = fh.read()

    # F-01/F-02: the EDKD key schedule and the static marshal seed are gone
    assert "_trx_derive_key" not in text
    assert "_TRX_MARSHAL_SEED" not in text
    assert "_trx_seed_a" not in text
    assert "_trx_seed_b" not in text

    # F-03: the API hash parameters must be runtime derived, not baked in
    assert "_TRX_SEED = 0x" not in text
    assert "const uint32_t c1 = 0x" not in text

    # F-04: the dispatcher state must go through the opaque mask
    assert "_trx_cff_enc" in text and "_trx_cff_dec" in text

    # F-08: the payload sizes must be masked, not stored plainly
    assert "_TRX_COMPRESSED_PAYLOAD_LEN" not in text
    assert "_TRX_CT_LEN_MASKED" in text


def test_native_binary_has_no_plaintext_fingerprints():
    """F-07/F-08: no author banner, module name or hand-off string in cleartext."""
    with tempfile.TemporaryDirectory(prefix="trx_extract_") as tmpdir:
        path = _build(tmpdir)
        with open(path, "rb") as fh:
            data = fh.read()

        for needle in (b"Tr0ngX", b"t.me/TrongX", b"python312.dll", b"__main__\x00",
                       b"_auth_decrypt\x00", b"getpass", b"argon2id",
                       b"Native payload password", b"TRX_TVM_ENC_KEY_V3"):
            assert needle not in data, f"plaintext fingerprint in artifact: {needle!r}"


def test_native_binary_has_no_raw_payload_length_constants():
    """F-08: the payload sizes must not be recoverable from plainly stored dwords.

    The generator masks both sizes with a per-build value, so the artifact only carries the
    obfuscated form. This test locks that invariant on the generated C template.
    """
    with open(pn.__file__, encoding="utf-8") as fh:
        text = fh.read()

    assert "_TRX_CT_LEN_MASKED" in text and "_TRX_RAW_LEN_MASKED" in text
    # the plain constants must not reappear anywhere in the template
    assert "static const size_t _TRX_COMPRESSED_PAYLOAD_LEN" not in text
    assert "static const size_t _TRX_UNCOMPRESSED_PAYLOAD_LEN" not in text


# ---------------------------------------------------------------------------
# F-05 - the framing filler must not be periodic
# ---------------------------------------------------------------------------
def test_interleave_filler_has_no_periodic_structure():
    """The old implementation repeated a 64 byte pool - that made de-interleaving trivial."""
    ciphertext = os.urandom(8192)
    framed, parity = pn.interleave_low_entropy(ciphertext)

    assert len(framed) == len(ciphertext) * 2
    ct_lane = framed[parity::2]
    filler_lane = framed[1 - parity::2]
    assert ct_lane == ciphertext
    assert filler_lane != ct_lane[:len(filler_lane)]

    for period in (64, 256, 4096):
        matches = sum(1 for i in range(0, len(filler_lane) - period)
                      if filler_lane[i] == filler_lane[i + period])
        ratio = matches / float(len(filler_lane) - period)
        # random data matches with probability 1/256 (~0.4%), a periodic pool matches 100%
        assert ratio < 0.05, f"filler lane is periodic with period {period} (ratio {ratio:.3f})"


# ---------------------------------------------------------------------------
# pyd parity
# ---------------------------------------------------------------------------
def test_native_pyd_requires_password_when_requested():
    """A password protected .pyd must refuse to import without the secret."""
    with tempfile.TemporaryDirectory(prefix="trx_extract_") as tmpdir:
        out = os.path.join(tmpdir, "probe_mod.pyd")
        pn.package_native_pyd(SRC, out, module_name="probe_mod", stealth_pe=True,
                              password=TEST_PASSWORD, salt=TEST_SALT)
        runner = os.path.join(tmpdir, "runner.py")
        with open(runner, "w", encoding="utf-8") as fh:
            fh.write("import sys\nsys.path.insert(0, r'%s')\nimport probe_mod\n" % tmpdir)

        env = dict(os.environ)
        env["TR0NGX_PASSWORD"] = TEST_PASSWORD
        ok = subprocess.run([sys.executable, runner], capture_output=True, text=True,
                            timeout=90, env=env)
        assert ok.returncode == 0, ok.stderr
        assert "TR0NGX_EXTRACT_PROBE_OK" in ok.stdout

        env.pop("TR0NGX_PASSWORD", None)
        bad = subprocess.run([sys.executable, runner], capture_output=True, text=True,
                             timeout=90, env=env)
        assert bad.returncode != 0
        assert "TR0NGX_EXTRACT_PROBE_OK" not in bad.stdout
