<template>
  <div id="app-layout">
    <Sidebar />
    <ChatView />
    <MemoryPanel />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import Sidebar from '@/components/Sidebar.vue'
import ChatView from '@/components/ChatView.vue'
import MemoryPanel from '@/components/MemoryPanel.vue'

const store = useChatStore()

onMounted(() => {
  store.loadConversations()
})
</script>

<style>
#app-layout {
  display: flex;
  flex: 1;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-main);
}
</style>
