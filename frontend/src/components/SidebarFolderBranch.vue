<template>
  <template v-for="folder in sortedChildFolders" :key="folder.id">
    <div
      class="folder-row"
      :style="{ paddingLeft: `${10 + depth * 14}px` }"
    >
      <button
        type="button"
        class="chevron"
        :class="{ open: store.expandedFolderIds.has(folder.id) }"
        title="展开/收起"
        @click="store.toggleFolderExpanded(folder.id)"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </button>
      <span class="folder-name" :title="folder.name">{{ folder.name }}</span>
      <div class="folder-actions" @click.stop>
        <button type="button" class="action-btn" title="在此文件夹新建对话" @click="store.newConversationInFolder(folder.id)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14"/>
          </svg>
        </button>
        <button type="button" class="action-btn" title="新建子文件夹" @click="addSubfolder(folder.id)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            <line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
          </svg>
        </button>
        <button type="button" class="action-btn danger" title="删除文件夹及其中所有对话" @click="confirmDeleteFolder(folder.id)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
          </svg>
        </button>
      </div>
    </div>
    <template v-if="store.expandedFolderIds.has(folder.id)">
      <SidebarFolderBranch :parent-id="folder.id" :depth="depth + 1" />
      <div
        v-for="conv in convsInFolder(folder.id)"
        :key="conv.id"
        class="conv-item"
        :class="{ active: conv.id === store.currentConvId }"
        :style="{ paddingLeft: `${18 + (depth + 1) * 14}px` }"
        @click="store.selectConversation(conv.id)"
      >
        <span v-if="editingId !== conv.id" class="conv-title">{{ conv.title }}</span>
        <input
          v-else
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
          <button class="action-btn danger" title="删除" @click="confirmDeleteConv(conv.id)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            </svg>
          </button>
        </div>
      </div>
    </template>
  </template>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Conversation } from '@/types'
import { useChatStore } from '@/stores/chat'
import SidebarFolderBranch from './SidebarFolderBranch.vue'
import { openConfirm, openPrompt } from '@/composables/useConfirmDialog'

const props = withDefaults(
  defineProps<{ parentId: string | null; depth?: number }>(),
  { depth: 0 },
)

const store = useChatStore()

const sortedChildFolders = computed(() =>
  store.folders
    .filter(f => (f.parent_id ?? null) === (props.parentId ?? null))
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN')),
)

function convsInFolder(folderId: string): Conversation[] {
  return store.filteredConversations.filter(c => c.folder_id === folderId)
}

const editingId = ref<string | null>(null)
const editTitle = ref('')

function startEdit(conv: Conversation) {
  editingId.value = conv.id
  editTitle.value = conv.title
}

function cancelEdit() {
  editingId.value = null
}

async function saveEdit(id: string) {
  if (editTitle.value.trim()) await store.renameConversation(id, editTitle.value.trim())
  editingId.value = null
}

async function confirmDeleteConv(id: string) {
  const ok = await openConfirm({
    title: '删除对话',
    message: '确定删除这条对话吗？删除后无法恢复。',
    confirmText: '删除',
  })
  if (ok) store.deleteConversation(id)
}

async function addSubfolder(parentId: string) {
  const name = await openPrompt({ title: '新建子文件夹', placeholder: '文件夹名称', defaultValue: '' })
  if (!name) return
  try {
    await store.createFolderByName(name, parentId)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : '创建失败')
  }
}

async function confirmDeleteFolder(id: string) {
  const ok = await openConfirm({
    title: '删除文件夹',
    message:
      '将删除此文件夹及其子文件夹内的全部对话，且不可恢复。确定继续吗？',
    confirmText: '删除全部',
  })
  if (ok) store.removeFolder(id)
}
</script>

<style scoped>
.folder-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px 6px 4px;
  min-height: 36px;
  border-radius: 8px;
  transition: background 0.1s;
}
.folder-row:hover {
  background: var(--bg-hover);
}
.folder-row:hover .folder-actions {
  opacity: 1;
}
.chevron {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: transform 0.15s;
}
.chevron.open {
  transform: rotate(90deg);
}
.chevron:hover {
  background: var(--bg-active);
  color: var(--text-primary);
}
.folder-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.folder-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.1s;
  flex-shrink: 0;
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
.conv-item:hover {
  background: var(--bg-hover);
}
.conv-item.active {
  background: var(--bg-active);
}
.conv-item:hover .conv-actions {
  opacity: 1;
}
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
.action-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.action-btn.danger:hover {
  color: var(--danger);
}
</style>
