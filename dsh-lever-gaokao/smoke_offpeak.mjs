/** 冒烟测试：潜机闲时（官方峰谷基准 + 调度窗口计算）。 */
import { estimateCost, isOffPeakNow } from './lib/deepseek-pricing.js'
import { nextOffPeakAfterSeconds, offPeakWindowText } from './lib/tools/offpeak.js'

console.log('=== 潜机闲时 · 官方峰谷基准冒烟 ===\n')
console.log('官方高峰时段：9-12、14-18（北京时间），闲时半价')
console.log('官方价 v4-flash：高峰输入 3.0 / 输出 9.0（元/百万 token）\n')

const now = new Date()
console.log(`当前时间: ${now.toLocaleString('zh-CN')}`)
console.log(`当前时段: ${isOffPeakNow() ? '闲时 ✅' : '高峰 ⏳'}`)
console.log(`下一个闲时窗口 after_seconds: ${nextOffPeakAfterSeconds(now)} 秒\n`)

for (const task of ['intake', 'candidate_search', 'adversarial_review', 'full_report']) {
  const est = estimateCost(task)
  console.log(`[${task}]`)
  console.log(`  高峰 ${est.peakCostYuan} 元 | 闲时 ${est.offPeakCostYuan} 元 | 节省 ${est.savingYuan} 元 | ${est.suggestion}`)
}

console.log(`\n闲时窗口: ${offPeakWindowText()}`)

// 验证不同时刻的窗口计算
console.log('\n=== 窗口计算边界验证 ===')
const cases = [['09:30 高峰', 9, 30], ['11:59 高峰末', 11, 59], ['12:00 午间闲时', 12, 0],
               ['13:00 午间闲时', 13, 0], ['14:00 高峰午', 14, 0], ['17:59 高峰末', 17, 59],
               ['18:00 晚间闲时', 18, 0], ['07:00 凌晨闲时', 7, 0]]
for (const [label, h, m] of cases) {
  const d = new Date(2026, 7, 17, h, m, 0)
  console.log(`  ${label} → after=${nextOffPeakAfterSeconds(d)}s, 闲时=${isOffPeakNow(h)}`)
}
console.log('\n✅ 潜机闲时冒烟通过')
