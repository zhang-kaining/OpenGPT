import type { Conversation, Message, MemoryItem, Citation } from '@/types'

const BASE = '/api'

// ---- Conversations ----

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch(`${BASE}/conversations`)
  return res.json()
}

export async function createConversation(title?: string): Promise<Conversation> {
  const res = await fetch(`${BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  return res.json()
}

export async function updateConversationTitle(id: string, title: string) {
  await fetch(`${BASE}/conversations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export async function deleteConversation(id: string) {
  await fetch(`${BASE}/conversations/${id}`, { method: 'DELETE' })
}

export async function getMessages(convId: string): Promise<Message[]> {
  const res = await fetch(`${BASE}/conversations/${convId}/messages`)
  return res.json()
}

export async function searchConversations(q: string): Promise<Conversation[]> {
  const res = await fetch(`${BASE}/conversations/search?q=${encodeURIComponent(q)}`)
  return res.json()
}

// ---- Memory ----

export async function getMemories(): Promise<MemoryItem[]> {
  const res = await fetch(`${BASE}/memory`)
  return res.json()
}

export async function deleteMemory(id: string) {
  await fetch(`${BASE}/memory/${id}`, { method: 'DELETE' })
}

// ---- Chat (SSE) ----

export interface ChatCallbacks {
  onConvId?: (convId: string) => void
  onToken?: (token: string) => void
  onSearching?: (query: string) => void
  onSearchResults?: (results: Citation[]) => void
  onDone?: (citations: Citation[]) => void
  onError?: (message: string) => void
}

export async function sendMessage(
  content: string,
  conversationId: string | null,
  enableSearch: boolean,
  callbacks: ChatCallbacks,
  signal?: AbortSignal,
  images?: string[]
) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      conversation_id: conversationId,
      enable_search: enableSearch,
      images: images?.length ? images : undefined,
    }),
    signal,
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
          case 'done':
            callbacks.onDone?.(event.citations ?? [])
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
