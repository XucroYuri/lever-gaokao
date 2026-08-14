/** 冒烟测试：验证 dsh-lever-gaokao 工具执行路径能真实调用 Python 数据层。 */
import { queryDuckdb, validateDuckdb } from './lib/bridge.js'
import { estimateCost, isOffPeakNow } from './lib/deepseek-pricing.js'

const cfg = {
  python: 'python',
  scriptDir: 'E:/Code/Github/lever-gaokao/lever-gaokao/scripts',
  dataDir: 'E:/Code/Github/lever-gaokao/data',
  timeoutMs: 120_000,
}

async function main() {
  console.log('=== 1. gaokao_query: 山东 2024 位次 45000-55000 选科物理（admission_major 种子数据）===')
  const q = await queryDuckdb(cfg, {
    province: '山东', year: 2024, minRank: 45000, maxRank: 55000, subject: '物理', limit: 3,
  })
  const arr = Array.isArray(q) ? q : [q]
  console.log('  返回行数:', arr.length)
  for (const row of arr.slice(0, 3)) {
    console.log('  ', JSON.stringify(row))
  }

  console.log('\n=== 2. gaokao_validate: 数据质量 ===')
  const v = await validateDuckdb(cfg)
  const tables = (v && typeof v === 'object' && 'tables' in v) ? v.tables : {}
  console.log('  score_range 行数:', tables.score_range?.rows, '| admission_major:', tables.admission_major?.rows)

  console.log('\n=== 3. gaokao_cost_estimate: 成本估算 ===')
  const e = estimateCost('full_report')
  console.log('  完整分析 高峰:', e.peakCostYuan, '元 / 闲时:', e.offPeakCostYuan, '元 / 当前闲时:', isOffPeakNow())

  console.log('\n✅ 冒烟测试通过：三个工具执行路径均可工作')
}

main().catch((err) => {
  console.error('❌ 失败:', err.message ?? err)
  process.exit(1)
})
