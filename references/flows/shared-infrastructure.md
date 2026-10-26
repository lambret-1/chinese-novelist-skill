# 共享机制
本文件定义跨阶段共享的机制和规则。
---
## 三大黄金法则
1. **展示而非讲述** - 用动作和对话表现，不要直接陈述
2. **冲突驱动剧情** - 每章必须有冲突或转折
3. **悬念承上启下** - 每章结尾必须留下钩子
---
## 用户偏好系统
### 存储文件
`user-preferences.json`（项目根目录，首次使用后自动创建）
### 数据结构
```json
{
  "version": 1,
  "updatedAt": "2026-04-12",
  "preferences": {
    "favoriteGenres": [],
    "preferredProtagonist": "",
    "preferredPerspective": "",
    "preferredTone": "",
    "typicalChapterCount": null,
    "styleReferences": [],
    "dislikes": [],
    "creationHistory": []
  }
}
```
偏好更新规则
时机 行为 
每完成一层问答 静默将本层回答同步到偏好文件（追加/更新，不删除历史） 
用户说"记住我的偏好" 保存当前所有配置到偏好 
用户说"忘记XX偏好" 清除指定维度的偏好 
用户说"重置偏好" 清空所有偏好数据 
一部长篇创作完成 将作品信息追加到 creationHistory 

偏好如何影响交互

1. 启动欢迎语：有偏好时显示"欢迎回来！" + 个性化提示

2. 选项排序：Q1中将 favoriteGenres 匹配项排前面

3. 常用标记：基调问（第二层调用一）、章节数问（第二层调用二）中对应用⭐标记"你的常用"/"上次选择"

4. 需求报告：结合偏好给个性化建议（如"你之前喜欢悬疑+第三人称限制，这次要不要试试多视角？"）

5. 随机生成：优先从偏好范围内随机选取，保持一致性

6. 风格参考追问：优先推荐 styleReferences 中的作者

错误恢复

• 回退修改：用户随时可说"重新问XX"、"修改XX"，AI 回退到指定问题重新询问

• 中途暂存：通过 02-写作计划.json 实现自动暂存；下次触发SKILL时 Phase 0 自动检测未完成项目，询问"继续上次的《XXX》？"

• 偏好文件损坏：JSON解析失败时忽略偏好，使用默认值，并在后台修复文件
标题传递机制

传递方式

标题通过对话上下文在阶段间传递，不单独持久化到文件。
传递链路：

1. Phase 1 Layer 3：用户选择/确认标题 → 标题存入对话上下文

2. Phase 2：从上下文读取标题 → 写入项目目录名、02-写作计划.json、01-大纲.md

中断恢复

若会话在 Layer 3 完成、Phase 2 开始前中断：

• Phase 0 不会找到已创建的项目目录（因为 Phase 2 尚未执行）

• 用户将重新进入 Layer 3 重新选择标题（标题选择耗时很短，重新选择成本可接受）

写作计划系统

存储文件

02-写作计划.json（项目文件夹内，Phase 2 创建）

作用

• 进度跟踪：记录每章创作状态（pending/in_progress/completed/failed）

• 写作模式：记录用户选择的写作模式（serial/subagent-parallel/agent-teams）

• 中断续写：Phase 0 读取 JSON 检测未完成项目，支持从断点继续

• 校验依据：Phase 4 基于 JSON 校验章节完成度、字数、文风AI痕迹

• 并行协调（可选）：多 Agent 并行写作时通过 JSON 状态避免冲突

与大纲的关系

• 01-大纲.md：章节规划（核心事件、悬念钩子、承接上章、出场人物、场景列表）+ 设定词典（设定名词的首现与揭示跟踪），纯规划文档，不随创作进度膨胀

• 99-章节摘要.md：逐章追加的 300‑500 字摘要（连贯性参考），每章收尾时写入

• 02‑写作计划.json：章节状态、字数、重试次数、写作模式（机器可读的进度跟踪）

• Phase 3 创作每章时必须读取 01‑大纲.md 中对应章节的规划信息，作为创作依据

• 两者严格对应：JSON 中的 chapterNumber 和 title 必须与大纲中的章节规划一致

JSON 损坏处理

• JSON 解析失败时：提示用户，尝试从 99‑章节摘要.md 推断完成进度

• 章节状态丢失时：通过文件存在性以及 check_prose.py 脚本输出重建状态

字数&去AI味合并检查脚本

使用 {skillBaseDir}/scripts/check_prose.py 做章节校验。{skillBaseDir} 指 SKILL.md 所在的 skill 安装根目录（如 ~/.claude/skills/chinese‑novelist）——脚本不在用户项目内，必须用 skill 安装目录的绝对路径调用，禁止写相对路径 scripts/...（那只存在于 skill 源码目录，用户项目解析不到）。
# 检查单个章节：文风检测 + 开启字数校验(默认最低2000字)，--json输出机器可读结果
python {skillBaseDir}/scripts/check_prose.py ./chinese‑novelist/项目文件夹/第01章.md --word-check --json

# 检查所有章节：按章号数值排序，第10章不会排在第2章前面
python {skillBaseDir}/scripts/check_prose.py --all ./chinese‑novelist/项目文件夹/ --word-check --json

# 自定义最低章节汉字字数
python {skillBaseDir}/scripts/check_prose.py ./chinese‑novelist/项目文件夹/第01章.md --word-check --min-words 2500 --json
退出码
退出码 含义 
0 全部达标：无failures、无warnings、字数满足最低要求 
1 存在不通过项：文风硬错误failures / 文风警告warnings / 章节字数不足（本项目warnings同样判定不通过） 
2 IO、目录、参数等系统错误 

Agent 优先用 --json + 退出码判断结果：

• JSON顶层字段files[]，单章字段chapter_word_count，该值可直接填入02‑写作计划.json的wordCount；

• 单章合格条件：文件无error、failures=[]、warnings=[]，对应设置章节wordCountPass=true；

• 不要解析控制台人类可读文本报告。

使用场景
阶段 用途 
Phase 3（逐章创作） 单章写完后执行校验，补齐字数同时清除全部AI文风痕迹 
Phase 4（自动校验） 批量全部章节校验，不合格章节进入自动重写修复流程 

说明：开启--word‑check才会执行字数校验；不添加该参数仅做文风检测，不校验章节字数。
章节不达标修复时，不能仅补字数，必须同时消除脚本输出failures与warnings全部条目，对照《执棋人》文风基准改写。
