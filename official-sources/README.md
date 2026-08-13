# official-sources - 官方源数据原文归档

本目录按**数据类别 → 省份 → 年份**归档从各省教育考试院下载的**官方公开原始文件**，
用于：

1. **人工校验原文对照**：所有解析入库的数据，最终必须由人工对照本目录原文文件逐项核验后
   才能标记 `verified=True`。PDF 数据尤其如此（解析依赖文本层，可能存在个别字符乱码）。
2. **可审计性**：任何入库数据都可追溯到原始官方文件。
3. **可复现性**：采集、解析、入库流程可基于本目录原文重放。

## 目录结构

```
official-sources/
├── README.md
├── yifenyiduan/                    # 一分一段表（分数/本段人数/累计人数）
│   └── {province}/{year}/yifenyiduan.{pdf|xls}
└── toudang/                        # 投档线（院校/专业/分数/位次/计划数）
    └── {province}/{year}/toudang.xls
```

分类规则：**数据类别**（yifenyiduan=一分一段、toudang=投档线；后续扩展：
plan=招生计划、schools=院校名单、rules=规则政策）→ **省份**（拼音小写）→ **年份**。

## 当前归档清单

| 分类 | 文件 | 来源 | 关联数据表 | verified |
|---|---|---|---|---|
| yifenyiduan | `beijing/2026/yifenyiduan.pdf`（10 页） | [北京教育考试院](https://www.bjeea.cn/html/gkgz/tzgg/2026/0624/88238.html) | score_range | 待人工核验 |
| yifenyiduan | `liaoning/2026/wuli.pdf`（物理类）+ `lishi.pdf`（历史类） | [辽宁招生考试之窗](https://www.lnzsks.com) | score_range | 待人工核验 |
| yifenyiduan | `guizhou/2026/wuli.pdf`（物理类）+ `lishi.pdf`（历史类） | [贵州省招生考试院](http://zsksy.guizhou.gov.cn) | score_range | 待人工核验 |
| yifenyiduan | `shandong/2026/yifenyiduan.xls` | sdzk.cn NewsID=7258 | score_range | True（Excel 直采+校验） |
| toudang | `shandong/2026/toudang.xls` | sdzk.cn NewsID=7312 | shandong_toudang_2026 | True（Excel 直采+校验） |
| toudang | `zhejiang/2026/toudang.xls` | [zjzs.net art_45_12550](https://www.zjzs.net/art/2026/7/21/art_45_12550.html) | zhejiang_toudang_2026 | True（Excel 直采+校验） |

> 注：
> - `shandong_toudang_2026.min_score` 为经官方一分一段位次反查的派生值（原表只有位次），原文对照时请同时核对 `yifenyiduan/shandong/2026/yifenyiduan.xls`。
> - 辽宁/贵州为 3+1+2 模式，一分一段按 物理类/历史类 分卷；贵州格式为宽表（分数从最高分列到 0 分，有分数才列出）。

## 核验流程（数据入库纪律）

1. **采集归档**：采集器从省级考试院官方发布页下载原始文件，保存到本目录（原始文件，不修改），
   同时解析入 DuckDB。
2. **解析**：xls 用 python-calamine，PDF 用 pypdf 提取文本层。
3. **人工对照核验**：由人工对照本目录原文抽查（建议抽 3 处：最高分段、中段、低分段），
   确认解析正确。PDF 可能有个别字符乱码（字体编码问题），但数据行已验证可完整解析。
4. **标记**：核验通过后在 `source_ledger.verified` 标记 `True`；未核验前保持 `False`（待人工核验）。
5. **入库**：核验通过后的数据才作为正式分析基准。

## 来源与许可说明

- 所有文件均为**省级教育考试院官方公开发布**的数据文件，属政府公开信息，收录仅为公益性
  原文对照与核验用途。
- 每份文件在 `source_ledger` 中有对应记录（来源 URL、类型、许可、verified 状态）。
- 若来源方要求移除，可随时删除对应文件并更新本说明。
