<template>
  <LoginPage v-if="!isLoggedIn" @success="onLoginSuccess" />
  <div v-else id="app-layout" :class="{ 'desktop-shell': isDesktop }">
    <div v-if="isDesktop" class="desktop-drag-strip"></div>
    <Sidebar />
    <ChatView v-show="currentView === 'chat'" />
    <NoteView v-if="currentView === 'notes'" />
    <MemoryPanel />
    <ConfirmDialog />
    <PromptDialog />
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
import NoteView from '@/views/NoteView.vue'
import MemoryPanel from '@/components/MemoryPanel.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import PromptDialog from '@/components/PromptDialog.vue'

const store = useChatStore()
const isDesktop = typeof navigator !== 'undefined' && navigator.userAgent.includes('Electron')
provide('isDesktop', ref(isDesktop))

const sidebarCollapsed = ref(false)
provide('sidebarCollapsed', sidebarCollapsed)

const currentView = ref<'chat' | 'notes'>('chat')
provide('currentView', currentView)

function onLoginSuccess() {
  store.refreshSidebar()
}

onMounted(() => {
  initTheme()
  if (isDesktop) {
    // 桌面壳统一使用深色，更贴近原生应用观感
    document.documentElement.classList.remove('light')
  }
  if (isLoggedIn.value) {
    store.refreshSidebar()
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

#app-layout.desktop-shell {
  position: relative;
}

.desktop-drag-strip {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 28px;
  z-index: 10;
  -webkit-app-region: drag;
}
</style>
