# Audio Transcriber

[English](#english) | [繁體中文](#繁體中文)

---

## English

### Overview
This skill guides the AI Agent to read an audio or video file (such as .mp3, .wav, .m4a, .mp4, etc.) and transcribe it into a verbatim transcript using its multimodal capabilities or external APIs. It utilizes a dual-engine architecture to cover different use cases.

#### 1. Gemini API Engine (Default)
- **Why use it?**: It leverages Gemini's native multimodal audio understanding. It is incredibly fast, supports extremely long audio/video (up to 22 hours) without the need for manual chunking, and provides native multi-language transcription without translation errors.
- **Cost**: You can use the **Free Tier**, which is more than enough for daily transcription needs. *Note: If you want to prevent Google from using your audio data and transcripts for model training, you must provide a paid-tier (pay-as-you-go) Gemini API Key.*
- **Get an API Key**: Apply for an API key at [Google AI Studio](https://aistudio.google.com/).

#### 2. AssemblyAI API Engine
- **Why use it?**: While Gemini is great for general transcription, AssemblyAI specializes in **High-Precision Speaker Diarization**. If you are transcribing a multi-person meeting (3+ people) and need the AI to perfectly distinguish who said what, AssemblyAI is the industry standard.
- **Cost**: AssemblyAI offers a **$50 starting free credit** for newly registered accounts. You can use this credit across multiple transcriptions until the $50 runs out (enough to process hundreds of hours of audio). No credit card is required. (Note: This is a finite starter pool, not a recurring monthly free tier).
- **Get an API Key**: Apply for an API key at [AssemblyAI](https://www.assemblyai.com/).

### Auto-Compression Mechanism
When an audio file is larger than 20MB, the skill automatically uses FFmpeg to compress it into a **32kbps `.ogg` (Opus)** file before transcription. 
**Why do we do this?** 
- **Speed & Stability**: It drastically reduces the file size, making API uploads much faster and significantly lowering the risk of network timeouts.
- **Quality Retention**: The 32kbps Opus format is highly optimized for human speech. It ensures a tiny file footprint without sacrificing the phonetic details required for accurate transcription.

### Prerequisites
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) (for optional audio compression)
- API keys: At least one of `GEMINI_API_KEY` or `ASSEMBLYAI_API_KEY`.

### Installation
1. **Install FFmpeg**:
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
2. **Install Python dependencies**:
   ```bash
   pip install google-genai assemblyai python-dotenv
   ```

### Configuration
1. Copy `.env.example` to a new file named `.env` in the skill's directory or your workspace root.
2. Fill in the required API keys.
3. (Optional) Set `GEMINI_MODEL` if you want to use a specific model version (default is `gemini-2.5-flash`).

### Usage
To trigger the skill, simply **@ mention** an audio or video file (e.g., @meeting_audio.mp3 or @meeting_video.mp4) in the chat and include a transcription keyword.
**Examples**:
- *"Please transcribe this audio file."* (Defaults to Gemini)
- *"Please transcribe this video file."*
- *"Help me generate a transcript for this meeting."*
- *"This is a multi-person meeting, please transcribe it."* (Triggers AssemblyAI)

> **Note**: If you request a multi-person meeting but only have the `GEMINI_API_KEY` configured, the skill will automatically fall back to using Gemini. Gemini will still attempt to distinguish speakers, though its voice recognition may be slightly less precise than AssemblyAI.
> *Even for meetings with 3+ people, you can still force the use of Gemini by explicitly requesting it in your prompt, or simply by leaving the `ASSEMBLYAI_API_KEY` blank in your `.env` file.*

---

## 繁體中文

### 概述
此技能指引 AI Agent 讀取對話中的音訊檔（如 .mp3）或影音檔（影片，如 .mp4），並將其轉錄為逐字稿。本技能採用雙引擎架構，以滿足不同的使用情境。

#### 1. Gemini API 引擎（預設）
- **為什麼使用它？**：利用 Gemini 原生的多模態音訊理解能力。速度極快，支援超長音訊/影音（高達 22 小時）且無需手動分段，並原生支援多語言轉錄而不會產生錯誤翻譯。
- **費用**：您可以使用 **免費版 (Free Tier)** 的 API，其額度對於日常轉錄需求已綽綽有餘。*註：如果您不希望您的語音與轉錄數據被 Google 用於模型訓練用途，請提供付費版 (Pay-as-you-go) 的 Gemini API Key，以保障數據隱私。*
- **申請金鑰**：請前往 [Google AI Studio](https://aistudio.google.com/) 申請 API Key。

#### 2. AssemblyAI API 引擎
- **為什麼使用它？**：雖然 Gemini 非常適合一般轉錄，但 AssemblyAI 專精於**高精度說話者分離 (Speaker Diarization)**。如果您要轉錄的是 3 人以上的多人會議，且需要 AI 精準分辨每一句話是誰說的，AssemblyAI 是業界的首選。
- **費用**：AssemblyAI 針對新註冊用戶**贈送 50 美元的初始免費額度 (Free Credit)**。這筆額度可以分次使用於多個音訊檔案，直到 50 美元扣完為止（大約可免費轉錄數百小時的音訊），且不需綁定信用卡。（註：此為開戶贈送的總額度，無每月免費重置機制）。
- **申請金鑰**：請前往 [AssemblyAI 官網](https://www.assemblyai.com/) 註冊並申請 API Key。

### 自動音訊壓縮機制
當音訊檔案大於 20MB 時，技能會自動使用 FFmpeg 將其壓縮為 **32kbps 的 `.ogg` (Opus 編碼)** 檔案後再進行轉錄。
**為什麼要這樣做？**
- **速度與穩定性**：大幅縮小檔案體積，不僅能讓上傳速度翻倍，還能極大程度地避免 API 傳輸網路超時（Timeout）或斷線的問題。
- **保留語音細節**：32kbps Opus 格式專為人類語音最佳化，能在極致壓縮體積的同時，完美保留轉錄所需的聲學特徵，完全不會影響語音辨識的精準度。

### 環境需求
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html)（用於音訊壓縮）
- API 金鑰：至少需要 `GEMINI_API_KEY` 或 `ASSEMBLYAI_API_KEY` 其中之一。

### 安裝
1. **安裝 FFmpeg**：
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
2. **安裝 Python 依賴套件**：
   ```bash
   pip install google-genai assemblyai python-dotenv
   ```

### 設定
1. 將 `.env.example` 複製為 `.env`，可放置於技能目錄或您的工作區根目錄。
2. 填入所需的 API 金鑰。
3. （可選）如果您想使用特定模型版本，可設定 `GEMINI_MODEL`（預設為 `gemini-2.5-flash`）。

### 使用方式
要觸發此技能，只需在對話中 **@ 標註**一個音訊或影音檔案（例如 @會議錄音.mp3 或 @會議錄影.mp4），並加上轉錄關鍵字。
**範例**：
- *「請幫我轉錄這段錄音。」*（預設使用 Gemini）
- *「請幫我把這部影片轉錄成逐字稿。」*
- *「幫我產生這場會議的逐字稿。」*
- *「這是一場多人會議，請幫我轉錄。」*（這將觸發 AssemblyAI 進行高精度說話者分離）

> **註**：如果您要求轉錄多人會議，但環境中僅配置了 `GEMINI_API_KEY`，技能將自動切換為使用 Gemini 執行。Gemini 依然會盡力去區分不同的說話者，雖然在聲紋辨識的精準度上可能略遜於 AssemblyAI，但仍能順利完成轉錄任務。
> *即使是 3 人以上的對話錄音或影片，您仍可要求使用 Gemini 進行轉錄（例如：在對話中直接要求使用 Gemini 引擎，或是在 `.env` 檔案中不要填入 `ASSEMBLYAI_API_KEY` 金鑰）。*
