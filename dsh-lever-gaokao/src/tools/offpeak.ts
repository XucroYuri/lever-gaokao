/**
 * gaokao_offpeak 工具：潜机闲时。
 *
 * 判断当前是否为 DeepSeek 官方峰谷定价的闲时（官方高峰：北京时间 9-12、14-18；
 * 其余闲时，闲时=高峰半价），给出重任务调度建议：成本对比 + 下一个闲时窗口的
 * after_seconds（供 dsh 的 schedule_create 工具把重任务排到闲时执行）。
 *
 * 典型用法（高峰时段）：模型调用本工具 → 得到 after_seconds → 调用 schedule_create
 * 把候选发现/对抗审查/完整报告排到闲时窗口自动执行，为平民家庭省钱。
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { estimateCost, isOffPeakNow, type DeepSeekPricing } from '../deepseek-pricing.js'

export interface OffPeakToolConfig {
  pricing?: DeepSeekPricing
}

/** 下一个闲时窗口开始的秒数（当前已是闲时则返回 0）。 */
export function nextOffPeakAfterSeconds(now: Date = new Date()): number {
  const h = now.getHours()
  const m = now.getMinutes()
  const cur = h * 60 + m
  let target: number | null = null
  if (cur >= 9 * 60 && cur < 12 * 60) target = 12 * 60 // 高峰上午 → 午间闲时 12:00
  else if (cur >= 14 * 60 && cur < 18 * 60) target = 18 * 60 // 高峰下午 → 晚间闲时 18:00
  if (target === null) return 0 // 已处闲时（0-9 / 12-14 / 18-24）
  return (target - cur) * 60
}

/** 闲时窗口描述（北京时间） */
export function offPeakWindowText(): string {
  return '闲时：0:00-9:00、12:00-14:00、18:00-24:00（北京时间）'
}

export function registerOffPeakTool(ctx: Context, cfg: OffPeakToolConfig = {}): void {
  const pricing = cfg.pricing
  ctx.tools.register(defineTool({
    name: 'gaokao_offpeak',
    description:
      '潜机闲时：判断当前是否为 DeepSeek 峰谷定价的闲时（官方高峰 9-12、14-18，闲时半价），' +
      '输出任务成本对比与调度建议。若当前为高峰，返回下一个闲时窗口的 after_seconds，' +
      '模型应配合 schedule_create 工具把重任务（候选发现/对抗审查/完整报告）调度到闲时执行，' +
      '为家庭节省 API 成本。',
    parameters: {
      task_type: {
        type: 'string',
        description: '任务类型：intake/candidate_search/adversarial_review/full_report',
      },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      const est = estimateCost(args.task_type ?? 'full_report', pricing)
      const offPeakNow = isOffPeakNow()
      const afterSeconds = nextOffPeakAfterSeconds()
      const payload = {
        ...est,
        off_peak_windows: offPeakWindowText(),
        schedule_hint: offPeakNow
          ? { action: 'run_now', note: '当前闲时，直接运行' }
          : {
              action: 'schedule_to_offpeak',
              note: `当前高峰（贵 ${est.savingYuan} 元），建议 schedule_create 排到闲时`,
              after_seconds: afterSeconds,
              target: new Date(Date.now() + afterSeconds * 1000).toLocaleString('zh-CN'),
            },
      }
      exec.signal.throwIfAborted()
      return JSON.stringify(payload, null, 2)
    },
  }))
}
