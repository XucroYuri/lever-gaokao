/**
 * DeepSeek API 定价（官方峰谷基准，2026-08-17 生效）。
 *
 * 来源：DeepSeek 官方公告（2026-08-13，微信公众号/官网，IT之家等转载一致）。
 * 高峰时段：北京时间 9:00-12:00、14:00-18:00；其余为空闲时段，闲时=高峰价一半。
 *
 * 价格单位：元 / 百万 tokens。
 */

export interface DeepSeekPricing {
  /** 高峰输入价（缓存未命中）元/百万 token */
  inputPerM: number
  /** 高峰输出价 元/百万 token */
  outputPerM: number
  /** 高峰输入价（缓存命中）元/百万 token */
  inputCacheHitPerM: number
  /** 闲时系数（官方=0.5） */
  offPeakFactor: number
}

/** 官方价格：deepseek-v4-flash（默认，便宜好用，本项目推荐模型） */
export const V4_FLASH_PRICING: DeepSeekPricing = {
  inputPerM: 3.0,
  outputPerM: 9.0,
  inputCacheHitPerM: 0.1,
  offPeakFactor: 0.5,
}

/** 官方价格：deepseek-v4-pro */
export const V4_PRO_PRICING: DeepSeekPricing = {
  inputPerM: 9.0,
  outputPerM: 27.0,
  inputCacheHitPerM: 0.3,
  offPeakFactor: 0.5,
}

export const DEFAULT_PRICING: DeepSeekPricing = V4_FLASH_PRICING

/** 官方高峰时段（北京时间）：9-12 与 14-18 */
export function isPeakHour(hour: number = new Date().getHours()): boolean {
  return (hour >= 9 && hour < 12) || (hour >= 14 && hour < 18)
}

/** 当前是否闲时 */
export function isOffPeakNow(hour: number = new Date().getHours()): boolean {
  return !isPeakHour(hour)
}

/** 一次志愿分析典型 token 消耗（输入+输出；占位估算，可按实测调整） */
export interface TaskCostProfile {
  inputTokens: number
  outputTokens: number
  /** 输入中缓存命中比例（0-1，占位，通常系统提示与多轮历史可命中） */
  cacheHitRatio: number
}

export const TASK_PROFILES: Record<string, TaskCostProfile> = {
  intake: { inputTokens: 20_000, outputTokens: 4_000, cacheHitRatio: 0.5 },
  candidate_search: { inputTokens: 60_000, outputTokens: 10_000, cacheHitRatio: 0.3 },
  adversarial_review: { inputTokens: 100_000, outputTokens: 20_000, cacheHitRatio: 0.3 },
  full_report: { inputTokens: 200_000, outputTokens: 40_000, cacheHitRatio: 0.3 },
}

export interface CostEstimate {
  taskType: string
  model: string
  /** 高峰成本（元） */
  peakCostYuan: number
  /** 闲时成本（元） */
  offPeakCostYuan: number
  /** 闲时节省（元） */
  savingYuan: number
  /** 高峰时段（北京时间，官方） */
  peakHours: string
  /** 当前是否闲时 */
  offPeakNow: boolean
  /** 建议 */
  suggestion: string
}

/** 计算一次任务的成本估算（含缓存命中，按官方峰谷价）。 */
export function estimateCost(
  taskType: string,
  pricing: DeepSeekPricing = DEFAULT_PRICING,
): CostEstimate {
  const profile = TASK_PROFILES[taskType] ?? TASK_PROFILES.full_report
  const hit = profile.inputTokens * (profile.cacheHitRatio ?? 0)
  const miss = profile.inputTokens - hit
  const peak =
    (miss / 1_000_000) * pricing.inputPerM +
    (hit / 1_000_000) * pricing.inputCacheHitPerM +
    (profile.outputTokens / 1_000_000) * pricing.outputPerM
  const offPeak = peak * pricing.offPeakFactor
  const offPeakNow = isOffPeakNow()
  return {
    taskType,
    model: pricing === V4_PRO_PRICING ? 'deepseek-v4-pro' : 'deepseek-v4-flash',
    peakCostYuan: round2(peak),
    offPeakCostYuan: round2(offPeak),
    savingYuan: round2(peak - offPeak),
    peakHours: '9:00-12:00、14:00-18:00（北京时间）',
    offPeakNow,
    suggestion: offPeakNow
      ? '当前为闲时（价格半价），适合现在运行重任务'
      : '当前为高峰（价格翻倍），建议攒到闲时运行；可用 schedule 调度到闲时窗口',
  }
}

function round2(x: number): number {
  return Math.round(x * 100) / 100
}
