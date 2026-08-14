/**
 * DeepSeek API 定价表与峰谷计算。
 *
 * DeepSeek 自 2026-08-17 起采用峰谷定价：闲时价格为高峰时段价格的一半。
 * 定价以"元 / 百万 token"计。默认值为占位（V4 Flash 官方价请按 DeepSeek 文档
 * 填写到插件 config 的 pricing 字段），峰谷系数默认 0.5。
 *
 * 用途：gaokao_cost_estimate 工具在进问诊前估算一次分析的成本，并引导用户在
 * 闲时（如 22:00 - 次日 08:00）运行重任务，降低贫困家庭使用门槛。
 */

export interface DeepSeekPricing {
  /** 高峰输入价：元/百万 token */
  inputPerM: number
  /** 高峰输出价：元/百万 token */
  outputPerM: number
  /** 闲时系数（闲时价 = 高峰价 × offPeakFactor），默认 0.5 */
  offPeakFactor: number
}

export const DEFAULT_PRICING: DeepSeekPricing = {
  inputPerM: 1.0,
  outputPerM: 4.0,
  offPeakFactor: 0.5,
}

/** 一次志愿分析典型 token 消耗（输入+输出，单位 token；占位估算，可调） */
export interface TaskCostProfile {
  inputTokens: number
  outputTokens: number
}

export const TASK_PROFILES: Record<string, TaskCostProfile> = {
  intake: { inputTokens: 20_000, outputTokens: 4_000 }, // 多轮问诊
  candidate_search: { inputTokens: 60_000, outputTokens: 10_000 }, // 候选发现
  adversarial_review: { inputTokens: 100_000, outputTokens: 20_000 }, // 对抗式审查
  full_report: { inputTokens: 200_000, outputTokens: 40_000 }, // 完整分析
}

export interface CostEstimate {
  taskType: string
  peakCostYuan: number
  offPeakCostYuan: number
  savingYuan: number
  offPeakHours: string
  recommended: boolean
}

/** 计算一次任务的成本估算（高峰 vs 闲时）。 */
export function estimateCost(
  taskType: string,
  pricing: DeepSeekPricing = DEFAULT_PRICING,
): CostEstimate {
  const profile = TASK_PROFILES[taskType] ?? TASK_PROFILES.full_report
  const peak =
    (profile.inputTokens / 1_000_000) * pricing.inputPerM +
    (profile.outputTokens / 1_000_000) * pricing.outputPerM
  const offPeak = peak * pricing.offPeakFactor
  return {
    taskType,
    peakCostYuan: round2(peak),
    offPeakCostYuan: round2(offPeak),
    savingYuan: round2(peak - offPeak),
    offPeakHours: '22:00 - 08:00（以 DeepSeek 公告为准）',
    recommended: offPeak < peak,
  }
}

/** 判断当前是否为闲时（近似：22:00 - 08:00；正式实现应以 DeepSeek 公告时段为准）。 */
export function isOffPeakNow(hour: number = new Date().getHours()): boolean {
  return hour >= 22 || hour < 8
}

function round2(x: number): number {
  return Math.round(x * 100) / 100
}
