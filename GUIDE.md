# 立维志愿 · 整体使用指南

**立维志愿**（lever-gaokao）——高考志愿填报 AI 助手。基于 DeepSeek Harness（`dsh`）的
BYOK 本地客户端：用户自配 DeepSeek API Key，本地运行，**零服务器成本**；结合 DeepSeek
官方峰谷定价，重任务攒到闲时跑，成本再减半——让普通甚至贫寒家庭也能以极低成本获得
AI 志愿填报辅助。

本指南覆盖从零开始到完成一次志愿分析的完整流程。

---

## 一、这是什么（30 秒看懂）

```
你的电脑（本地，零服务器）
├── Node.js + DeepSeek Harness（dsh Web UI，浏览器访问 127.0.0.1:3080）
│   └── dsh-lever-gaokao 插件（6 个工具）
│       ├── 立维问诊   gaokao_intake       → 九层问诊收集考生信息
│       ├── 立维查询   gaokao_query        → 位次/科类/学费约束查官方数据
│       ├── 立维校验   gaokao_validate     → 数据质量检查
│       ├── 成本估算   gaokao_cost_estimate → 任务成本测算
│       ├── 立维闲时   gaokao_offpeak      → 峰谷调度建议
│       └── （数据层）  lever-gaokao 官方源数据（DuckDB）
└── DeepSeek API（你自配 Key，按官方价付费）
```

**成本**（官方价，元/百万 token）：deepseek-v4-flash 高峰输入 3.0 / 输出 9.0；
闲时半价（高峰 = 北京时间 9-12、14-18，其余闲时）。一次完整分析约 0.79 元（高峰）/ 0.39 元（闲时）。

---

## 二、开始前准备

- 一台可联网的电脑（Windows / macOS / Linux）
- 一个 DeepSeek API Key（在 [platform.deepseek.com](https://platform.deepseek.com) 申请，按量付费）
- 建议：可访问 [github.com/XucroYuri/lever-gaokao](https://github.com/XucroYuri/lever-gaokao)（本仓库）

---

## 三、步骤 1：安装 Node.js

立维志愿需要 Node.js ≥ 20。

- **Windows**：到 [nodejs.org](https://nodejs.org) 下载 LTS 版安装（一路下一步）。
- **macOS**：`brew install node`
- **Linux**：`curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt install -y nodejs`

验证：

```sh
node --version    # 应输出 v20 或更高
```

> 国内网络较慢时，可先配置 npm 镜像：`npm config set registry https://registry.npmmirror.com`

---

## 四、步骤 2：准备数据层（可选但强烈推荐）

立维志愿的查询依赖本地官方数据（DuckDB）。两种方式：

### 方式 A：克隆仓库 + 运行数据层脚本（推荐）

```sh
git clone https://github.com/XucroYuri/lever-gaokao.git
cd lever-gaokao

# 种子数据入库（GaokaoCompass，MIT 许可）
python lever-gaokao/scripts/data_ingest.py ingest --province shandong --year 2024

# 采集当年官方数据（示例：山东 2026 一分一段 + 投档线）
python lever-gaokao/scripts/data_collect.py collect --province shandong --year 2026
python lever-gaokao/scripts/data_collect.py collect --province shandong --year 2026 --type toudang

# 校验数据质量
python lever-gaokao/scripts/data_ingest.py validate
```

> 数据全部来自各省考试院官方源，原始文件归档在 `official-sources/` 供人工核验。

### 方式 B：跳过（仅用示例数据）

不准备数据也能跑通流程（工具会提示数据缺失），但查询会返回空。建议至少跑方式 A 的山东样例。

---

## 五、步骤 3：启动 DeepSeek Harness

```sh
npx @deepseek-ai/dsh web
```

首次运行会自动拉取 dsh（耐心等待），然后浏览器自动打开
**http://127.0.0.1:3080**——这就是立维志愿的主界面。

> 每次使用都执行这一步（或在桌面端中一键启动，见步骤 7）。

---

## 六、步骤 4：挂载立维志愿插件

dsh 通过 profile 的 `cordis.patch.yml` 挂载插件。

**找到你的 profile 配置**：dsh 在首次运行时会创建配置目录（Windows 一般在
`%USERPROFILE%\.config\dsh\`，macOS/Linux 在 `~/.config/dsh/`）。找到 profile 的
`cordis.patch.yml`（或按 dsh 文档创建），加入：

```yaml
- insert:
    - id: lever-gaokao
      name: 'dsh-lever-gaokao'
      config:
        bridge:
          python: 'python'
          scriptDir: 'C:/path/to/lever-gaokao/lever-gaokao/scripts'
          dataDir: 'C:/path/to/lever-gaokao/data'
        pricing:
          inputPerM: 3.0        # deepseek-v4-flash 官方高峰输入价（元/百万 token）
          outputPerM: 9.0       # 官方高峰输出价
          offPeakFactor: 0.5    # 官方闲时系数
        allowTableSwitch: true
```

关键点：
- `scriptDir` / `dataDir` 填你电脑上 lever-gaokao 仓库的**绝对路径**（步骤 2 克隆的位置）。
- 若插件未安装，先在插件目录执行 `npm install --registry=https://registry.npmmirror.com`。

重启 dsh 后，插件生效，模型即可调用 6 个工具。

---

## 七、步骤 5：配置 DeepSeek 模型

在 dsh Web UI 的 **Providers / 模型设置** 页：

| 项 | 值 |
|---|---|
| Base URL | `https://api.deepseek.com` |
| API Key | 你的 DeepSeek Key |
| 模型 | `deepseek-v4-flash`（便宜推荐）或 `deepseek-v4-pro`（更强） |

> 桌面端（Tauri）首次启动会引导完成此配置，见步骤 7。

---

## 八、步骤 6：完整跑一遍志愿分析

配置好后，在对话窗口输入（可整段复制）：

> 请使用立维志愿为一名中国高考考生生成志愿填报分析。先完成问诊，再查询数据，最后给出报告。省钱优先：重任务请配合闲时调度。

模型会自动按如下流程执行：

| 阶段 | 工具 | 动作 |
|---|---|---|
| 1. 问诊 | `gaokao_intake` + `ask_user_question` | 九层问诊（先边界后策略，每轮 3-5 题），逐层收集考生信息 |
| 2. 成本预判 | `gaokao_cost_estimate` / `gaokao_offpeak` | 估算分析成本，判断当前时段；高峰则提示攒到闲时 |
| 3. 数据校验 | `gaokao_validate` | 确认本地官方数据可用 |
| 4. 候选查询 | `gaokao_query` | 按位次区间/科类/选科/学费查候选院校专业 |
| 5. 分析报告 | （模型综合） | 冲稳保梯度 + 低估机会备选 + 风险清单 + 待核验项 |

**手动查询示例**（也可以直接输入给模型）：

> gaokao_query：山东 2026 物理类，位次 45000-55000，学费 8000 以内，查专业级。

**闲时调度示例**（高峰时段省钱）：

> 现在是下午 3 点（高峰），请把候选发现任务用 schedule 排到闲时跑，先告诉我能省多少钱。

---

## 九、步骤 7（可选）：桌面端（Tauri）

想一键启动、不用记命令？用立维志愿桌面端（`dsh-lever-gaokao/desktop/`）：

```sh
cd dsh-lever-gaokao/desktop
npm install --registry=https://registry.npmmirror.com
npm run tauri dev     # 开发运行
npm run tauri build   # 打包安装包
```

桌面端启动页会引导填写 DeepSeek Key → 一键启动 dsh → 进入主界面。
（需本机安装 Rust 工具链，见 `desktop/README.md`。）

---

## 十、常见问题

| 问题 | 解决 |
|---|---|
| `npx` 拉取 dsh 很慢 | 先 `npm config set registry https://registry.npmmirror.com` |
| 查询返回空 | 数据层未准备（步骤 2），或 scriptDir/dataDir 路径配错 |
| 插件未生效（工具列表看不到） | 确认 `cordis.patch.yml` 挂载正确并重启 dsh；插件目录已 `npm install` |
| 中文输出乱码 | Windows 控制台 GBK 导致；数据层脚本已内置 `PYTHONIOENCODING=utf-8` 处理，dsh 内正常 |
| 高峰时段太贵 | 用 `gaokao_offpeak` + `schedule_create` 把重任务排到闲时（半价） |
| 想换 v4-pro | 改 plugin config 的 `pricing` 为 pro 价（9.0/27.0），模型选 `deepseek-v4-pro` |

---

## 十一、边界与免责

- 立维志愿不替代省级考试院、高校招生网和官方志愿系统；不输出精确录取概率。
- 查询结果来自已入库的官方源数据（`official-sources/` 可对照原文），但当年政策请以官方最新发布为准。
- 数据层 `verified` 状态区分"已核验 / 待人工核验"来源；正式填报前建议让熟悉本省规则的老师或专业人士复核。
- 本项目非商用（CC BY-NC-SA / PolyForm Noncommercial）；用户自行承担 DeepSeek API 费用。

---

## 附：项目结构速览

```
lever-gaokao/
├── lever-gaokao/           # 数据层 + 方法论（5 省官方源、审计、归档）
├── dsh-lever-gaokao/       # 立维志愿插件（6 工具）+ 桌面端壳
│   ├── src/tools/          # intake / query / validate / cost / offpeak
│   ├── desktop/            # Tauri 桌面端（可选）
│   └── README.md           # 插件开发与挂载说明
├── official-sources/       # 官方原文归档（供人工核验）
└── GUIDE.md                # 本指南
```
