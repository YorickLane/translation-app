# REFACTORING_AUDIT — translation-app 优化/重构审计

> 审计日期: 2026-06-20 · 分支 `master` · 审计基线 commit `0dea038`
> 方法: 全量阅读 15 个 `*.py` + `upload.js` + 模板 + 全部文档；每条"死代码/漂移"断言均 `rg` 坐实（附 `file:line`）；实现前跑通现有测试做基线。
> **每条结论都有证据。种子线索中已被实测推翻/修正的部分，本文如实标注（verify-first）。**

---

## 0. TL;DR — 优先级总表

| # | 发现 | 证据 | 价值 | 工作量 | 归类 | 状态 |
|---|------|------|:---:|:---:|------|------|
| C.6 | 无测试框架 → 立 pytest 安全网 | 根目录 2 个 stdlib 测试 / `rg pytest` 未装 | 高 | 中 | quick-win（**先做**） | ✅ `62ac108` |
| A.1 | `MODEL_RECOMMENDATIONS` 死代码 + 过时直连 slug | `translation_config.py:51`，0 消费者 | 中 | 小 | quick-win | ✅ `ddde1c2` |
| A.1+ | `CACHE_CONFIG`/`LOGGING_CONFIG` 死代码（描述不存在的功能） | `translation_config.py:199,206`，0 消费者 | 中 | 小 | quick-win | ✅ `ddde1c2` |
| A.3 | `commit_message.txt` 遗留物 | 根目录 4KB，0 引用 | 低 | 小 | quick-win | ✅ `ddde1c2` |
| A.3+ | `templates/upload.html.backup` 旧单体（1752 行） | 含旧 `/api/claude-models` + 内联 JS | 中 | 小 | quick-win | ✅ `ddde1c2` |
| B-cfg | `config.ALLOWED_EXTENSIONS` 死+漂移；`MAX_FILE_SIZE` 死 | `config.py:36-37`，0 消费者 | 中 | 小 | quick-win（TDD） | ✅ ALLOWED `488cc28` · MAX_FILE_SIZE→D4 |
| A.2 | `fix_translation_issues.py`+`fix_translation_auto.py` 删除 | 0 导入，用旧 buggy 检测 | 中 | 中 | quick-win（可逆 commit） | ✅ `e1618dd` |
| B.4/DOC | CLAUDE.md 文档漂移（端点/扩展名/zip/外链 JS/批次） | 见 §4 | 高 | 小 | quick-win | ✅ `4ff424f` |
| DOC6 | 2 个 OPTIMIZATION 文档严重过时 | Sonnet 3.5/BATCH=5/已删文件 | 中 | 小 | quick-win（归档） | ✅ `e1618dd` |
| B.5 | 英文检测算法分散（check_quality 接 SoT，顺修 Password/Login 误报） | 5 处 → 2 处 | 中 | 中 | 已批准 | ✅ `b4dd834` |
| **D.7** | 回灌重译闭环（接上 cb780b2 检测的下游） | `strict_validation` 仅检测→已闭环 | 高 | 大 | 已批准 | ✅ `4ad4946` |
| **D.8** | 双引擎 JS 真重复（"批处理重复"前提已实测推翻，缩小到 JS） | 抽 `js_locale` + 修双引号 key bug | 中 | 中 | 已批准(缩小) | ✅ `44dae42` |
| **D.9** | 无头 CLI（自动化/CI/批量） | `cli.py` + 抽 `translation_runner` | 中 | 中 | 已批准 | ✅ `295c3a7` |
| **D.10** | `ensure_term_consistency` 整 key 精确匹配有限角色 | docstring + 契约测试 | 中 | 中 | 已批准 | ✅ `2cace65` |
| D4 | `MAX_FILE_SIZE` 未接线（上传无上限） | `config.py:36` | 中 | 小 | **待限值决策** | ⏳ 待你给数值 |
| E.11-14 | 质量打磨（简繁变体/标点/tokenizer 等） | 见 §7 | 低 | 杂 | 文档化/择机 | ⏳ 择机 |

### 已实现（quick-win + 已批准 D 类，全程 TDD，pytest 62→84 绿）

| commit | 内容 |
|---|---|
| `ff38390` | docs: REFACTORING_AUDIT.md |
| `62ac108` | test: pytest 安全网（tests/ 迁移 + smoke + SoT 不变量 + setup.sh 自检）|
| `ddde1c2` | chore: 删死代码（MODEL_RECOMMENDATIONS/CACHE_CONFIG/LOGGING_CONFIG + commit_message.txt + upload.html.backup）|
| `488cc28` | refactor: ALLOWED_EXTENSIONS 单源真相 |
| `e1618dd` | chore: 删 fix_translation_*（0 导入）+ 归档 OPTIMIZATION 文档 |
| `4ff424f` | docs: CLAUDE.md 文档漂移修正 + llm_models 文档串 |
| `295c3a7` | **D.9** 无头 CLI cli.py + 抽 translation_runner 分发 |
| `44dae42` | **D.8(scoped)** 抽 js_locale 两引擎共用 + 修 translate.py 双引号 key bug |
| `b4dd834` | **B.5** check_translation_quality 词表接 SoT + 清死 import |
| `2cace65` | **D.10** ensure_term_consistency 有限角色文档化 + 契约测试 |
| `4ad4946` | **D.7** 回灌重译闭环 + needs_review sidecar |

**Google 引擎决策**：保留（在用的文档化功能，无弃用信号）。故 D.8 不删 `translate.py`，
缩小为抽 `js_locale` 去 JS 真重复（"双引擎批处理重复"前提实测站不住——Google 逐条递归
vs LLM 扁平批处理，结构不同，强抽 = premature abstraction）。

**仍待你定**：D4 `MAX_FILE_SIZE` 上传上限的数值（10/50MB 或不接）；E.11-14 择机。

### D4 — MAX_FILE_SIZE 接线（小，需限值决策）
`config.MAX_FILE_SIZE`（10MB）当前 0 消费者；Flask 未设 `MAX_CONTENT_LENGTH` → 上传无大小上限。
接线 `app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE` 即得保护，但 >10MB 的合法 ZIP 会收 413。
**需定限值**（10MB？50MB？）后我 TDD 接线。未定前保留常量 + 注释（已加于 `config.py:36`）。

---

## 1. 端到端数据流（实读心智模型）

```
浏览器 (upload.html + static/js/upload.js)
  │  拖拽/选择 .json/.js/.zip + 选语言 + 选引擎/模型
  ├─ POST /api/llm-models      → app.get_llm_models_api → llm_models.get_models()   [模型下拉]
  ├─ POST /api/estimate-cost   → cost_estimator.estimate_cost (字符估算, 20-30% 误差)
  └─ POST /translate           → app.translate_file_route
        ├─ ZIP → process_zip_archive → 逐文件逐语言 → create_zip_with_structure
        └─ 单文件 → translate_single_file
              ├─ engine=openrouter:
              │     .json → translate_llm.translate_json_file_llm
              │     .js   → translate_llm.translate_js_file_llm
              │        └─ _create_dynamic_batches → translate_with_llm
              │              └─ llm_client.translate_batch  (OpenAI SDK → OpenRouter,
              │                    response_format=json_schema, 注入 _build_prompt)
              │              └─ translation_postprocess.post_process_translation
              │                    ├─ strict_validation (zh-TW/ar: 检测 contains_english /
              │                    │     contains_simplified → 仅 log，非破坏性)  ← cb780b2
              │                    ├─ moderate_validation (罗曼语系: 比例告警)
              │                    ├─ apply_post_processing_rules (罗曼语系小写)
              │                    └─ ensure_term_consistency (TERM_GLOSSARY 整 key 精确)
              └─ engine=google: translate.translate_file (逐条 Google Translate)
        └─ Socket.IO `/test` namespace emit progress
```

配置层级: `config.py`（基础，读 shell env）← `translation_config.py`（高级，可选覆盖；`USE_ADVANCED_CONFIG` flag）。

**最近 3 commit 的 baseline（不重复）**: `cb780b2` 重写 `contains_english`（去占位符+白名单）/ 新增 `contains_simplified`（OpenCC s2tw）/ `strict_validation` 改非破坏性；`1b2eea6` zh-TW 词汇现代化（prompt+glossary）；`0dea038` 白名单补文件格式。

---

## 2. 死代码（全部 `rg` 坐实，0 消费者）

| 符号/文件 | 位置 | 证据 | 处置 |
|---|---|---|---|
| `MODEL_RECOMMENDATIONS` | `translation_config.py:51-57` | `rg MODEL_RECOMMENDATIONS` 仅定义处。内含 **Anthropic 直连 slug**（`claude-sonnet-4-5-20250929` / `claude-opus-4-20250514` / `claude-3-5-haiku-20241022` / `claude-3-haiku-20240307`），与实际 OpenRouter slug 格式（`anthropic/claude-sonnet-4.6`）不兼容，且与引擎默认矛盾 | **删除** |
| `CACHE_CONFIG` | `translation_config.py:199-203` | 0 消费者。描述一个**不存在**的翻译缓存层（`enabled/ttl/max_size`），误导读者以为有缓存 | **删除** |
| `LOGGING_CONFIG` | `translation_config.py:206-211` | 0 消费者。描述 `translation.log` 文件日志+轮转，**从未接线**（app 用 `basicConfig`） | **删除** |
| `MAX_FILE_SIZE` | `config.py:36` | 0 消费者。Flask **未设** `MAX_CONTENT_LENGTH` → 上传无大小限制 | **接线**（赋给 `MAX_CONTENT_LENGTH`，10MB 上限有实际价值）或删 |
| `ALLOWED_EXTENSIONS` | `config.py:37` | 0 消费者，**且漂移**：值 `{"json","js"}` 缺 `zip`；`app.py:32` 另有 canonical `{"json","js","zip"}`（实际生效，`app.py:109`） | **统一 SoT**：config 为源（含 zip），app import |
| `validate_translation_quality` | `translation_postprocess.py:202-237` | 0 消费者。干净的 QA 助手但无人调用 | 低优先：留作 D.7 素材 or 删 |
| `fix_translation_issues.py` | 整文件(283 行) | `rg 'import fix_translation'` = 空，0 导入。用旧 substring 检测（`:47` 硬编码词表 + `'kw' in value.lower()`），正是 cb780b2 根治掉的误报类 | **删除**（见 §3） |
| `fix_translation_auto.py` | 整文件(196 行) | 同上，`:30` 硬编码词表 | **删除**（见 §3） |

---

## 3. A.2 — fix_translation_* 删除（修正种子前提）

**种子线索说**：「是给老 `[需要重新翻译]` 标记善后的脚本」。
**实测修正**：两脚本**不引用** `[需要重新翻译]`（`rg` 证实）。它们的真实行为是——加载已译文件+源文件，用**硬编码英文词表 + substring 匹配**找"疑似含英文"的条目，调 `translate_with_llm` 重译并写回（带 backup）。

**删除理由（比种子更硬）**：
1. **0 导入、未接入 app**（`rg 'import fix_translation'` 空）。纯手动 CLI。
2. **检测算法是被根治掉的旧实现**：`'cancel' in value.lower()` 这类 substring 匹配，正是 `cb780b2` 用 `contains_english`（去占位符+白名单+小写词判定）替换掉的误报根源。在罗曼语系上会误伤（`'error'` 命中西语 `error`）。
3. 它们提供的"重译"能力，正确形态是 **D.7 闭环**（接入 SoT 检测 + 人工队列），而非这两份各自硬编码的旧脚本。
4. 可逆：单独 commit，`git revert` 即恢复。

**级联**：`TRANSLATION_OPTIMIZATION_GUIDE.md` / `TRANSLATION_OPTIMIZATION_SUMMARY.md` 记录了这两脚本的用法（`rg` 证实），删脚本须同步处理这两份文档（见 DOC6 → 归档）。

> 保留 `check_translation_quality.py`（只读报告型 CLI，有独立价值）与 `split_json.py`（干净的大文件切分/合并工具，README 文件树在列）——它们不是 stale/buggy，只是 standalone。

---

## 4. 文档漂移（CLAUDE.md = 约定权威，高价值修正）

| # | 位置 | 现状（错） | 实际（对，附证据） |
|---|---|---|---|
| DOC1 | `CLAUDE.md:58` | API 端点 `/api/claude-models` | `/api/llm-models`（`app.py:178`） |
| DOC2 | `CLAUDE.md:243` + "仅处理 .js 和 .json" | `ALLOWED_EXTENSIONS = {"json","js"}` | `{"json","js","zip"}`（`app.py:32`）+ 完整 ZIP 处理（`app.py:215 process_zip_archive`），**zip 支持全程未文档化** |
| DOC3 | `CLAUDE.md` "无前端构建工具/所有 CSS/JS 内嵌在 HTML 模板" | 内嵌 | **外链**：`static/js/upload.js` + `static/css/upload.css`（`upload.html:11,224`）。内联 `<script>`（`:219`）仅注入 `languages` 数据 |
| DOC4 | `CLAUDE.md:222` | "加模型要改两处" | `upload.js:778` 已 fetch `/api/llm-models`；`loadDefaultModels()`（`:817`）只是 API 不可用兜底（合理冗余，work_philosophy §7）。应 reframe |
| DOC5 | `CLAUDE.md` | "BATCH_SIZE=10（Google），BATCH_SIZE=5（Claude）" | 实际 `config.BATCH_SIZE` 默认 3，被 `BATCH_CONFIG['size']=15` 覆盖 + 动态分批（`translation_config.py:9`, `translate_llm.py:188`） |
| DOC-code | `llm_models.py:8` 文档串 | "新增模型 = 改这个文件 + cost_estimator.py 的 `MODEL_PRICING`" | `cost_estimator.py` **无** `MODEL_PRICING`，直接读 `get_model_info()`（`cost_estimator.py:13,85`）。定价已是单源（AVAILABLE_MODELS）。文档串过时 |
| DOC6 | `TRANSLATION_OPTIMIZATION_GUIDE.md` / `SUMMARY.md` | 描述 "Claude Sonnet 3.5"、`BATCH_SIZE=5`、已删文件（`check_api_status.py` 等）、`fix_translation_*`、缓存/日志（死配置） | 全面过时的 4 月历史叙事 → **归档 `docs/archive/`** |
| DOC7 | `commit_message.txt` | 提到 `translate_claude.py`（已删） | 遗留物 → 删 |
| DOC8 | `templates/upload.html.backup` | 1752 行旧单体，含 `/api/claude-models`（`:1663`）+ 内联 JS | git 即备份 → 删 |

---

## 5. 重复 / 单源真相（SoT）

- **英文检测 5 处分散**：
  - 活路径已收敛到 SoT：`translation_postprocess.contains_english_keywords`（`:189`）+ `translate_llm._contains_too_much_english`（`:130`）共用 `QUALITY_CHECK_RULES['english_keywords']`，仅各自 `re.compile`（`:183` / `:124`，可抽公共访问器，价值低）。
  - 分散源：`check_translation_quality.py:23` / `fix_translation_issues.py:47` / `fix_translation_auto.py:30` 各自硬编码词表 + 算法各异。
  - 删 `fix_translation_*` 后只剩 `check_translation_quality.py` 一处分散 → **B.5 提案**：抽 `is_english_contaminated()` 共享，或令其 import SoT。
- **模型列表**：`llm_models.AVAILABLE_MODELS`（SoT）vs `upload.js loadDefaultModels()`（兜底副本）。JS 主路径已走 API → 非违反，文档 reframe 即可（DOC4）。
- **JS 解析正则重复**：`translate_llm.py:314` 与 `translate.py:256` 同款 `(\'[^\']+\'|[^\s:]+):...` → 属 D.8。

---

## 6. D 类较大重构提案（**先批准再做**）

### D.7 — 回灌重译闭环（价值高/工作量大）
**现状**：`strict_validation`（`translation_postprocess.py:47`）经 cb780b2 改为只检测+log，**不自动重译**。检出的 flagged 条目无下游消费。
**提案**：QA 闸 → 调 LLM 重译 flagged → 仍不过则进人工队列。三个设计点（需拍板）：
- (a) **回灌触发层**：在 `translate_json_file_llm` 主循环里（批次级，省往返）还是 `post_process` 后（全量级，简单）？
- (b) **重译预算**：最多重译 N 轮 / 占比上限（防死循环烧 token）。
- (c) **人工队列落地**：写 `output/<file>.needs_review.json`？还是 progress 回调带 flagged 列表给前端？
**影响面**：`translate_llm.py`（主循环）、`translation_postprocess.py`（返回 flagged 而非吞掉）、可能前端。`validate_translation_quality`（现死代码）可复用。

### D.8 — 双引擎公共模块（价值中/工作量大）
**现状**：`translate.py`（Google）与 `translate_llm.py`（LLM）各自实现分批/重试/进度回调/JS `export default` 组装/JSON 读写。
**提案**：抽 `translation_core.py`（批次迭代器 + 重试装饰器 + 进度协议 + JS/JSON IO），两引擎注入"翻译一批"的回调。
**取舍**：收益=去重~150 行+一处改两处生效；成本=引入抽象层，若未来只留 LLM 引擎则过度设计。**先确认 Google 引擎是否长期保留**——若计划弃用 Google，D.8 不如直接删 `translate.py`。

### D.9 — 无头 CLI（价值中/工作量中）
**现状**：只有 Web(`app.py`) + 库函数，无 `批量 文件→语言列表` 入口。
**提案**：`cli.py`（argparse）：`python cli.py <src> --langs zh-TW,es,fr --model ... --engine openrouter --out dir/`，直接复用 `translate_json_file_llm`。利于自动化/CI/无浏览器环境。低风险（纯新增，不碰 Web）。**可并入 quick-win 若你同意**。

### D.10 — glossary 角色重设计（价值中/工作量中）
**现状**：`ensure_term_consistency`（`:107`）是 `if key in glossary` **整 key 精确匹配**。真实数据 key 多为整句，几乎不触发——真正杠杆是 prompt 指南（`_TRADITIONAL_CHINESE_TW_RULE`）。
**提案**：二选一——(a) **文档化**其有限角色（仅对"单词即 key"的 UI 词兜底），明确主杠杆是 prompt；(b) 谨慎重设计为**子串替换**（风险：误替换句中片段，需词边界/白名单）。推荐 (a)，低风险。

---

## 7. E 类质量打磨（文档化 / 择机）

- **E.11** `contains_simplified` 变体策略：`了解/瞭解`、`返佣/返傭` 等台湾正字偏好可能被 s2tw 标"简体残留"（非破坏性，仅 log）。→ 文档化或微调 `_TRAD_VARIANT_OK`（`translation_postprocess.py:164`）。
- **E.12** 繁中标点策略：是否在 prompt 规定全/半角（LLM 现会把 `()` 转 `（）`）。需 Yorick 定方向。
- **E.13** 模型时效：stale slug 仅存于 `MODEL_RECOMMENDATIONS`（删）+ 文档；`AVAILABLE_MODELS` 当前（Sonnet 4.6 / GPT-5.4 / Gemini 3.1）。
- **E.14** `cost_estimator` 真 tokenizer：现字符估算 20-30% 误差；另 `cost_estimator.py:77` `lang[:2]` 使 `zh-TW`→`'zh'` 未命中 `OUTPUT_LENGTH_MULTIPLIER`（落 default 0.85），轻微偏差。

---

## 8. 验证基线（实现前）

```
./venv/bin/python test_translation_postprocess.py  → 31 passed, 0 failed (exit 0)
./venv/bin/python test_tw_vocabulary.py            → 20 passed, 0 failed (exit 0)
环境: Python 3.14.6 · opencc ✅ · flask/socketio/openai/google ✅ · pytest ❌(待装)
```

---

## 9. 执行顺序（TDD + 安全网优先）

1. **C.6 安全网**（pytest+`tests/`+迁移+import-smoke+SoT 不变量+runner+setup.sh）— 先红后绿，破坏一处验证可失败。
2. **死代码删除**（A.1/CACHE/LOGGING/commit_message/upload.html.backup）— 删后全套测试仍绿。
3. **config SoT**（MAX_FILE_SIZE 接线 + ALLOWED_EXTENSIONS 统一）— 先写失败测试。
4. **A.2 fix_translation_* 删除 + OPTIMIZATION 文档归档** — 单独可逆 commit。
5. **CLAUDE.md 文档漂移修正**（DOC1-5）。
6. **D 类提案 → 等批准**。

> 状态在本表 §0 随实现更新。
