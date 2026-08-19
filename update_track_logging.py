import os, sys

def update_track(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    old_fn = """def _track_debug_stage(name: str, duration_sec: float, initial_size: int, final_size: int, details: dict = None):
    _DEBUG_MAP["stages"].append({
        "stage": name,
        "duration_seconds": round(duration_sec, 4),
        "initial_size_bytes": initial_size,
        "final_size_bytes": final_size,
        "delta_bytes": final_size - initial_size,
        "details": details or {}
    })"""

    new_fn = """def _track_debug_stage(name: str, duration_sec: float, initial_size: int, final_size: int, details: dict = None):
    delta = final_size - initial_size
    delta_str = f"+{delta:,} B" if delta >= 0 else f"-{abs(delta):,} B"
    _log_debug(f"Completed ({duration_sec:.4f}s, size: {initial_size:,} -> {final_size:,} B [{delta_str}])", stage=name, duration=duration_sec)
    _DEBUG_MAP["stages"].append({
        "stage": name,
        "duration_seconds": round(duration_sec, 4),
        "initial_size_bytes": initial_size,
        "final_size_bytes": final_size,
        "delta_bytes": delta,
        "details": details or {}
    })"""

    content = content.replace(old_fn, new_fn)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

update_track(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
update_track(r"C:\Users\trong\Downloads\procheck.py")
print("Updated _track_debug_stage with real-time stage logging!")
