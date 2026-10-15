<script setup lang="ts">
import type { ReviewActionType } from '@/types/api'

defineProps<{
  actionType: ReviewActionType
  deciding: boolean
}>()
defineEmits<{
  approve: []
  approveFollowUp: []
  reject: []
}>()
</script>

<template>
  <div class="drawer-actions">
    <ElButton :disabled="deciding" @click="$emit('reject')">拒绝</ElButton>
    <ElButton
      v-if="!['SEND_REPLY', 'ARCHIVE_EMAIL', 'RESTORE_EMAIL'].includes(actionType)"
      :disabled="deciding"
      @click="$emit('approveFollowUp')"
    >
      批准并自动执行后续
    </ElButton>
    <ElButton type="primary" :loading="deciding" @click="$emit('approve')">
      {{ actionType === 'SEND_REPLY' ? '确认并发送' : '批准' }}
    </ElButton>
  </div>
</template>
