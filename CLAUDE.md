# Life Leverage for College Admission (Lever-GaoKao) — AI Agent Onboarding

## What It Is
An AI Agent-assisted college admission (Gaokao) volunteer application advisory project. Uses first-principles reasoning and adversarial review to identify undervalued opportunities, assess risks, and provide structured admission recommendations.

## Stack
- Python 3 (ledger validation tools)
- Markdown-based Skill + references (AI agent consumption)
- Compatible with: Codex, Claude Code, Cursor, Kimi Code, Gemini CLI, Aider, Cline, etc.

## Quick Start (Agent Users)
```
# Codex:
请使用 $lever-gaokao，先问清资料，再为一名中国高考考生生成有依据、讲风险、兼顾长期机会的志愿填报建议。

# Others: read lever-gaokao/SKILL.md, then references/ as needed
```

## Script Validation
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B lever-gaokao/scripts/ledger_tool.py selftest
python3 lever-gaokao/scripts/ledger_tool.py template --output candidates.csv
python3 lever-gaokao/scripts/ledger_tool.py validate-candidate-table candidates.csv
```

## Architecture
- `lever-gaokao/SKILL.md` — Skill entry (for AI agents)
- `lever-gaokao/references/` — 7 reference docs: guided intake, methodology, candidate discovery, schema, communication style, data roadmap
- `lever-gaokao/scripts/ledger_tool.py` — Mechanical table validation (no probability prediction)

## Quality Bar
- High-quality operation: ask before recommending, verify evidence, keep ledgers, don't fabricate.
- High-quality output: conclusion first, show evidence/risks/next steps, use plain language, include disclaimers.
- Before final delivery, run the checklist in `lever-gaokao/SKILL.md` → `高质量运行与输出质量门`.

## Key Philosophy
- Finds undervalued opportunities, not just hot cities/majors
- Adversarial review of first principles, evidence, and risks
- Does NOT replace official admission systems
- Non-commercial license: CC BY-NC-SA 4.0 (docs) + PolyForm Noncommercial (code)
