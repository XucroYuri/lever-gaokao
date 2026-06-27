# Lever-GaoKao - 高考志愿填报智能体

<p align="center">
  <em>Life Leverage for College Admission</em><br>
  <strong>人生杠杆・高考志愿填报 Agent</strong>
</p>

<p align="center">
  <a href="#怎么开始">快速开始</a> ·
  <a href="#选择哲学">选择哲学</a> ·
  <a href="#它怎么工作">工作方式</a> ·
  <a href="#源码开放但非商用">非商用许可</a>
</p>

<p align="center">
  <img src="docs/assets/imagegen/cover.png" alt="Lever-GaoKao 封面：人生杠杆・高考志愿填报 Agent" width="100%">
</p>

`Lever-GaoKao` 是一个**AI Agent高考志愿填报辅助项目**。

它做三件事：
- 先问清孩子和家庭的真实情况，
- 再整理可选学校和专业，
- 最后把每个选择的好处、风险和还要核验的资料说清楚。

它不会替你拍板，也不会保证录取。它更像一个谨慎的助手，帮你少被焦虑、热门说法和零散信息带着走。

## 先看三句话

- 它不能代替省级考试院、高校招生网、招生章程和官方志愿系统。
- 它不是全国院校数据库，也不能给出精确录取概率。
- 它的重点是给出几条可选方向，并把依据、风险和下一步核验说清楚。

## 项目来源

项目来自本人在2025年真实的高考志愿填报实践：
- **考生情况**：家中晚辈：1名选择空间不宽的考生（高竞争省份/超低本科录取率，中位数成绩/正常报考只能读本省末流公办本科），需要在省内热门选择和全国范围的低估机会之间做取舍。
- **实践过程**：我用 AI Agent 辅助整理了数百个候选学校和专业方向，反复比较、排除、复核，最终选择了一个录取把握较稳、长期机会也不错的方案，在分数有限、资源有限的基础上，尽可能为考生选择有利于改变人生命运的志愿填报和入学之后的学业+职业生涯组合方案。
- **最终结果**：是被位于国内某一线城市外围的一所公办本科高校录取。由于特殊的入学时机，该校在考生入学后不到半年就完成了**院校合并、更名、学院->大学的档次提升*，从普通公办本科升档为值得重点关注的发展机会型中央部委直属院校。
- **后续现状**：并在就读期间积极寻求转专业/交换生/保研/考研机会，进一步提升人生跃迁机会和发展的杠杆率。

这个结果当然不是“神预测”，也不能照搬到别人身上。但它说明了一件事：只要把学校清单、资料来源、排除理由、家庭约束和未来路径记清楚，志愿填报就不必只靠印象、焦虑和跟风，提前买入潜力股，一定的时间和耐心基础上，最终会给考生/家长超出预期的回报。

## 适合谁

- 高考考生、家长、老师和公益志愿填报协助者。
- 会使用 Codex、Claude Code、Cursor、Kimi Code、OpenCode、Gemini CLI、Qwen Code、Aider、Cline/Roo Code、Continue、Zed/Zcoe、Windsurf、GitHub Copilot Coding Agent、Trae 等工具的人。
- 不想只听“热门城市 + 热门专业 + 一个标准答案”，希望把选择讲清楚、想明白的人。

## 怎么开始

### 1. 准备资料

至少准备：省份、年份、选科/科类、分数、位次、批次、预算、不可接受项、学生本人偏好、家庭约束。

只给“省份 + 分数”时，只能先粗看。最好补上位次、选科、批次和不能接受的学校/地区/专业。

### 2. 会用 Agent 工具的人这样做

Codex 用户可以使用：

```text
请使用 $lever-gaokao，先问清资料，再为一名中国高考考生生成有依据、讲风险、兼顾长期机会的志愿填报建议。
```

其他 Agent 工具可以先读取 [Skill 入口](lever-gaokao/SKILL.md)，再按需要读取 `references/`。不要一次性把所有文档塞进去。

### 3. 有表格时跑机械校验

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B lever-gaokao/scripts/ledger_tool.py selftest
python3 lever-gaokao/scripts/ledger_tool.py template --output candidates.csv
python3 lever-gaokao/scripts/ledger_tool.py validate-candidate-table candidates.csv
```

脚本只检查表格字段、状态和明显硬限制，不判断学校好坏，也不预测录取概率。

## 没有网络代理怎么办

可以使用支持本地文件读取、工具调用或自定义模型 API 的国产/开源 Agent 工具。国内模型可考虑 GLM、DeepSeek、Kimi、Qwen 等。常见做法是选择支持 OpenAI-compatible 接口的工具，再配置 `base_url`、`api_key` 和 `model`。

如果只能使用网页聊天，也可以复制 [SKILL.md](lever-gaokao/SKILL.md)、[引导式问诊](lever-gaokao/references/guided-intake.md) 和 [输入输出规范](lever-gaokao/references/input-output-schema.md) 的相关片段，让模型先问问题，再做分析。这样也能用上方法论，只是不能自动检查候选表。

## 选择哲学

<p align="center">
  <img src="docs/assets/imagegen/decision-framework.png" alt="选择框架：不是学校好坏题，而是路径取舍题" width="100%">
</p>

志愿填报不是只追热门，也不是赌运气。更重要的是：这个选择能不能录上、能不能接受，四年后有没有继续升学、就业转向或平台跃迁的空间。

## 它怎么工作

<p align="center">
  <img src="docs/assets/imagegen/workflow-convergence.png" alt="工作方式：从大量候选，到能解释的方案" width="100%">
</p>

完整分析会先问清情况，再查规则和资料，然后整理候选学校，逐步排除不合适的选择，最后给出报告、表格和入学后的行动建议。简单问题会只走必要步骤。

## 核心文档

- [Skill 入口](lever-gaokao/SKILL.md)
- [引导式问诊](lever-gaokao/references/guided-intake.md)
- [选择哲学与方法论](lever-gaokao/references/methodology.md)
- [候选清单发现与筛选](lever-gaokao/references/candidate-discovery-and-convergence.md)
- [输入输出规范](lever-gaokao/references/input-output-schema.md)
- [对外表达风格](lever-gaokao/references/communication-style.md)
- [数据与模型路线图](lever-gaokao/references/data-and-model-roadmap.md)
- [候选表工具](lever-gaokao/scripts/ledger_tool.py)

## 不要这样用

- 不要只给一个分数，就要求它直接拍板。
- 不要把第三方工具的概率当成官方录取保证。
- 不要上传身份证号、准考证号、手机号、完整住址等敏感信息。
- 不要让商业志愿填报机构把本项目包装成付费服务。
- 不要把“升格、合并、更名、捡漏、热门 AI 专业”当作确定收益。

## 后续规划

我正在继续探索：如何把这套志愿填报参考机制和 AI Agent 能力，更低门槛地提供给普通家庭、偏远地区、以及来自高考录取竞争烈度较高省份的学生和家长。

如果你有更好的公益合作、数据建设、工具落地或使用传播建议，欢迎联系我。

## 支持项目

<!-- SUPPORT-PROJECT:START -->
如果这个项目对你有帮助，可以自愿赞赏支持后续维护。赞赏不是付费咨询服务，也不构成任何结果承诺；请不要在转账备注中填写姓名、手机号、证件号等敏感信息。

<p align="center">
  <img src="https://raw.githubusercontent.com/XucroYuri/lever-gaokao/main/docs/assets/sponsor/alipay-card.png" alt="支付宝赞助二维码" width="260">
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/XucroYuri/lever-gaokao/main/docs/assets/sponsor/wechat-reward-card.png" alt="微信赞赏二维码" width="260">
</p>

<p align="center"><strong>时不我待，功不唐捐</strong></p>
<!-- SUPPORT-PROJECT:END -->

## 源码开放但非商用

本项目是公益导向的“源码开放、非商用”项目，不是 OSI 定义下的无限制开源项目。

- 文档、Skill、方法论和模板：采用 [CC BY-NC-SA 4.0](LICENSES/CC-BY-NC-SA-4.0.txt)。
- 脚本代码：采用 [PolyForm Noncommercial 1.0.0](LICENSES/PolyForm-Noncommercial-1.0.0.md)。

特别声明：
- 基于公益性目的，本项目禁止用于：商业志愿填报咨询机构、教育咨询公司、SaaS 平台、付费知识产品、内部商业工具和其他营利性服务，不得基于本项目进行二次开发、集成、训练、包装或付费交付，除非获得项目维护者的单独书面授权。详见 [LICENSE](LICENSE)、[NONCOMMERCIAL.md](NONCOMMERCIAL.md) 和 [DISCLAIMER.md](DISCLAIMER.md)。

## 贡献

- 欢迎公益方向的规则补充、信源核验、文档改进、脚本修复和压力测试。
- 请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。不要提交任何真实考生隐私信息。
