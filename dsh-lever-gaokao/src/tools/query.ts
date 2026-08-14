/**
 * gaokao_query 工具：高考志愿数据约束查询。
 *
 * 桥接 lever-gaokao Python 数据层（data_ingest.py query → DuckDB），
 * 支持按位次区间/科类/选科/学费上限/院校层级查询匹配的院校与专业。
 * 结果按位次升序，供模型作为候选发现与风险审计的依据。
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { BridgeConfig } from '../bridge.js'
import { queryDuckdb } from '../bridge.js'

export interface QueryToolConfig extends BridgeConfig {
  /** 是否允许指定 table（major/school） */
  allowTableSwitch?: boolean
}

export function registerQueryTool(ctx: Context, cfg: QueryToolConfig): void {
  ctx.tools.register(defineTool({
    name: 'gaokao_query',
    description:
      '高考志愿数据约束查询：按位次区间/科类/选科/学费上限查询本地 DuckDB 中的院校与专业' +
      '（数据来自各省考试院官方源，位次优先于分数）。用于候选发现与风险审计。' +
      '省份如 山东/浙江/北京，位次为全省排名，选科如 物理。',
    parameters: {
      province: { type: 'string', required: true, description: '省份中文名，如 山东' },
      year: { type: 'number', description: '年份，缺省用最新' },
      min_rank: { type: 'number', description: '最低位次（含），如 45000' },
      max_rank: { type: 'number', description: '最高位次（含），如 55000' },
      category: { type: 'string', description: '科类，如 综合/物理/历史（3+1+2 省份）' },
      subject: { type: 'string', description: '选科关键词，如 物理（3+3 省份选科要求）' },
      max_tuition: { type: 'number', description: '学费上限（元/年）' },
      level: { type: 'string', description: '院校层级，985 或 211' },
      table: { type: 'string', description: '查询粒度，major（专业级）或 school（院校级），默认 major' },
      limit: { type: 'number', description: '返回条数上限，默认 30' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      if (!cfg.allowTableSwitch && args.table && args.table !== 'major') {
        args.table = 'major'
      }
      const result = await queryDuckdb(cfg, {
        table: args.table,
        province: args.province,
        year: args.year,
        category: args.category,
        subject: args.subject,
        minRank: args.min_rank,
        maxRank: args.max_rank,
        maxTuition: args.max_tuition,
        level: args.level,
        limit: args.limit,
      })
      exec.signal.throwIfAborted()
      return JSON.stringify(result, null, 2)
    },
  }))
}
