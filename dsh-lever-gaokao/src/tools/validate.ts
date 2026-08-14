/**
 * gaokao_validate 工具：数据质量校验。
 *
 * 桥接 data_ingest.py validate，返回各表行数、一分一段完整性、字段覆盖率等。
 * 校验报告用于：报告输出前确认数据可信度；区分"已核验/待人工核验"来源。
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { BridgeConfig } from '../bridge.js'
import { validateDuckdb } from '../bridge.js'

export function registerValidateTool(ctx: Context, cfg: BridgeConfig): void {
  ctx.tools.register(defineTool({
    name: 'gaokao_validate',
    description:
      '校验本地高考数据质量：各表行数、一分一段完整性、分数-位次单调性、字段覆盖率等。' +
      '输出 JSON 报告，帮助判断候选数据可信度与缺失项。',
    parameters: {},
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(_args, exec) {
      const result = await validateDuckdb(cfg)
      exec.signal.throwIfAborted()
      return JSON.stringify(result, null, 2)
    },
  }))
}
