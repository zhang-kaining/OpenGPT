<template>
  <LoginPage v-if="!isLoggedIn" @success="onLoginSuccess" />
  <div v-else id="app-layout">
    <Sidebar />
    <ChatView />
    <MemoryPanel />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, provide } from 'vue'
import { useChatStore } from '@/stores/chat'
import { initTheme } from '@/composables/useTheme'
import { isLoggedIn } from '@/composables/useAuth'
import LoginPage from '@/components/LoginPage.vue'
import Sidebar from '@/components/Sidebar.vue'
import ChatView from '@/components/ChatView.vue'
import MemoryPanel from '@/components/MemoryPanel.vue'

const store = useChatStore()

const sidebarCollapsed = ref(false)
provide('sidebarCollapsed', sidebarCollapsed)

function onLoginSuccess() {
  store.loadConversations()
}

onMounted(() => {
  initTheme()
  if (isLoggedIn.value) {
    store.loadConversations()
  }
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
