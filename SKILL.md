---
name: audio-transcriber
description: 用於將會議錄音檔轉為逐字稿。當使用者在對話中上傳、提及或 @ 一個音訊檔案（如 mp3、m4a、wav 等格式），並提到「轉錄」、「逐字稿」、「會議紀錄」、「語音轉文字」等關鍵字時，務必觸發此技能。
---

# 會議錄音轉錄逐字稿技能 (audio-transcriber)

此技能指引 AI Agent 讀取對話中被標註（@）的音訊檔案，並利用其多模態能力將錄音內容精準轉錄為符合特定格式的繁體中文逐字稿，且自動在工作區存檔。

## 核心工作流程

1. **解析使用者輸入**：
   - 檢查使用者是否在 prompt 中指定了說話者姓名（例如：`第1位說話者：張三，第2位說話者：李四`）。
   - 檢查是否提供了「正確用字」清單。
2. **音訊讀取與引導檢查（重要前置檢查）**：
   - **檢查讀取方式**：確認使用者是否是以 `@` 附加音訊檔案。
   - **路徑引導規則**：如果使用者僅貼上本地檔案路徑（例如 `c:\錄音\meeting.mp3`），**嚴禁**使用 `view_file` 工具讀取該音訊。此時必須立即暫停並引導使用者：「請使用對話框的 `@` 按鈕將音訊檔案附加到對話中，這樣我才能讀取並聆聽音訊內容。」
   - **確認音訊就緒**：確認已正確加載被 `@` 的音訊檔後，始可進入下一步。
3. **金鑰偵測與引擎選擇（智慧路由）**：
   - **讀取金鑰**：AI 必須在音訊檔案所在目錄、工作區根目錄，或本技能所在的目錄尋找 `.env` 檔案，或從系統環境變數中讀取 `GROQ_API_KEY` 與 `ASSEMBLYAI_API_KEY`。可以使用本機指令或簡單 Python 腳本來進行多重路徑偵測。
   - **引擎路由規則**：
     - **情境 A：僅有 `GROQ_API_KEY`** -> 自動選擇 **Groq API 引擎**。
     - **情境 B：僅有 `ASSEMBLYAI_API_KEY`** -> 自動選擇 **AssemblyAI API 引擎**。
     - **情境 C：雙金鑰皆有** -> 預設選擇 **Groq API 引擎**（免費、高隱私）。但若使用者在 Prompt 中明確提及「區分說話者」、「高精度」、「多人會議」、「diarization」或直接指定使用「AssemblyAI」時，則切換選擇 **AssemblyAI API 引擎**。
     - **情境 D：完全沒有金鑰** -> 🔴 CHECKPOINT · 🛑 STOP: 暫停並回報錯誤，在對話中提示並引導使用者在 `.env` 中設定 `GROQ_API_KEY` 或 `ASSEMBLYAI_API_KEY`，直到使用者配置金鑰才可繼續。
4. **語音識別與說話者區分（第一階段：Raw 原始轉錄）**：
   - 根據選擇的引擎，呼叫相應的實作規範（詳見下方「雙引擎實作規範」），產生 Python 轉錄腳本並執行。
   - 區分不同的發言者聲音，並為其分配說話者標籤（指定姓名或預設的「說話者 1」、「說話者 2」）。
   - 聽寫內容並**直接寫入**生肉備份檔 `[YYYY-MM-DD]-raw.md`（存檔於與該音訊檔案相同的資料夾內）。
   - 此階段的重點是：時間戳記與發言者標籤正確、聽寫內容忠實，暫不需要進行美化排版。
   - **重要防禦規則**：`_raw.md` 一旦寫入，後續流程**不得**對其進行任何修改或刪除，以作為最安全的原始備份。
5. **格式化與後處理（第二階段：Transcript 排版輸出）**：
   - 讀取已產生的 `_raw.md` 內容。
   - 依據格式規範進行排版（合併同發言者連續發言、套用 glossary 術語修正、清理格式等）。
   - 將格式化後的最終結果寫入熟肉檔 `[YYYY-MM-DD]-transcript.md`（存檔於與該音訊檔案相同的資料夾內）。
   - 若排版或術語替換過程中發生任何錯誤，應隨時從 `_raw.md` 重新產生熟肉檔，**絕對不可**重新聆聽或轉錄音訊。
6. **後處理名字替換**：
   - 🔴 CHECKPOINT · 🛑 STOP: 若轉錄時使用了預設標籤（如說話者 1、2），轉錄結束後必須主動暫停並詢問使用者是否替換為真實姓名。若使用者提供，需讀取 `_raw.md` 進行全文姓名替換，並重新產生 `_transcript.md`。

## 雙引擎實作規範

當 AI 選擇了轉錄引擎後，應在當前對話的臨時工作目錄或音訊所在目錄產生一個臨時的 Python 腳本（例如 `transcribe_task.py`），並透過本機執行該腳本來完成轉錄。

- **錯誤處理與自動重試機制**：由於網路抖動、平台暫時超載或限流，產出的 Python 腳本必須具備 `try-except` 與自動重試（Retry）機制。當呼叫 API 失敗時，腳本應自動捕捉異常，等待數秒（如 3~5 秒）後再次嘗試呼叫相同的模型，共重試 1~2 次。若重試後仍失敗，則直接回報錯誤，不要嘗試其他已被下架或非預期的舊備用模型。

### 1. Gemini API 引擎實作規範 (預設優先/免分片雲端方案)
- **環境依賴**：`google-genai` (Google Gen AI SDK)、`python-dotenv`、本機 `ffmpeg` 工具。
- **為何選擇 Gemini**：Gemini 模型具備原生音訊多模態理解能力，可直接「聆聽」音訊檔並產出文字，無需分片、無需額外的後處理 LLM 步驟。單次請求支援最長約 **9.5 小時**的音訊（受 1M token 上下文窗口限制），搭配 `max_output_tokens=65536` 可一次輸出約 **3～4.5 萬中文字**（約 2 小時的錄音量），且能原生理解中英文與多語言混合語音，徹底消除傳統 ASR 引擎對非主要語言的空耳亂碼問題。
- **處理流程**：
  1. **音訊壓縮（可選但建議）**：
     - **壓縮目的**：減少上傳時間與 API token 用量，加速轉錄。壓縮不影響語音識別品質。
     - **壓縮判斷**：若原始音訊檔案 ≤ 20MB，可跳過壓縮步驟直接上傳。若 > 20MB，建議先行壓縮。
     - **壓縮參數配置**：單聲道 (mono)、取樣率 16000Hz、Opus 編碼、位元率 **24kbps** 的 OGG 檔。
     - **FFmpeg 指令範例**：`ffmpeg -i {input_path} -ac 1 -ar 16000 -c:a libopus -b:a 24k {output_path}.ogg`
     - **特殊情境（聲學偵測）**：若使用者提到錄音中有「物理撞擊聲、爆炸聲、巨大背景雜訊」需辨識，或 AI 以本機腳本偵測到突發巨響（滑動視窗最大振幅超越全局平均 20 倍），🔴 CHECKPOINT · 🛑 STOP: 主動暫停詢問使用者是否提升位元率至 **32kbps**。
  2. **上傳音訊至 Google File API**：
     - 使用 `google-genai` SDK 的 `client.files.upload()` 方法將音訊檔案上傳至 Google 雲端暫存空間。
     - 上傳後會取得一個 `file` 物件，其中包含 `file.uri` 與 `file.mime_type`，用於後續傳入模型。
     - **等待就緒**：上傳後需輪詢 `client.files.get(name=file.name)`，直到 `file.state` 為 `"ACTIVE"` 才可發送轉錄請求。
     - **上傳大小限制**：Google File API 單檔上限為 **2GB**，足以涵蓋絕大部分錄音場景，**完全不需要分片**。
  3. **呼叫 Gemini 模型進行一步轉錄**：
     - **模型選擇**：從 `.env` 讀取 `GEMINI_MODEL` 環境變數。若未設定，預設使用 `gemini-2.5-flash`。
     - **API 金鑰載入**：依序載入 `.env` 檔案（優先讀取音訊檔案目錄下的 `.env`，次之為本技能目錄下的 `.env`，最後為預設的 `load_dotenv()`），載入 `GEMINI_API_KEY`。
     - **SDK 初始化範例**：
       ```python
       from google import genai
       from google.genai import types
       import os
       from dotenv import load_dotenv

       load_dotenv()  # 載入 .env 中的 GEMINI_API_KEY 與 GEMINI_MODEL
       
       # 關鍵：必須在初始化 Client 時，透過 http_options 將連線逾時設定為 10 分鐘（600,000 毫秒）
       client = genai.Client(
           api_key=os.environ["GEMINI_API_KEY"],
           http_options=types.HttpOptions(timeout=600_000)
       )
       model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")  # 可由 .env 自訂模型
       ```
     - **Prompt 設計（關鍵）**：向 Gemini 傳送包含上傳音訊與文字指令的複合請求。Prompt 應指示模型：
       1. 逐段聆聽音訊，忠實聽寫所有發言內容。
       2. 區分不同的說話者聲音，為每位發言者分配標籤（說話者 A、B、C…）。
       3. 為每段發言標記精確的開始時間戳（格式：`HH:MM:SS` 或 `MM:SS`，依音訊總長度決定）。
       4. 若音訊包含多語言（如中英混合），以原始語言忠實聽寫，不要翻譯。
       5. 若使用者有指定「正確用字」清單或 glossary，在 Prompt 中一併傳入供模型參考。
       6. 輸出格式嚴格遵循：`{時間戳} 說話者 {X}：{聽寫內容}`。
     - **呼叫範例**：
       ```python
       # 上傳音訊
       audio_file = client.files.upload(file=audio_path)

       # 等待上傳完成
       import time
       while True:
           f = client.files.get(name=audio_file.name)
           if f.state == "ACTIVE":
               break
           time.sleep(2)

       # 建構 Prompt
       prompt = """你是一位專業的逐字稿轉錄員。請仔細聆聽這段音訊，並完成以下任務：

       1. 逐段忠實聽寫所有發言內容，不要遺漏任何發言。
       2. 區分不同的說話者聲音，為每位發言者分配標籤（說話者 A、說話者 B、說話者 C…以此類推）。
       3. 為每段發言標記精確的開始時間戳，格式為 HH:MM:SS。
       4. 若音訊包含多語言（如中英文混合），請以原始語言忠實聽寫，不要翻譯。
       5. 輸出格式嚴格遵循：{時間戳} 說話者 {X}：{聽寫內容}
       6. 若單一講者連續發言超過 3 分鐘，或語意主題有明顯轉換時，請主動切分段落並標註新時間戳。

       請直接開始輸出逐字稿，不要加任何額外的說明或前言。"""

       # 配置輸出參數，極為關鍵：
       # 1. 顯式設定 max_output_tokens=65536 以支持最大輸出
       # 2. 當模型為 gemini-2.5-flash 時，必須設定 thinking_budget=0 關閉思考以避免消耗 token 輸出額度
       # 3. 若使用其他不支援關閉 thinking 的模型 (如 gemini-3.5-flash)，請忽略 thinking_config
       config_params = {"max_output_tokens": 65536}
       if model_name == "gemini-2.5-flash":
           config_params["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
           
       config = types.GenerateContentConfig(**config_params)

       # 呼叫模型，SDK 支援直接傳入 prompt 與 audio_file 構成的 list
       response = client.models.generate_content(
           model=model_name,
           contents=[prompt, audio_file],
           config=config
       )

       # 取得轉錄結果
       transcript_text = response.text
       ```
  4. **結果寫入**：
     - 將 Gemini 回傳的轉錄文字直接寫入生肉備份檔 `[YYYY-MM-DD]-raw.md`。
     - 由於 Gemini 原生具備說話者聲紋辨識能力，**產出生肉檔時不需要額外呼叫任何 LLM 進行二次說話者猜測**。
  5. **清理暫存檔案**：
     - 轉錄完成後，呼叫 `client.files.delete(name=audio_file.name)` 刪除 Google 雲端的暫存音訊，避免佔用配額。

- **Gemini 免費版注意事項**：
  - Google AI Studio 免費版 API（`aistudio.google.com` 取得的 API Key）可直接用於此流程，**無需付費**。
  - **免費版限制**：每分鐘 15 次請求 (RPM)、每日 1,500 次請求 (RPD)，對於逐字稿轉錄場景綽綽有餘。
  - **隱私提醒**：免費版 API 送出的資料**可能被 Google 用於產品改善**。若處理高度機密的法律錄音或涉及客戶隱私的內容，🔴 CHECKPOINT · 🛑 STOP: 應在轉錄前主動提醒使用者此隱私風險，並建議升級至付費版（Pay-as-you-go）以獲得資料不被用於訓練的保證。


### 2. AssemblyAI API 引擎實作規範 (高精度說話者分離方案)
- **環境依賴**：`assemblyai` (官方 Python SDK)、`python-dotenv`。
- **處理流程**：
  1. **金鑰載入**：依序載入 `.env` 檔案（優先讀取音訊檔案目錄下的 `.env`，次之為本技能目錄下的 `.env`，最後為預設的 `load_dotenv()`），載入 `ASSEMBLYAI_API_KEY`。
  2. **SDK 配置**：設定 `aai.settings.api_key = os.environ["ASSEMBLYAI_API_KEY"]`。特別注意：金鑰字串直接代入，**不可手動加上 `Bearer` 前綴**，SDK 會自動處理。
  3. **建立轉錄設定**：
     ```python
     import assemblyai as aai
     # 智慧詞彙提權 (Keyterms Prompting)：腳本應動態讀取 references/glossary.md 或使用者提供的「正確用字」清單，
     # 提取其中的核心專有名詞或常錯字（每個片語不超過 6 個字，總數不超過 1000 個），放入 word_boost 清單中。
     boost_words = ["特定術語", "人名", "品牌名稱"]  # 依實際 glossary 及對話動態載入
          # 智慧語言配置（安全預設）：
      # 1. 預設主導語言設定為中文 language_code="zh"，這比 language_detection=True（自動偵測）安全許多，
      #    可完全規避音訊開頭音樂、空白或敲擊雜訊導致自動語言偵測誤判，而使整篇中文被強行用英文轉錄成亂碼。
      # 2. 如果使用者主動提到是其他語言會議，則特別指明：英文="en"、德文="de"、日文="ja"。
      # 3. 僅在主要語言不明且多語言混合時，才改用 language_detection=True（與 language_code 互斥，僅能擇一）。
      lang_code = "zh"  # 預設指定中文
      
      config = aai.TranscriptionConfig(
          speech_models=["universal-2"],  # 必填，必須使用 universal-2 以支援中文識別（純字串，SDK 無 Enum）
          speaker_labels=True,   # 啟用聲紋說話者分離 (Speaker Diarization)
          language_code=lang_code,  # 顯式指定主導語言，避免開頭雜音誤判
          word_boost=boost_words,  # 提權自訂詞彙，直接在 API 端提升專有名詞準確率
          boost_param="high",  # 提權強度，可設為 "high"、"default" 或 "low"
      )
     ```
  4. **執行轉錄**：使用 `transcriber = aai.Transcriber(config=config)`，並呼叫 `transcript = transcriber.transcribe(audio_path)`。SDK 會自動處理音訊上傳至 AssemblyAI 雲端與後續的非同步輪詢，**嚴禁手寫 HTTP 請求輪詢**。
  5. **狀態檢查與錯誤處理**：
     - 若 `transcript.status == aai.TranscriptStatus.error`，應透過 `transcript.error` 取得錯誤訊息，拋出 Exception 並中斷。
     - 若因網路暫時異常呼叫失敗，應在腳本中設定 `try-except` 與自動重試機制，間隔 3~5 秒重試 1~2 次。
  6. **結果解析與格式轉換**：
     - 遍歷 `transcript.utterances` 陣列。
     - 每個 utterance 物件包含：`speaker`（說話者標籤，如 "A"、"B" 等）、`start`（以毫秒表示的開始時間戳記）、`text`（該段聽寫文字）。
     - 將 `start` 毫秒值轉換為時間格式：音訊長度小於 1 小時轉換為 `MM:SS`，達 1 小時或以上轉換為 `HH:MM:SS`。
     - 格式化為：`{時間戳} 說話者 {speaker}：{text}` 並寫入生肉備份檔 `[YYYY-MM-DD]-raw.md`。由於 AssemblyAI 原生包含聲紋說話者標記，**產出生肉檔時絕對不要呼叫 LLM 進行二次發言者猜測**。
- **禁止事項**：
  - 絕對不要在 `TranscriptionConfig` 中使用已廢棄的參數：`auto_chapters`、`summarization`、`summary_model` , `summary_type`。

## 格式規範

- **排列方式**：`（時間戳）（說話者）：（說話內容）（換行）`
- **時間戳規則**：
   - 音訊總長未滿 1 小時：採用 `MM:SS`（如 `05:14`）。
   - 音訊總長達 1 小時或以上：採用 `HH:MM:SS`（如 `01:05:14`）。
- **段落切換**：當換另一人開始說話時，逐字稿換下一段。**【重要】**若是單一講者長篇演講，當連續發言超過約 3 分鐘，或語意/主題有明顯轉換時，**必須主動進行段落切分**並標註新的時間戳記，避免產生過長的文字牆。
- **排版範例**：
  ```text
  00:02 甲：OK，還有別的事情嗎？還有需要我補充的嗎？
  00:07 乙：現在講一下Line的事情。因為這是重要的事情。
  00:08 甲：Line的事情，Line 甚麼事情?為什麼很重要？
  00:09 乙：John 的意思不是說跟客戶談的時候，就是
  ```

## 術語修正與替換限制

- AI 在轉錄或後處理時必須參考 `references/glossary.md`。
- 如果使用者提供「正確用字：XXX -> OOO」，必須強制進行全局修正。
- **正則與腳本替換禁令**：執行文字替換或術語修正時，**嚴禁使用 Python 腳本、sed、re.sub 等批量正則替換方式**。所有替換必須使用 AI 自身的自然語言理解能力，或使用行級精確編輯工具（如 `replace_file_content`），以避免正則表達式出錯導致時間戳記或結構損毀。

## 長音訊分段處理與 Checkpoint 機制

若音訊長度預估超過 2.5 小時，或預期轉錄字數超過 4 萬中文字（接近 65,536 tokens 輸出上限），在適當發言點暫停並進行以下安全處理：

1. 將當前已轉錄的內容**立即追加寫入** `_raw.md` 檔案中，不得等全部完成才一次寫入。
2. 在寫入的 `_raw.md` 尾部加上進度標記：`<!-- checkpoint: HH:MM:SS -->`。
3. 🔴 CHECKPOINT · 🛑 STOP: 在對話框中主動暫停輸出，並顯示：`[已轉錄至 HH:MM:SS，原始資料已安全存檔。請回覆「繼續」以輸出下一段。]`，等待使用者回覆「繼續」後始可繼續。
4. 若中途發生 session 中斷或需要重啟，AI 必須讀取 `_raw.md`，解析最後一個 checkpoint 標記的時間戳，並從該時間點繼續轉錄，避免重頭開始。

> [!NOTE]
> 對於一般約 1 小時的會議錄音，AI 通常能一次完成轉錄，此規則不會觸發。這是針對極長錄音（3 小時以上）的防禦性設計。

## 錯誤處理

- **無法讀取**：回報錯誤，不建立空檔案。
- **無聲/雜音**：忽略無意義雜音段落。
- **多人重疊**：轉錄主要聲音，並標註 `（多人混音/無法辨識）`。

## 存檔格式

`_raw.md` 與 `_transcript.md` 存檔頂部都必須包含以下標頭：
```markdown
# 會議逐字稿 (Raw) 或 (Transcript)

- **音訊檔案**：[音訊檔名]
- **轉錄日期**：[YYYY-MM-DD]
- **識別說話者**：[說話者名單]

---

[逐字稿內容]
```

## 語音轉錄反例與黑名單 (不要做的事)

為確保轉錄與排版品質，AI 在執行此技能時**嚴禁**執行以下動作：
- **嚴禁手寫 HTTP 輪詢**：呼叫 AssemblyAI 時，必須直接使用官方 SDK 的 `aai.Transcriber().transcribe()`，絕對不要手動寫 `requests` 去輪詢狀態。
- **嚴禁 Bearer 金鑰前綴**：在配置 `aai.settings.api_key` 時，直接傳入金鑰字串，絕對不要手動加上 `"Bearer "` 前綴。
- **嚴禁使用已下線或廢棄的參數**：絕對不要在 `TranscriptionConfig` 中使用已廢棄的 `auto_chapters`、`summarization`、`summary_model`、`summary_type`。
- **嚴禁批量正則替換**：執行術語替換或 Glossary 修正時，嚴禁使用 Python 批處理、sed 或 `re.sub` 正則批量替換，必須使用行級精確編輯或自然語言理解進行局部修正，避免損毀時間戳記結構。
- **嚴禁對 raw 備份檔進行二次修改**：`[YYYY-MM-DD]-raw.md` 一旦寫入，後續的術語替換和排版必須讀取其內容並另存為 `-transcript.md`，絕對不得對 raw 備份進行任何修改或刪除。
