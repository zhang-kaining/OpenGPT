<template>
  <div class="message-row" :class="message.role">
    <div class="message-inner">
      <!-- AI 消息：左对齐，无气泡 -->
      <template v-if="message.role === 'assistant'">
        <div class="assistant-avatar">
          <img src="/hamster.svg" alt="AI" width="20" height="20" />
        </div>
        <div class="assistant-content">
          <!-- 搜索中状态 -->
          <div v-if="message.searching" class="searching-indicator">
            <div class="search-spinner"><span></span></div>
            <span class="search-text">正在搜索{{ message.searchQuery ? '：' + message.searchQuery : '...' }}</span>
          </div>
          <div v-if="message.toolCall && !message.searching" class="searching-indicator tool-call-indicator">
            <div class="search-spinner"><span></span></div>
            <span class="search-text">{{ message.toolCall }}</span>
          </div>

          <div
            v-if="message.content"
            class="markdown-body"
            v-html="renderedContent"
          ></div>

          <!-- 等待动画（还没有内容时） -->
          <div v-if="message.streaming && !message.searching && !message.content" class="thinking-indicator">
            <div class="thinking-bars">
              <span></span><span></span><span></span><span></span>
            </div>
            <span class="thinking-label">思考中</span>
          </div>

          <!-- 引用来源 -->
          <CitationList :citations="message.citations" />

          <!-- 操作按钮 + Token 消耗 -->
          <div v-if="!message.streaming && message.content" class="message-actions">
            <button class="msg-action-btn" :class="{ copied: copied }" title="复制" @click="copyContent">
              <svg v-if="copied" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
            </button>
            <button class="msg-action-btn" title="点赞">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
                <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
              </svg>
            </button>
            <button class="msg-action-btn" title="点踩">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
                <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
              </svg>
            </button>
            <!-- Token 消耗 -->
            <div v-if="message.usage" class="token-usage" :title="usageDetail">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
              <span>{{ message.usage.total_tokens }} tokens</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 用户消息：右对齐，有气泡 -->
      <template v-else>
        <div class="user-message">
          <!-- 图片 -->
          <div v-if="message.images?.length" class="user-images">
            <img
              v-for="(img, i) in message.images"
              :key="i"
              :src="img"
              class="user-image"
              @click="openImage(img)"
            />
          </div>
          <!-- 文字气泡 -->
          <div v-if="message.content" class="user-bubble">
            {{ message.content }}
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import type { Message } from '@/types'
import CitationList from './CitationList.vue'

const props = defineProps<{ message: Message }>()
const copied = ref(false)

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})

function processCitations(html: string): string {
  return html.replace(/\[(\d+)\]/g, (_, num) => {
    return `<a class="citation-ref" title="来源 ${num}">${num}</a>`
  })
}

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  const html = md.render(props.message.content)
  return processCitations(html)
})

const usageDetail = computed(() => {
  const u = props.message.usage
  if (!u) return ''
  return `输入: ${u.prompt_tokens}  输出: ${u.completion_tokens}  合计: ${u.total_tokens}`
})

async function copyContent() {
  const text = props.message.content
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      // 降级方案：execCommand
      const el = document.createElement('textarea')
      el.value = text
      el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {}
}

function openImage(src: string) {
  window.open(src, '_blank')
}
</script>

<style scoped>
.message-row {
  width: 100%;
  padding: 8px 0;
}

.message-inner {
  max-width: 720px;
  margin: 0 auto;
  padding: 0 16px;
}

/* 用户消息右对齐 */
.message-row.user .message-inner {
  display: flex;
  justify-content: flex-end;
}

.user-message {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  max-width: 85%;
}

.user-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.user-image {
  max-width: 240px;
  max-height: 240px;
  border-radius: 12px;
  object-fit: cover;
  cursor: pointer;
  transition: opacity 0.15s;
}
.user-image:hover { opacity: 0.9; }

.user-bubble {
  background: var(--bg-message-user);
  padding: 12px 18px;
  border-radius: 18px;
  font-size: 16px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
  color: var(--text-primary);
}

/* AI 消息左对齐 */
.message-row.assistant .message-inner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.assistant-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #fef3dc;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 4px;
  overflow: hidden;
}

.assistant-content {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
}

.searching-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 10px;
  padding: 6px 12px 6px 10px;
  background: var(--surface-1);
  border-radius: 20px;
  border: 1px solid var(--border-light);
}
.tool-call-indicator {
  background: rgba(0, 168, 112, 0.08);
  border-color: rgba(0, 168, 112, 0.2);
  color: #19c37d;
}

/* 搜索中：三个跳动小球 */
.search-spinner {
  display: flex;
  align-items: center;
  gap: 3px;
  flex-shrink: 0;
}
.search-spinner::before,
.search-spinner::after,
.search-spinner span {
  content: '';
  display: block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: bounce 1.2s ease-in-out infinite;
}
.search-spinner::before { animation-delay: 0s; }
.search-spinner span { animation-delay: 0.2s; }
.search-spinner::after { animation-delay: 0.4s; }

/* 等待回复：脉冲光条 + 文字 */
.thinking-indicator {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 14px 6px 12px;
  background: var(--surface-1);
  border: 1px solid var(--border-light);
  border-radius: 20px;
}
.thinking-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.thinking-bars {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 16px;
}
.thinking-bars span {
  display: block;
  width: 3px;
  border-radius: 2px;
  background: var(--text-secondary);
  animation: bar-pulse 1.2s ease-in-out infinite;
}
.thinking-bars span:nth-child(1) { height: 8px;  animation-delay: 0s; }
.thinking-bars span:nth-child(2) { height: 12px; animation-delay: 0.15s; }
.thinking-bars span:nth-child(3) { height: 16px; animation-delay: 0.3s; }
.thinking-bars span:nth-child(4) { height: 10px; animation-delay: 0.45s; }

@keyframes bar-pulse {
  0%, 100% {
    opacity: 0.35;
    transform: scaleY(0.6);
  }
  50% {
    opacity: 1;
    transform: scaleY(1);
  }
}

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.message-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.15s;
}

.message-row.assistant .message-inner:hover .message-actions {
  opacity: 1;
}

.msg-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}
.msg-action-btn:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
}
.msg-action-btn.copied {
  color: #19c37d;
}

.token-usage {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 6px;
  padding: 2px 8px;
  font-size: 11px;
  color: var(--text-muted);
  background: var(--surface-1);
  border-radius: 10px;
  cursor: default;
  user-select: none;
  transition: color 0.15s, background 0.15s;
}
.token-usage:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}
</style>
