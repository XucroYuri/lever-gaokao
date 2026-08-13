# 数据层实现设计

> 使用边界：本文档是 `data-and-model-roadmap.md` 的落地实现设计，用于指导数据采集、标准化、入库、查询与人工纠正的具体建设。产出数据源决策、架构选型、schema、查询机制和试点计划。本文档描述的是"待建设"能力，不是已具备能力。
>
> 最后更新：2026-08。数据源价格、许可、覆盖范围均以 2026-08 核实为准，落地前需再次确认。

## 目录

- 决策摘要
- 数据源决策
- 架构设计
- Schema 设计（DuckDB DDL）
- 查询机制设计
- 试点计划（山东）
- 人工纠正流程
- 当年数据时限日历
- 风险与未决事项

## 决策摘要

调研后收敛出的五项核心决策（依据见各章节）：

1. **查询机制不是单一 RAG，而是"确定性 SQL 为主 + 文档 RAG 为辅"的混合架构**。约束查询（"位次 5 万、物理类、学费低于 8000"）必须走参数化 SQL 模板，既不能靠 RAG（向量无法表达不等式/排序语义），也不能靠自由 text2sql（中文企业级 text2sql 执行准确率上限约 50%，见 Falcon benchmark）。
2. **结构化数据用 DuckDB + Parquet**（列式、零依赖、版本化），**文档数据用 Qdrant/Milvus + BGE-M3**（dense+sparse 一体，中文 SOTA）。
3. **种子历史数据用 Gaokao-Compass-11M**（HuggingFace，MIT 许可，31 省 2017–2025，4 表 11.3M 行）——当前唯一可直接再分发的免费结构化数据集；但需逐省做位次/科类一致性校验。
4. **当年数据走官方源采集，试点选山东**（一分一段 HTML + 投档情况 .xls 双机器可读、免登录、历史归档格式稳定）。
5. **人工提供（咕咕数据/CnOpenData）仅作内部核对通道，不分发数据**（其协议禁止再分发，且项目为非商用 CC BY-NC-SA）。

## 数据源决策

### 分层数据源策略

| 层 | 数据源 | 用途 | 许可/限制 |
|---|---|---|---|
| 种子数据 | Gaokao-Compass-11M（HF: choucsan/zifeiren，MIT，DOI 10.57967/hf/9882） | 31 省 2017–2025 四表历史数据入库 | MIT，可再分发 ✅ |
| 官方源（当年+试点） | 山东 sdzk.cn（一分一段 HTML + 投档 .xls）、浙江 zjzs.net（投档 .xls） | 当年数据采集、跨年交叉验证 | 官方公开，事实数据，标注来源 |
| 官方聚合（复查） | 阳光高考 gaokao.chsi.com.cn（一分一段汇总页、批次线 pcx.jsp、历年分数线） | 数据复查入口、缺省兜底 | 官方，批次线为服务端渲染 HTML 可爬 |
| 人工提供（内部） | 咕咕数据 gugudata.com、CnOpenData | 人工核对、补全缺口 | **禁止随仓库分发**（协议§6），仅内部调用/核对 |
| 院校元数据 | 教育部《全国普通高等学校名单》+ zmex schools.json（2025，2919 所） | 院校维度表 | 官方/ MIT |
| 爬虫管线参考 | lifefloating/gaokao-vault（Apache-2.0）、HA7CH/gaokao-pro（一分一段 source manifest） | 自建采集管线的工程参考与官方源 URL 清单 | Apache-2.0 / 无许可（仅参考清单） |

### 各省可爬性地图（2026 实测，决定采集优先级）

| 形态 | 省份 | 难度 |
|---|---|---|
| PDF 含文本层（pdftotext） | 北京、天津、辽宁、吉林、安徽、上海 | 易 |
| HTML 表格 | 山东、广西、陕西、宁夏、重庆、河北、黑龙江、河南、内蒙古、青海、湖南、江西、山西、海南、广东 | 易 |
| ZIP 附件 | 贵州 | 易 |
| 纯图片需 OCR | 江苏、福建、湖北、四川、云南 | 难 |
| 发布晚/不完整 | 浙江（PDF 7 月才发）、甘肃、新疆 | 中 |
| 不发布逐分表 | 西藏（仅批次线） | 无 |

### 明确不采用的来源

- **淘宝/闲鱼/经管之家转卖数据**：无许可、来源不明、质量不可验证，法律与数据双重风险。
- **掌上高考 api.eol.cn**：半公开反爬接口（signsafe 签名），抓取属灰色地带，仅低频率补充，不作主源。
- **GPL-3.0 数据仓库**（如 ramwin/china-public-data）：share-alike 传染性，与 CC BY-NC-SA 组合需谨慎。

### 数据源可信度审计结论（2026-08-13 首版）

审计详情见 `data/reports/source_credibility_audit.md`（工作产物，不入库）。核心结论：

1. **官方源（山东考试院）高可信**：直接抓取官方 .xls，一分一段单调性 0 违反，累计考生 70.9 万与山东规模一致。可作正式分析基准。
2. **种子数据（GaokaoCompass）中可信**：院校位次排序符合常识（985 < 省属强校 < 普通公办 < 专科）、位次覆盖率 99.99%、最大位次与当年考生数一致——**位次字段可信**；但 min_score/plan_count/university_code/school_nature 全空、provenance 不明——**只能作高召回候选池，正式推荐前必须官方源交叉验证**。
3. **已知数据模型缺陷**：本科+专科专业混排同表（中国民航大学位次跨度 57 万即因此），查询与报告必须按 `batch` 过滤。

### verified 标志纪律（流程改进）

- 采集 → 内部校验通过 → `source_ledger.verified=True`。官方源默认高可信，聚合数据源须官方交叉验证后才可升级。
- 种子数据进入正式推荐前，须与官方源做同校同位次比对（交叉验证纪律）。

### 官方原文归档纪律（人工校验原文对照）

- **所有下载的官方数据/文件源版**（PDF/xls）按 **数据类别 → 省份 → 年份** 归档到
  `official-sources/`（随仓库提交）：`yifenyiduan/`、`toudang/`，后续扩展 `plan/`、`schools/`、`rules/`。
- **PDF 数据必须人工校验后才最终入库**：解析依赖文本层（可能有个别字符乱码），入库时
  `source_ledger.verified=False`（待人工核验），人工对照 `official-sources/` 原文抽查
  （建议最高分段/中段/低分段各 1 处）通过后才标记 `True`。
- 归档文件为官方公开发布文件，仅作公益性原文对照与核验用途；来源记录见 `source_ledger`。

## 架构设计

```
                          ┌────────────────────────────────────────────┐
   用户/Agent 查询 ──────▶ │  查询路由（3 层，最廉价者优先）              │
                          └────────────────────────────────────────────┘
   │ 第 1 层：确定性槽位提取器（规则/正则，无 LLM）——位次/分数/学费/省份/年份/选科/批次
   ├─────────────────────────────────────────────▶ SQL：参数化模板
   │ 第 2 层：LLM 分类器（单字输出 sql | rag | hybrid）
   ├─────────────────────────────────────────────▶ RAG
   │ 第 3 层：混合合成器（SQL 结果 → 向量查询 → 融合）
   ▼
┌────────────────────────────┐        ┌──────────────────────────────┐
│ DuckDB（Parquet 事实/维度表）│        │ 向量库 Qdrant/Milvus          │
│  score_range               │        │  BGE-M3 dense + sparse        │
│  admission_school          │        │  chunk 元数据：province, year, │
│  admission_major           │        │  school_id, section_path      │
│  enrollment_plan           │        │  （招生章程 → Laws 式分块）     │
│  school_dim / major_dim    │        └──────────────────────────────┘
│  source_ledger / correction│
└────────────────────────────┘
```

### 选型依据（要点）

- **DuckDB**：列式、零依赖、直接查询 Parquet/CSV、支持版本化数据仓库；DB-GPT 已有一等公民的 duckdb datasource 连接器，证明其作为 RAG 系统结构化层的可行性。
- **BGE-M3**：单次推理产出 dense + sparse（BM25 等价）+ ColBERT 三向量，8192 token，中文 SOTA，无需指令前缀；sparse 模式在长文档检索上比 dense 强约 10 点。
- **RAGFlow DeepDoc + Laws 分块模板**：招生章程与中文法律文档结构同构（总则→组织机构→招生计划→录取规则→收费标准→附则，第X章/第X条），Laws 模板的 `tree_merge` + `第X章/第X条` 正则检测 + 表内分块"保留章节标题路径作为检索上下文"是现成最优解。
- **不在 DuckDB 里做向量检索（vss 扩展）**：vss 仍实验性、索引驻留内存、且**不支持混合标量+向量过滤下推**（issue #35）。结构化与向量分离到两个存储。
- **约束查询禁止自由 text2sql**：中文企业级 text2sql（Falcon benchmark）无模型超过 50% 执行准确率，4 表以上 join 错误率 78.57%。约束查询用槽位填充（NL2DSL）而非 SQL 合成。

## Schema 设计（DuckDB DDL）

### 事实表

```sql
-- 一分一段表
CREATE TABLE score_range (
    province      VARCHAR,      -- 省份
    year          SMALLINT,     -- 年份
    category      VARCHAR,      -- 物理类/历史类/理科/文科/综合
    score         SMALLINT,     -- 分数
    num_people    INTEGER,      -- 本分段人数
    accumulate    INTEGER,      -- 累计人数（>= score）
    source_id     VARCHAR,      -- 来源 ledger 外键
    PRIMARY KEY (province, year, category, score)
);

-- 院校投档线表
CREATE TABLE admission_school (
    province      VARCHAR,
    year          SMALLINT,
    school_code   VARCHAR,      -- 院校代码（省内）
    school_name   VARCHAR,
    category      VARCHAR,      -- 科类/选科
    batch         VARCHAR,      -- 批次
    major_group   VARCHAR,      -- 专业组（新高考）
    min_score     SMALLINT,     -- 最低分
    min_rank      INTEGER,      -- 最低位次
    avg_score     SMALLINT,
    max_score     SMALLINT,
    admit_count   INTEGER,      -- 录取/投档人数
    is_985        BOOLEAN,
    is_211        BOOLEAN,
    source_id     VARCHAR
);

-- 专业录取表
CREATE TABLE admission_major (
    province      VARCHAR,
    year          SMALLINT,
    school_code   VARCHAR,
    major_code    VARCHAR,      -- 专业代码
    major_name    VARCHAR,
    major_group   VARCHAR,
    category      VARCHAR,
    batch         VARCHAR,
    min_score     SMALLINT,
    min_rank      INTEGER,
    avg_score     SMALLINT,
    admit_count   INTEGER,
    subject_req   VARCHAR,      -- 选科要求
    source_id     VARCHAR
);

-- 招生计划表
CREATE TABLE enrollment_plan (
    province      VARCHAR,
    year          SMALLINT,
    school_code   VARCHAR,
    major_code    VARCHAR,
    major_group   VARCHAR,
    category      VARCHAR,
    batch         VARCHAR,
    plan_count    INTEGER,      -- 计划招生人数
    tuition       INTEGER,      -- 学费（元/年）
    campus        VARCHAR,      -- 校区
    subject_req   VARCHAR,
    source_id     VARCHAR
);
```

### 维度表

```sql
-- 院校维度
CREATE TABLE school_dim (
    school_code    VARCHAR PRIMARY KEY,
    school_name    VARCHAR,
    school_nature  VARCHAR,     -- 公办/民办/中外合作/职业本科
    authority      VARCHAR,     -- 主管部门/行业背景
    city           VARCHAR,
    is_985         BOOLEAN,
    is_211         BOOLEAN,
    is_double_first BOOLEAN,    -- 双一流
    has_graduate_school BOOLEAN, -- 硕博点
    has_recommendation BOOLEAN,  -- 推免资格
    source_id      VARCHAR
);

-- 专业维度
CREATE TABLE major_dim (
    major_code     VARCHAR PRIMARY KEY,
    major_name     VARCHAR,
    discipline     VARCHAR      -- 学科门类
);
```

### 治理表（贯穿数据层，对应现有 ledger 约定）

```sql
-- 来源治理
CREATE TABLE source_ledger (
    source_id      VARCHAR PRIMARY KEY,
    source_name    VARCHAR,
    source_type    VARCHAR,     -- 当年官方/近年官方/开放数据/商业API/口碑线索/用户提供
    source_url     VARCHAR,
    license        VARCHAR,
    fetch_time     TIMESTAMP,
    province       VARCHAR,
    year           SMALLINT,
    data_type      VARCHAR,     -- 一分一段/院校投档线/专业录取/招生计划/章程
    sha256         VARCHAR,
    verified       BOOLEAN      -- 是否已与官方交叉核验
);

-- 人工纠错
CREATE TABLE correction_log (
    correction_id  INTEGER PRIMARY KEY,
    table_name     VARCHAR,
    row_pk         VARCHAR,     -- 被纠错行的主键
    field          VARCHAR,
    old_value      VARCHAR,
    new_value      VARCHAR,
    reason         VARCHAR,
    corrector      VARCHAR,
    corrected_time TIMESTAMP,
    source_id      VARCHAR
);
```

### GaokaoCompass → 本 schema 映射

| GaokaoCompass 表（11.3M 行） | 映射到 | 行数（约） |
|---|---|---|
| score-range（一分一段） | `score_range` | 20.5 万 |
| school-admission（院校投档线） | `admission_school` | 76.4 万 |
| major-admission（专业录取） | `admission_major` | 449.7 万 |
| enrollment-plan（招生计划） | `enrollment_plan` | 586.2 万 |

**入库前强制校验**（研究发现的已知缺陷）：① 老高考省份部分 school-admission 行 `category` 为空 → 需按批次/科类回填；② 个别 `min_rank` 与 `min_score` 不自洽（如鞍山师范学院 193 分位次 103,279 与同批郑州科技学院 185 分位次 345,303 矛盾）→ 需逐省做"分数-位次单调性"校验；③ HF 数据集查看器因多表列不一致报错 → 必须直接下载原始 CSV，勿用 `load_dataset` 默认方式。

## 查询机制设计

### 查询分类与路由

| 查询类型 | 示例 | 路由 | 机制 |
|---|---|---|---|
| 约束查询（数值/范围谓词） | "位次 5 万、物理类、学费 < 8000 的学校" | 第 1 层 | 参数化 SQL 模板（槽位填充，非自由 text2sql） |
| 文档查询（语义/政策） | "这所学校的转专业政策是什么" | 第 2 层 → RAG | 向量检索 + 元数据过滤（province/year/school_id） |
| 混合查询（事实 + 文档） | "位次 5 万的学校里，哪些的章程限制体检" | 第 3 层 | SQL 先取 school_id → 向量检索带 ID 过滤 → 融合 |

### 约束查询模板（核心能力）

槽位提取器识别：位次（±范围，考虑一分一段同分段与大小年波动）、分数、科类/选科、学费上限、省份、年份、批次。模板：

```sql
SELECT s.*, m.major_name, e.tuition
FROM admission_major m
JOIN school_dim s ON s.school_code = m.school_code
WHERE m.province = ? AND m.year = ?
  AND m.category = ?            -- 物理类
  AND m.min_rank BETWEEN ? AND ? -- 位次区间（含安全边际）
  AND m.tuition < ?              -- 学费上限
ORDER BY s.is_211 DESC, m.min_rank;
```

### 文档 RAG 设计

- **分块**：招生章程用 RAGFlow Laws 式分块（`第X章/第X条` 章节树 + 表内分块保留章节标题路径）。
- **嵌入**：BGE-M3（dense + sparse 一体）。
- **检索**：混合检索（dense 权重 1.0 + sparse 0.7，Milvus WeightedRanker 参考值）+ bge-reranker-v2-m3 重排（中文实测 +10–15% 命中率）。
- **元数据过滤**：province/year/school_id 作为过滤字段（cardinality-collapsing，应在 SQL/前置过滤而非后过滤，避免 top_k 遗漏）。
- **一分一段表不进向量库**：表格数据一律走 DuckDB。

## 试点计划（山东）

选山东为首个试点省份，理由：一分一段 HTML 表 + 投档情况 .xls 双机器可读、免登录、`sdzk.cn/NewsList.aspx?BCID=1198` 历史归档逐年格式稳定、且山东"专业+院校"志愿模式与 lever-gaokao 冲稳保逻辑最契合。

试点步骤：

1. 采集 2017–2025 山东一分一段 + 投档情况表（官方源）。
2. 用 GaokaoCompass 山东数据做交叉验证（同省同年度量一致性）。
3. 标准化入库 DuckDB，跑"分数-位次单调性"与"科类回填"校验。
4. 产出校验报告 → 进入人工纠正流程。
5. 试点通过后，将采集脚本模板化推广到第二梯队（浙江投档线 .xls、贵州 ZIP、北京/天津/辽宁 PDF 文本层）。

## 人工纠正流程

```
采集/入库 ──▶ 自动校验（字段完整性/单调性/科类一致性/来源sha256）
                │
                ├─ 通过 ──▶ 标记 verified=true，进入查询层
                │
                └─ 失败 ──▶ 生成校验报告（问题行+预期值+来源证据）
                              │
                              ▼
                        人工核验（对照官方源）
                              │
                              ▼
                        写入 correction_log（表名+主键+字段+旧值+新值+理由+纠错人+时间）
                              │
                              ▼
                        版本化回写（新增版本，不覆盖原始行，保留 provenance）
```

原则：**不覆盖原始采集数据，纠错以增量版本叠加**（对应项目"不覆盖原始资料、每次处理生成新文件保留版本"的既有纪律）。纠错记录可追溯、可回滚。

## 当年数据时限日历

高考数据管道是事件驱动 + 硬截止。硬截止①（出分前完成招生计划全量采集）是全局安全线，硬截止②（一分一段 48h 内采集）是最高压环节。

| 时间窗 | 数据项 | 动作 | 截止性质 |
|---|---|---|---|
| 前一年 9 月–当年 3 月 | 招生工作规定、政策变化、选科调整 | 跟踪教育部+各省考试院 | 软截止 |
| 当年 3–5 月 | 招生章程、招生计划预发布、院校更名/合并/新增硕博点 | 批量采集+人工录入院校状态变化 | 软截止 |
| 5 月底–6 月初 | 完整招生计划书/专业组目录 | **出分前完成全量采集** | 硬截止① |
| 6 月下旬出分后 | 省控线、一分一段表 | **48h 内采集+校验** | 硬截止② |
| 6 月底–7 月初填报期 | 填报系统动态数据、计划变更 | 每日刷新 | 硬截止③ |
| 7 月投档期 | 投档线、专业组投档分 | 出线后 24h 入库 | 硬截止④ |
| 7–8 月征集期 | 征集志愿计划、缺额 | 每轮征集实时更新 | 硬截止⑤ |
| 9–12 月 | 专业录取分、录取统计、复盘 | 下一年回测与校准 | 软截止 |

## 风险与未决事项

1. **GaokaoCompass 数据原始出处不明**（疑聚合自 eol/chsi）——MIT 许可可再分发，但 provenance 需自建 source_ledger 补全，不能依赖其"官方清洗"声明。
2. **咕咕数据/CnOpenData 具体报价与确切年份范围未直接核实**（订单页需登录、销售渠道）——下单前需与销售确认。
3. **掌上高考/阳光高考接口可能随时变更**——官方源采集是正道，爬虫仅作补充，保持低频率。
4. **BGE-M3 嵌入模型选定后不可更换**（换模型需全量重建索引）——day one 定死 BGE-M3。
5. **西藏无逐分表、江苏/福建/湖北/四川/云南需 OCR**——这些省份当年数据需人工提供或 OCR 管线，排后处理。
6. **本设计尚未实现**——下一阶段任务：v1 采集脚本 + DuckDB 建库 + 查询模板。
