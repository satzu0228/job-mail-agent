import { describe, expect, it } from 'vitest'

import { analysisFieldLabel, workflowStatusLabels } from './dictionaries'

describe('界面字典', () => {
  it('将抽取模型的待确认字段映射为具体中文名称', () => {
    expect(analysisFieldLabel('CONTACT_NAME')).toBe('联系人')
    expect(analysisFieldLabel('meeting_url')).toBe('会议链接')
    expect(analysisFieldLabel('MATERIALS')).toBe('所需材料')
  })

  it('未知待确认字段保留原始名称，避免显示成重复占位文案', () => {
    expect(analysisFieldLabel('NEW_FIELD')).toBe('未识别字段：NEW_FIELD')
  })

  it('工作流状态均有中文展示文案', () => {
    expect(workflowStatusLabels.RUNNING).toBe('处理中')
    expect(workflowStatusLabels.FAILED).toBe('处理失败')
  })
})
