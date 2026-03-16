<template>
  <div class="chat-view">
    <!-- 顶部栏（有对话时显示模型名） -->
    <div class="chat-header" v-if="store.messages.length > 0">
      <div class="model-selector">
        <span>ChatGPT</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="m6 9 6 6 6-6"/>
        </svg>
      </div>
    </div>

    <!-- 消息区域 -->
    <div ref="scrollEl" class="messages-container">
      <!-- 欢迎页 -->
      <div v-if="store.messages.length === 0" class="welcome">
        <div class="welcome-logo">
          <svg width="32" height="32" viewBox="0 0 41 41" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.239-2.975 10.079 10.079 0 0 0-10.699 4.988 9.964 9.964 0 0 0-6.675 4.529 10.079 10.079 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.239 2.974 10.079 10.079 0 0 0 10.699-4.987 9.965 9.965 0 0 0 6.675-4.53 10.079 10.079 0 0 0-1.24-11.817zm-17.297 24.12a7.474 7.474 0 0 1-4.799-1.735c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.49 7.601zm-16.124-6.908a7.474 7.474 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103l-8.051 4.649a7.504 7.504 0 0 1-10.24-2.744zm-2.09-17.496a7.473 7.473 0 0 1 3.908-3.285c0 .068-.004.19-.004.274v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L4.502 23.464a7.504 7.504 0 0 1-.482-10.878zm27.693 6.44l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.048 4.648a7.498 7.498 0 0 1-1.158 13.528v-9.476a1.293 1.293 0 0 0-.647-1.13zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.05-4.645a7.497 7.497 0 0 1 11.135 7.763zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.497 7.497 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V21z" fill="currentColor"/>
          </svg>
        </div>
        <h2>有什么可以帮忙的？</h2>
        <div class="suggestion-grid">
          <button
            v-for="s in suggestions"
            :key="s.title"
            class="suggestion-btn"
            @click="useSuggestion(s.text)"
          >
            <span class="suggestion-title">{{ s.title }}</span>
            <span class="suggestion-sub">{{ s.sub }}</span>
          </button>
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
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble.vue'
import InputBar from './InputBar.vue'

const store = useChatStore()
const scrollEl = ref<HTMLElement | null>(null)

const suggestions = [
  { title: '今天有什么重要新闻？', sub: '搜索最新资讯', text: '今天有什么重要新闻？' },
  { title: '帮我写一个 Python 快速排序', sub: '代码示例', text: '帮我写一个 Python 快速排序算法' },
  { title: '解释一下量子纠缠', sub: '科学概念', text: '请用简单的语言解释量子纠缠' },
  { title: '推荐几本科幻小说', sub: '书单推荐', text: '推荐几本经典科幻小说' },
]

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

.model-selector {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.model-selector:hover { background: var(--bg-hover); }

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

.suggestion-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
  max-width: 560px;
  width: 100%;
}

.suggestion-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 14px 16px;
  background: var(--bg-input);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: background 0.15s;
  gap: 2px;
}
.suggestion-btn:hover {
  background: rgba(255,255,255,0.1);
}

.suggestion-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.suggestion-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.messages-list {
  padding: 8px 0 24px;
}
</style>
