<template>
  <div
    class="note-item"
    :class="{ active: store.currentNoteId === note.id }"
    :style="{ paddingLeft: `${14 + indent * 14}px` }"
    @click="store.selectNote(note.id)"
  >
    <span class="note-title">{{ note.title }}</span>
    <div class="item-actions" @click.stop>
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
import { openConfirm } from '@/composables/useConfirmDialog'

const props = withDefaults(
  defineProps<{ note: Note; indent?: number }>(),
  { indent: 0 },
)

const store = useNoteStore()

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
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.1s;
  min-height: 30px;
}
.note-item:hover {
  background: var(--bg-hover);
}
.note-item.active {
  background: var(--bg-active);
}
.note-item:hover .item-actions {
  opacity: 1;
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
