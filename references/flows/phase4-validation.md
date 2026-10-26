# 第四阶段：自动校验与修复

**目标**：确保所有章节完成、字数达标、文风检测全部通过；自动重试修复，达到最大3轮重试上限，尽量无需用户介入。

---

## 校验流程

### 1. 初始化校验

读取 `02-写作计划.json`，将项目 `status` 更新为 `"validating"`。

> 若为子Agent并行/Teams 模式，先确认各批次的状态与章节摘要已合并回 `02-写作计划.json` 和 `99-章节摘要.md`（未合并则先合并），并对每个批次接缝做衔接检查：校验相邻章节结尾/开头人物、剧情、设定连续性，出现明显断层标记到章节备注。

### 2. 逐章检查

对每一章执行以下检查：

1. **文件存在性**：检查 `filePath` 指定的文件是否存在
2. **字数与AI味检查**：使用脚本批量检查（`{skillBaseDir}` 为 skill 安装根目录，见 [shared-infrastructure.md](shared-infrastructure.md)）：
   ```bash
   python {skillBaseDir}/scripts/check_prose.py --all <项目文件夹路径> --word-check --json
退出码：0=全部达标，1=有不达标，2=错误。从 --json 输出的 files[] 读取各章 chapter_word_count，单章合格判断：该文件failures为空、warnings为空、文件无error字段。

3. 更新 JSON：将 wordCount 和 wordCountPass 写入对应章节记录
wordCountPass=true 条件：文件存在，该章节failures=[]，warnings=[]；同时字数≥2000。
3. 汇总结果

• 全部通过（所有章节文件存在且 wordCountPass == true）→ 更新项目 status 为 "completed"，进入步骤5

• 有不通过 → 进入步骤4

4. 自动修复（最多3轮）

对每个不通过的章节：

1. 将 status 设为 "failed"，retryCount 加 1

2. 回到第三阶段对该章节执行逐章创作流程（写前分析→撰写→润色→收尾）
修复目标：补齐字数，同时消除所有failures硬错误、消除所有warnings文风警告。
3. 重写完成后重新执行全套脚本检测，不可仅校验字数

4. 更新 02-写作计划.json

循环规则：

• 最多执行 3轮 校验-修复循环；单章节retryCount >=3不再重试重写

• 超过3次仍不合格的章节，保留记录但不阻塞流程

• 区分项目状态：

◦ 无遗留不合格章节：项目status为"completed"

◦ 存在达到3次重试上限依旧不合格章节：项目status为"completed‑with‑issues"，代表完成但存在遗留风险点

5. 完成报告

向用户展示创作完成总结：
📊 《[小说名称]》创作完成

总章数：[X] 章
总字数：[X] 字
完成率：[X]%

各章节状态：
✅ 第1章：[标题]（[字数]字）
✅ 第2章：[标题]（[字数]字）
...

项目文件夹：./chinese-novelist/[timestamp]-[小说名称]/
如有不合格章节（超过3次重写仍未通过），在报告中标注：
⚠️ 第X章：【原因】（[实际字数]/2000），已重试3次，未自动修复，请人工审阅修改。
补充给Agent的关键约束

1. 脚本返回退出码2是系统异常，禁止进入重试修复，直接报错终止。

2. 修复不能只补字数，必须同时消除脚本输出的failures和warnings全部条目，对照《执棋人》文风基准做改写。

3. 解析脚本只读取stdout的JSON，忽略stderr打印的人类可读日志。

4. --word-check 参数不能省略，省略将不会执行2000字数校验。
