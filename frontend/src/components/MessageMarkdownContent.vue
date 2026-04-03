<template>
  <div
    ref="contentRef"
    class="markdown-body"
    v-html="renderedContent"
  ></div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const props = defineProps<{
  content: string
}>()

const contentRef = ref<HTMLElement | null>(null)

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
  highlight(str: string, lang: string): string {
    const validLang = lang && hljs.getLanguage(lang) ? lang : ''
    const highlighted = validLang
      ? hljs.highlight(str, { language: validLang, ignoreIllegals: true }).value
      : escapeHtml(str)
    const label = validLang || 'text'
    return (
      `<div class="code-block-wrapper">` +
      `<div class="code-block-header">` +
      `<span class="code-lang">` +
      `${label}` +
      `<svg class="code-lang-chevron" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>` +
      `</span>` +
      `<span class="code-actions">` +
      `<button class="code-icon-btn code-copy-btn" data-code="${encodeURIComponent(str)}" title="复制代码">` +
      `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>` +
      `</button>` +
      `<button class="code-icon-btn code-wrap-btn" title="切换换行">` +
      `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>` +
      `</button>` +
      `</span>` +
      `</div>` +
      `<pre class="hljs"><code class="hljs-code">${highlighted}</code></pre>` +
      `</div>`
    )
  },
})

function processCitations(html: string): string {
  return html.replace(/\[(\d+)\]/g, (_, num) => {
    return `<a class="citation-ref" title="来源 ${num}">${num}</a>`
  })
}

const renderedContent = computed(() => {
  if (!props.content) return ''
  return processCitations(md.render(props.content))
})

function bindCopyButtons() {
  if (!contentRef.value) return
  contentRef.value.querySelectorAll<HTMLButtonElement>('.code-copy-btn').forEach((btn: HTMLButtonElement) => {
    btn.onclick = async () => {
      const code = decodeURIComponent(btn.dataset.code || '')
      try {
        await navigator.clipboard.writeText(code)
      } catch {
        const el = document.createElement('textarea')
        el.value = code
        el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
        document.body.appendChild(el)
        el.select()
        document.execCommand('copy')
        document.body.removeChild(el)
      }
      btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
      btn.classList.add('copied')
      setTimeout(() => {
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'
        btn.classList.remove('copied')
      }, 2000)
    }
  })
  contentRef.value.querySelectorAll<HTMLButtonElement>('.code-wrap-btn').forEach((btn: HTMLButtonElement) => {
    btn.onclick = () => {
      const pre = btn.closest('.code-block-wrapper')?.querySelector('pre')
      if (!pre) return
      const isWrapped = pre.style.whiteSpace === 'pre-wrap'
      pre.style.whiteSpace = isWrapped ? '' : 'pre-wrap'
      pre.style.overflowX = isWrapped ? 'auto' : 'hidden'
      btn.classList.toggle('active', !isWrapped)
    }
  })
}

watch(renderedContent, () => nextTick(bindCopyButtons), { immediate: true })
</script>
