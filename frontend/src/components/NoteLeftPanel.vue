<template>
  <div class="note-left">
    <!-- 顶部工具栏 -->
    <div class="panel-top" :class="{ desktop: isDesktop }">
      <span class="panel-label">备忘录</span>
      <div class="panel-actions">
        <button class="icon-btn" title="新建文件夹" @click="onNewFolder(null)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            <line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
          </svg>
        </button>
        <button class="icon-btn" title="新建笔记" @click="store.newNote(null)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 文件夹树 + 笔记列表 -->
    <div class="list-scroll">
      <!-- 根文件夹 -->
      <NoteFolderNode
        v-for="folder in store.childFolders(null)"
        :key="folder.id"
        :folder="folder"
        :depth="0"
      />
      <!-- 未分类笔记 -->
      <div v-if="store.notesInFolder(null).length" class="section-label">未分类</div>
      <NoteItem
        v-for="note in store.notesInFolder(null)"
        :key="note.id"
        :note="note"
        :indent="0"
      />
      <div
        v-if="store.folders.length === 0 && store.notes.length === 0"
        class="empty-hint"
      >
        暂无笔记，点击 + 新建
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject, ref } from 'vue'
import type { Ref } from 'vue'
import { useNoteStore } from '@/stores/note'
import { openPrompt } from '@/composables/useConfirmDialog'
import NoteFolderNode from './NoteFolderNode.vue'
import NoteItem from './NoteItem.vue'

const store = useNoteStore()
const isDesktop = inject<Ref<boolean>>('isDesktop', ref(false))

async function onNewFolder(parentId: string | null) {
  const name = await openPrompt({ title: '新建文件夹', placeholder: '文件夹名称' })
  if (!name) return
  try {
    await store.createFolder(name, parentId)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : '创建失败')
  }
}
</script>

<style scoped>
.note-left {
  width: 220px;
  min-width: 220px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-top {
  display: flex;
  align-items: center;
  padding: 10px 8px 8px;
  gap: 4px;
  border-bottom: 1px solid var(--border-light);
}

.panel-top.desktop {
  padding-top: 34px;
  min-height: 62px;
  -webkit-app-region: drag;
}

.panel-label {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  padding-left: 6px;
  letter-spacing: 0.02em;
}

.panel-actions {
  display: flex;
  gap: 2px;
}

.icon-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  -webkit-app-region: no-drag;
}
.icon-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.list-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 6px 6px;
}

.section-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  padding: 8px 8px 3px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.empty-hint {
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  padding: 24px 8px;
}
</style>
