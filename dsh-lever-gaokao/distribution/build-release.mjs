/**
 * 立维志愿三平台打包脚本（@yao-pkg/pkg SEA 单文件可执行）。
 *
 * 产物（out/）：
 *   立维志愿-win-x64.exe / 立维志愿-win-arm64.exe
 *   立维志愿-mac-x64 / 立维志愿-mac-arm64
 *   立维志愿-linux-x64 / 立维志愿-linux-arm64
 *
 * 用法：npm run build:release  （先 npm run build 产出 lib/index.js）
 */

import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const ROOT = resolve(import.meta.dirname)
const OUT = resolve(ROOT, 'out')
const ENTRY = resolve(ROOT, 'lib', 'index.js')

/** pkg 目标：node24（SEA 模式需要 Node 22+；与 dsh 官方打包一致） */
const TARGETS = [
  ['node24-win-x64', '立维志愿-win-x64.exe'],
  ['node24-win-arm64', '立维志愿-win-arm64.exe'],
  ['node24-macos-x64', '立维志愿-mac-x64'],
  ['node24-macos-arm64', '立维志愿-mac-arm64'],
  ['node24-linux-x64', '立维志愿-linux-x64'],
  ['node24-linux-arm64', '立维志愿-linux-arm64'],
]

if (!existsSync(ENTRY)) {
  console.error('[立维志愿] 未找到 lib/index.js，请先运行: npm run build')
  process.exit(1)
}
mkdirSync(OUT, { recursive: true })

for (const [target, outName] of TARGETS) {
  console.log(`[立维志愿] 打包 ${outName} (${target}) ...`)
  const r = spawnSync(
    'npx',
    ['pkg', ENTRY, '--target', target, '--output', resolve(OUT, outName), '--no-bytecode'],
    { cwd: ROOT, stdio: 'inherit', shell: process.platform === 'win32' },
  )
  if (r.status !== 0) {
    console.error(`[立维志愿] ${target} 打包失败`)
    process.exit(r.status ?? 1)
  }
}

console.log(`[立维志愿] 打包完成，产物在 ${OUT}`)
