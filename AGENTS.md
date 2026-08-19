# Lever-GaoKao - College Admission AI Agent
<!-- MANUAL: -->
## Purpose
AI Agent-assisted Gaokao (college admission) volunteer application advisory. Uses first-principles reasoning and adversarial review to identify undervalued opportunities and assess admission risks.

## Key Files
| File | Role |
|------|------|
| `README.md` | Full documentation with philosophy and workflow |
| `lever-gaokao/SKILL.md` | Skill entry for AI agents |
| `lever-gaokao/scripts/ledger_tool.py` | Candidate table validation tool |

## Subdirectories
| Dir | Purpose |
|-----|---------|
| `lever-gaokao/` | Core skill directory (SKILL.md + references + scripts) |
| `lever-gaokao/references/` | 7 reference docs: guided intake, methodology, candidate discovery, schema, communication style, data roadmap |
| `lever-gaokao/scripts/` | leder_tool.py for table validation |
| `docs/` | Assets, images, sponsor info |

## For AI Agents
- AI Agent skill system (compatible with Codex, Claude Code, Cursor, etc.)
- Read `lever-gaokao/SKILL.md` first, then `references/` as needed
- Script: `python3 lever-gaokao/scripts/ledger_tool.py selftest`
- Does NOT replace official admission systems or give probability predictions
- Non-commercial license: CC BY-NC-SA 4.0 + PolyForm Noncommercial

## Quality Bar
- Run high-quality: ask before recommending, verify evidence, keep ledgers, don't fabricate.
- Output high-quality: conclusion first, show evidence/risks/next steps, use plain language, include disclaimers.
- Before final delivery, run the checklist in `lever-gaokao/SKILL.md` → `高质量运行与输出质量门`.

## Dependencies
- Python 3 (for ledger validation scripts only)
