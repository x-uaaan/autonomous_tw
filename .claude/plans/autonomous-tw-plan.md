# autonomous.tw — 開發計畫與進度

> 從 Horizon 分支演進為 autonomous.tw，打造繁體中文（台灣）讀者的 AI 驅動資訊聚合系統。
> 最後更新：2026-06-07

---

## Phase 1 — 在地化與品牌重塑 ✅ COMPLETED

**目標**：將專案從 Horizon 改名為 autonomous.tw，全面繁體中文化

- [x] 品牌更名：Horizon → autonomous.tw（所有檔案）
- [x] 全部 AI prompt 簡中 → 繁中（支援 Taiwan 用語）
- [x] README 加入 Ollama 安裝指南（安裝方式、推薦模型、Docker 網路設定）
- [x] 評分領域從單一技術維度擴展為 5 領域（AI Tech, Taiwan Affairs, Intl Politics, Sports, Knowledge Management）
- [x] CLI / Webhook / MCP branding 更新
- [x] tag aliases 轉為台灣用語（47+ 條目）
- [x] `src/models.py` sender_name 改為 "autonomous.tw Daily"

## Phase 2 — 溯源與資料擴充 ✅ COMPLETED

**目標**：完整的資料溯源鏈，擴充資訊來源（Threads）

- [x] `ContentItem.provenance` 欄位 + `add_provenance()` 方法
- [x] 每個 pipeline 階段記錄 provenance（fetch → dedup → score → enrich → summarize）
- [x] 語義去重（Semantic Dedup）：AI 驅動的主題重複檢測
- [x] Threads.net scraper：關鍵字搜尋 + 雙重擷取策略（JSON-LD → HTML meta fallback）
- [x] Threads 整合進 `fetch_all_sources()`
- [x] `ThreadsConfig` model 定義
- [x] OpenBB 金融新聞來源
- [x] OSS Insight 趨勢 repos 來源
- [x] Twitter 回覆擴展（第二階段 re-analysis）

## Phase 3 — Card-Based UI/UX ✅ COMPLETED

**目標**：卡片式 UI 搭配 Wolfgang Forest 自訂配色，支援日夜模式

- [x] Wolfgang Forest 配色方案（深苔綠 #2D423F、霧灰綠 #7B8F8A、暖木色 #8C6A5E）
- [x] CSS variables 實現日夜模式切換（prefers-color-scheme）
- [x] 完整配色體系：背景、文字、強調色、琥珀光、琥珀金
- [x] Hero Card（最重點新聞的大卡）
- [x] Featured Cards（次重點的 2-3 欄網格）
- [x] List View（其餘新聞清單）
- [x] Tag Cloud（點擊篩選）
- [x] Calendar（日期導航）
- [x] RWD 斷點：768px / 480px
- [x] Jekyll Cayman theme override（default.html, header.html, head-custom.html）
- [x] `docs/assets/css/horizon.css`（~15.5 KB）
- [x] `docs/assets/js/horizon.js`（~18.2 KB）
- [x] 語言切換功能
- [x] Jekyll 本地預覽確認（localhost:4000）

## Phase 4 — 自動插圖與 Agentic 協作 ✅ COMPLETED

### Phase 4a — Auto-Illustration Pipeline ✅

- [x] `src/ai/illustrator.py`：Unsplash API（有 key）+ Unsplash Source（免費 fallback）
- [x] 關鍵字擷取：從 AI tags + 標題產生搜尋關鍵字
- [x] Hero image + thumbnail 雙尺寸支援
- [x] 整合進主 pipeline（step 6.5，enrichment 之後）
- [x] 圖片 URL 存入 `item.metadata["hero_image"]` / `["thumb_image"]`

### Phase 4b — Multi-Agent Refinement Architecture ✅

- [x] `src/agents/dispatcher.py`：DispatcherAgent — 分析整個 batch，路由到 5 個領域 specialist
- [x] `src/agents/specialists.py`：5 個 SpecialistAgent（AI Tech, Taiwan Affairs, Intl Politics, Sports, KM），各有領域特化評分標準
- [x] `src/agents/synthesizer.py`：SynthesizerAgent — 合併 multi-specialist 評分（primary 0.7 + secondary 0.3），產生 Executive Brief（zh + en）
- [x] `src/agents/orchestrator.py`：AgenticOrchestrator — 統籌 Dispatcher → Specialists（平行執行）→ Synthesizer 流程
- [x] `FilteringConfig.agentic_enabled` 開關（預設 False）
- [x] 整合進主 pipeline：enrichment 之後、illustration 之前（step 6.3）
- [x] Executive Brief 注入 Jekyll post 的 front matter 下方
- [x] `AgenticResult` dataclass 包含 executive_brief_zh/en, cross_domain_themes, top_story_index
- [x] 所有新檔案語法檢查通過

---

## 技術架構

```
src/
├── scrapers/          # 資料擷取（GitHub, HN, RSS, Reddit, Telegram, Twitter, OpenBB, OSS Insight, Threads）
├── ai/                # AI 客戶端與處理邏輯
│   ├── client.py      # 統一 AIClient（Ollama 優先）
│   ├── analyzer.py    # 內容評分（5 領域）
│   ├── enricher.py    # 背景知識補充
│   ├── summarizer.py  # 每日摘要生成（純程式化渲染）
│   ├── illustrator.py # 自動插圖（Unsplash）
│   └── prompts.py     # AI prompt 模板
├── agents/            # Multi-Agent 協作
│   ├── dispatcher.py  # 路由分配
│   ├── specialists.py # 領域專家（×5）
│   ├── synthesizer.py # 合成與 Executive Brief
│   └── orchestrator.py# Agentic 編排器
├── services/          # 傳遞通道（Email, Webhooks）
├── storage/           # 持久化與狀態管理
├── models.py          # Pydantic 資料模型
├── orchestrator.py    # 主 Pipeline（HorizonOrchestrator）
└── main.py            # CLI 入口
```

## Pipeline 流程

1. Fetch（所有來源平行）
2. Deduplicate（跨來源 URL + 語義主題）
3. Analyze/Score（AI 5 領域評分，含 Twitter 回覆擴展）
4. Filter（ai_score_threshold 篩選）
5. Enrich（背景知識補充）
6. **Agentic Refine**（如啟用：Dispatcher → Specialists → Synthesizer）
7. Illustrate（Unsplash 自動插圖）
8. Summarize（產生多語每日摘要 + Executive Brief）
9. Deliver（Email + Webhook + Jekyll GitHub Pages）

## 核心設計原則

- **Local LLM First**：Ollama 預設，cloud API 為 fallback
- **資料主權**：使用者資料不離開本地環境（除非明確設定）
- **完整溯源**：每個 ContentItem 記錄完整 pipeline 歷程
- **繁體中文（台灣）**：所有 zh 輸出使用台灣用語與 Pangu 空格
- **漸進增強**：Agentic refinement 為可選開關，不影響核心 pipeline