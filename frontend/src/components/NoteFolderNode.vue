<template>
  <div>
    <!-- 文件夹行 -->
    <div
      class="folder-row"
      :class="{ nested: depth > 0 }"
      :style="{ marginLeft: `${depth * 18}px` }"
    >
      <button
        class="chevron"
        :class="{ open: isExpanded }"
        @click="store.toggleFolder(folder.id)"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </button>
      <svg class="folder-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      <span class="folder-name" :title="folder.name">{{ folder.name }}</span>
      <div class="row-actions" @click.stop>
        <button class="action-btn" title="在此新建笔记" @click="store.newNote(folder.id)">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 5v14M5 12h14"/>
          </svg>
        </button>
        <button class="action-btn" title="新建子文件夹" @click="onNewSubfolder">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            <line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
          </svg>
        </button>
        <button class="action-btn danger" title="删除文件夹" @click="onDeleteFolder">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 展开内容 -->
    <template v-if="isExpanded">
      <NoteFolderNode
        v-for="sub in store.childFolders(folder.id)"
        :key="sub.id"
        :folder="sub"
        :depth="depth + 1"
      />
      <NoteItem
        v-for="note in store.notesInFolder(folder.id)"
        :key="note.id"
        :note="note"
        :indent="depth + 1"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { NoteFolder } from '@/types'
import { useNoteStore } from '@/stores/note'
import { openConfirm, openPrompt } from '@/composables/useConfirmDialog'
import NoteItem from './NoteItem.vue'
import NoteFolderNode from './NoteFolderNode.vue'

const props = withDefaults(
  defineProps<{ folder: NoteFolder; depth?: number }>(),
  { depth: 0 },
)

const store = useNoteStore()
const isExpanded = computed(() => store.expandedFolderIds.has(props.folder.id))

async function onNewSubfolder() {
  const name = await openPrompt({ title: '新建子文件夹', placeholder: '文件夹名称' })
  if (!name) return
  try {
    await store.createFolder(name, props.folder.id)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : '创建失败')
  }
}

async function onDeleteFolder() {
  const ok = await openConfirm({
    title: '删除文件夹',
    message: '将删除此文件夹及其下所有子文件夹和笔记，无法恢复。确定继续吗？',
    confirmText: '删除全部',
  })
  if (ok) {
    try {
      await store.deleteFolder(props.folder.id)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : '删除失败')
    }
  }
}
</script>

<style scoped>
.folder-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 5px 6px 5px 6px;
  border-radius: 6px;
  transition: background 0.1s;
  min-height: 32px;
}
.folder-row.nested::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 7px;
  bottom: 7px;
  width: 1px;
  background: var(--border-light);
}
.folder-row:hover {
  background: var(--bg-hover);
}
.folder-row:hover .row-actions {
  opacity: 1;
}

.chevron {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  transition: transform 0.15s;
}
.chevron.open {
  transform: rotate(90deg);
}

.folder-icon {
  flex-shrink: 0;
  color: var(--text-muted);
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

.row-actions {
  display: flex;
  gap: 1px;
  opacity: 0;
  transition: opacity 0.1s;
  flex-shrink: 0;
}

.action-btn {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.12s, background 0.12s;
}
.action-btn:hover {
  background: var(--bg-active);
  color: var(--text-primary);
}
.action-btn.danger:hover {
  color: var(--danger);
}
</style>
