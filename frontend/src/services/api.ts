import type { Conversation, ConversationFolder, Message, MemoryItem, Citation, Note, NoteFolder, FileMemoryFile, FileMemoryLine } from '@/types'
import { getAuthHeaders, clearAuth } from '@/composables/useAuth'

const BASE = '/api'

async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = { ...getAuthHeaders(), ...init.headers as Record<string, string> }
  const res = await fetch(url, { ...init, headers })
  if (res.status === 401) {
    clearAuth()
    window.location.reload()
  }
  return res
}

// ---- Auth ----

export async function login(username: string, password: string) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function register(username: string, password: string, displayName?: string) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, display_name: displayName || '' }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchRuntimeSettings(): Promise<Record<string, unknown>> {
  const res = await authFetch(`${BASE}/settings/runtime`)
  return res.json()
}

export async function putRuntimeSettings(values: Record<string, unknown>) {
  const res = await authFetch(`${BASE}/settings/runtime`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
}

export async function validateProvider(
  providerType: 'llm' | 'embedding',
  provider: Record<string, unknown>,
  globals: Record<string, unknown>,
) {
  const res = await authFetch(`${BASE}/settings/validate-provider`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_type: providerType, provider, globals }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function cleanupEmbeddingStore(provider: Record<string, unknown>) {
  const res = await authFetch(`${BASE}/settings/cleanup-embedding-store`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export interface FeishuRecipient {
  open_id: string
  name: string
}

export interface FeishuBindStatus {
  bound: boolean
  bound_open_id_masked: string
  bound_at: string | null
  active_code: string
  active_code_expires_at: string | null
}

export async function fetchFeishuRecipients(): Promise<FeishuRecipient[]> {
  const res = await authFetch(`${BASE}/settings/feishu-recipients`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  const data = await res.json()
  return Array.isArray(data.items) ? data.items : []
}

export async function fetchFeishuBindStatus(): Promise<FeishuBindStatus> {
  const res = await authFetch(`${BASE}/settings/feishu-bind`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function createFeishuBindCode(ttlSeconds = 120): Promise<{ code: string; expires_at: string }> {
  const res = await authFetch(`${BASE}/settings/feishu-bind-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ttl_seconds: ttlSeconds }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export interface LlmProviderOption {
  id: string
  name?: string
  kind?: string
  model?: string
  deployment?: string
}

export async function fetchLlmCatalog(): Promise<{ providers: LlmProviderOption[]; active_id: string }> {
  const res = await authFetch(`${BASE}/settings/llm-catalog`)
  return res.json()
}

export async function changePassword(oldPassword: string, newPassword: string) {
  const res = await authFetch(`${BASE}/auth/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ---- Conversations ----

export async function listConversations(): Promise<Conversation[]> {
  const res = await authFetch(`${BASE}/conversations`)
  return res.json()
}

export async function createConversation(title?: string, folderId?: string | null): Promise<Conversation> {
  const res = await authFetch(`${BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, folder_id: folderId ?? null }),
  })
  return res.json()
}

export async function updateConversationTitle(id: string, title: string) {
  await authFetch(`${BASE}/conversations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export async function deleteConversation(id: string) {
  await authFetch(`${BASE}/conversations/${id}`, { method: 'DELETE' })
}

export async function getMessages(convId: string): Promise<Message[]> {
  const res = await authFetch(`${BASE}/conversations/${convId}/messages`)
  return res.json()
}

export async function searchConversations(q: string): Promise<Conversation[]> {
  const res = await authFetch(`${BASE}/conversations/search?q=${encodeURIComponent(q)}`)
  return res.json()
}

// ---- Folders ----

export async function listFolders(): Promise<ConversationFolder[]> {
  const res = await authFetch(`${BASE}/folders`)
  return res.json()
}

export async function createFolder(name: string, parentId?: string | null): Promise<ConversationFolder> {
  const res = await authFetch(`${BASE}/folders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_id: parentId ?? null }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function deleteFolder(id: string) {
  const res = await authFetch(`${BASE}/folders/${id}`, { method: 'DELETE' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
}

// ---- Note Folders ----

export async function listNoteFolders(): Promise<NoteFolder[]> {
  const res = await authFetch(`${BASE}/note-folders`)
  return res.json()
}

export async function createNoteFolder(name: string, parentId?: string | null): Promise<NoteFolder> {
  const res = await authFetch(`${BASE}/note-folders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_id: parentId ?? null }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function deleteNoteFolder(id: string) {
  const res = await authFetch(`${BASE}/note-folders/${id}`, { method: 'DELETE' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
}

// ---- Notes ----

export async function listNotes(): Promise<Note[]> {
  const res = await authFetch(`${BASE}/notes`)
  return res.json()
}

export async function createNote(title?: string, folderId?: string | null): Promise<Note> {
  const res = await authFetch(`${BASE}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: title || '未命名', folder_id: folderId ?? null }),
  })
  return res.json()
}

export async function getNote(id: string): Promise<Note> {
  const res = await authFetch(`${BASE}/notes/${id}`)
  return res.json()
}

export async function saveNote(id: string, title: string, content: string) {
  await authFetch(`${BASE}/notes/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, content }),
  })
}

export async function deleteNote(id: string) {
  await authFetch(`${BASE}/notes/${id}`, { method: 'DELETE' })
}

export interface AiRefineCallbacks {
  onToken?: (token: string) => void
  onDone?: () => void
  onError?: (msg: string) => void
}

export async function aiRefineNote(
  noteId: string,
  prompt: string | undefined,
  callbacks: AiRefineCallbacks,
  signal?: AbortSignal,
) {
  const res = await authFetch(`${BASE}/notes/${noteId}/ai-refine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: prompt || null }),
    ...(signal ? { signal } : {}),
  })
  if (!res.ok) {
    callbacks.onError?.(`HTTP ${res.status}`)
    return
  }
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (raw === '[DONE]') return
      if (!raw) continue
      try {
        const event = JSON.parse(raw)
        if (event.type === 'token') callbacks.onToken?.(event.content)
        else if (event.type === 'done') callbacks.onDone?.()
        else if (event.type === 'error') callbacks.onError?.(event.message)
      } catch { /* ignore */ }
    }
  }
}

// ---- Memory ----

export async function getMemories(): Promise<MemoryItem[]> {
  const res = await authFetch(`${BASE}/memory`)
  return res.json()
}

export async function deleteMemory(id: string) {
  await authFetch(`${BASE}/memory/${id}`, { method: 'DELETE' })
}

// ---- File Memory ----

export async function listFileMemories(): Promise<FileMemoryFile[]> {
  const res = await authFetch(`${BASE}/file-memory/files`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getFileMemoryLines(name: string): Promise<FileMemoryLine[]> {
  const res = await authFetch(`${BASE}/file-memory/${name}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function addFileMemoryLine(name: string, text: string, priority: string = 'P3', kind: string = 'fact') {
  const res = await authFetch(`${BASE}/file-memory/${name}/lines`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, priority, kind })
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateFileMemoryLine(name: string, lineId: string, text: string, priority: string, kind: string) {
  const res = await authFetch(`${BASE}/file-memory/${name}/lines/${lineId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, priority, kind })
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function deleteFileMemoryLine(name: string, lineId: string) {
  const res = await authFetch(`${BASE}/file-memory/${name}/lines/${lineId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function pinFileMemoryLine(name: string, lineId: string, priority: string = 'P1') {
  const res = await authFetch(`${BASE}/file-memory/${name}/lines/${lineId}/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ priority })
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ---- Chat (SSE) ----

export interface ChatCallbacks {
  onConvId?: (convId: string) => void
  onToken?: (token: string) => void
  onSearching?: (query: string) => void
  onSearchResults?: (results: Citation[]) => void
  onToolCall?: (name: string, status: string) => void
  onDone?: (citations: Citation[], usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }) => void
  onError?: (message: string) => void
}

export async function sendMessage(
  content: string,
  conversationId: string | null,
  enableSearch: boolean,
  callbacks: ChatCallbacks,
  signal?: AbortSignal,
  images?: string[],
  folderId?: string | null,
  llmProviderId?: string | null,
) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      content,
      conversation_id: conversationId,
      folder_id: conversationId ? undefined : folderId ?? undefined,
      enable_search: enableSearch,
      images: images?.length ? images : undefined,
      llm_provider_id: llmProviderId || undefined,
    }),
    signal,
  })

  if (res.status === 401) {
    clearAuth()
    window.location.reload()
    return
  }

  if (!res.ok) {
    callbacks.onError?.(`HTTP ${res.status}`)
    return
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (raw === '[DONE]') return
      if (!raw) continue

      try {
        const event = JSON.parse(raw)
        switch (event.type) {
          case 'conv_id':
            callbacks.onConvId?.(event.conv_id)
            break
          case 'token':
            callbacks.onToken?.(event.content)
            break
          case 'searching':
            callbacks.onSearching?.(event.query)
            break
          case 'search_results':
            callbacks.onSearchResults?.(event.results)
            break
          case 'tool_call':
            callbacks.onToolCall?.(event.name, event.status)
            break
          case 'done':
            callbacks.onDone?.(event.citations ?? [], event.usage)
            break
          case 'error':
            callbacks.onError?.(event.message)
            break
        }
      } catch {
        // ignore parse errors
      }
    }
  }
}
