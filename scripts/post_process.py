import os
import sys
import re

def parse_time(time_str):
    time_str = time_str.strip()
    
    # 1. 支援標準冒號格式如 "00:04:27" 或 "04:27" 或 "01:04:27"，且容忍冒號前後的各種空格與前導零缺失 (例如 " 1 : 04 : 27 " 或 "0:4:27")
    pattern = r'^\s*(?:(\d+)\s*:\s*)?(\d+)\s*:\s*(\d+)\s*$'
    match = re.match(pattern, time_str)
    if match:
        try:
            h = int(match.group(1)) if match.group(1) else 0
            m = int(match.group(2))
            s = int(match.group(3))
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            else:
                return f"{m:02d}:{s:02d}"
        except ValueError:
            pass
            
    # 2. 支援原有的 "0m0s428ms", "1h2m3s4ms" 格式
    pattern_legacy = r'(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?\s*(?:(\d+)ms)?'
    match_legacy = re.match(pattern_legacy, time_str)
    if match_legacy and any(match_legacy.groups()):
        try:
            h = int(match_legacy.group(1)) if match_legacy.group(1) else 0
            m = int(match_legacy.group(2)) if match_legacy.group(2) else 0
            s = int(match_legacy.group(3)) if match_legacy.group(3) else 0
            
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            else:
                return f"{m:02d}:{s:02d}"
        except ValueError:
            pass
            
    # 如果都不匹配，直接返回原字串
    return time_str

def apply_glossary(text):
    # 根據 glossary.md 定義的規則進行術語替換
    text = re.sub(r'(?i)\bline\b', 'Line', text)
    text = re.sub(r'(?i)\bapp\b', 'App', text)
    text = re.sub(r'(?i)\bemail\b', 'Email', text)
    text = re.sub(r'(?i)\be-mail\b', 'Email', text)
    text = re.sub(r'(?i)\bok\b', 'OK', text)
    text = re.sub(r'(?i)\bgoogle\b', 'Google', text)
    text = re.sub(r'(?i)\byoutube\b', 'YouTube', text)
    text = re.sub(r'(?i)\bpowerpoint\b', 'PowerPoint', text)
    text = re.sub(r'(?i)\bppt\b', 'PowerPoint', text)
    text = re.sub(r'(?i)\bword\b', 'Word', text)
    text = re.sub(r'(?i)\bexcel\b', 'Excel', text)
    text = re.sub(r'(?i)\bteams\b', 'Teams', text)
    text = re.sub(r'(?i)\bzoom\b', 'Zoom', text)
    text = re.sub(r'(?i)\bpdf\b', 'PDF', text)
    text = re.sub(r'(?i)\be-mail\b', 'Email', text)
    text = re.sub(r'(?i)\bios\b', 'iOS', text)
    text = re.sub(r'(?i)\bandroid\b', 'Android', text)
    
    # 中文與台灣常用詞（直接替換）
    text = re.sub(r'賴', 'Line', text)
    text = re.sub(r'艾普|阿普', 'App', text)
    text = re.sub(r'歐[kK]|歐[ｋＫ]', 'OK', text)
    text = re.sub(r'估狗', 'Google', text)
    text = re.sub(r'油管', 'YouTube', text)
    text = re.sub(r'渥德', 'Word', text)
    text = re.sub(r'艾克索', 'Excel', text)
    text = re.sub(r'提姆', 'Teams', text)
    text = re.sub(r'祖姆', 'Zoom', text)
    text = re.sub(r'安卓', 'Android', text)
    
    return text

def main():
    if len(sys.argv) < 3:
        print("Usage: python post_process.py <input_raw_path> <output_transcript_path>")
        return
        
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    # 根據輸入檔名動態決定發言人對照表，避免污染其他檔案
    SPEAKER_MAP = {}
    if "討論案情" in input_path:
        SPEAKER_MAP = {
            'Speaker A': '張律師'
        }
    elif "全球人工智慧治理" in input_path:
        SPEAKER_MAP = {
            'Speaker A': '蔡律師',
            'Speaker B': 'David 教授',
            'Speaker C': '孫教授',
            'Speaker D': 'David 教授',
            'Speaker E': '蔡律師',
            'Speaker F': 'Claudia 律師',
            'Speaker G': '國祥律師'
        }
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} does not exist.")
        return
        
    parsed_lines = []
    # 時間戳記正則：[ {Timestamp} ] {Speaker}: {Content}
    line_pattern = r'^\[\s*([^\]]+)\s*\]\s*([^:]+):\s*(.*)$'
    
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            match = re.match(line_pattern, line)
            if match:
                raw_time = match.group(1)
                speaker = match.group(2).strip()
                content = match.group(3).strip()
                
                # 替換發言人真實姓名
                speaker = SPEAKER_MAP.get(speaker, speaker)
                
                formatted_time = parse_time(raw_time)
                
                # 術語修正
                content = apply_glossary(content)
                parsed_lines.append((formatted_time, speaker, content))
            else:
                # 若是不符合標準格式的行，與上一行合併
                if parsed_lines:
                    prev_time, prev_speaker, prev_content = parsed_lines[-1]
                    parsed_lines[-1] = (prev_time, prev_speaker, prev_content + " " + apply_glossary(line))
                else:
                    parsed_lines.append(("", "Unknown", apply_glossary(line)))
                    
    # 合併同一個 Speaker 連續發言的行（只有在沒有新時間戳記，或時間戳記相同時才合併）
    merged_lines = []
    for item in parsed_lines:
        if not merged_lines:
            merged_lines.append(item)
            continue
            
        prev_time, prev_speaker, prev_content = merged_lines[-1]
        curr_time, curr_speaker, curr_content = item
        
        # 只有發言人相同，且「新行沒有時間戳記」或「新舊時間戳記相同」時，才進行物理合併
        if prev_speaker == curr_speaker and (not curr_time or curr_time == prev_time):
            merged_lines[-1] = (prev_time, prev_speaker, prev_content + " " + curr_content)
        else:
            merged_lines.append(item)
            
    # 寫入最終輸出
    with open(output_path, "w", encoding="utf-8") as f:
        for time_str, speaker, content in merged_lines:
            if time_str:
                f.write(f"[{time_str}] {speaker}: {content}\n")
            else:
                f.write(f"{speaker}: {content}\n")
                
    print(f"Post-processing complete. Saved to {output_path}")

if __name__ == "__main__":
    main()
