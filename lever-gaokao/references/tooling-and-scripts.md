# 工具与脚本接口规格

> 使用边界：当用户提供 CSV/表格、要求候选表校验、硬规则过滤、ledger 合并、终表审计或覆盖审计时读取本文档；产出脚本命令、字段规范和限制；不要让脚本替代官方核验或主 Agent 价值判断。

本文档说明 `scripts/ledger_tool.py` 的使用方式。脚本只能处理确定性任务，不能替代官方资料核验和主 Agent 的价值判断。

## 目录

- CLI 快速使用
- 工具使用原则
- 候选 CSV 最小字段
- 可用子命令
- 表格状态约定
- 质量门槛

## CLI 快速使用

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/ledger_tool.py selftest
python3 scripts/ledger_tool.py template --output candidates.csv
python3 scripts/ledger_tool.py validate-candidate-table candidates.csv --report validate.json
python3 scripts/ledger_tool.py filter-candidates candidates.csv --subject-type 物化政 --batch 本科批 --max-tuition 8000 --output filtered.csv --report filter.json
python3 scripts/ledger_tool.py merge-ledgers candidates.csv filtered.csv --output merged.csv --report merge.json
python3 scripts/ledger_tool.py audit-final-table final.csv --report final-audit.json
python3 scripts/ledger_tool.py coverage-audit candidates.csv --home-province 样例本省 --popular-city 样例热门城市 --home-region-keyword 样例本省 --home-region-keyword 样例区域 --report coverage.json
```

默认输出中文审计摘要到 stdout；`--report` 写出 JSON 审计报告；需要生成 CSV 的命令使用 `--output`。

## 工具使用原则

1. 脚本负责机械标准化、筛选、合并和校验；主 Agent 负责规则解释、风险判断和最终组合。
2. 脚本输出必须保留来源、字段缺失、异常值和处理时间。
3. 不覆盖原始资料；每次处理生成新文件或新表，保留版本和时间戳。
4. 缺失字段不得自动猜测，必须写入待核验状态。
5. 任何高风险结论都需要回到官方资料或权威信源复核。

## 候选 CSV 最小字段

| 字段 | 说明 |
| --- | --- |
| candidate_id | 候选唯一 ID，用于合并、冲突检查和复入追踪 |
| province | 省份 |
| year | 年份 |
| batch | 批次 |
| category | 普通类、艺术、体育、专项、定向等 |
| subject_type | 科类或选科组合 |
| institution | 院校名称 |
| city | 城市 |
| school_nature | 公办、民办、中外合作、职业本科等 |
| authority | 主管部门或行业背景 |
| volunteer_unit | 实际志愿单位 |
| major_group | 专业组编号或名称 |
| major | 专业名称；专业组场景可为组内专业列表 |
| plan_count | 招生人数 |
| selection_requirements | 选科要求 |
| tuition | 学费 |
| campus | 校区 |
| restrictions | 身体、单科、语种、政审、性别、户籍等限制 |
| source_type | 当年官方、近年官方、商业 API、开放研究数据、辅助数据、口碑线索、用户提供 |
| source_ref | 文件名、链接、页码或截图编号 |
| source_status | 已核验、待交叉验证、待核验假设 |
| discovery_method | 官方计划导入、硬规则过滤后保留、机会雷达扩展、用户意向、子代理发现、漏选审计补充、宏观变量扫描补充 |
| tags | 画像、杠杆、宏观、风险标签 |
| current_status | 候选、观察、降级、剔除、待核验、最终组合 |
| downgrade_reason | 降级或剔除原因 |
| reentry_condition | 复入条件 |
| next_action | 下一步核验或处理动作 |
| review_role | 审查角色或子代理来源 |

## 可用子命令

### selftest

运行标准库自检，用临时 CSV 覆盖模板、候选表校验、硬规则过滤、ledger 合并、最终组合审计和覆盖审计。自检不读取真实招生数据，不生成仓库内文件。

建议在修改脚本后运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/ledger_tool.py selftest
```

### template

输出候选 CSV 最小字段模板。模板只给字段，不填充真实数据。

### validate-candidate-table

检查：

- 必填字段是否存在。
- `candidate_id` 是否重复。
- `current_status` 是否属于固定状态枚举。
- `source_type`、`source_status`、`discovery_method` 是否缺失。
- 观察、降级、剔除、待核验候选是否缺少复入条件。

缺少关键字段或候选 ID 重复时退出非 0。

### filter-candidates

按显式硬约束过滤候选，支持：

- `--subject-type`：考生选科文本。
- `--batch`：允许批次。
- `--max-tuition`：最高可接受学费。
- `--allow-nature`：允许办学性质，可重复。
- `--exclude-region`：排除地区关键词，可重复。
- `--unacceptable-major-keyword`：不可接受专业关键词，可重复。

命中硬约束的候选会被标记为 `剔除`，并写入 `downgrade_reason` 和 `review_role=filter-candidates`。脚本不判断学校质量或人生杠杆。

### merge-ledgers

合并多轮候选池和 ledger：

- 候选不会因后续文件缺少而被删除。
- 相同 `candidate_id` 的后续非空字段覆盖前序空字段。
- 院校或志愿单位冲突视为错误。
- 状态变化写入 JSON 报告的冲突项。

### audit-final-table

检查最终组合表：

- 是否包含 `待核验` 或 `剔除` 状态候选。
- 是否缺少明确保底或兜底标签。
- 是否存在专业组但看不到专业组调剂审计线索。
- 是否存在最终组合状态不一致。

### coverage-audit

提示覆盖缺口和过拟合风险：

- 省份过度集中。
- 热门城市过度集中。
- 本省、本区域、熟悉城市群或家庭照护半径过度集中。
- 高平台、行业特色、特殊身份候选不足。
- 宏观变量标签不足。
- 优质高职/职业本科扩展画像缺失。
- 专业方向过度集中。

覆盖提示只作为补充搜索方向，不直接进入最终志愿表。

新增地域惯性参数：

```bash
python3 scripts/ledger_tool.py coverage-audit candidates.csv \
  --home-region-keyword 样例本省 \
  --home-region-keyword 样例区域 \
  --min-outside-home-region-ratio 0.25 \
  --report coverage.json
```

- `--home-region-keyword` 可重复，用任意省份、区域、城市群或家庭熟悉范围关键词定义需要审计的地域惯性，不内置任何固定地区规则。
- 地域惯性比例只匹配 `province`、`city`、`campus` 等显式地理字段；`institution`、`authority`、`tags` 里的叙事关键词不计入本区域匹配。
- `--min-outside-home-region-ratio` 默认 `0.25`，取值范围为 `0` 到 `1`；当本区域外候选比例低于阈值时输出 warning。
- JSON report 的 `details` 会包含 `home_region_keywords`、`home_region_match_count` 和 `outside_home_region_ratio`。

## 表格状态约定

| 状态 | 含义 |
| --- | --- |
| 候选 | 已进入高召回候选池，尚未完成全部审计 |
| 观察 | 有机会逻辑，但证据或可达性不足 |
| 降级 | 原本有吸引力，但风险导致排序或名额下调 |
| 剔除 | 不符合规则、不可达或基本盘不可接受 |
| 待核验 | 缺少关键资料，不能形成结论 |
| 最终组合 | 已进入拟定志愿组合，仍需填报前复核 |

## 质量门槛

脚本或工具输出进入报告前，主 Agent 必须检查：

- 数据来源是否标明。
- 是否存在跨年、跨省、跨批次混用。
- 院校专业组是否被错误拆分或合并。
- 专业组内专业是否遗漏。
- 剔除原因是否可追溯。
- 复入条件是否具体。
- 候选状态是否和最终表一致。
