/**
 * gaokao_intake 工具：潜机问诊推进。
 *
 * 模型每轮：调用本工具（传入已收集信息）→ 得到下一批应问的问题 →
 * 用 ask_user_question 逐一询问用户 → 收集答案 → 再次调用本工具推进，
 * 直到 done=true 开始完整志愿分析。
 *
 * 设计：无状态（模型是状态载体），遵循 guided-intake 的"先边界后策略、
 * 不一次性抛过多问题"原则。
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { nextIntakeQuestions, type IntakeState } from '../intake/engine.js'

export function registerIntakeTool(ctx: Context): void {
  ctx.tools.register(defineTool({
    name: 'gaokao_intake',
    description:
      '高考志愿问诊推进工具。输入已收集的考生信息（collected），返回下一步应问的问题清单' +
      '（含字段、问题、优先级、所属层）。流程：先补齐边界信息（省份/年份/选科/分数/位次/批次/预算/不可接受项），' +
      '再按层推进学生偏好、家庭约束、风险偏好、长期目标。拿到问题后必须用 ask_user_question 逐一询问用户，' +
      '收集答案后把 collected 合并再次调用本工具，直到 done=true 再开始志愿分析。',
    parameters: {
      collected: {
        type: 'object',
        description: '已收集的考生信息字典（字段名 → 回答）。首次调用可传空对象 {}。',
        additionalProperties: true,
      },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      // 工具参数为 JsonValue，过滤为字符串字典（用户回答都是文本）
      const collected: Record<string, string> = {}
      for (const [k, v] of Object.entries(args.collected ?? {})) {
        if (typeof v === 'string') collected[k] = v
      }
      const state: IntakeState = { collected }
      const result = nextIntakeQuestions(state)
      exec.signal.throwIfAborted()
      return JSON.stringify(result, null, 2)
    },
  }))
}
