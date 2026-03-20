import type { Conversation, ConversationFolder, Message, MemoryItem, Citation } from '@/types'
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

// ---- Memory ----

export async function getMemories(): Promise<MemoryItem[]> {
  const res = await authFetch(`${BASE}/memory`)
  return res.json()
}

export async function deleteMemory(id: string) {
  await authFetch(`${BASE}/memory/${id}`, { method: 'DELETE' })
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
