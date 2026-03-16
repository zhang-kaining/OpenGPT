<template>
  <aside class="sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 顶部操作栏 -->
    <div class="sidebar-top">
      <button class="icon-btn" title="收起侧边栏" @click="isCollapsed = !isCollapsed">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <path d="M9 3v18"/>
        </svg>
      </button>
      <button class="icon-btn" title="搜索对话" @click="showSearch = !showSearch">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
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
      <div v-if="!store.searchQuery" class="conv-section-label">聊天记录</div>
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
      <div v-if="store.filteredConversations.length === 0" class="empty-hint">
        {{ store.searchQuery ? '没有匹配的对话' : '' }}
      </div>
    </div>

    <!-- 底部用户区域 -->
    <div class="sidebar-footer">
      <button class="footer-user-btn" @click="openMemory">
        <div class="user-avatar">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>
          </svg>
        </div>
        <span class="user-name">davis kenny</span>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { Conversation } from '@/types'

const store = useChatStore()
const editingId = ref<string | null>(null)
const editTitle = ref('')
const editInput = ref<HTMLInputElement | null>(null)
const isCollapsed = ref(false)
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

function confirmDelete(id: string) {
  if (confirm('确定删除这个对话吗？')) {
    store.deleteConversation(id)
  }
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
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.search-input:focus {
  border-color: rgba(255,255,255,0.25);
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
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.2);
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
  border-top: 1px solid rgba(255,255,255,0.06);
}

.footer-user-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px;
  background: none;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
}
.footer-user-btn:hover { background: var(--bg-hover); }

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #19c37d;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.user-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}
</style>
