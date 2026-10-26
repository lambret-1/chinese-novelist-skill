# 第三阶段：疯狂创作

**重要：全程无需再次向用户确认，必须逐章创作直到完成**

---

## 0\. 启动检测与模式读取

开始创作前：

1. 读取 `02-写作计划.json`

2. 读取 `writingMode` 字段，进入对应模式流程

3. 如果存在 `status: "in_progress"` 的章节 → 从该章节继续（中断续写）

4. 如果所有章节 `status: "pending"` → 从第 1 章开始

5. 如果存在 `status: "failed"` 的章节（Phase 4 回退）→ 从第一个 failed 章节开始

6. 如果项目缺少 `03-文风基准.md`（旧版本项目）→ 已有完成章节的，从第 1 章提取最佳段落补生成；一个章节都没有的，按题材生成默认基准

7. **旧项目迁移**：如果 `01-大纲.md` 存在非空「章节摘要」区且 `99-章节摘要.md` 不存在 → 将摘要区内容迁移到 `99-章节摘要.md`，并删除大纲中的「章节摘要」区

---

## 1\. 逐章创作流程（所有模式共用）

每一章的完整创作流程（写前分析 → 撰写 → 撰写后优化 → 收尾）统一执行 **\[chapter\-checklist\.md\]\(chapter\-checklist\.md\)**，所有写作模式共用同一份清单，不得自行增删步骤。

> ✅ 新增前置要求：动笔前载入 `{skillBaseDir}/references/guides/` 目录全套写作技巧文档，提取本章适用手法与约束，创作全程遵守规范。
> 
> 强制要求：**每一章定稿收尾之前，必须执行 check\_prose\.py 合并脚本校验（字数\+文风AI痕迹），必须清零全部 failures / warnings，拿到合格结果，才算本章创作完成；脚本不通过不允许标记 status 为 completed，不允许进入下一章。**
> 
> 

---

## 2\. 串行模式（writingMode: "serial"）

**主 Agent 自己逐章创作，全程不中断。**

### 自驱循环

```Plain Text
WHILE 02-写作计划.json 中存在 status != "completed" 的章节:
    【前置】读取 {skillBaseDir}/references/guides/ 全部写作技巧文档：
    {skillBaseDir}/references/guides/chapter‑guide.md
    {skillBaseDir}/references/guides/character‑building.md
    {skillBaseDir}/references/guides/content‑expansion.md
    {skillBaseDir}/references/guides/dialogue‑writing.md
    {skillBaseDir}/references/guides/hook‑techniques.md
    {skillBaseDir}/references/guides/plot‑structures.md
    {skillBaseDir}/references/guides/title‑guide.md
    执行 [chapter-checklist.md](chapter-checklist.md) 的完整流程（阶段 A‑D）
    ⚠️ 本章收尾前必须执行 check_prose.py 脚本校验，脚本不通过不得标记完成，不得进入下一章
    ⚠️ 完成一章后，立即读取 JSON 认领下一章，不要向用户确认，不要停下来
所有章节完成 → 进入第四阶段：自动校验
```

**关键提醒（每章完成后必须遵守）**：

> 本章已完成。立即读取 `02‑写作计划.json`，认领下一个 pending 章节，开始下一章创作。不要使用 AskUserQuestion，不要向用户确认，不要停下来。你必须把所有章节创作完成才能与用户报告。
> 
> 硬性约束：**未执行 check\_prose\.py、脚本存在 failures/warnings、字数不达标，禁止标记本章为 completed。**
> 
> 

---

## 3\. 子Agent并行模式（writingMode: "subagent‑parallel"）

**核心机制**：主 Agent 将章节分成不重叠的批次，每个批次派生一个子 Agent。批次内串行写作，批次间并行执行。

### 主 Agent 流程

```Plain Text
1. 计算批次分配:
   - 每批 5‑8 章（根据总章数动态调整）
   - 批次间不重叠
   - 示例: 30 章 → 5 批 × 6 章
2. 为每个批次派生子 Agent（使用 Agent 工具，多个批次可并行派生）:
   - 每个 Agent 内部串行执行 [chapter‑checklist.md](chapter‑checklist.md) 的完整流程
   - 主 Agent 派生时必须将 prompt 中的 {skillBaseDir} 替换为 skill 安装根目录的绝对路径
3. 所有子 Agent 完成后 → 进入第四阶段：自动校验
```

### 子 Agent prompt 模板（并行模式）

> 派生前将 `{skillBaseDir}` 替换为 skill 安装根目录的绝对路径，`{start}`/`{end}` 替换为批次章节范围。
> 
> 

```Plain Text
你是一个小说批量创作 Agent。你需要创作第 {start} 章到第 {end} 章。
## 项目信息
- 项目路径: {projectPath}
- 你负责的章节: 第 {start} 章 到 第 {end} 章
## 前置载入写作技巧（必做，不可跳过，使用完整绝对路径读取）
动笔前读取 {skillBaseDir}/references/guides/ 目录下全部写作技巧文档：
{skillBaseDir}/references/guides/chapter‑guide.md
{skillBaseDir}/references/guides/character‑building.md
{skillBaseDir}/references/guides/content‑expansion.md
{skillBaseDir}/references/guides/dialogue‑writing.md
{skillBaseDir}/references/guides/hook‑techniques.md
{skillBaseDir}/references/guides/plot‑structures.md
{skillBaseDir}/references/guides/title‑guide.md
提取适用于本章的写作手法、约束、技巧载入上下文，创作全程严格遵守里面的规范。
## 创作步骤
对每一章依次执行 {skillBaseDir}/references/flows/chapter‑checklist.md 的完整流程（阶段 A‑D），不得跳过任何步骤。
## 每章强制脚本校验（不可省略）
每一章定稿收尾前，**必须运行合并检测脚本做字数+文风校验**：
python {skillBaseDir}/scripts/check_prose.py <本章md文件路径> --word-check --min-words 2000 --json
- 退出码必须等于0，failures、warnings必须全部为空；
- 读取返回JSON内 chapter_word_count，写入02‑写作计划.json对应章节 wordCount；
- 脚本不达标，禁止将章节 status 设置为 completed，必须扩充/改写后重新复检，直到脚本全部通过。
## 重要约束
- 不要使用 AskUserQuestion，不要向用户确认任何事
- **每章开始前必须读取大纲、细纲**，严格按大纲、细纲的核心事件和悬念钩子创作
- 字数必须达到 2000 字以上，并且脚本校验全部通过才算本章完成
- 共享文件（02‑写作计划.json、99‑章节摘要.md、设定词典）只用 Edit 工具更新且改前重读，禁止 Bash 整体重写
- 你负责的所有章节必须全部完成，每一章都要执行脚本校验
完成后报告: 各章编号、字数、脚本退出码、是否全部通过脚本检查
```

### 并行写入协议

写作工具对并发修改有检测（文件在读取后被他人改动，Edit/Write 会报错强制重读），但 Bash 写入没有这层保护，报错重试也会浪费轮次。因此并行期间各批次必须遵守：

1. **写作计划**：每批只允许用 Edit 工具修改 `02‑写作计划.json` 中**自己章节**的 `status`/`wordCount`/`wordCountPass` 字段；修改前必须重新读取 JSON（不要基于派生时缓存的旧内容 Edit）；**禁止用 Bash/脚本整体重写 JSON**

2. **章节摘要**：按各自章号小节追加到 `99‑章节摘要.md`，同样只用 Edit 且改前重读

3. **设定词典**：更新 `01‑大纲.md` 设定词典只用 Edit 且改前重读；遇到持续报错，稍候重试，不要改用 Bash 追加

4. **跨批次衔接**：每批第一章动笔时，上一批末章可能尚未落盘——此时以大纲、细纲该章「承接上章」「悬念钩子」栏为衔接依据，不阻塞等待。全部批次完成后，主 Agent 对每个批次接缝做衔接检查（读前批末章结尾 \+ 后批首章开头），断裂处轻量修顺

---

## 4\. 多 Agent 协作模式（writingMode: "agent‑teams"）

**通用描述**：适用于宿主环境提供多 Agent 协作机制的场景（共享任务队列、Agent 间通讯、团队管理），需用户按需开启。**以能力描述为准，具体工具名称随宿主环境而定**——环境中有什么就用什么；不提供这些能力时，回退到「子Agent并行模式」。

### 主 Agent 流程

```Plain Text
1. 用环境提供的团队/任务机制创建协作团队，并为每一章创建一个可认领任务（任务描述含章号）
2. 派生 3‑5 个团队成员，下发成员 prompt 模板
3. 成员循环（环境工具随宿主而定）:
   a. 读取共享任务列表中的可用任务
   b. 认领任务（认领即独占，避免两人写同一章）
   c. 【前置】使用完整路径读取 {skillBaseDir}/references/guides/ 全套写作技巧文档，载入创作规范
   d. 对该章执行 {skillBaseDir}/references/flows/chapter‑checklist.md 的完整流程（阶段 A‑D）
   e. 【强制】本章收尾前执行 check_prose.py 脚本校验，全部通过才可标记完成
   f. 标记任务完成
   g. 回到任务列表认领下一章
4. 所有任务完成后 → 关闭团队 → 进入第四阶段：自动校验
```

### 团队成员 prompt 模板

```Plain Text
你是一个小说创作团队成员。按团队任务机制认领章节并创作。
## 项目信息
- 项目路径: {projectPath}
- 逐章清单: {skillBaseDir}/references/flows/chapter‑checklist.md（阶段 A‑D 不得跳步）
## 前置载入写作技巧（必做，不可跳过，使用完整绝对路径读取）
动笔前读取 {skillBaseDir}/references/guides/ 目录下全部写作技巧文档：
{skillBaseDir}/references/guides/chapter‑guide.md
{skillBaseDir}/references/guides/character‑building.md
{skillBaseDir}/references/guides/content‑expansion.md
{skillBaseDir}/references/guides/dialogue‑writing.md
{skillBaseDir}/references/guides/hook‑techniques.md
{skillBaseDir}/references/guides/plot‑structures.md
{skillBaseDir}/references/guides/title‑guide.md
提取适用于本章的写作手法、约束、技巧载入上下文，创作全程严格遵守里面的规范。
## 工作循环
1. 从共享任务列表认领一个未认领的章节（认领即独占）
2. 对该章执行逐章清单完整流程
3. 【每章强制脚本校验，不可跳过】
运行脚本：
python {skillBaseDir}/scripts/check_prose.py <本章md文件路径> --word-check --min‑words 2000 --json
要求：退出码=0，failures=[]，warnings=[]；脚本不通过不能标记任务完成，必须改写复检。
4. 标记任务完成，认领下一章，直到没有可用任务
## 重要约束
- 不要向用户确认任何事
- **每章开始前必须读取大纲、细纲**，严格按大纲、细纲的核心事件和悬念钩子创作
- 字数必须达到 2000 字以上，脚本校验全部通过才算完成
- 只通过团队通讯机制与其他成员协调，禁止写他人已认领的章节
- 共享文件写入遵守「并行写入协议」
```

**并发安全**：任务认领的原子独占语义保证一章只被一个成员写；共享文件（写作计划 JSON、章节摘要、设定词典）的写入遵守「并行写入协议」。
