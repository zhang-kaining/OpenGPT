<template>
  <aside class="sidebar" :class="{ collapsed: isCollapsed, desktop: isDesktop }">
    <!-- 顶部操作栏 -->
    <div class="sidebar-top">
      <button class="icon-btn" title="收起侧边栏" @click="isCollapsed = !isCollapsed">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <path d="M9 3v18"/>
        </svg>
      </button>
      <button v-if="!isDesktop" class="icon-btn" title="搜索对话" @click="showSearch = !showSearch">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
      </button>
      <button
        v-if="!isDesktop"
        class="icon-btn"
        title="新建文件夹"
        @click="newRootFolder"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          <line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
        </svg>
      </button>
      <button class="icon-btn new-chat-icon" title="新对话" @click="store.newConversation()">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14"/>
        </svg>
      </button>
    </div>

    <!-- 搜索框 -->
    <div v-if="showSearch" class="search-box">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
      </svg>
      <input
        ref="searchInputRef"
        v-model="store.searchQuery"
        type="text"
        placeholder="搜索聊天记录"
        class="search-input"
        @keyup.escape="showSearch = false; store.searchQuery = ''"
      />
      <button v-if="store.searchQuery" class="clear-search" @click="store.searchQuery = ''">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M18 6 6 18M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- 对话列表 -->
    <div class="conv-list">
      <template v-if="store.searchQuery">
        <div class="conv-section-label">搜索结果</div>
        <div
          v-for="conv in store.filteredConversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === store.currentConvId }"
          @click="store.selectConversation(conv.id)"
        >
          <span v-if="editingId !== conv.id" class="conv-title">{{ conv.title }}</span>
          <input
            v-else
            ref="editInput"
            v-model="editTitle"
            class="conv-edit-input"
            @blur="saveEdit(conv.id)"
            @keyup.enter="saveEdit(conv.id)"
            @keyup.escape="cancelEdit"
            @click.stop
          />
          <div class="conv-actions" @click.stop>
            <button class="action-btn" title="重命名" @click="startEdit(conv)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button class="action-btn danger" title="删除" @click="confirmDelete(conv.id)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                <path d="M10 11v6M14 11v6"/>
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
              </svg>
            </button>
          </div>
        </div>
        <div v-if="store.filteredConversations.length === 0" class="empty-hint">没有匹配的对话</div>
      </template>
      <template v-else>
        <div class="conv-section-label">文件夹</div>
        <SidebarFolderBranch :parent-id="null" :depth="0" />
        <div class="conv-section-label">未分类对话</div>
        <div
          v-for="conv in rootConversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === store.currentConvId }"
          @click="store.selectConversation(conv.id)"
        >
          <span v-if="editingId !== conv.id" class="conv-title">{{ conv.title }}</span>
          <input
            v-else
            ref="editInput"
            v-model="editTitle"
            class="conv-edit-input"
            @blur="saveEdit(conv.id)"
            @keyup.enter="saveEdit(conv.id)"
            @keyup.escape="cancelEdit"
            @click.stop
          />
          <div class="conv-actions" @click.stop>
            <button class="action-btn" title="重命名" @click="startEdit(conv)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button class="action-btn danger" title="删除" @click="confirmDelete(conv.id)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                <path d="M10 11v6M14 11v6"/>
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
              </svg>
            </button>
          </div>
        </div>
        <div
          v-if="rootConversations.length === 0 && store.folders.length === 0"
          class="empty-hint"
        >
          暂无对话，点击 + 开始
        </div>
      </template>
    </div>

    <!-- 底部用户区域 -->
    <div class="sidebar-footer">
      <button class="footer-user-btn" @click="openMemory">
        <div class="user-avatar">
          <img src="/hamster.svg" alt="avatar" width="20" height="20" />
        </div>
        <span class="user-name">{{ currentUser?.display_name || currentUser?.username || '用户' }}</span>
      </button>
      <button
        class="icon-btn settings-btn"
        :class="{ 'view-active': currentView === 'notes' }"
        title="备忘录"
        @click="currentView = currentView === 'notes' ? 'chat' : 'notes'"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      </button>
      <button class="icon-btn settings-btn" title="退出登录" @click="logout">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
          <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
        </svg>
      </button>
      <button class="icon-btn settings-btn" title="设置" @click="showSettings = true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </div>

    <SettingsPanel :visible="showSettings" @close="showSettings = false" />
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, inject } from 'vue'
import type { Ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { currentUser, clearAuth } from '@/composables/useAuth'
import type { Conversation } from '@/types'
import SettingsPanel from './SettingsPanel.vue'
import SidebarFolderBranch from './SidebarFolderBranch.vue'
import { openConfirm, openPrompt } from '@/composables/useConfirmDialog'

const showSettings = ref(false)

const store = useChatStore()
const isCollapsed = inject<Ref<boolean>>('sidebarCollapsed', ref(false))
const currentView = inject<Ref<string>>('currentView', ref('chat'))
const isDesktop = inject<Ref<boolean>>('isDesktop', ref(false))

const rootConversations = computed(() =>
  store.filteredConversations.filter(c => c.folder_id == null || c.folder_id === ''),
)

async function newRootFolder() {
  const name = await openPrompt({ title: '新建文件夹', placeholder: '文件夹名称', defaultValue: '' })
  if (!name) return
  try {
    await store.createFolderByName(name, null)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : '创建失败')
  }
}

async function logout() {
  const ok = await openConfirm({
    title: '退出登录',
    message: '确定要退出当前账号吗？',
    danger: false,
    confirmText: '退出',
  })
  if (ok) {
    clearAuth()
    window.location.reload()
  }
}
const editingId = ref<string | null>(null)
const editTitle = ref('')
const editInput = ref<HTMLInputElement | null>(null)
const showSearch = ref(false)
const searchInputRef = ref<HTMLInputElement | null>(null)

watch(showSearch, (val) => {
  if (val) nextTick(() => searchInputRef.value?.focus())
  else store.searchQuery = ''
})

function startEdit(conv: Conversation) {
  editingId.value = conv.id
  editTitle.value = conv.title
  nextTick(() => editInput.value?.focus())
}

function cancelEdit() {
  editingId.value = null
}

async function saveEdit(id: string) {
  if (editTitle.value.trim()) {
    await store.renameConversation(id, editTitle.value.trim())
  }
  editingId.value = null
}

async function confirmDelete(id: string) {
  const ok = await openConfirm({
    title: '删除对话',
    message: '确定删除这条对话吗？删除后无法恢复。',
    confirmText: '删除',
  })
  if (ok) store.deleteConversation(id)
}

function openMemory() {
  store.showMemoryPanel = true
  store.loadMemories()
}
</script>

<style scoped>
.sidebar {
  width: 260px;
  min-width: 260px;
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s ease, min-width 0.2s ease;
}

.sidebar.collapsed {
  width: 0;
  min-width: 0;
}

.sidebar-top {
  display: flex;
  align-items: center;
  padding: 10px 8px;
  gap: 2px;
  -webkit-app-region: drag;
}
.sidebar.desktop .sidebar-top {
  padding-top: 34px;
}

.icon-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
  -webkit-app-region: no-drag;
}
.icon-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.new-chat-icon {
  margin-left: auto;
}

.search-box {
  position: relative;
  padding: 4px 8px 8px;
}
.search-icon {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}
.search-input {
  width: 100%;
  padding: 8px 28px 8px 32px;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.search-input:focus {
  border-color: var(--border-strong);
}
.search-input::placeholder { color: var(--text-muted); }
.clear-search {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
}
.clear-search:hover { color: var(--text-primary); }

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.conv-section-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  padding: 8px 8px 4px;
  letter-spacing: 0.01em;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.1s;
  position: relative;
  min-height: 40px;
}
.conv-item:hover { background: var(--bg-hover); }
.conv-item.active { background: var(--bg-active); }
.conv-item:hover .conv-actions { opacity: 1; }

.conv-title {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-edit-input {
  flex: 1;
  background: var(--surface-2);
  border: 1px solid var(--border-strong);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 14px;
  padding: 2px 6px;
  outline: none;
}

.conv-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.1s;
  flex-shrink: 0;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.12s, background 0.12s;
}
.action-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.action-btn.danger:hover { color: var(--danger); }

.empty-hint {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: 24px 12px;
}

.sidebar-footer {
  padding: 8px;
  border-top: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  gap: 4px;
}

.footer-user-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px;
  background: none;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
  min-width: 0;
}
.footer-user-btn:hover { background: var(--bg-hover); }

.settings-btn {
  flex-shrink: 0;
}
.settings-btn.view-active {
  color: var(--accent);
  background: var(--accent-light);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #fef3dc;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.user-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}
</style>
