# 立维志愿 · lever-gaokao（dsh-lever-gaokao）

**立维志愿**（Lì wéi zhì yuàn）——**「立 + 维」谐音 lever**，与英文项目名 `lever-gaokao` 天然双关统一，技术标识零改动。

- **「立」**：立竿见影，快速确立报考方向（直击"志愿填报第一步"）
- **「维」**：多维度分数匹配、全维度升学规划（分数/位次/选科/家庭约束/长期路径）
- **记忆点**：科学填报、多维筛选的理性专业风格；谐音 lever（人生杠杆），与英文名互文
- **适配**：家长与考生双用户群体

技术标识保留 `lever-gaokao` / `dsh-lever-gaokao`（开发与插件生态）。英文传播名可直接用 **Lever**（谐音统一）。

> 命名历程（2026-08）：曾深入评估"潜机"（谐音先机/change，但域名 qianji.com 被占）等 13+ 候选，最终以"立维志愿"定稿——核心优势是**与 lever 技术标识谐音对应、零迁移成本**，且"立=确立方向、维=多维科学"语义直白，理性专业风格契合项目定位。

高考志愿填报的 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh`）插件。
**BYOK 本地客户端**：用户自配 DeepSeek API Key，本地运行，零服务器成本；结合 DeepSeek 峰谷定价
（闲时=高峰一半，2026-08-17 生效）引导重任务在闲时运行，让普通甚至贫寒家庭也能以极低成本
获得 AI 志愿填报辅助。

## 工具

| 工具 | 说明 |
|---|---|
| `gaokao_intake` | **立维问诊**：按 guided-intake 九层问诊推进（先边界后策略，每轮 3-5 题），配合 `ask_user_question` 多轮收集考生信息，产出画像 |
| `gaokao_query` | 高考志愿数据约束查询：按位次区间/科类/选科/学费上限/院校层级查询本地 DuckDB（数据来自各省考试院官方源），返回院校与专业，按位次升序 |
| `gaokao_validate` | 数据质量校验：各表行数、一分一段完整性、字段覆盖率，输出 JSON 报告 |
| `gaokao_cost_estimate` | DeepSeek API 成本估算：按任务类型（问诊/候选发现/对抗审查/完整分析）估算高峰/闲时价格，引导闲时运行重任务省钱 |
| `gaokao_offpeak` | **立维闲时**：判断当前是否为 DeepSeek 官方峰谷闲时，输出成本对比 + 下一个闲时窗口的 `after_seconds`，供 `schedule_create` 把重任务调度到闲时自动执行 |

## 原理

```
dsh（本地） ──> dsh-lever-gaokao 插件 ──spawn──> lever-gaokao Python 数据层
                                                    └─> DuckDB（data/gaokao.duckdb）
```

- 工具通过 `defineTool` 注册到 `ctx.tools`，schema 自动进入 dsh 的 system-prompt 组装。
- 执行时 spawn 调用 `lever-gaokao/scripts/data_ingest.py`（query/validate），复用已建好的
  官方源数据层，避免在 Node 侧重复实现。
- 数据层能力边界：只做确定性约束查询，不预测录取概率，结果仅供参考。

## 安装与加载

前置：已安装 Node.js ≥ 20，已构建 lever-gaokao 数据层（`data/gaokao.duckdb` 存在）。

### 1. 安装 dsh 并起 Web UI

```sh
npm install -g @deepseek-ai/dsh
dsh web          # 浏览器打开 http://127.0.0.1:3080
```

### 2. 挂载本插件

在 dsh 的 profile `cordis.patch.yml` 中插入本插件的 bundle：

```yaml
- insert:
    - id: lever-gaokao
      name: 'dsh-lever-gaokao'
      config:
        bridge:
          python: 'python'
          scriptDir: '<你的 lever-gaokao/scripts 绝对路径>'
          dataDir: '<你的 data 目录绝对路径>'
        pricing:                    # DeepSeek 定价（元/百万 token，按官方价填写）
          inputPerM: 1.0
          outputPerM: 4.0
          offPeakFactor: 0.5
```

（`dsh-lever-gaokao/cordis.patch.yml` 是现成模板，改路径即可。）

### 3. 配置模型

在 dsh Web UI 配置 DeepSeek provider：`base_url=https://api.deepseek.com`，填入你的
`api_key`，模型选 `deepseek-chat`（V4 Flash 系列，便宜）。

### 4. 使用

问 agent："用 gaokao_cost_estimate 估一下完整分析的成本，然后 gaokao_query 帮我查山东
物理类位次 4.5-5.5 万的学校"。

## 开发

```sh
npm install --registry=https://registry.npmmirror.com   # 国内镜像
npx tsc -p tsconfig.json                                # 类型检查
node smoke.mjs                                          # 冒烟测试（直接验证工具执行路径）
```

## 成本与峰谷说明（DeepSeek 官方基准，2026-08-17 生效）

- **官方峰谷时段**（北京时间）：高峰 = 9:00-12:00、14:00-18:00；其余为闲时，**闲时 = 高峰半价**（DeepSeek 官方公告，2026-08-13 发布）。
- **官方价格**（元/百万 token）：`deepseek-v4-flash` 高峰输入 3.0 / 输出 9.0，闲时 1.5 / 4.5；`deepseek-v4-pro` 高峰输入 9.0 / 输出 27.0，闲时 4.5 / 13.5。定价表见 `src/deepseek-pricing.ts`（默认 v4-flash）。
- 任务 token 估算为占位（intake 2.4 万 / candidate_search 7 万 / adversarial_review 12 万 / full_report 24 万 token，含缓存命中比例），可按实测调整。
- 完整分析（问诊+候选发现+对抗审查）按官方 v4-flash 价约 **0.79 元（高峰）/ 0.39 元（闲时）**——重任务攒到闲时跑，成本减半。
- `gaokao_offpeak` 工具提供下一个闲时窗口的 `after_seconds`，配合 dsh `schedule_create` 自动调度重任务到闲时。

## 边界与免责

- 不替代省级考试院、高校招生网和官方志愿系统；不输出精确录取概率。
- 查询结果来自已入库的官方源数据，但涉及当年政策请以官方最新发布为准。
- 数据层 `verified` 状态区分"已核验/待人工核验"来源（见 lever-gaokao 数据层设计）。
