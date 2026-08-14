/**
 * gaokao_cost_estimate 工具：DeepSeek API 成本估算与峰谷建议。
 *
 * 在进问诊前估算一次分析（按任务类型）的 API 成本，对比高峰/闲时价格，
 * 引导用户把重任务（候选发现、对抗审查、完整报告）安排在闲时运行，降低
 * 贫困家庭的使用门槛。定价表可在插件 config 中按官方价覆盖。
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { DeepSeekPricing } from '../deepseek-pricing.js'
import { DEFAULT_PRICING, estimateCost, isOffPeakNow, TASK_PROFILES } from '../deepseek-pricing.js'

export interface CostToolConfig {
  pricing?: DeepSeekPricing
}

export function registerCostTool(ctx: Context, cfg: CostToolConfig = {}): void {
  const pricing = { ...DEFAULT_PRICING, ...cfg.pricing }
  ctx.tools.register(defineTool({
    name: 'gaokao_cost_estimate',
    description:
      '估算一次志愿分析任务的 DeepSeek API 成本（元），并对比高峰/闲时价格。' +
      '任务类型：intake（问诊）、candidate_search（候选发现）、adversarial_review（对抗审查）、' +
      'full_report（完整分析）。用于引导用户在闲时运行重任务以省钱。',
    parameters: {
      task_type: {
        type: 'string',
        description: '任务类型，可选 intake/candidate_search/adversarial_review/full_report',
      },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      const estimate = estimateCost(args.task_type ?? 'full_report', pricing)
      const offPeak = isOffPeakNow()
      const lines = [
        `任务类型: ${estimate.taskType}`,
        `高峰价格: 约 ${estimate.peakCostYuan} 元`,
        `闲时价格: 约 ${estimate.offPeakCostYuan} 元（${estimate.offPeakHours}）`,
        `闲时节省: 约 ${estimate.savingYuan} 元`,
        `当前时段: ${offPeak ? '闲时 ✅ 建议现在运行' : '高峰 ⏳ 重任务建议攒到闲时运行'}`,
      ]
      return lines.join('\n')
    },
  }))
}

export { TASK_PROFILES }
