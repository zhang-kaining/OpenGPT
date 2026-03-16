<template>
  <div class="message-row" :class="message.role">
    <div class="message-inner">
      <!-- AI 消息：左对齐，无气泡 -->
      <template v-if="message.role === 'assistant'">
        <div class="assistant-avatar">
          <svg width="16" height="16" viewBox="0 0 41 41" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.239-2.975 10.079 10.079 0 0 0-10.699 4.988 9.964 9.964 0 0 0-6.675 4.529 10.079 10.079 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.239 2.974 10.079 10.079 0 0 0 10.699-4.987 9.965 9.965 0 0 0 6.675-4.53 10.079 10.079 0 0 0-1.24-11.817zm-17.297 24.12a7.474 7.474 0 0 1-4.799-1.735c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.49 7.601zm-16.124-6.908a7.474 7.474 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103l-8.051 4.649a7.504 7.504 0 0 1-10.24-2.744zm-2.09-17.496a7.473 7.473 0 0 1 3.908-3.285c0 .068-.004.19-.004.274v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L4.502 23.464a7.504 7.504 0 0 1-.482-10.878zm27.693 6.44l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.048 4.648a7.498 7.498 0 0 1-1.158 13.528v-9.476a1.293 1.293 0 0 0-.647-1.13zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.05-4.645a7.497 7.497 0 0 1 11.135 7.763zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.497 7.497 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V21z" fill="currentColor"/>
          </svg>
        </div>
        <div class="assistant-content">
          <!-- 搜索中状态 -->
          <div v-if="message.searching" class="searching-indicator">
            <div class="search-spinner"><span></span></div>
            <span class="search-text">正在搜索{{ message.searchQuery ? '：' + message.searchQuery : '...' }}</span>
          </div>

          <div
            v-if="message.content"
            class="markdown-body"
            v-html="renderedContent"
          ></div>

          <!-- 等待动画（还没有内容时） -->
          <div v-if="message.streaming && !message.searching && !message.content" class="thinking-dots">
            <span></span><span></span><span></span>
          </div>

          <!-- 引用来源 -->
          <CitationList :citations="message.citations" />

          <!-- 操作按钮 -->
          <div v-if="!message.streaming && message.content" class="message-actions">
            <button class="msg-action-btn" :class="{ copied: copied }" title="复制" @click="copyContent">
              <!-- 复制成功：勾 -->
              <svg v-if="copied" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <!-- 默认：复制图标 -->
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
  background: #19c37d;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  margin-top: 4px;
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
  background: rgba(255,255,255,0.04);
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.08);
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

/* 等待回复：三个渐变跳动点 */
.thinking-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
  height: 28px;
}
.thinking-dots span {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: thinking 1.4s ease-in-out infinite;
}
.thinking-dots span:nth-child(1) { animation-delay: 0s; }
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes thinking {
  0%, 60%, 100% {
    transform: translateY(0);
    background: var(--text-muted);
  }
  30% {
    transform: translateY(-6px);
    background: var(--text-secondary);
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
</style>
