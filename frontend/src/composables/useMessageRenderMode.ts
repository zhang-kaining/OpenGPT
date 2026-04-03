import { ref } from 'vue'

export type MessageRenderMode = 'structured' | 'markdown'

const STORAGE_KEY = 'mygpt-message-render-mode'

function isMessageRenderMode(value: unknown): value is MessageRenderMode {
  return value === 'structured' || value === 'markdown'
}

function readMessageRenderMode(): MessageRenderMode {
  const raw = localStorage.getItem(STORAGE_KEY)
  return isMessageRenderMode(raw) ? raw : 'structured'
}

export const messageRenderMode = ref<MessageRenderMode>(readMessageRenderMode())

export function setMessageRenderMode(mode: MessageRenderMode) {
  messageRenderMode.value = mode
  localStorage.setItem(STORAGE_KEY, mode)
}
