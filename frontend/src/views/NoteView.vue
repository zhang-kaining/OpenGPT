<template>
  <div class="note-view">
    <NoteLeftPanel />
    <NoteEditor />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useNoteStore } from '@/stores/note'
import NoteLeftPanel from '@/components/NoteLeftPanel.vue'
import NoteEditor from '@/components/NoteEditor.vue'

const store = useNoteStore()
onMounted(() => store.loadAll())
</script>

<style scoped>
.note-view {
  display: flex;
  flex: 1;
  overflow: hidden;
  height: 100%;
}
</style>
