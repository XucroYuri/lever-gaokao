# 潜机 · Latent Edge（dsh-lever-gaokao）

**潜机**（qián jī）——潜藏的机会。谐音"先机"：别人还没看到，你抢先看到了。**空耳近英文 change（改变/改变命运），中英双关："发现潜藏的机会，改变命运"**。出自易经《乾卦》"潜龙勿用"与佛家"禅机、玄机"的思辨：时机未显，先潜藏蓄力，待时而跃。对应本项目最独特的主张——帮考生用有限分数，买入被大多数人忽略、但长期更有价值的选择（低估机会发现）。

**英文名 Latent Edge**：latent（潜藏/潜在，亚里士多德"潜能现实论"哲学出处）+ Edge（先机/优势），与"潜机"一一对应；"潜机"拼音变体 **Qiange**（读似 change）可作传播/国际名。技术标识保留 `lever-gaokao` / `dsh-lever-gaokao`（供开发与插件生态）。

**商标注册策略**：主名"潜机"作传播名；商标以 **"潜机志愿"** 或 **"潜机AI"**（三字/加后缀）申请注册——组合词显著性远强于两字、注册成功率更高，且规避"潜机"两字在教育/软件类可能存在的在先权利。

**域名策略**（WHOIS 可靠查证 2026-08；此前 DNS 快查不可靠，勿用）：`qianji.com`/`qianjiai.com`/`qiange.com` 已注册（两字拼音域名行业性枯竭）。**可注册域名**：`qianjizhiyuan.com`（潜机志愿，与商标注册名完美对应，推荐主域名）、`getqiange.com`（qiange 双关）、`jianqianji.cn`（见潜机备选）。

> **命名定稿**（2026-08）：先后排除 12+ 候选（登科/跃龙门/拾机/见独/拨云/风眼/司南/折桂/拿云/摘星/击水等——均为占用或谐音/域名问题）。"潜机"商标层面查证干净、谐音"先机"记忆成本趋近零、直击"低估机会发现"主线，最终定稿。若"潜机"两字商标最终受阻，回落备选 **见潜机**（3 字，jianqianji.cn 可注册）。

高考志愿填报的 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh`）插件。
**BYOK 本地客户端**：用户自配 DeepSeek API Key，本地运行，零服务器成本；结合 DeepSeek 峰谷定价
（闲时=高峰一半，2026-08-17 生效）引导重任务在闲时运行，让普通甚至贫寒家庭也能以极低成本
获得 AI 志愿填报辅助。

## 工具

| 工具 | 说明 |
|---|---|
| `gaokao_query` | 高考志愿数据约束查询：按位次区间/科类/选科/学费上限/院校层级查询本地 DuckDB（数据来自各省考试院官方源），返回院校与专业，按位次升序 |
| `gaokao_validate` | 数据质量校验：各表行数、一分一段完整性、字段覆盖率，输出 JSON 报告 |
| `gaokao_cost_estimate` | DeepSeek API 成本估算：按任务类型（问诊/候选发现/对抗审查/完整分析）估算高峰/闲时价格，引导闲时运行重任务省钱 |

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

## 成本与峰谷说明

- 定价表 `src/deepseek-pricing.ts`：`inputPerM`/`outputPerM`（元/百万 token，高峰价）、
  `offPeakFactor`（默认 0.5 = 闲时半价）。**占位值需按 DeepSeek 官方价覆盖**。
- 任务 token 估算为占位（intake 2.4 万 / candidate_search 7 万 / adversarial_review 12 万 /
  full_report 24 万 token），可按实测调整。
- 峰谷时段近似 22:00-08:00，正式实现以 DeepSeek 公告为准。
- 完整分析（含问诊+候选发现+对抗审查）在默认占位价下约 0.36 元（高峰）/ 0.18 元（闲时）。

## 边界与免责

- 不替代省级考试院、高校招生网和官方志愿系统；不输出精确录取概率。
- 查询结果来自已入库的官方源数据，但涉及当年政策请以官方最新发布为准。
- 数据层 `verified` 状态区分"已核验/待人工核验"来源（见 lever-gaokao 数据层设计）。
