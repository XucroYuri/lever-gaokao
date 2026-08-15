/**
 * gaokao_check_update 工具：数据版本检查。
 *
 * 读本地 data/version.json（立维数据版本化），可选联网对比 GitHub 仓库最新版本
 * （CI 定时更新 workflow 会提交 data/version.json），判断数据是否可更新。
 * 客户端启动时可静默调用（见 index.ts），有更新则提示。
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export interface CheckUpdateConfig {
  dataDir: string
  /** 仓库（默认 lever-gaokao） */
  repo?: string
}

const GITHUB_API = 'https://api.github.com'

export function readLocalVersion(dataDir: string): Record<string, unknown> | null {
  try {
    const raw = readFileSync(join(dataDir, 'version.json'), 'utf8')
    return JSON.parse(raw)
  } catch {
    return null
  }
}

/** 联网查仓库最新 data/version.json */
export async function fetchRemoteVersion(repo: string): Promise<Record<string, unknown> | null> {
  const url = `${GITHUB_API}/repos/${repo}/contents/data/version.json`
  try {
    const resp = await fetch(url, {
      headers: { 'User-Agent': 'liwei-zhiyuan', 'Accept': 'application/vnd.github+json' },
    })
    if (!resp.ok) return null
    const payload = await resp.json() as { content: string }
    return JSON.parse(Buffer.from(payload.content, 'base64').toString('utf8'))
  } catch {
    return null
  }
}

export function registerCheckUpdateTool(ctx: Context, cfg: CheckUpdateConfig): void {
  const repo = cfg.repo ?? 'XucroYuri/lever-gaokao'
  ctx.tools.register(defineTool({
    name: 'gaokao_check_update',
    description:
      '检查本地高考数据版本与仓库最新版本，判断数据是否可更新（联网可选）。' +
      '本地数据含 version.json（数据版本/覆盖省份/来源核验状态）；联网可对比 CI 定时更新发布的仓库最新版本。',
    parameters: {
      check_remote: { type: 'boolean', description: '是否联网对比仓库最新版本（默认 true）' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      const local = readLocalVersion(cfg.dataDir)
      const result: Record<string, unknown> = {
        local_version: local?.data_version ?? null,
        local_exists: local !== null,
      }
      if (local) {
        result.coverage = local.coverage
        result.sources_total = Array.isArray(local.sources) ? local.sources.length : 0
        result.verified_total = Array.isArray(local.sources)
          ? local.sources.filter((s: Record<string, unknown>) => s.verified).length : 0
      }

      if (args.check_remote !== false) {
        const remote = await fetchRemoteVersion(repo)
        if (remote) {
          result.remote_version = remote.data_version
          result.update_available = Boolean(local && remote.data_version !== local.data_version)
          result.download_hint = result.update_available
            ? '有新版数据：请运行数据更新流程或从仓库 Releases 下载最新数据包'
            : '本地数据已是最新'
        } else {
          result.remote_error = '无法连接仓库（离线或仓库无版本文件）'
        }
      }
      exec.signal.throwIfAborted()
      return JSON.stringify(result, null, 2)
    },
  }))
}
