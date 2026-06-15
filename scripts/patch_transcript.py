import os
import sys
import re
import time
import argparse
import subprocess
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

def parse_time_to_seconds(time_str):
    time_str = time_str.strip()
    # 支援 HH:MM:SS 或 MM:SS
    parts = list(map(int, time_str.split(':')))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0

def seconds_to_time_str(total_seconds):
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def upload_file_resumable(api_key, file_path, display_name):
    file_size = os.path.getsize(file_path)
    mime_type = "audio/ogg"
    
    init_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json"
    }
    metadata = {
        "file": {
            "displayName": display_name
        }
    }
    
    res = requests.post(init_url, headers=headers, json=metadata, timeout=60)
    res.raise_for_status()
    
    upload_url = res.headers.get("X-Goog-Upload-URL")
    if not upload_url:
        raise Exception("Failed to get X-Goog-Upload-URL.")
        
    upload_headers = {
        "X-Goog-Upload-Offset": "0",
        "X-Goog-Upload-Command": "upload, finalize",
        "Content-Length": str(file_size)
    }
    
    with open(file_path, "rb") as f:
        upload_res = requests.put(upload_url, headers=upload_headers, data=f, timeout=600)
    upload_res.raise_for_status()
    
    file_info = upload_res.json()
    remote_name = file_info.get("file", {}).get("name")
    return remote_name

def main():
    parser = argparse.ArgumentParser(description="語音轉錄局部精準修補工具 (Hot-Patching Tool)")
    parser.add_argument("--audio", required=True, help="原始音檔路徑 (例如: 全球人工智慧治理.mp3)")
    parser.add_argument("--raw-md", required=True, help="要修補的原始轉錄備份 raw.md 路徑")
    parser.add_argument("--start", required=True, help="開始修補時間 (格式如 01:19:00 或 79:00)")
    parser.add_argument("--end", help="結束修補時間 (格式如 01:21:38，若不提供則截取至音檔結束)")
    parser.add_argument("--replace-to-end", action="store_true", help="是否刪除並替換開始時間之後的所有內容至檔案結尾")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.audio):
        print(f"Error: 找不到音檔 {args.audio}")
        sys.exit(1)
        
    if not os.path.exists(args.raw_md):
        print(f"Error: 找不到轉錄檔 {args.raw_md}")
        sys.exit(1)
        
    start_sec = parse_time_to_seconds(args.start)
    end_sec = parse_time_to_seconds(args.end) if args.end else None
    
    temp_ogg = "temp_patch_segment.ogg"
    
    # 1. 執行 ffmpeg 截取局部音訊
    print(f"[1/5] 正在截取音訊自 {args.start} ...")
    ffmpeg_cmd = ["ffmpeg", "-y", "-ss", args.start]
    if args.end:
        ffmpeg_cmd += ["-to", args.end]
    ffmpeg_cmd += ["-i", args.audio, "-ac", 1, "-ar", 16000, "-ab", 32k, "-c:a", "libopus", temp_ogg]
    
    # 執行 ffmpeg 轉碼
    subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"局部音訊已儲存至 {temp_ogg}")
    
    # 2. 載入金鑰與配置
    env_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(env_dir, ".env"))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: 找不到 GEMINI_API_KEY。")
        if os.path.exists(temp_ogg): os.remove(temp_ogg)
        sys.exit(1)
        
    preferred_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    models_to_try = [preferred_model, "gemini-2.5-flash", "gemini-1.5-flash"]
    
    client = genai.Client(api_key=api_key)
    
    # 3. 上傳與轉錄
    print(f"[2/5] 正在上傳至 Gemini API 轉錄...")
    remote_name = None
    response_text = None
    try:
        remote_name = upload_file_resumable(api_key, temp_ogg, "temp_patch_segment.ogg")
        
        while True:
            file_info = client.files.get(name=remote_name)
            if file_info.state.name == "ACTIVE":
                break
            time.sleep(3)
            
        prompt = """You are a professional audio/video transcriber. Listen carefully to the audio/video and complete the following tasks:

1. Transcribe all spoken content faithfully without omitting anything.
2. Transcribe in the original spoken language; do not translate.
3. Distinguish different speakers and assign a label to each (e.g., Speaker A, Speaker B, Speaker C).
4. Mark the exact start timestamp for each utterance in HH:MM:SS format (relative to the start of this audio clip, starting from 00:00:00).
5. Format strictly as: {Timestamp} {Speaker}: {Content}
6. CRITICAL: Avoid looping, repetition, or stuttering.

Start outputting the transcript directly without any preamble."""

        active_file = client.files.get(name=remote_name)
        
        # 嘗試模型與重試
        for model in models_to_try:
            print(f"嘗試使用模型: {model}...")
            thinking_config = None
            if "2.5" in model:
                try:
                    thinking_config = types.ThinkingConfig(thinking_budget=0)
                except:
                    pass
                    
            config = types.GenerateContentConfig(
                max_output_tokens=65536,
                temperature=0.0,
                thinking_config=thinking_config,
                system_instruction="You are a professional transcriber. Never loop or repeat the same phrase endlessly."
            )
            
            # 重試 3 次
            success = False
            for attempt in range(3):
                try:
                    res = client.models.generate_content(
                        model=model,
                        contents=[active_file, prompt],
                        config=config
                    )
                    response_text = res.text
                    success = True
                    break
                except Exception as e:
                    print(f"重試 {attempt+1}/3 失敗: {e}")
                    time.sleep(5)
            
            if success and response_text:
                print(f"模型 {model} 轉錄成功！")
                break
                
        if not response_text:
            raise Exception("所有備用模型均轉錄失敗。")
            
    except Exception as e:
        print(f"轉錄過程中發生錯誤: {e}")
        if os.path.exists(temp_ogg): os.remove(temp_ogg)
        if remote_name: client.files.delete(name=remote_name)
        sys.exit(1)
    finally:
        if remote_name:
            try: client.files.delete(name=remote_name)
            except: pass
        if os.path.exists(temp_ogg):
            try: os.remove(temp_ogg)
            except: pass
            
    # 4. 解析轉錄結果並套用時間戳偏移補正
    print(f"[3/5] 正在處理時間戳偏移補正 (加上 {args.start} 即 {start_sec} 秒)...")
    line_pattern = r'^\[\s*([^\]]+)\s*\]\s*([^:]+):\s*(.*)$'
    patched_lines = []
    
    for raw_line in response_text.strip().split('\n'):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        match = re.match(line_pattern, raw_line)
        if match:
            raw_time = match.group(1).strip()
            speaker = match.group(2).strip()
            content = match.group(3).strip()
            
            # 對於雙語講座結尾，特別進行 Speaker 標籤的映射微調（僅適用本講座，通用場景可直接使用原始標籤）
            # patch 的 Speaker B ➔ 國祥律師 (大檔 Speaker G)
            # patch 的 Speaker C ➔ 蔡律師 (大檔 Speaker E)
            if "全球人工智慧治理" in args.raw_md:
                if speaker == "Speaker B":
                    speaker = "Speaker G"
                elif speaker == "Speaker C":
                    speaker = "Speaker E"
                elif speaker == "Speaker A":
                    speaker = "Speaker D"
            
            secs = parse_time_to_seconds(raw_time)
            new_secs = secs + start_sec
            new_time_str = seconds_to_time_str(new_secs)
            patched_lines.append(f"[ {new_time_str} ] {speaker}: {content}\n")
        else:
            patched_lines.append(raw_line + "\n")
            
    # 5. 修補 raw.md 檔案
    print(f"[4/5] 正在套用修補至 {args.raw_md} ...")
    with open(args.raw_md, "r", encoding="utf-8") as f:
        original_lines = f.readlines()
        
    final_lines = []
    has_replaced = False
    
    for line in original_lines:
        line_strip = line.strip()
        match = re.match(line_pattern, line_strip)
        if match:
            raw_time = match.group(1).strip()
            secs = parse_time_to_seconds(raw_time)
            
            # 比對秒數
            if args.replace_to_end or (end_sec is None):
                # 刪除所有 >= start_sec 的行
                if secs >= start_sec:
                    continue
            else:
                # 刪除 [start_sec, end_sec] 範圍內的行
                if start_sec <= secs <= end_sec:
                    continue
        
        final_lines.append(line)
        
    # 將 patch 追加或併入
    final_lines.extend(patched_lines)
    
    with open(args.raw_md, "w", encoding="utf-8") as f:
        f.writelines(final_lines)
        
    print(f"原始轉錄備份 {args.raw_md} 修補完成。新行數: {len(final_lines)}")
    
    # 6. 自動調用後處理更新 transcript.md
    print(f"[5/5] 正在重新執行後處理...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    post_process_script = os.path.join(script_dir, "post_process.py")
    
    output_transcript = args.raw_md.replace("-raw.md", "-transcript.md")
    
    if os.path.exists(post_process_script):
        subprocess.run([sys.executable, post_process_script, args.raw_md, output_transcript], check=True)
        print(f"修補後的格式化逐字稿已更新存檔至 {output_transcript}。")
    else:
        print("Warning: 找不到 post_process.py 腳本，未能重新渲染格式化檔。")

if __name__ == "__main__":
    main()
