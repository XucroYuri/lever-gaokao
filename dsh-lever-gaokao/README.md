# 立维志愿 · Lever·College

> **用有限的分数，撬动更好的大学——高考志愿填报 AI 助手**

**立维志愿**（Lì wéi）＝ 谐音 **lever**（人生杠杆），与英文项目名 `lever-gaokao` 天然双关。

- **「立」**：立竿见影，快速确立报考方向
- **「维」**：多维度分数匹配、全维度升学规划
- **记忆点**：科学填报、多维筛选；谐音 lever（人生杠杆）
- **适配**：家长与考生双用户群体

基于 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh`）的 **BYOK 本地客户端**：用户自配 DeepSeek API Key，本地运行，**零服务器成本**；结合官方峰谷定价（闲时=高峰半价）引导重任务闲时运行——让普通甚至贫寒家庭也能以极低成本获得 AI 志愿填报辅助。

---

## 快速开始（下载客户端，3 步）

1. **下载**：从 [GitHub Releases](https://github.com/XucroYuri/lever-gaokao/releases) 下载对应系统的安装包（Windows / macOS / Linux）
2. **运行**：双击安装 → 首次启动自动打开向导 → 填 DeepSeek API Key
3. **问诊**：对话中让模型完成「问诊 → 查官方数据 → 出报告」，重任务攒到闲时跑更省钱

> 完整使用指南见 [GUIDE.md](../GUIDE.md)（含数据采集、维护、常见问题）。

---

## 工具（立维志愿 7 个能力）

| 工具 | 说明 |
|---|---|
| `gaokao_intake` | **立维问诊**：按 guided-intake 九层问诊推进（先边界后策略，每轮 3-5 题），配合 `ask_user_question` 多轮收集考生信息 |
| `gaokao_query` | **立维查询**：位次/科类/选科/学费约束查询本地官方数据（DuckDB），按位次升序 |
| `gaokao_validate` | **立维校验**：数据质量报告（行数/一分一段完整性/字段覆盖率） |
| `gaokao_cost_estimate` | **成本估算**：按任务类型估算高峰/闲时价格 |
| `gaokao_offpeak` | **立维闲时**：官方峰谷判断 + 下一个闲时窗口 `after_seconds`（配合 `schedule_create` 调度） |
| `gaokao_check_update` | **版本检查**：本地数据版本 vs 仓库最新（启动时自动静默检查） |
| `gaokao_update` | **数据更新**：从 GitHub Release 拉取数据包（SHA256 校验） |

---

## 数据维护（长期可用）

数据来自各省考试院官方源（一分一段/投档线/院校名单），三套机制保证长期可维护：

1. **版本化**：`data/version.json`（版本/覆盖/缺口/核验状态），`data_version.py` 生成
2. **自动检查**：插件启动静默 `check_update`；`gaokao_update` 拉取最新数据包
3. **本地采集**（最可靠）：`data_collect.py` 采集指定省官方数据

```
数据采集（本地）→ 版本化 → 提交 version.json → CI 校验+打包 → Release data-{version}
客户端：启动检查版本 → 有新版 → data_update.py 拉取（SHA256 校验）
```

> 说明：GitHub CI 海外 runner 访问国内政府站受限，**采集以本地执行为主**；CI 负责发布。

---

## 架构

```
立维志愿（dsh 客户端，本地）
├── 立维志愿插件（dsh-lever-gaokao，7 工具）
│   └── spawn → lever-gaokao Python 数据层 → DuckDB（官方源）
├── 数据维护（版本化 + Release 数据包 + 本地采集）
└── DeepSeek API（BYOK，官方峰谷定价省钱）
```

**三平台打包**：`distribution/` 用 `@yao-pkg/pkg` 把 dsh + 插件 + 数据打成单文件可执行；
Windows 额外 NSIS 安装器；CI 三平台矩阵自动发布。

---

## DIY 部署（进阶：从源码）

```sh
# 1. 装 dsh（需 Node ≥ 20）
npm install -g @deepseek-ai/dsh
# 2. 克隆仓库 + 数据层
git clone https://github.com/XucroYuri/lever-gaokao.git
cd lever-gaokao
python lever-gaokao/scripts/data_ingest.py ingest --province shandong --year 2024
python lever-gaokao/scripts/data_collect.py collect --province shandong --year 2026
# 3. 挂载插件（profile cordis.patch.yml 指向 dsh-lever-gaokao）
# 4. 起 dsh
dsh web    # http://127.0.0.1:3080
```

> 插件挂载配置见 `cordis.patch.yml` 模板；详细步骤见 [GUIDE.md](../GUIDE.md)。

---

## 成本（DeepSeek 官方基准，2026-08-17 生效）

- **峰谷**：高峰 9-12、14-18（价格翻倍），其余闲时**半价**
- **官方价**（元/百万 token）：`deepseek-v4-flash` 高峰输入 3.0 / 输出 9.0（闲时 1.5/4.5）；`v4-pro` 高峰 9.0/27.0
- **完整分析**约 0.79 元（高峰）/ 0.39 元（闲时）——攒到闲时跑，成本减半

---

## 开发与贡献

```sh
cd dsh-lever-gaokao
npm install --registry=https://registry.npmmirror.com
npx tsc -p tsconfig.json        # 类型检查
node smoke.mjs                   # 冒烟测试
```

- 欢迎公益方向的规则补充、信源核验、脚本修复、压力测试（见 [CONTRIBUTING.md](../CONTRIBUTING.md)）
- 数据缺口省份：运行 `data_version.py` 查看 `coverage_gaps`，按缺口补充官方源

---

## 边界与免责

- 不替代省级考试院、高校招生网和官方志愿系统；不输出精确录取概率。
- 查询结果来自已入库的官方源数据，当年政策请以官方最新发布为准。
- 数据层 `verified` 状态区分"已核验/待人工核验"来源；正式填报前建议让熟悉本省规则的老师或专业人士复核。
- 本项目非商用（CC BY-NC-SA / PolyForm Noncommercial）；用户自行承担 DeepSeek API 费用。
