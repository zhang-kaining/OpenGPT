export interface Citation {
  index: number
  title: string
  url: string
  content: string
  score?: number
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  images?: string[]        // base64 data URLs，仅用户消息
  citations?: Citation[] | null
  created_at: string
  // 流式状态
  streaming?: boolean
  searching?: boolean
  searchQuery?: string
}

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface MemoryItem {
  id: string
  memory: string
  created_at?: string
}
