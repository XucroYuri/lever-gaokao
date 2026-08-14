/**
 * 桥接 lever-gaokao Python 数据层。
 *
 * dsh 工具（TypeScript/Node）通过 spawn 调用 lever-gaokao/scripts 下的 Python 脚本
 * （data_ingest.py / data_collect.py / data_collect_provinces.py），复用已建好的
 * DuckDB 数据层，避免在 Node 侧重复实现查询逻辑。
 *
 * 环境变量约束：Windows 控制台为 GBK，必须注入 PYTHONIOENCODING=utf-8 才能可靠
 * 读取中文输出。
 */

import { execFile } from 'node:child_process'

/** 桥接配置：由插件 config 提供（见 index.ts 的默认值）。 */
export interface BridgeConfig {
  /** Python 可执行文件，默认 'python' */
  python: string
  /** lever-gaokao/scripts 的绝对路径 */
  scriptDir: string
  /** 数据目录（含 gaokao.duckdb），默认 scripts 同级 ../data */
  dataDir?: string
  /** 命令超时 ms，默认 120000 */
  timeoutMs?: number
}

export class DataBridgeError extends Error {
  constructor(message: string, public readonly script: string) {
    super(`${script}: ${message}`)
    this.name = 'DataBridgeError'
  }
}

/** 运行一个 Python 数据脚本命令，返回 stdout（期望为 JSON 或纯文本）。 */
export function runDataScript(
  cfg: BridgeConfig,
  args: string[],
): Promise<string> {
  return new Promise((resolve, reject) => {
    const timeoutMs = cfg.timeoutMs ?? 120_000
    execFile(
      cfg.python,
      args,
      {
        cwd: cfg.scriptDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        maxBuffer: 16 * 1024 * 1024,
        timeout: timeoutMs,
        windowsHide: true,
      },
      (err, stdout, stderr) => {
        if (err) {
          const detail = (stderr || '').trim() || String(err)
          reject(new DataBridgeError(detail.slice(0, 2000), args[0] ?? 'data-script'))
          return
        }
        resolve(stdout)
      },
    )
  })
}

/** 运行 data_ingest.py query，返回解析后的 JSON 数组。 */
export async function queryDuckdb(
  cfg: BridgeConfig,
  params: {
    table?: string
    province?: string
    year?: number
    category?: string
    subject?: string
    minRank?: number
    maxRank?: number
    maxTuition?: number
    level?: string
    limit?: number
  },
): Promise<unknown> {
  const args = ['data_ingest.py', 'query', '--table', params.table ?? 'major', '--json']
  if (params.province) args.push('--province', params.province)
  if (params.year) args.push('--year', String(params.year))
  if (params.category) args.push('--category', params.category)
  if (params.subject) args.push('--subject', params.subject)
  if (params.minRank) args.push('--min-rank', String(params.minRank))
  if (params.maxRank) args.push('--max-rank', String(params.maxRank))
  if (params.maxTuition) args.push('--max-tuition', String(params.maxTuition))
  if (params.level) args.push('--level', params.level)
  args.push('--limit', String(params.limit ?? 30))
  if (cfg.dataDir) args.push('--db', `${cfg.dataDir}/gaokao.duckdb`)
  const stdout = await runDataScript(cfg, args)
  // query 命令输出含非 JSON 前缀行（查询条件说明），提取最后一段 JSON
  const lines = stdout.trim().split('\n')
  const jsonLine = [...lines].reverse().find((l) => l.trim().startsWith('[') || l.trim().startsWith('{'))
  if (!jsonLine) throw new DataBridgeError('query 输出中未找到 JSON', 'query')
  return JSON.parse(jsonLine)
}

/** 运行 data_ingest.py validate，返回解析后的报告对象。 */
export async function validateDuckdb(cfg: BridgeConfig): Promise<unknown> {
  const args = ['data_ingest.py', 'validate', '--json']
  if (cfg.dataDir) args.push('--db', `${cfg.dataDir}/gaokao.duckdb`)
  const stdout = await runDataScript(cfg, args)
  const line = stdout.trim().split('\n').find((l) => l.trim().startsWith('{'))
  if (!line) throw new DataBridgeError('validate 输出中未找到 JSON', 'validate')
  return JSON.parse(line)
}
