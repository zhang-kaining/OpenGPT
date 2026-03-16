<template>
  <Teleport to="body">
    <div v-if="store.showMemoryPanel" class="overlay" @click.self="store.showMemoryPanel = false">
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2a9 9 0 0 1 9 9c0 3.18-1.65 5.97-4.13 7.6L16 21H8l-.87-2.4A9 9 0 0 1 3 11a9 9 0 0 1 9-9z"/>
              <path d="M9 11h6M9 14h4"/>
            </svg>
            记忆管理
          </div>
          <button class="close-btn" @click="store.showMemoryPanel = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="panel-body">
          <p class="panel-desc">
            以下是 AI 从对话中提取并记住的关于你的信息，跨会话生效。
          </p>

          <div v-if="store.memories.length === 0" class="empty-state">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 2a9 9 0 0 1 9 9c0 3.18-1.65 5.97-4.13 7.6L16 21H8l-.87-2.4A9 9 0 0 1 3 11a9 9 0 0 1 9-9z"/>
            </svg>
            <p>暂无记忆</p>
            <span>开始对话后，AI 会自动记住关于你的信息</span>
          </div>

          <div v-else class="memory-list">
            <div
              v-for="item in store.memories"
              :key="item.id"
              class="memory-item"
            >
              <div class="memory-dot"></div>
              <span class="memory-text">{{ item.memory }}</span>
              <button class="delete-mem-btn" title="删除此记忆" @click="store.deleteMemory(item.id)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useChatStore } from '@/stores/chat'
const store = useChatStore()
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.panel {
  background: var(--bg-sidebar);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  width: 480px;
  max-width: 90vw;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}
.close-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.panel-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 16px;
  line-height: 1.5;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 0;
  color: var(--text-muted);
}
.empty-state p { font-size: 15px; font-weight: 500; color: var(--text-secondary); }
.empty-state span { font-size: 13px; text-align: center; }

.memory-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.memory-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-hover);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border);
}

.memory-dot {
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
}

.memory-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

.delete-mem-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: none;
  border: none;
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.12s, background 0.12s;
}
.delete-mem-btn:hover { color: var(--danger); background: rgba(239,68,68,0.1); }
</style>
