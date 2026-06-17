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
      思考态、停止/重试、建议追问、空态、滚动行为等交互细节。
      （✓ 已对齐：**头部模型选择器**——见已完成记录 2026-06-18；自动滚动 hook 已核为忠实移植、无差异。）
- [ ] **聊天附件上传/展示**（大特性，多轮）：参考 `message-composer`/`attachment-picker`/`message-bubble`
      支持图片+文档的拖拽/粘贴/选择上传与气泡展示，后端配额/白名单已就绪（CHAT_* 配置），
      但我们 `Composer` 仅纯文本。需拆：①上传 api+lib ②AttachmentPicker+预览 ③气泡附件渲染
      ④useChatStream 传附件。受 `CHAT_ATTACHMENT_URL_PREFIXES` 域名白名单门控（默认空=拒绝）。
- [ ] 应用编排（orchestrate）：模型参数面板、工具/知识库/工作流选择器的交互与校验、调试面板、
      发布流程提示、开场白/开场问题编辑体验。
      （✓ 已对齐：**回答后建议追问 chips**（debug+published），见已完成记录 2026-06-18。）
- [ ] 内置插件 / 自定义插件（API 工具）：插件列表、配置表单、参数校验与错误提示交互。
- [ ] 知识库：上传、分段预览、检索测试 UI 的交互。
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
