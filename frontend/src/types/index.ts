export interface Citation {
  index: number
  title: string
  url: string
  content: string
  score?: number
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  images?: string[]        // base64 data URLs，仅用户消息
  citations?: Citation[] | null
  usage?: TokenUsage | null
  created_at: string
  // 流式状态
  streaming?: boolean
  searching?: boolean
  searchQuery?: string
  toolCall?: string    // 正在执行的工具名称提示
}

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  folder_id?: string | null
}

export interface ConversationFolder {
  id: string
  parent_id: string | null
  name: string
  created_at: string
  updated_at: string
}

export interface MemoryItem {
  id: string
  memory: string
  created_at?: string
}

export interface NoteFolder {
  id: string
  parent_id: string | null
  name: string
  created_at: string
  updated_at: string
}

export interface Note {
  id: string
  folder_id: string | null
  title: string
  content?: string
  created_at: string
  updated_at: string
}

export interface NoteImageAsset {
  id: string
  filename: string
  content_type: string
  size: number
  url: string
}

export interface FileMemoryFile {
  name: string
  title: string
  filename: string
  max_lines: number
  enabled_for_prompt: boolean
  visible_in_frontend: boolean
  description: string
}

export interface FileMemoryLine {
  id: string
  time: string
  priority: string
  kind: string
  text: string
  raw: string
}
