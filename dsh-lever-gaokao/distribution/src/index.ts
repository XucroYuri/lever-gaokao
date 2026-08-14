/**
 * 立维志愿专用版 Agent 入口。
 *
 * 以立维专用 profile 启动 DeepSeek Harness Web UI（127.0.0.1:3080）。
 * 打包后（pkg SEA）为单文件可执行，用户无需安装 Node。
 *
 * 行为：
 * 1. 用随包的 profile（profile/liwei.cordis.yml）启动 dsh
 * 2. profile 预装 dsh-lever-gaokao 插件（6 工具）+ 默认数据路径（随包 data/）
 * 3. 首次启动由前端向导引导 DeepSeek Key 配置
 */

import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

// 打包闭包内 dsh 的 CLI 入口（node_modules/.bin/dsh）
const dshBin = join(__dirname, '..', 'node_modules', '.bin', 'dsh')
const profilePath = join(__dirname, '..', 'profile', 'liwei.cordis.yml')

const args = ['web']
if (process.env.LIWEI_PROFILE) {
  args.push('--profile', process.env.LIWEI_PROFILE)
}

console.log('[立维志愿] 启动 DeepSeek Harness（profile: liwei）...')
const child = spawn(dshBin, args, {
  stdio: 'inherit',
  // Windows 下 .bin/dsh 是 cmd 脚本，需经 shell
  shell: process.platform === 'win32',
  env: { ...process.env },
})

child.on('error', (err) => {
  console.error('[立维志愿] 启动失败，请确认安装包完整（含 dsh 运行时）:', err.message)
  process.exit(1)
})
child.on('exit', (code) => process.exit(code ?? 0))
