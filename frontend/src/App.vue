<template>
  <LoginPage v-if="!isLoggedIn" @success="onLoginSuccess" />
  <div v-else id="app-layout" :class="{ 'desktop-shell': isDesktop }">
    <div v-if="isDesktop" class="desktop-drag-strip"></div>
    <button
      v-if="sidebarCollapsed"
      class="global-expand-sidebar-btn"
      title="展开侧边栏"
      @click="sidebarCollapsed = false"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M9 3v18" />
      </svg>
    </button>
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

.global-expand-sidebar-btn {
  position: absolute;
  left: 12px;
  bottom: 14px;
  z-index: 30;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  -webkit-app-region: no-drag;
}

.global-expand-sidebar-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

#app-layout.desktop-shell .global-expand-sidebar-btn {
  bottom: 16px;
}
</style>
