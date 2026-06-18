# 对齐循环台账（alignment-loop-log）

> 这是「每小时自动对齐循环」的**唯一连续性来源**。每次循环都是全新上下文，
> 只能依赖本文件 + 仓库状态 + CLAUDE.md + 记忆，不依赖任何对话历史。
> 由 CronCreate 创建的 hourly 任务驱动（cron `13 * * * *`，durable）。

## 目标

**只对齐目标网站「AI 工坊」相关的 AI 功能**——首页助手、应用编排、工作流、内置/自定义插件、
知识库、以及这些 AI 功能相关的设置——**尤其是它们的前端交互**；逐步对齐到只读参考系统：
- 前端参考：`/code/linMing`（Next.js）—— **只读，绝不修改**
- 后端参考：`/code/linMing_ai`（Flask）—— **只读，绝不修改**

**范围边界：不碰非 AI 功能**（用户/权限/组织/计费/站点通用框架等与 AI 工坊无关的部分一律不对齐）。
用户对**当前前端交互最不满意**，因此前端交互对齐优先级最高。

## 铁律（每轮必须遵守）

1. **权限/RBAC/管理员限制类差异一律不对齐、直接跳过。** 参考系统对非管理员成员做了
   大量限制（超管不限、成员受限）；本项目刻意让**所有已登录用户都能无限制使用全部功能**，
   这是认证解耦铁律（见 CLAUDE.md），**永不改动**。凡是"参考站对某成员限制了 X"的差异，
   都**不是**对齐目标。
2. **只对齐 AI 工坊相关 AI 功能，非 AI 功能一律不碰**（用户/权限/组织/计费/站点通用框架等）。
3. 优先对齐**前端交互**；后端只在为支撑某个交互/行为对齐所必需时才改。
4. 不改 `/code/**`；**绝不 push**（只 `git commit` 到本地）；提交前按 CLAUDE.md 做隐私扫描
   （密钥 / 真实 IP `134.175.*` / `tencentyun` / `hf-mirror` / 私有名 `linMing`*/Next.js-isms）。
5. 每轮只做**一个**范围可控、能在单轮内完成并测试通过的对齐点。大特性（如工作流可视化编辑器，
   属 v1.1/Phase 8）若无法单轮完成，则**拆成最小增量**推进，或在 backlog 标注"暂缓"。
6. 测试不绿不提交：前端 `npm run test` + `npm run build` 必须过；动了后端则按 CLAUDE.md
   用 SQLite 跑 `pytest`。修不绿则回退本轮改动，记录原因。

## 每轮流程

1. 读本文件 + `CLAUDE.md` + `MEMORY.md`（记忆）。
2. 从下方 **候选 backlog** 选一个 **AI 工坊范围内、非权限类、未完成**的对齐点（或对照参考站新发现一个，优先前端交互）。
3. 读参考站对应实现 → 规划 → 实施（前端和/或后端，无需用户确认）。
4. 跑测试，必须全绿。
5. 隐私扫描 → **本地** `git commit`（不 push）。
6. 在「已完成记录」追加一条（日期 / 对齐点 / 改动 / 测试 / commit hash），并把该项从 backlog 移除。
7. **更新记忆**：把本轮进展 / 对参考站或本项目的新发现，更新进 `alignment-loop.md` 记忆条目
   （沿用「一事一文件、更新而非重复」原则；无新增持久事实就只更新进度行，别每轮新建文件）。
8. 简要向用户汇报本轮成果。

## 候选 backlog（待核实——动手前先对照参考站确认确有差异，且非权限类）

> 下列是**待调查区域**，不是已确认的差异。每轮挑一个去参考站比对，确认有真实交互差异再做。
> 优先级从上到下递减；前端交互类优先。

- [ ] 首页助手（`/code/linMing` 对应页 vs `frontend/src/features/home/assistant`）：流式渲染、
      思考态、停止/重试、滚动行为等交互细节。
      （✓ 已对齐：**头部模型选择器**、**空态四类随机引导便签**——见已完成记录 2026-06-18；
      自动滚动 hook、停止流程已核为忠实移植/同构、无差异。）
- [ ] **聊天附件上传/展示**（大特性，多轮）：参考 `message-composer`/`attachment-picker`/`message-bubble`
      支持图片+文档的拖拽/粘贴/选择上传与气泡展示，后端配额/白名单已就绪（CHAT_* 配置），
      但我们 `Composer` 仅纯文本。受 `CHAT_ATTACHMENT_URL_PREFIXES` 域名白名单门控（默认空=拒绝）。
      增量进度：①✓ **气泡附件渲染 + 历史映射**（增量1，见已完成记录）。
      **⚠️ 增量2（发送）经核实被阻塞——非纯前端**：上传 `/upload-files/file` 的 `to_dict` **只回 `key`、不回 URL**；
      后端**无通用上传文件服务路由**（仅 `serve_image_file` 服务生成图）；而 chat 附件需一个**可被后端/LLM 拉取的公网
      URL** 且必须命中 `CHAT_ATTACHMENT_URL_PREFIXES` 白名单（默认空=拒）。故发送附件需：(a) 后端上传返回公网 URL +
      (b) 新增上传文件服务路由（可仿 `serve_image_file`）+ (c) 部署设 `FILES_BASE_URL`/`CHAT_ATTACHMENT_URL_PREFIXES`
      + (d) 安全评审（公开服务用户上传文件 / SSRF）。**涉及后端改动+部署配置+安全面，建议经用户拍板后专门做，勿在自动循环单方面推进。**
- [ ] 应用编排（orchestrate）：模型参数面板、工具/知识库/工作流选择器的交互与校验、调试面板、
      发布流程提示、开场白/开场问题编辑体验。
      （✓ 已对齐：**回答后建议追问 chips**（debug+published）、**携带上下文轮数改 Slider**，见已完成记录 2026-06-18。
      已核：模型参数面板参考站也无（不做）；config-editor 开关仅差「语音播报」(TTS, v1.1 暂缓)。）
- [x] 内置插件 / 自定义插件（API 工具）：已核为**已对齐**——自定义插件编辑器已有请求头 + OpenAPI 校验，
      且多了「校验后本地解析工具预览」（比参考更全）；内置工具分类 chips + 卡片展开同构。无缺口。
- [ ] 知识库：上传、分段预览、检索测试 UI 的交互。
      （✓ 已对齐：**查询历史独立视图/tab**、**自定义分段规则前端校验**，见已完成记录 2026-06-18；
      命中测试侧栏本就有；ProcessRuleForm 其余控件已同构；参考无「分段预览」。）
- [ ] 设置 / 模型目录管理：表单与列表交互。
- [ ] 工作流可视化编辑器（参考站有，本项目目前是 placeholder，属 v1.1/Phase 8）：**大特性，
      拆最小增量推进或暂缓**；动前在台账写清增量边界。

## 已完成记录

> 格式：`YYYY-MM-DD HH:MM | 对齐点 | 改了什么 | 测试 | commit`

- 2026-06-18 00:33 | **首页助手头部模型选择器** | 参考站 `_home/chat` 头部有 ModelPicker 让用户选助手用哪个模型，
  我们没有；后端 `assistant_agent_schema` 早已支持可选 `provider`/`model`（按轮覆盖），纯前端缺口。新增持久化
  `stores/ai-model-store.ts` + `home/assistant/ModelPicker.tsx`（原生 select+optgroup，过滤非 chat/弃用，
  «默认模型»选项），`use-assistant-chat` 的 buildBody 读 store 在成对时附带 provider/model，AssistantChat 头部
  渲染选择器。后端未改。 | 113 passed（+2）、typecheck+build 绿 | 见本次提交（feat: assistant model picker）
- 2026-06-18 01:30 | **回答后建议追问（follow-up chips）** | 参考站 `debug-preview` 回答结束后据末条消息 id 拉
  follow-up 并在输入框上方渲染可点 chips；我们后端 `/ai/suggested-questions` + 前端 `api/ai.suggestQuestions`
  都已存在但聊天 UI 从未用。改：`ChatMessage` 加 `id`、`FINISH_ASSISTANT` 存 `agent_end` 的 message_id、
  history 回填 id；新增 `use-followups.ts`（仅对本轮实时回答 key=`a-` 取、流式/未开启隐藏、同条只取一次）；
  `ChatPanel` 加 followups/onPickFollowup（输入框上方 chips）；接入 DebugChatPanel（草稿 suggested_after_answer）
  与 PublishedChat（已发布配置）。后端未改。 | 117 passed（+4）、typecheck+build 绿 | 见本次提交（feat: follow-up chips）
- 2026-06-18 02:29 | **知识库「查询历史」视图** | 参考站知识库详情有独立「查询历史」tab（来源徽标 命中测试/应用对话
  + 时间）；我们后端 `GET /datasets/<id>/queries` + 前端 `api/datasets.listDatasetQueries` + `DatasetQuery` 类型
  全已就绪，仅被命中测试侧栏简单用了（只显示文本），无独立视图。新增 `datasets/detail/QueriesView.tsx`（列表：
  query+来源徽标+MM-DD HH:mm 时间、空态引导去命中测试），DatasetDetailLayout 加「查询历史」nav，router 加
  `:id/queries` 路由。后端未改。 | 119 passed（+2）、typecheck+build 绿 | 见本次提交（feat: dataset queries view）
- 2026-06-18 03:27 | **编排页「携带上下文轮数」改 Slider** | 参考 config-editor 用 Slider(0–20，带实时数值)
  控制 dialog_round，我们用数字 Input。改为原生 range 滑块(accent-primary 主题色)+实时数值+「携带最近 N 轮历史」
  提示(范围用我们后端常量 0–100)。先排除了模型参数面板(参考站也无)、插件领域(已对齐)等。后端未改。
  | 120 passed（+1）、typecheck+build 绿 | 见本次提交（feat: dialog-round slider）
- 2026-06-18 04:26 | **首页助手空态四类随机引导便签** | 参考 `chat-empty` 空态是 4 类(写作/读书/代码/心情)
  便签卡片、每类 10 条、进入/新对话随机各取一条、点击即发；我们原是 4 条固定建议竖列。重写 `EmptyState.tsx`
  为同款(便签图标+「今天想聊点什么？」+4 卡片随机取词，genericize 去「华语」)。同步改 AssistantChat.test
  两处旧文案断言(改 data-testid 取卡片实际文本、标题断言)。先核应用商店/store-app-card 已同构、不做。后端未改。
  | 120 passed、typecheck+build 绿 | 见本次提交（feat: assistant empty-state starter cards）
- 2026-06-18 05:28 | **知识库自定义分段规则前端校验** | 参考 `segment-settings-step` 提交前校验
  chunk_size>0 / overlap<chunk_size / 至少一个分隔符；我们 DocumentUploadModal 提交自定义规则前不校验、
  非法值直接打到后端。新增纯函数 `types/datasets.validateProcessRule`，modal 中 custom 模式算 ruleError →
  禁用「创建」+ 内联红字提示。先核 ChatEmptyState/ThinkingIndicator 为忠实移植无差异、ProcessRuleForm 控件同构。
  后端未改。 | 124 passed（+4，含校验器单测）、typecheck+build 绿 | 见本次提交（feat: segment-rule validation）
- 2026-06-18 06:27 | **聊天附件展示 + 历史映射（附件特性增量 1/3）** | 后端历史 `.../messages` 每轮已回
  `image_urls`/`file_infos`（模型有列、`_message_view` 映射），前端从未读取/渲染。`chat-core`：`ChatMessage`
  加 `imageUrls`/`fileInfos`+`ChatFileInfo` 类型、`HistoryRound` 加 `image_urls`/`file_infos`、`historyToMessages`
  映射到 user 气泡；`MessageItem` user 气泡上方渲染图片缩略图(点击新开)+文档 chip(忠实移植参考 message-bubble)。
  低风险：不动 Composer/发送路径。后端未改。**注：发送路径(增量2)未做，故现暂无新附件可显示——为下轮铺路。**
  | 128 passed（+4）、typecheck+build 绿 | 见本次提交（feat: chat attachment display）
- 2026-06-18 07:33 | **聊天「清空会话」二次确认** | 参考 `debug-preview` 清空用 AlertDialog 确认（销毁不可恢复），
  且我们全站销毁操作（删应用/库/片段/插件…）本就用 `ConfirmDialog`，唯独聊天清空直接清、无确认。把现有
  `ConfirmDialog` 接到 DebugChatPanel + PublishedChat 的清空按钮（destructive，确认后才调清空端点）。首页助手
  清空照参考用 title 提示、不弹框（保持一致）。**本轮另核实并记录附件增量2 被后端/部署/安全阻塞（见 backlog）。**
  后端未改。 | 129 passed（+1 确认门控测试）、typecheck+build 绿 | 见本次提交（feat: confirm before clearing chat）
- 2026-06-18 08:26 | **新建应用表单补「人设/提示词」字段** | 参考 `app-create-dialog` 创建表单有 图标上传/
  名称/描述/**人设提示词** 四项，我们 `AppFormModal` 只有 名称/描述。后端 `CreateAppReq` 早已收 `preset_prompt`
  (≤8000)。`AppCreate` 类型加 `preset_prompt?`，表单加可选「人设/提示词」Textarea，空则传 undefined。图标上传依赖
  公网 URL（同附件阻塞，跳过）。后端未改。 | 131 passed（+2，新增 AppFormModal 测试）、typecheck+build 绿
  | 见本次提交（feat: preset prompt on app create）
