---
name: audio-transcriber
description: >-
  Transcribe audio/video recordings into verbatim transcripts. Trigger this skill whenever the user uploads, mentions, or @-attaches an audio or video file (mp3, m4a, wav, mp4, mkv, avi, etc.) and mentions keywords such as "transcribe", "transcript", "meeting notes", "speech-to-text", "轉錄", "逐字稿", "會議紀錄", "語音轉文字". Always use this skill for any audio/video transcription task.
---

# Audio Transcriber Skill (audio-transcriber)

This skill guides the AI Agent to read an @-attached audio or video file from the conversation and leverage its portfolio of tools and APIs to lease, convert, and transcribe the recording into a verbatim transcript and save it to the database/workspace.

## Core Workflow

1. **Parse User Input**:
   - Check if the user specified speaker names in the prompt (e.g., `Speaker 1: Alice, Speaker 2: Bob`).
   - Check if a "correct wording" (glossary) list was provided.
   - **Language Context**: Determine the primary language of the recording based on the user's prompt or the current conversation language.
2. **Audio/Video Reading & Guidance (Important Pre-check)**:
   - **Check Attachment Method**: Ensure the user attached the audio/video file using the `@` mention mechanism.
   - **Path Guidance Rule**: If the user only pastes a local file path (e.g., `c:\recordings\meeting.mp4`), **DO NOT** use the `view_file` tool to read the file. You must immediately pause and guide the user: "Please use the `@` button in the chat to attach the file to the conversation so I can read it."
   - **Confirm File is Ready**: Proceed only after confirming the @-attached file is loaded correctly.
3. **Key Detection & Engine Routing (Smart Routing)**:
   - **Read Keys**: The AI must look for a `.env` file in the file's directory, the workspace root, or this skill's directory, or read `GEMINI_API_KEY` and `ASSEMBLYAI_API_KEY` from system environment variables. You can use local commands or a simple Python script for this data detection.
   - **Routing Rules**:
     - **Scenario A: Only `GEMINI_API_KEY` exists** -> Automatically choose **Gemini API Engine**.
     - **Scenario B: Only `ASSEMBLYAI_API_KEY` exists** -> Automatically choose **AssemblyAI API Engine**.
     - **Scenario C: Both keys exist** -> Default to **Gemini API Engine** (free, high privacy). However, switch to **AssemblyAI API Engine** if the user explicitly mentions "speaker diarization", "high precision", "多人會議" (multi-person meeting, 3+ people), "diarization", or explicitly requests "AssemblyAI".
     - **Scenario D: No keys found** -> 🔴 CHECKPOINT · 🛑 STOP: Pause and report the error. Guide the user to configure either `GEMINI_API_KEY` or `ASSEMBLYAI_API_KEY` in a `.env` file before continuing.
4. **Pre-processing (Phase 0: Media Conversion & Audio Extraction)**:
   - Run the pre-processing script `scripts/audio_prep.py` to extract and compress the audio from the input audio or video file.
   - **Compression Rule**: The audio must be extracted and compressed into a 32 kbps single-channel 16000Hz OGG (Opus) file to minimize size (ideally under 25MB) and ensure very low Token usage.
   - **Command**: `python [Path to audio_prep.py] <input_file> <output_file.ogg>`
   - This step ensures a uniform format for the Gemini File API, and because pure audio is charged at only 12.5 tokens/sec, even 23 hours of content fits within the 1M token window without any chunking.
5. **Speech Recognition & Speaker Diarization (Phase 1: Raw Transcription)**:
   - Based on the chosen engine, use the preprocessed OGG file with the generated Python script to transcribe the audio.
   - Distinguish different speakers and assign them labels (specified names or defaults like "Speaker A", "Speaker B").
   - Transcribe the content and **write directly** to a raw backup file `[YYYY-MM-DD]-raw.md` (saved in the same directory as the input file).
   - **Important Defensive Rule**: Once `_raw.md` is written, you **MUST NOT** modify or delete it in subsequent steps. It serves as the secure original backup.
6. **Formatting & Post-Processing (Phase 2: Transcript Output)**:
   - Read the generated `_raw.md` content.
   - Format the text according to the formatting rules (merge consecutive utterances by the same speaker, apply glossary replacements if applicable, clean up format).
   - Write the final formatted result to `[YYYY-MM-DD]-transcript.md` (saved in the same directory as the input file).
   - If any errors occur during formatting or glossary replacement, always regenerate the transcript from `_raw.md`. **NEVER** re-listen to or re-transcribe the original audio/video.
7. **Post-Processing Name Replacement**:
   - 🔴 CHECKPOINT · 🛑 STOP: If default labels (e.g., Speaker A, Speaker B) were used during transcription, you must proactively pause after transcription completes and ask the user if they want to replace them with real names. If provided, read `_raw.md`, perform a full-text name replacement, and regenerate `_transcript.md`.

## Dual-Engine/Script execution Details

The executing agent should write/update a temporary script (e.g. `transcribe_task.py`) or run helper commands to execute the transcription.

- **Error Handling & Retry Mechanism**: All scripts/commands must include safety nets for network issues, API limit, etc.

### 1. Gemini API Engine Specification (Default / Cloud-native)
- **Dependencies**: `google-genai` SDK, `python-dotenv`, local `ffmpeg`.
- **Why Gemini?**: Native. High precision, handles multi-language.
- **Workflow**:
  1. **Pre-processing**: Run `scripts/audio_prep.py` to extract 32 kbps OGG audio.
  2. **Upload to Google File API**:
     - Use `client.files.upload()`. Poll `client.files.get(name=file.name)` until `file.state` is `"ACTIVE"`.
  3. **Call Gemini Model**:
     - Load `GEMINI_MODEL` from `.env` (default to `gemini-2.5-flash`).
     - Load `GEMINI_API_KEY`.
     - **Critical Prompt Design**: The prompt must be in **English** to prevent the model from translating non-English audio. Use the following prompt:
       ```python
       prompt = """You are a professional audio/video transcriber. Listen carefully to the audio/video and complete the following tasks:

       1. Transcribe all spoken content faithfully without omitting anything.
       2. Transcribe in the original spoken language; do not translate. For example, if the audio is in English, output English text. If it is mixed languages, output the original mixed languages.
       3. Distinguish different speakers and assign a label to each (e.g., Speaker A, Speaker B, Speaker C).
       4. Mark the exact start timestamp for each utterance in HH:MM:SS format.
       5. Format strictly as: {Timestamp} {Speaker}: {Content}
       6. If a single speaker speaks continuously for over 3 minutes, or there is a major topic shift, proactively break the paragraph and mark a new timestamp.

       Start outputting the transcript directly without any preamble."""
       ```
     - **Config Settings**: Explicitly set `max_output_tokens=65536`. If the model is `gemini-2.5-flash`, you **must** disable thinking (`thinking_config = types.ThinkingConfig(thinking_budget=0)`) to avoid consuming the output token budget. Set a 10-minute HTTP timeout.
  4. **Write Results**:
     - Write the raw transcript directly to `[YYYY-MM-DD]-raw.md`.
  5. **Cleanup**: Delete the uploaded file using `client.files.delete()`.

### 2. AssemblyAI API Engine Specification
- **Dependencies**: `assemblyai` SDK, `python-dotenv`.
- **Workflow**:
  1. **Load Key**: `ASSEMBLYAI_API_KEY`. Set `aai.settings.api_key = os.environ["ASSEMBLYAI_API_KEY"]` directly.
  2. **Transcription Configuration**:
     ```python
     import assemblyai as aai
     
     # Use "zh" for traditional Chinese, or other languages as needed.
     lang_code = "zh"
     
     boost_words = ["SpecificTerm", "PersonName", "BrandName"] 
     
     config = aai.TranscriptionConfig(
         speech_models=["universal-2"],
         speaker_labels=True,
         language_code=lang_code,
         word_boost=boost_words,
         boost_param="high",
     )
     ```
  3. **Execute**: Use `transcriber.transcribe(audio_path)`.
  4. **Parse & Format**:
     - Convert `start` (milliseconds) to `MM:SS` or `HH:MM:SS`.
     - Write formatted `{Timestamp} Speaker {speaker}: {text}` to `[YYYY-MM-DD]-raw.md`.

## Output Format Specification
- **Pattern**: `(Timestamp) (Speaker): (Content)`
- **Timestamp Rules**: `MM:SS` or `HH:MM:SS`.

## Glossary and Term Replacement
- Refer to `references/glossary.md` if the target language is Chinese.
- **Do not use regex or other high-risk text replacement scripts** that might accidentally strip timestamps or misalign speaker tags.

## Long Audio Checkpoint Mechanism
- Pure audio files up to 23 hours can be transcribed in a single API call due to the low token rate (12.5 tokens/sec). Thus, segment chunking and checkpoint resumption are not required, simplifying execution and ensuring flawless timestamp continuity.
