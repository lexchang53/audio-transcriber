import os
import sys
import subprocess

def convert_to_audio(input_path, output_path):
    print(f"[audio_prep] Extracting and compressing {input_path} to {output_path} (32 kbps OGG)...")
    if not os.path.exists(input_path):
        print(f"[audio_prep] Error: Input file {input_path} does not exist.")
        return False
        
    # 統一使用 libopus 32 kbps 單聲道 16000 Hz 壓縮輸出為 OGG 格式，並忽略影像 (-vn)
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "libopus",
        "-b:a", "32k",
        output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(f"[audio_prep] Success! Output saved to {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[audio_prep] Error: FFmpeg execution failed. Command: {' '.join(cmd)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python audio_prep.py <input_media_path> <output_ogg_path>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    success = convert_to_audio(input_file, output_file)
    if not success:
        sys.exit(1)

