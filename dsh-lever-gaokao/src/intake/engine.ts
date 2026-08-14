/**
 * 潜机问诊：无状态问诊引擎。
 *
 * 模型是问诊状态的载体（在对话中维护 collected），工具根据已收集字段计算
 * "下一步该问的问题"：先补齐 required（决定方案边界），再按层推进 important，
 * optional 可延后。每层限 MAX_PER_CALL 个问题，避免一次性抛出过多。
 */

import { QUESTIONS, LAYER_NAMES, MAX_PER_CALL, type IntakeQuestion } from './questions.js'

export interface IntakeState {
  /** 已收集字段：field → 用户回答 */
  collected: Record<string, string>
}

export interface IntakeResult {
  done: boolean
  /** 下一步该问的问题（模型应通过 ask_user_question 逐一询问） */
  missing: IntakeQuestion[]
  /** 各层覆盖情况 */
  coverage: { layer: number; name: string; answered: number; total: number }[]
  /** 一句话状态说明（给模型） */
  note: string
}

export function nextIntakeQuestions(state: IntakeState): IntakeResult {
  const collected = state.collected ?? {}

  // 缺 required（决定边界）→ 先补齐
  const missingRequired = QUESTIONS.filter(
    (q) => q.priority === 'required' && !collected[q.field],
  )
  if (missingRequired.length > 0) {
    return result(false, state, missingRequired.slice(0, MAX_PER_CALL),
      `还缺 ${missingRequired.length} 个必要信息（决定方案边界）：${missingRequired.map((q) => q.label).join('、')}。请用 ask_user_question 逐一询问。`)
  }

  // required 齐了 → 按层推进 important（层 2-6 为主，7-9 延后）
  const missingImportant = QUESTIONS.filter(
    (q) => q.priority === 'important' && !collected[q.field],
  )
  if (missingImportant.length > 0) {
    // 按层分组，取最早未完成层的最多 MAX_PER_CALL 个
    const byLayer = new Map<number, IntakeQuestion[]>()
    for (const q of missingImportant) {
      if (!byLayer.has(q.layer)) byLayer.set(q.layer, [])
      byLayer.get(q.layer)!.push(q)
    }
    const nextLayer = Math.min(...byLayer.keys())
    const batch = byLayer.get(nextLayer)!.slice(0, MAX_PER_CALL)
    const remaining = byLayer.get(nextLayer)!.length - batch.length
    const note = `第 ${nextLayer} 层「${LAYER_NAMES[nextLayer]}」待收集${batch.length}项`
      + (remaining > 0 ? `（本层还有 ${remaining} 项待问）` : '')
      + `。请用 ask_user_question 逐一询问，收集后再次调用本工具推进。`
    return result(false, state, batch, note)
  }

  // 全部重要字段齐 → 可进入完整分析（optional 视情况问）
  const missingOptional = QUESTIONS.filter(
    (q) => q.priority === 'optional' && !collected[q.field],
  )
  const note = missingOptional.length > 0
    ? `核心信息已齐（边界+策略字段完整）。可选补充：${missingOptional.map((q) => q.label).join('、')}。可直接开始候选发现；如需更完整画像可再问 1-2 项。`
    : '问诊信息已完整，可直接开始完整志愿分析。'
  return result(true, state, missingOptional.slice(0, MAX_PER_CALL), note)
}

function result(
  done: boolean,
  state: IntakeState,
  missing: IntakeQuestion[],
  note: string,
): IntakeResult {
  const collected = state.collected ?? {}
  const coverage = QUESTIONS.reduce<IntakeResult['coverage']>((acc, q) => {
    const layer = q.layer
    let entry = acc.find((e) => e.layer === layer)
    if (!entry) {
      entry = { layer, name: LAYER_NAMES[layer] ?? String(layer), answered: 0, total: 0 }
      acc.push(entry)
    }
    entry.total += 1
    if (collected[q.field]) entry.answered += 1
    return acc
  }, [])
  return { done, missing, coverage, note }
}
