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
   - **Read Keys**: Look for a `.env` file in the file's directory, the workspace root, or this skill's directory, or read `GEMINI_API_KEY` and `ASSEMBLYAI_API_KEY` from system environment variables.
   - **Routing Rules**:
     - **Scenario A: Only `GEMINI_API_KEY` exists** -> Automatically choose **Gemini API Engine**.
     - **Scenario B: Only `ASSEMBLYAI_API_KEY` exists** -> Automatically choose **AssemblyAI API Engine**.
     - **Scenario C: Both keys exist** -> Default to **Gemini API Engine** (free, high privacy). However, switch to **AssemblyAI API Engine** if the user explicitly mentions "speaker diarization", "high precision", "多人會議" (multi-person meeting, 3+ people), "diarization", or explicitly requests "AssemblyAI".
     - **Scenario D: No keys found** -> 🔴 CHECKPOINT · 🛑 STOP: Pause and report the error. Guide the user to configure keys in a `.env` file before continuing.
4. **Pre-processing (Phase 0: Media Conversion & Audio Extraction)**:
   - Run the pre-processing script `scripts/audio_prep.py` to extract and compress the audio from the input audio or video file.
   - **Compression Rule**: The audio must be compressed into a 32 kbps single-channel 16000Hz OGG (Opus) file to minimize size and ensure very low Token usage.
   - **Command**: `python [Path to audio_prep.py] <input_file> <output_file.ogg>`
5. **Speech Recognition & Diarization (Phase 1: Raw Transcription)**:
   - Write a temporary script (e.g., `transcribe_task.py`) to execute the transcription.
   - **Robust API Retry & Fallback Mechanism (Defensive Design)**:
     - The script **must** include a retry loop (e.g., 3 attempts, waiting 5 seconds) to handle transient 503 (Unavailable) errors from the API.
     - The script **must** support model fallback. If the primary model `gemini-2.5-flash` fails continuously, fallback to `gemini-1.5-flash` as a backup to guarantee execution.
   - **Output Format**: Format strictly as `[ HH:MM:SS ] {Speaker}: {Content}`. Write directly to a raw backup file `[YYYY-MM-DD]-raw.md` (saved in the same directory as the input file). Do not modify or delete this file once written.
6. **Formatting & Post-Processing (Phase 2: Transcript Output)**:
   - Invoke `scripts/post_process.py` to format the transcript:
     - **Robust Time Parsing**: The post-processor uses a high-tolerance regex (`^\s*(?:(\d+)\s*:\s*)?(\d+)\s*:\s*(\d+)\s*$`) to capture and standardize timestamps, ensuring that formatting variances (like extra spaces or missing leading zeros) do not break time parsing or cause timestamps to reset to `[00:00]`.
     - **Glossary & Merger**: Apply terms from `references/glossary.md` and merge consecutive utterances by the same speaker.
   - Write the final formatted result to `[YYYY-MM-DD]-transcript.md`.
7. **Post-Processing Name Replacement**:
   - 🔴 CHECKPOINT · 🛑 STOP: Proactively ask the user if they want to replace speaker labels (e.g., Speaker A, Speaker B) with real names. If provided, update the speaker mapping in `scripts/post_process.py` and run it again to update the final transcript.

## Long Audio & Output Token Limits

- **Pre-set Strategy**: Pure audio files up to 4 hours can be transcribed in a single API call due to the Gemini 65,536 output token capacity (roughly 50,000 words). Thus, segment chunking is **not required by default**, preserving timestamp continuity and simple flow.
- **Defensive Hot-Patching for Looping Errors**:
  - For long bilingual or noisy audio, the model might occasionally loop (e.g., repeat the same word endlessly like "under under under") near the end of the transcription.
  - **Do not restart the whole 2-hour transcription**. Instead, run the hot-patching script `scripts/patch_transcript.py` to extract, transcribe, and repair only the affected segment:
    `python [Path to patch_transcript.py] --audio <audio_file> --raw-md <raw_md> --start <error_start_time> [--end <error_end_time>]`
  - This script automatically transcribes the patch segment with fallbacks, shifts the timestamp offsets, replaces the looping segment in the `_raw.md`, and rebuilds the final `_transcript.md`.

## Bundled Scripts Usage

- **Audio prep**: `python scripts/audio_prep.py <input> <output.ogg>`
- **Post-processor**: `python scripts/post_process.py <raw.md> <transcript.md>`
- **Hot-patching**: `python scripts/patch_transcript.py --audio <audio> --raw-md <raw.md> --start <start_time> [--end <end_time>]`

## Banned Actions & Anti-Patterns (反模式與黑名單)

To guarantee safety, accuracy, and efficiency, you MUST strictly avoid the following actions:

1. **NO view_file on Binary Media**: Never invoke the `view_file` tool on raw audio or video files (e.g., `.mp3`, `.mp4`). This will flood the context window with binary garbage and crash the session. Proactively guide the user to @-attach the file instead.
2. **NO Redundant Re-transcription**: If formatting, naming, or glossary replacement fails, always debug and run the post-processing script (`scripts/post_process.py`) using the existing `_raw.md`. Never call the Gemini API to re-transcribe the original audio/video, which wastes time and API quota.
3. **NO Full Re-transcription for Local Loops**: If a looping error (e.g., repeated "under") or a timestamp error is reported for a specific section of a long transcript, never re-transcribe the entire 2-hour audio. Always use the hot-patching tool (`scripts/patch_transcript.py`) to target and repair only the affected segment.
