<template>
  <div v-if="citations && citations.length > 0" class="citation-list">
    <div class="citation-header">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/>
      </svg>
      参考来源
    </div>
    <div class="citation-items">
      <a
        v-for="c in citations"
        :key="c.index"
        :href="c.url"
        target="_blank"
        rel="noopener noreferrer"
        class="citation-card"
      >
        <span class="citation-num">{{ c.index }}</span>
        <div class="citation-info">
          <div class="citation-title">{{ c.title || c.url }}</div>
          <div class="citation-domain">{{ getDomain(c.url) }}</div>
        </div>
        <svg class="citation-link-icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
          <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Citation } from '@/types'

defineProps<{ citations?: Citation[] | null }>()

function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return url
  }
}
</script>

<style scoped>
.citation-list {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.citation-header {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.citation-items {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.citation-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  text-decoration: none;
  transition: border-color 0.15s, background 0.15s;
  cursor: pointer;
}
.citation-card:hover {
  border-color: var(--accent);
  background: var(--accent-light);
}

.citation-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--accent-light);
  color: var(--accent);
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.citation-info {
  flex: 1;
  min-width: 0;
}

.citation-title {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.citation-domain {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 1px;
}

.citation-link-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}
</style>
