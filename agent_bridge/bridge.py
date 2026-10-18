# -*- coding: utf-8 -*-
"""
Tr0ngX Autonomous Web AI Bridge (AGY Simulator)
Thiết kế riêng cho dự án Tr0ngX-Ultimate-AST-Obfuscator.

Chức năng:
1. Nhận JSON từ Web AI (Claude 3.7 / ChatGPT / DeepSeek / o3).
2. Tự động parse và thực thi hành động: view_file, replace_file_content, write_to_file, run_command, syntax_check, finish.
3. Đóng gói kết quả thành JSON Observation và tự động đưa vào Clipboard hoặc in ra màn hình để dán lại vào Web AI.
"""

import os
import sys
import json
import time
import subprocess
import py_compile
from pathlib import Path

# Cấu hình môi trường mặc định của dự án Tr0ngX
REPO_ROOT = Path(r"C:\Users\trong\AppData\Local\Temp\opencode\Tr0ngX-Ultimate-AST-Obfuscator").resolve()
PYTHON_BIN = r"C:\Python312\python.exe"
GIT_BIN = r"C:\Users\trong\tools\git\bin\git.exe"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def _resolve_path(rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.resolve()

def _copy_to_clipboard(text: str) -> bool:
    try:
        proc = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
        proc.communicate(text.encode('utf-8'))
        return proc.returncode == 0
    except Exception:
        return False

def _get_clipboard() -> str:
    try:
        res = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            text=True, encoding="utf-8", errors="ignore"
        )
        return res.strip()
    except Exception:
        return ""

# ==========================================
# TOOL EXECUTORS (AGY COMPATIBLE)
# ==========================================

def tool_view_file(params: dict) -> dict:
    raw_path = params.get("file_path", "").strip()
    if not raw_path or raw_path in (".", "/", "\\"):
        file_path = REPO_ROOT
    else:
        file_path = _resolve_path(raw_path)

    if not file_path.exists():
        return {
            "status": "error",
            "error": f"Đường dẫn không tồn tại: {file_path}. Gợi ý: Hãy dùng đường dẫn tương đối (ví dụ 'tr0ngx/vm.py', 'tr0ngx/pipeline.py', 'main.py')."
        }

    if file_path.is_dir():
        items = []
        for item in sorted(file_path.iterdir()):
            if item.name.startswith((".", "__pycache__")):
                continue
            suffix = "/" if item.is_dir() else ""
            items.append(f"{item.name}{suffix}")
        return {
            "status": "success",
            "type": "directory_listing",
            "directory": str(file_path),
            "entries": items,
            "message": f"Đây là một thư mục, không phải tệp. Hãy gọi view_file vào tệp cụ thể bên trong (ví dụ: 'tr0ngx/pipeline.py')."
        }
    
    start_line = params.get("start_line", 1)
    end_line = params.get("end_line")
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        if start_line < 1: start_line = 1
        if end_line is None or end_line > total_lines:
            end_line = total_lines
            
        selected_lines = lines[start_line - 1 : end_line]
        numbered_lines = [f"{start_line + i:4}: {line}" for i, line in enumerate(selected_lines)]
        content_view = "".join(numbered_lines)
        
        return {
            "status": "success",
            "file": str(file_path),
            "total_lines": total_lines,
            "range": [start_line, end_line],
            "content": content_view
        }
    except Exception as e:
        return {"status": "error", "error": f"Lỗi đọc file: {str(e)}"}

def tool_replace_file_content(params: dict) -> dict:
    file_path = _resolve_path(params.get("file_path", ""))
    target_content = params.get("target_content")
    replacement_content = params.get("replacement_content")
    
    if not file_path.is_file():
        return {"status": "error", "error": f"Tệp không tồn tại: {file_path}"}
    if target_content is None or replacement_content is None:
        return {"status": "error", "error": "Thiếu target_content hoặc replacement_content"}
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            full_text = f.read()
            
        occurrences = full_text.count(target_content)
        if occurrences == 0:
            return {"status": "error", "error": "Không tìm thấy target_content trong file. Hãy dùng view_file để kiểm tra lại chính xác khoảng trắng và dòng."}
        if occurrences > 1:
            return {"status": "error", "error": f"target_content xuất hiện {occurrences} lần trong file (cần duy nhất 1 lần để tránh sửa nhầm)."}
            
        new_text = full_text.replace(target_content, replacement_content, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_text)
            
        # Tự động syntax check nếu là file Python
        syntax_status = "ok"
        if file_path.suffix == ".py":
            try:
                py_compile.compile(str(file_path), doraise=True)
            except py_compile.PyCompileError as pe:
                syntax_status = f"SYNTAX_ERROR: {pe.msg}"
                
        return {
            "status": "success",
            "file": str(file_path),
            "syntax_check": syntax_status,
            "message": "Đã thay thế nội dung thành công."
        }
    except Exception as e:
        return {"status": "error", "error": f"Lỗi chỉnh sửa file: {str(e)}"}

def tool_write_to_file(params: dict) -> dict:
    file_path = _resolve_path(params.get("file_path", ""))
    content = params.get("content", "")
    
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        syntax_status = "ok"
        if file_path.suffix == ".py":
            try:
                py_compile.compile(str(file_path), doraise=True)
            except py_compile.PyCompileError as pe:
                syntax_status = f"SYNTAX_ERROR: {pe.msg}"
                
        return {
            "status": "success",
            "file": str(file_path),
            "bytes_written": len(content.encode("utf-8")),
            "syntax_check": syntax_status
        }
    except Exception as e:
        return {"status": "error", "error": f"Lỗi ghi file: {str(e)}"}

def tool_run_command(params: dict) -> dict:
    cmd = params.get("command", "")
    if not cmd:
        return {"status": "error", "error": "Lệnh rỗng."}
        
    cwd = params.get("cwd")
    exec_cwd = _resolve_path(cwd) if cwd else REPO_ROOT
    timeout = params.get("timeout", 180)
    
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            cwd=str(exec_cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )
        return {
            "status": "success",
            "command": cmd,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-15000:] if len(proc.stdout) > 15000 else proc.stdout,
            "stderr": proc.stderr[-5000:] if len(proc.stderr) > 5000 else proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"Lệnh vượt quá thời gian chờ ({timeout}s)."}
    except Exception as e:
        return {"status": "error", "error": f"Lỗi thực thi lệnh: {str(e)}"}

def tool_syntax_check(params: dict) -> dict:
    files = params.get("files", [])
    if isinstance(files, str):
        files = [files]
        
    results = {}
    all_ok = True
    for f in files:
        fp = _resolve_path(f)
        if not fp.is_file():
            results[f] = "FILE_NOT_FOUND"
            all_ok = False
            continue
        try:
            py_compile.compile(str(fp), doraise=True)
            results[f] = "OK"
        except py_compile.PyCompileError as pe:
            results[f] = f"ERROR: {pe.msg}"
            all_ok = False
            
    return {
        "status": "success" if all_ok else "failed",
        "results": results
    }

def tool_finish(params: dict) -> dict:
    msg = params.get("message", "Nhiệm vụ đã hoàn tất.")
    return {
        "status": "completed",
        "final_message": msg
    }

TOOLS = {
    "view_file": tool_view_file,
    "replace_file_content": tool_replace_file_content,
    "write_to_file": tool_write_to_file,
    "run_command": tool_run_command,
    "syntax_check": tool_syntax_check,
    "finish": tool_finish
}

# ==========================================
# DISPATCHER & CLI INTERFACE
# ==========================================

def execute_payload(raw_json_str: str) -> dict:
    clean_str = raw_json_str.strip()
    if clean_str.startswith("```json"):
        clean_str = clean_str[7:]
    if clean_str.startswith("```"):
        clean_str = clean_str[3:]
    if clean_str.endswith("```"):
        clean_str = clean_str[:-3]
    clean_str = clean_str.strip()
    
    try:
        payload = json.loads(clean_str)
    except Exception as e:
        return {
            "observation_type": "error",
            "error": f"JSON không hợp lệ: {str(e)}. Hãy đảm bảo output chỉ gồm JSON thuần."
        }
        
    thought = payload.get("thought", "")
    action = payload.get("action", "")
    params = payload.get("params", {})
    
    print(f"\n[AI THOUGHT]: {thought}")
    print(f"[ACTION]: {action} | [PARAMS]: {list(params.keys())}")
    
    executor = TOOLS.get(action)
    if not executor:
        return {
            "observation_type": "error",
            "error": f"Tool '{action}' không tồn tại. Các tool hợp lệ: {list(TOOLS.keys())}"
        }
        
    start_t = time.time()
    result = executor(params)
    elapsed = round(time.time() - start_t, 3)
    
    observation = {
        "observation_type": "tool_result",
        "action": action,
        "elapsed_seconds": elapsed,
        "result": result
    }
    return observation

def main():
    print("=" * 70)
    print("  TR0NGX AUTONOMOUS WEB AI BRIDGE (AGY LOCAL SIMULATOR)")
    print(f"  Repo Root: {REPO_ROOT}")
    print("=" * 70)
    print("\nChọn chế độ hoạt động:")
    print("  [1] Auto Clipboard Watch (Tự động tóm JSON mỗi khi bạn copy từ Web AI)")
    print("  [2] Nhập trực tiếp qua console / dán thủ công")
    choice = input("\nLựa chọn của bạn (mặc định 1): ").strip() or "1"
    
    if choice == "1":
        print("\n[*] Đang lắng nghe Clipboard... Hãy copy JSON phản hồi từ Web AI.")
        last_clip = ""
        while True:
            time.sleep(1)
            current_clip = _get_clipboard().strip()
            if current_clip and current_clip != last_clip and ("\"action\"" in current_clip or "action:" in current_clip):
                last_clip = current_clip
                print("\n[+] Phát hiện JSON mới từ Clipboard! Đang xử lý...")
                obs = execute_payload(current_clip)
                obs_json = json.dumps(obs, indent=2, ensure_ascii=False)
                _copy_to_clipboard(obs_json)
                print("\n" + "="*50)
                print("[OBSERVATION ĐÃ COPY VÀO CLIPBOARD - BẤM CTRL+V DÁN VÀO WEB AI]:")
                print(obs_json[:500] + ("..." if len(obs_json) > 500 else ""))
                print("="*50)
                if obs.get("result", {}).get("status") == "completed":
                    print("\n[★] NHIỆM VỤ ĐÃ HOÀN TẤT BỞI AI!")
                    break
                print("\n[*] Đang chờ lượt tiếp theo từ Clipboard...")
    else:
        while True:
            print("\n" + "-"*50)
            print("Dán chuỗi JSON từ Web AI vào đây (tự động xử lý ngay khi nhận đủ ngoặc, hoặc gõ 'exit'):")
            lines = []
            open_braces = 0
            has_started = False
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                stripped = line.strip()
                if stripped.lower() == "exit":
                    return
                if stripped == "EOF":
                    break
                lines.append(line)
                open_braces += line.count('{') - line.count('}')
                if '{' in line:
                    has_started = True
                if has_started and open_braces <= 0 and lines:
                    break
            raw_input = "\n".join(lines).strip()
            if not raw_input:
                continue
                
            obs = execute_payload(raw_input)
            obs_json = json.dumps(obs, indent=2, ensure_ascii=False)
            _copy_to_clipboard(obs_json)
            print("\n[OBSERVATION ĐÃ COPY VÀO CLIPBOARD]:\n", obs_json)
            if obs.get("result", {}).get("status") == "completed":
                print("\n[★] NHIỆM VỤ ĐÃ HOÀN TẤT BỞI AI!")
                break

if __name__ == "__main__":
    main()
