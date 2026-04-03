<template>
  <section
    v-if="node.type === 'section'"
    class="msg-section-card"
    :class="`level-${node.level}`"
  >
    <div class="msg-section-head">
      <span class="msg-section-kicker">{{ node.level <= 2 ? '重点' : '分节' }}</span>
      <h3 class="msg-section-title" v-html="node.titleHtml"></h3>
    </div>
    <div class="msg-section-body">
      <MessageStructuredNode
        v-for="(child, idx) in node.children"
        :key="idx"
        :node="child"
      />
    </div>
  </section>

  <p
    v-else-if="node.type === 'paragraph'"
    class="msg-paragraph"
    :class="node.kind"
    v-html="node.html"
  ></p>

  <component
    :is="node.ordered ? 'ol' : 'ul'"
    v-else-if="node.type === 'list'"
    class="msg-list"
    :class="{ ordered: node.ordered }"
  >
    <li
      v-for="(item, idx) in node.items"
      :key="idx"
      class="msg-list-item"
    >
      <div class="msg-list-item-body">
        <MessageStructuredNode
          v-for="(child, childIdx) in item.children"
          :key="childIdx"
          :node="child"
        />
      </div>
    </li>
  </component>

  <blockquote
    v-else-if="node.type === 'quote'"
    class="msg-quote-card"
  >
    <MessageStructuredNode
      v-for="(child, idx) in node.children"
      :key="idx"
      :node="child"
    />
  </blockquote>

  <div
    v-else-if="node.type === 'code'"
    class="msg-code-card"
  >
    <div class="msg-code-head">
      <span class="msg-code-lang">{{ node.lang || 'text' }}</span>
      <div class="msg-code-actions">
        <button
          class="msg-code-btn"
          :class="{ active: wrapCode }"
          title="切换换行"
          @click="wrapCode = !wrapCode"
        >
          换行
        </button>
        <button
          class="msg-code-btn"
          :class="{ copied }"
          title="复制代码"
          @click="copyCode"
        >
          {{ copied ? '已复制' : '复制' }}
        </button>
      </div>
    </div>
    <pre class="msg-code-pre" :class="{ wrap: wrapCode }"><code v-html="node.highlightedHtml"></code></pre>
  </div>

  <div
    v-else-if="node.type === 'table'"
    class="msg-table-card"
  >
    <table class="msg-table">
      <thead v-if="node.rows.length">
        <tr>
          <th
            v-for="(cell, idx) in node.rows[0]"
            :key="idx"
            v-html="cell || '&nbsp;'"
          ></th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, rowIdx) in node.rows.slice(1)"
          :key="rowIdx"
        >
          <td
            v-for="(cell, cellIdx) in row"
            :key="cellIdx"
            v-html="cell || '&nbsp;'"
          ></td>
        </tr>
      </tbody>
    </table>
  </div>

  <hr
    v-else-if="node.type === 'divider'"
    class="msg-divider"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { MessageRenderNode } from '@/utils/messageRichText'

defineOptions({ name: 'MessageStructuredNode' })

const props = defineProps<{
  node: MessageRenderNode
}>()

const copied = ref(false)
const wrapCode = ref(false)

async function copyCode() {
  if (props.node.type !== 'code') return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(props.node.code)
    } else {
      const el = document.createElement('textarea')
      el.value = props.node.code
      el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 1800)
  } catch {
    /* ignore */
  }
}
</script>

<style scoped>
.msg-section-card {
  margin: 18px 0;
  padding: 18px 18px 16px;
  border: 1px solid color-mix(in oklab, var(--border) 78%, var(--accent) 22%);
  border-radius: 18px;
  background:
    linear-gradient(180deg, color-mix(in oklab, var(--accent-light) 72%, transparent) 0%, transparent 46%),
    color-mix(in oklab, var(--surface-1) 78%, var(--panel-bg) 22%);
}

.msg-section-card.level-1,
.msg-section-card.level-2 {
  box-shadow: inset 0 1px 0 color-mix(in oklab, var(--accent) 18%, transparent);
}

.msg-section-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.msg-section-kicker {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.msg-section-title {
  font-size: 18px;
  line-height: 1.35;
  color: var(--text-primary);
}

.msg-section-body > :first-child {
  margin-top: 0;
}

.msg-section-body > :last-child {
  margin-bottom: 0;
}

.msg-paragraph {
  margin: 10px 0;
  color: var(--text-primary);
  line-height: 1.82;
  font-size: 15px;
}

.msg-paragraph.lead {
  font-size: 16px;
  line-height: 1.9;
  color: color-mix(in oklab, var(--text-primary) 88%, var(--accent) 12%);
}

.msg-list {
  margin: 12px 0;
  padding-left: 20px;
  color: var(--text-primary);
}

.msg-list.ordered {
  padding-left: 22px;
}

.msg-list-item {
  margin: 8px 0;
}

.msg-list-item-body :deep(p) {
  margin: 0;
}

.msg-quote-card {
  margin: 14px 0;
  padding: 14px 16px;
  border-left: 3px solid var(--accent);
  background: color-mix(in oklab, var(--surface-2) 70%, var(--accent-light) 30%);
  border-radius: 0 14px 14px 0;
}

.msg-code-card {
  margin: 16px 0;
  overflow: hidden;
  border: 1px solid var(--code-block-border);
  border-radius: 16px;
  background: var(--code-block-bg);
}

.msg-code-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px 10px 14px;
  background: var(--code-block-header);
  border-bottom: 1px solid var(--code-block-border);
}

.msg-code-lang {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: lowercase;
}

.msg-code-actions {
  display: flex;
  gap: 6px;
}

.msg-code-btn {
  border: none;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-2);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.msg-code-btn:hover,
.msg-code-btn.active,
.msg-code-btn.copied {
  background: var(--accent-light);
  color: var(--accent);
}

.msg-code-pre {
  margin: 0;
  padding: 16px 18px;
  overflow-x: auto;
  white-space: pre;
  line-height: 1.7;
  font-size: 13.5px;
}

.msg-code-pre.wrap {
  white-space: pre-wrap;
  overflow-x: hidden;
}

.msg-code-pre code {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
  color: var(--code-block-text);
}

.msg-code-pre :deep(.hljs-comment),
.msg-code-pre :deep(.hljs-quote) { color: #7a6e5e; font-style: italic; }
.msg-code-pre :deep(.hljs-keyword),
.msg-code-pre :deep(.hljs-selector-tag),
.msg-code-pre :deep(.hljs-built_in),
.msg-code-pre :deep(.hljs-name),
.msg-code-pre :deep(.hljs-tag) { color: #c97eb0; }
.msg-code-pre :deep(.hljs-string),
.msg-code-pre :deep(.hljs-addition) { color: #9fbe8c; }
.msg-code-pre :deep(.hljs-title),
.msg-code-pre :deep(.hljs-section),
.msg-code-pre :deep(.hljs-attribute),
.msg-code-pre :deep(.hljs-literal),
.msg-code-pre :deep(.hljs-template-tag),
.msg-code-pre :deep(.hljs-template-variable),
.msg-code-pre :deep(.hljs-type) { color: #9fbe8c; }
.msg-code-pre :deep(.hljs-deletion),
.msg-code-pre :deep(.hljs-selector-attr),
.msg-code-pre :deep(.hljs-selector-pseudo),
.msg-code-pre :deep(.hljs-meta) { color: #b08898; }
.msg-code-pre :deep(.hljs-doctag) { color: #7a9abf; }
.msg-code-pre :deep(.hljs-attr) { color: #b8a86a; }
.msg-code-pre :deep(.hljs-symbol),
.msg-code-pre :deep(.hljs-bullet),
.msg-code-pre :deep(.hljs-link) { color: #7dc4b8; }
.msg-code-pre :deep(.hljs-number),
.msg-code-pre :deep(.hljs-regexp) { color: #c4956a; }
.msg-code-pre :deep(.hljs-variable),
.msg-code-pre :deep(.hljs-params) { color: #e4d9c8; }
.msg-code-pre :deep(.hljs-function) { color: #82aadf; }
.msg-code-pre :deep(.hljs-class .hljs-title),
.msg-code-pre :deep(.hljs-title.class_) { color: #e8c06a; font-weight: 600; }
.msg-code-pre :deep(.hljs-punctuation),
.msg-code-pre :deep(.hljs-operator) { color: #9a9080; }

.msg-table-card {
  margin: 16px 0;
  overflow: hidden;
  border: 1px solid var(--table-border);
  border-radius: 16px;
  background: color-mix(in oklab, var(--surface-1) 84%, var(--panel-bg) 16%);
}

.msg-table {
  width: 100%;
  border-collapse: collapse;
}

.msg-table th,
.msg-table td {
  padding: 11px 14px;
  border-bottom: 1px solid var(--table-border);
  vertical-align: top;
  text-align: left;
}

.msg-table tr:last-child td {
  border-bottom: none;
}

.msg-table th {
  font-size: 12px;
  color: var(--text-secondary);
  background: color-mix(in oklab, var(--table-header-bg) 72%, var(--surface-2) 28%);
}

.msg-table td {
  font-size: 14px;
  color: var(--text-primary);
}

.msg-divider {
  margin: 18px 0;
  border: none;
  border-top: 1px solid var(--border-light);
}

:deep(a) {
  color: var(--accent);
  text-decoration: none;
}

:deep(a:hover) {
  text-decoration: underline;
}

:deep(strong) {
  font-weight: 650;
}

:deep(code):not(pre code) {
  padding: 0.12em 0.45em;
  border-radius: 999px;
  background: var(--code-inline-bg);
  color: var(--code-inline-color);
  font-size: 0.9em;
}

:deep(.msg-citation-chip) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  margin: 0 2px;
  border-radius: 999px;
  background: var(--accent-light);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  vertical-align: text-top;
}
</style>
