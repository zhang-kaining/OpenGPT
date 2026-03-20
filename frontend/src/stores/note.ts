import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Note, NoteFolder } from '@/types'
import * as api from '@/services/api'

export const useNoteStore = defineStore('note', () => {
  const folders = ref<NoteFolder[]>([])
  const notes = ref<Note[]>([])
  const currentNoteId = ref<string | null>(null)
  const currentContent = ref('')
  const currentTitle = ref('')
  const expandedFolderIds = ref<Set<string>>(new Set())
  const isSaving = ref(false)
  const isRefining = ref(false)
  /** 整理前的原始内容，用于「撤销 AI 整理」 */
  const beforeRefineContent = ref<string | null>(null)

  const currentNote = computed(() => notes.value.find(n => n.id === currentNoteId.value) ?? null)
  const sortedFolders = computed(() => [...folders.value].sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN')))

  function notesInFolder(folderId: string | null): Note[] {
    return notes.value.filter(n => (n.folder_id ?? null) === folderId)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  }

  function childFolders(parentId: string | null): NoteFolder[] {
    return sortedFolders.value.filter(f => (f.parent_id ?? null) === parentId)
  }

  async function loadAll() {
    const [f, n] = await Promise.all([api.listNoteFolders(), api.listNotes()])
    folders.value = f
    notes.value = n
  }

  async function selectNote(id: string) {
    if (id === currentNoteId.value) return
    const full = await api.getNote(id)
    currentNoteId.value = id
    currentContent.value = full.content ?? ''
    currentTitle.value = full.title
    beforeRefineContent.value = null
  }

  async function newNote(folderId?: string | null) {
    const note = await api.createNote('未命名', folderId)
    notes.value.unshift(note)
    await selectNote(note.id)
    if (folderId) expandFolder(folderId)
  }

  async function saveCurrentNote() {
    if (!currentNoteId.value) return
    isSaving.value = true
    try {
      await api.saveNote(currentNoteId.value, currentTitle.value || '未命名', currentContent.value)
      const note = notes.value.find(n => n.id === currentNoteId.value)
      if (note) {
        note.title = currentTitle.value || '未命名'
        note.updated_at = new Date().toISOString()
      }
    } finally {
      isSaving.value = false
    }
  }

  async function deleteNote(id: string) {
    await api.deleteNote(id)
    notes.value = notes.value.filter(n => n.id !== id)
    if (currentNoteId.value === id) {
      currentNoteId.value = null
      currentContent.value = ''
      currentTitle.value = ''
    }
  }

  async function createFolder(name: string, parentId?: string | null) {
    const folder = await api.createNoteFolder(name, parentId)
    folders.value.push(folder)
    if (parentId) expandFolder(parentId)
  }

  async function deleteFolder(id: string) {
    await api.deleteNoteFolder(id)
    // 删掉所有属于该文件夹子树的文件夹 + 笔记（粗清，刷新更准）
    await loadAll()
    if (currentNoteId.value && !notes.value.find(n => n.id === currentNoteId.value)) {
      currentNoteId.value = null
      currentContent.value = ''
      currentTitle.value = ''
    }
  }

  function expandFolder(id: string) {
    const next = new Set(expandedFolderIds.value)
    next.add(id)
    expandedFolderIds.value = next
  }

  function toggleFolder(id: string) {
    const next = new Set(expandedFolderIds.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    expandedFolderIds.value = next
  }

  let refineAbort: AbortController | null = null

  async function aiRefine(prompt?: string) {
    if (!currentNoteId.value || isRefining.value) return
    beforeRefineContent.value = currentContent.value
    isRefining.value = true
    let refined = ''
    refineAbort = new AbortController()
    try {
      await api.aiRefineNote(
        currentNoteId.value,
        prompt,
        {
          onToken(t) { refined += t; currentContent.value = refined },
          onDone() { isRefining.value = false },
          onError(msg) { currentContent.value = beforeRefineContent.value!; isRefining.value = false; console.error(msg) },
        },
        refineAbort.signal,
      )
    } finally {
      isRefining.value = false
      refineAbort = null
    }
  }

  function undoRefine() {
    if (beforeRefineContent.value !== null) {
      currentContent.value = beforeRefineContent.value
      beforeRefineContent.value = null
    }
  }

  function stopRefine() {
    refineAbort?.abort()
    refineAbort = null
    isRefining.value = false
  }

  return {
    folders,
    notes,
    currentNoteId,
    currentContent,
    currentTitle,
    expandedFolderIds,
    isSaving,
    isRefining,
    beforeRefineContent,
    currentNote,
    notesInFolder,
    childFolders,
    loadAll,
    selectNote,
    newNote,
    saveCurrentNote,
    deleteNote,
    createFolder,
    deleteFolder,
    expandFolder,
    toggleFolder,
    aiRefine,
    undoRefine,
    stopRefine,
  }
})
