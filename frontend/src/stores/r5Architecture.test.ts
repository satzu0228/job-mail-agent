import { readdirSync, readFileSync, statSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = resolve(directory, entry)
    if (statSync(path).isDirectory()) return sourceFiles(path)
    if (!/\.(ts|vue)$/.test(entry) || entry.endsWith('.test.ts')) return []
    return [path]
  })
}

describe('R5 前端架构约束', () => {
  it('不重新引入全局 DOM 刷新、页面定时器或前端状态矩阵', () => {
    const forbidden = [
      'job-' + 'mail:',
      'dispatch' + 'Event(',
      'allowed' + 'StageTransitions',
      'set' + 'Interval(',
    ]
    const violations = sourceFiles(resolve(process.cwd(), 'src')).flatMap((path) => {
      const source = readFileSync(path, 'utf8')
      return forbidden
        .filter((pattern) => source.includes(pattern))
        .map((pattern) => `${path}: ${pattern}`)
    })

    expect(violations).toEqual([])
  })
})
