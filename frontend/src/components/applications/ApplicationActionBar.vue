<script setup lang="ts">
import type { JobApplication } from '@/types/api'

defineProps<{ application: JobApplication }>()
defineEmits<{
  transition: []
  reopen: []
}>()
</script>

<template>
  <ElButton
    v-if="application.allowed_actions.includes('TRANSITION_STAGE') && application.current_stage !== 'INTERVIEW'"
    type="primary"
    plain
    @click="$emit('transition')"
  >
    更新阶段
  </ElButton>
  <ElButton
    v-if="application.allowed_actions.includes('REOPEN_APPLICATION')"
    type="primary"
    plain
    @click="$emit('reopen')"
  >
    重新打开
  </ElButton>
</template>
