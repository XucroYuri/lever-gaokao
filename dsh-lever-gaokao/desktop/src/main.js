/**
 * 立维志愿桌面端前端逻辑：
 * 1. 加载已保存的 DeepSeek 配置（localStorage）
 * 2. 点击"保存并启动" → 保存配置 + 调用 Rust start_dsh command
 * 3. 轮询 dsh Web UI（127.0.0.1:3080）就绪后跳转
 */

const dshUrl = 'http://127.0.0.1:3080'

const apiKeyEl = document.getElementById('apiKey')
const baseUrlEl = document.getElementById('baseUrl')
const modelEl = document.getElementById('model')
const startBtn = document.getElementById('startBtn')
const statusEl = document.getElementById('status')

// 载入已保存配置
const saved = JSON.parse(localStorage.getItem('liwei-config') || '{}')
if (saved.apiKey) apiKeyEl.value = saved.apiKey
if (saved.baseUrl) baseUrlEl.value = saved.baseUrl
if (saved.model) modelEl.value = saved.model

function setStatus(msg, isErr = false) {
  statusEl.textContent = msg
  statusEl.className = isErr ? 'status err' : 'status'
}

/** 轮询 dsh Web UI 是否就绪 */
async function waitForDsh(timeoutMs = 120000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const resp = await fetch(dshUrl, { signal: AbortSignal.timeout(3000) })
      if (resp.ok) return true
    } catch {
      /* 未就绪，继续等 */
    }
    await new Promise((r) => setTimeout(r, 2000))
  }
  return false
}

startBtn.addEventListener('click', async () => {
  const apiKey = apiKeyEl.value.trim()
  if (!apiKey) {
    setStatus('请先填写 DeepSeek API Key', true)
    return
  }
  // 保存配置（供后续读取；实际调用 dsh 时由用户在 dsh Web UI 配置页粘贴）
  localStorage.setItem('liwei-config', JSON.stringify({
    apiKey, baseUrl: baseUrlEl.value.trim(), model: modelEl.value,
  }))

  startBtn.disabled = true
  setStatus('正在启动 DeepSeek Harness（首次需 npx 拉取，可能较慢）...')

  try {
    // 调用 Rust：后台启动 npx @deepseek-ai/dsh web
    await window.__TAURI__.core.invoke('start_dsh')
    setStatus('Harness 已启动，等待就绪...')
  } catch (e) {
    startBtn.disabled = false
    setStatus(String(e), true)
    return
  }

  const ok = await waitForDsh()
  if (ok) {
    setStatus('就绪，正在进入立维志愿...')
    window.location.href = dshUrl
  } else {
    startBtn.disabled = false
    setStatus('等待超时：请确认已安装 Node.js（>=20）后重试', true)
  }
})
