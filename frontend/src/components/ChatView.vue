<template>
  <div class="chat-view">
    <!-- 顶部栏 -->
    <div class="chat-header">
      <button v-if="sidebarCollapsed" class="expand-sidebar-btn" title="展开侧边栏" @click="sidebarCollapsed = false">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <path d="M9 3v18"/>
        </svg>
      </button>
      <div v-if="store.llmProviders.length" class="model-selector-wrap">
        <select
          v-model="store.selectedLlmProviderId"
          class="model-select"
          title="本条对话使用的模型提供方"
          @change="store.persistLlmProviderSelection()"
        >
          <option v-for="p in store.llmProviders" :key="p.id" :value="p.id">
            {{ providerLabel(p) }}
          </option>
        </select>
      </div>
      <div v-else class="model-selector-hint" title="未配置多模型">
        未配置模型提供方 · 请打开「设置 → 环境与模型」添加
      </div>
    </div>

    <!-- 消息区域 -->
    <div ref="scrollEl" class="messages-container">
      <!-- 欢迎页 -->
      <div v-if="store.messages.length === 0" class="welcome">
        <div class="welcome-logo">
          <img src="/hamster.svg" alt="logo" width="48" height="48" />
        </div>
        <h2>有什么可以帮忙的？</h2>

        <!-- 动态资讯 -->
        <div v-if="newsItems.length" class="news-section">
          <div class="news-header">
            <span class="news-header-dot"></span>
            <span>热点资讯</span>
          </div>
          <div class="news-grid">
            <a
              v-for="(n, i) in newsItems"
              :key="i"
              class="news-card"
              :href="n.link"
              target="_blank"
              rel="noopener"
              @click.prevent="useSuggestion(n.title)"
            >
              <span class="news-title">{{ n.title }}</span>
              <span class="news-meta">
                <span class="news-source">{{ n.source }}</span>
                <span class="news-dot">·</span>
                <span v-if="n.timeAgo">{{ n.timeAgo }}</span>
              </span>
            </a>
          </div>
        </div>
        <div v-else-if="newsLoading" class="news-loading">
          <span class="news-loading-dot"></span>
          <span class="news-loading-dot"></span>
          <span class="news-loading-dot"></span>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-else class="messages-list">
        <MessageBubble
          v-for="msg in store.messages"
          :key="msg.id"
          :message="msg"
        />
      </div>
    </div>

    <!-- 输入框 -->
    <InputBar />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, inject, onMounted, onUnmounted } from 'vue'
import type { LlmProviderOption } from '@/services/api'
import type { Ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble.vue'
import InputBar from './InputBar.vue'

const store = useChatStore()
const sidebarCollapsed = inject<Ref<boolean>>('sidebarCollapsed', ref(false))
const scrollEl = ref<HTMLElement | null>(null)

function providerLabel(p: LlmProviderOption) {
  const tail = p.kind === 'openai' ? (p.model || 'OpenAI 兼容') : (p.deployment || 'Azure')
  return `${p.name || p.id} · ${tail}`
}


interface NewsEntry {
  title: string
  link: string
  source: string
  summary: string
  published: string
  timeAgo?: string
}

const newsItems = ref<NewsEntry[]>([])
const newsLoading = ref(false)

function timeAgo(iso: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} 小时前`
  const days = Math.floor(hrs / 24)
  return `${days} 天前`
}

async function loadNews() {
  if (newsItems.value.length) return
  newsLoading.value = true
  try {
    const res = await fetch('/api/news')
    if (!res.ok) return
    const data = await res.json()
    newsItems.value = (data.items || []).slice(0, 6).map((n: NewsEntry) => ({
      ...n,
      timeAgo: timeAgo(n.published),
    }))
  } catch { /* ignore */ } finally {
    newsLoading.value = false
  }
}

onMounted(() => {
  store.loadLlmCatalog()
  loadNews()
  window.addEventListener('mygpt-llm-providers-updated', store.loadLlmCatalog)
})

onUnmounted(() => {
  window.removeEventListener('mygpt-llm-providers-updated', store.loadLlmCatalog)
})

function useSuggestion(text: string) {
  store.sendMessage(text)
}

function scrollToBottom() {
  nextTick(() => {
    if (scrollEl.value) {
      scrollEl.value.scrollTop = scrollEl.value.scrollHeight
    }
  })
}

watch(() => store.messages.length, scrollToBottom)
watch(
  () => store.messages[store.messages.length - 1]?.content,
  scrollToBottom
)
</script>

<style scoped>
.chat-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-main);
  min-width: 0;
}

.chat-header {
  height: 48px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  flex-shrink: 0;
}

.expand-sidebar-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}
.expand-sidebar-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.model-selector-wrap {
  margin-left: auto;
}
.model-select {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  background: var(--bg-sidebar);
  max-width: min(280px, 42vw);
  cursor: pointer;
}
.model-selector-hint {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-muted);
  max-width: min(320px, 50vw);
  text-align: right;
  line-height: 1.35;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
  min-height: 0;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
  text-align: center;
  gap: 16px;
  padding: 0 20px;
}

.welcome-logo {
  color: var(--text-primary);
  margin-bottom: 4px;
}

.welcome h2 {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.news-section {
  max-width: 640px;
  width: 100%;
  margin-top: 20px;
}

.news-header {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 10px;
  padding-left: 4px;
}

.news-header-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
  flex-shrink: 0;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.news-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.news-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  background: var(--surface-1);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.18s, border-color 0.18s, transform 0.18s;
  min-height: 72px;
}
.news-card:hover {
  background: var(--bg-active);
  border-color: var(--border);
  transform: translateY(-1px);
}

.news-title {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.45;
  text-align: left;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-meta {
  display: flex;
  align-items: center;
  gap: 0;
  font-size: 11px;
  color: var(--text-muted);
}

.news-source {
  color: var(--text-secondary);
  font-weight: 500;
}

.news-dot {
  margin: 0 4px;
  opacity: 0.5;
}

.news-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 24px;
}

.news-loading-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: news-bounce 1.4s ease-in-out infinite;
}
.news-loading-dot:nth-child(2) { animation-delay: 0.16s; }
.news-loading-dot:nth-child(3) { animation-delay: 0.32s; }

@keyframes news-bounce {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

@media (max-width: 560px) {
  .news-grid {
    grid-template-columns: 1fr;
  }
}

.messages-list {
  padding: 8px 0 24px;
}
</style>
