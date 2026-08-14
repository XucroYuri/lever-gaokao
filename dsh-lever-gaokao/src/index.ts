/**
 * dsh-lever-gaokao 插件入口。
 *
 * 注册 3 个模型可见工具到 ctx.tools：
 *  - gaokao_query          高考志愿数据约束查询（桥接 DuckDB）
 *  - gaokao_validate       数据质量校验
 *  - gaokao_cost_estimate  DeepSeek API 成本估算 + 峰谷引导
 *
 * 插件 config（在 cordis.patch.yml 中配置）：
 *  - python:     Python 可执行文件，默认 'python'
 *  - scriptDir:  lever-gaokao/scripts 绝对路径（必填）
 *  - dataDir:    DuckDB 数据目录，默认 scripts 同级 ../data
 *  - pricing:    DeepSeek 定价覆盖（inputPerM/outputPerM/offPeakFactor）
 */

import type { Context } from '@deepseek-ai/cordis'
import type { BridgeConfig } from './bridge.js'
import { registerQueryTool } from './tools/query.js'
import { registerValidateTool } from './tools/validate.js'
import { registerCostTool } from './tools/cost.js'
import type { DeepSeekPricing } from './deepseek-pricing.js'

export const name = 'dsh-lever-gaokao'
export const inject = ['tools']

export interface GaokaoConfig {
  bridge: BridgeConfig
  pricing?: DeepSeekPricing
  allowTableSwitch?: boolean
}

export function apply(ctx: Context, config: Partial<GaokaoConfig> = {}): void {
  const bridge: BridgeConfig = {
    python: config.bridge?.python ?? 'python',
    scriptDir: config.bridge?.scriptDir ?? '../lever-gaokao/scripts',
    dataDir: config.bridge?.dataDir ?? '../data',
    timeoutMs: config.bridge?.timeoutMs,
  }
  registerQueryTool(ctx, { ...bridge, allowTableSwitch: config.allowTableSwitch })
  registerValidateTool(ctx, bridge)
  registerCostTool(ctx, { pricing: config.pricing })
}
