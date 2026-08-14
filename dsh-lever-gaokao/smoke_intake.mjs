/** 冒烟测试：潜机问诊引擎的多轮推进流程。 */
import { nextIntakeQuestions } from './lib/intake/engine.js'

let collected = {}
let round = 0
console.log('=== 潜机问诊引擎冒烟测试（模拟多轮问诊）===\n')

while (true) {
  round++
  const r = nextIntakeQuestions({ collected })
  console.log(`--- 第 ${round} 轮 ---`)
  console.log(`note: ${r.note}`)
  if (r.done) {
    if (r.missing.length > 0) {
      console.log(`可选补充: ${r.missing.map((q) => q.label).join('、')}`)
    }
    console.log('\n✅ 问诊完成')
    console.log(`覆盖: ${r.coverage.map((c) => `${c.name} ${c.answered}/${c.total}`).join(' | ')}`)
    break
  }
  // 模拟用户回答每个问题
  for (const q of r.missing) {
    collected[q.field] = `[${q.label}的回答]`
    console.log(`  问「${q.question}」 → 用户回答（模拟）`)
  }
  if (round > 12) { console.log('⚠️ 超过 12 轮，终止'); break }
}
