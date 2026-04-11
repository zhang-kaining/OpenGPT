<template>
  <div
    class="note-item"
    :class="{ active: store.currentNoteId === note.id, nested: indent > 0 }"
    :style="{ marginLeft: `${indent * 18}px` }"
    @click="store.selectNote(note.id)"
  >
    <span v-if="indent > 0" class="note-branch" aria-hidden="true"></span>
    <span class="note-title" @dblclick.stop="onRename">{{ note.title }}</span>
    <div class="item-actions" @click.stop>
      <button class="action-btn" title="重命名" @click="onRename">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/>
        </svg>
      </button>
      <button class="action-btn danger" title="删除笔记" @click="onDelete">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Note } from '@/types'
import { useNoteStore } from '@/stores/note'
import { openConfirm, openPrompt } from '@/composables/useConfirmDialog'

const props = withDefaults(
  defineProps<{ note: Note; indent?: number }>(),
  { indent: 0 },
)

const store = useNoteStore()

async function onRename() {
  const t = await openPrompt({
    title: '重命名笔记',
    placeholder: '标题',
    defaultValue: props.note.title,
  })
  if (t === null) return
  const name = t.trim()
  if (!name || name === props.note.title) return
  try {
    await store.renameNote(props.note.id, name)
  } catch (e: unknown) {
    alert(e instanceof Error ? e.message : '重命名失败')
  }
}

async function onDelete() {
  const ok = await openConfirm({
    title: '删除笔记',
    message: `确定删除「${props.note.title}」吗？删除后无法恢复。`,
    confirmText: '删除',
  })
  if (ok) store.deleteNote(props.note.id)
}
</script>

<style scoped>
.note-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.1s;
  min-height: 30px;
}
.note-item.nested::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 7px;
  bottom: 7px;
  width: 1px;
  background: var(--border-light);
}
.note-item:hover {
  background: var(--bg-hover);
}
.note-item.active {
  background: var(--bg-active);
}
.note-item:hover .item-actions,
.note-item.active .item-actions {
  opacity: 1;
}

@media (hover: none) {
  .note-item .item-actions {
    opacity: 1;
  }
}

.note-branch {
  width: 10px;
  height: 1px;
  background: var(--border);
  flex-shrink: 0;
}

.note-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-actions {
  display: flex;
  opacity: 0;
  transition: opacity 0.1s;
  flex-shrink: 0;
}

.action-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.12s;
}
.action-btn.danger:hover {
  color: var(--danger);
}
</style>
