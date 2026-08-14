/**
 * 立维志愿专用版 Agent 入口。
 *
 * 以立维专用 profile 启动 DeepSeek Harness Web UI（127.0.0.1:3080），
 * 并打开首次启动向导页（guide.html）引导 DeepSeek 配置。
 * 打包后（pkg SEA）为单文件可执行，用户无需安装 Node。
 */

import { spawn } from 'node:child_process'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

// 打包闭包内 dsh 的 CLI 入口（node_modules/.bin/dsh）
const dshBin = join(__dirname, '..', 'node_modules', '.bin', 'dsh')
const profilePath = join(__dirname, '..', 'profile', 'liwei.cordis.yml')
const guidePath = join(__dirname, '..', 'guide.html')

const DSH_URL = 'http://127.0.0.1:3080'

/** 用系统默认浏览器打开 URL（跨平台） */
function openBrowser(url: string): void {
  const cmd =
    process.platform === 'win32' ? 'start' : process.platform === 'darwin' ? 'open' : 'xdg-open'
  try {
    spawn(cmd, [url], { shell: true, detached: true, stdio: 'ignore' }).unref()
  } catch {
    /* 打开失败不阻塞（用户可手动访问） */
  }
}

function main(): void {
  console.log('[立维志愿] 启动 DeepSeek Harness（profile: liwei）...')
  const args = ['web']
  if (process.env.LIWEI_PROFILE) {
    args.push('--profile', process.env.LIWEI_PROFILE)
  }

  const child = spawn(dshBin, args, {
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: { ...process.env },
  })

  child.on('error', (err) => {
    console.error('[立维志愿] 启动失败，请确认安装包完整（含 dsh 运行时）:', err.message)
    process.exit(1)
  })

  // dsh 启动后，打开首次启动向导（引导 DeepSeek 配置）
  const timer = setTimeout(() => {
    console.log(`[立维志愿] Harness 已启动：${DSH_URL}`)
    try {
      openBrowser(pathToFileURL(guidePath).href)
    } catch {
      openBrowser(DSH_URL)
    }
  }, 4000)
  timer.unref()

  child.on('exit', (code) => process.exit(code ?? 0))
}

main()
