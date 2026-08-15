/**
 * gaokao_update 工具：从 GitHub Release 检查/更新本地高考数据包。
 *
 * 桥接 data_update.py：check（查最新数据包版本）/ update（下载 + SHA256 校验 + 应用）。
 * 配合 gaokao_check_update（版本检测）使用：检测到可更新后，调用本工具拉取新数据。
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { BridgeConfig } from '../bridge.js'
import { runDataScript } from '../bridge.js'

export function registerUpdateTool(ctx: Context, cfg: BridgeConfig): void {
  ctx.tools.register(defineTool({
    name: 'gaokao_update',
    description:
      '从 GitHub Release 检查或更新本地高考数据包。action=check 只查看最新数据包版本；' +
      'action=update 下载数据包并做 SHA256 校验后应用到本地数据目录。' +
      '通常流程：先 gaokao_check_update 检测，若有新版本再 gaokao_update update。',
    parameters: {
      action: {
        type: 'string',
        description: 'check（只检查）或 update（下载并应用），默认 check',
      },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      const action = args.action ?? 'check'
      const stdout = await runDataScript(cfg, ['data_update.py', action])
      exec.signal.throwIfAborted()
      return stdout
    },
  }))
}
