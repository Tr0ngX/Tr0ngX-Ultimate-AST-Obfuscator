"""
Test Suite 09: Anti-VM & Advanced Anti-Debug Matrix Verification
Tests --antivm and enhanced --antidebug vectors across multiple modes.
"""
import os
import sys
import subprocess
import tempfile

def test_antivm_generation_and_execution():
    """Verify that --antivm generates valid code that executes cleanly on standard hardware."""
    sample_code = """
def calculate(n):
    return sum(i * 2 for i in range(n))

val = calculate(10)
print(f"CALC_RESULT:{val}")
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "source.py")
        out_path = os.path.join(tmpdir, "obf_antivm.py")
        
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(sample_code)
            
        # Obfuscate with --antivm y and --antidebug y
        cmd = [
            sys.executable, "tr0ngx_obfuscator.py",
            "-i", src_path,
            "-o", out_path,
            "-m", "2",
            "--antivm", "y",
            "--antidebug", "y",
            "--force-py", "off",
            "--no-art"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert res.returncode == 0, f"Obfuscation with --antivm failed: {res.stderr}"
        assert os.path.exists(out_path), "Output file was not created"
        
        # Execute obfuscated output
        run_res = subprocess.run([sys.executable, out_path], capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert run_res.returncode == 0, f"Execution failed: {run_res.stderr}"
        assert "CALC_RESULT:90" in run_res.stdout, f"Output mismatch: {run_res.stdout}"
        print("  [PASS] Anti-VM + Anti-Debug Mode 2 execution verified")

def test_antivm_with_double_compile():
    """Verify --antivm inside full double-compile pipeline."""
    sample_code = """
x = [i**2 for i in range(5)]
print(f"SQUARES:{x}")
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "source.py")
        out_path = os.path.join(tmpdir, "obf_antivm_dc.py")
        
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(sample_code)
            
        cmd = [
            sys.executable, "tr0ngx_obfuscator.py",
            "-i", src_path,
            "-o", out_path,
            "-m", "2",
            "--compile", "y",
            "--velimatix", "y",
            "--veli-level", "2",
            "--double-compile", "y",
            "--antivm", "y",
            "--antidebug", "y",
            "--force-py", "off",
            "--no-art"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert res.returncode == 0, f"Obfuscation failed: {res.stderr}"
        
        run_res = subprocess.run([sys.executable, out_path], capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert run_res.returncode == 0, f"Execution failed: {run_res.stderr}"
        assert "SQUARES:[0, 1, 4, 9, 16]" in run_res.stdout, f"Output mismatch: {run_res.stdout}"
        print("  [PASS] Anti-VM + Double Compile verified")

if __name__ == "__main__":
    print("[TEST 09] Running Anti-VM & Anti-Debug Test Suite...")
    test_antivm_generation_and_execution()
    test_antivm_with_double_compile()
    print("[TEST 09] ALL ANTI-VM & ANTI-DEBUG TESTS PASSED!")
