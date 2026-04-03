<template>
  <div class="msg-structured-content">
    <MessageStructuredNode
      v-for="(node, idx) in nodes"
      :key="idx"
      :node="node"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MessageStructuredNode from './MessageStructuredNode.vue'
import { parseMessageRichText } from '@/utils/messageRichText'

const props = defineProps<{
  content: string
}>()

const nodes = computed(() => parseMessageRichText(props.content))
</script>

<style scoped>
.msg-structured-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
</style>
