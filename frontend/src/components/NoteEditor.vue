<template>
    <div class="note-editor">
        <!-- 无笔记时的空状态 -->
        <div v-if="!store.currentNoteId" class="empty-state">
            <svg
                width="40"
                height="40"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.2"
            >
                <path
                    d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="11" x2="12" y2="17" />
                <line x1="9" y1="14" x2="15" y2="14" />
            </svg>
            <p>选择一篇笔记或点击 + 新建</p>
        </div>

        <template v-else>
            <!-- 顶部工具栏 -->
            <div class="toolbar" :class="{ desktop: isDesktop }">
                <input
                    v-model="store.currentTitle"
                    class="title-input"
                    placeholder="笔记标题…"
                    @blur="scheduleSave"
                />
                <div class="toolbar-actions">
                    <!-- 编辑 / 预览 切换 -->
                    <button
                        class="tool-btn"
                        :class="{ active: viewMode === 'edit' }"
                        title="编辑"
                        @click="viewMode = 'edit'"
                    >
                        <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <path
                                d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"
                            />
                            <path
                                d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"
                            />
                        </svg>
                    </button>
                    <button
                        class="tool-btn"
                        :class="{ active: viewMode === 'preview' }"
                        title="预览"
                        @click="viewMode = 'preview'"
                    >
                        <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <path
                                d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"
                            />
                            <circle cx="12" cy="12" r="3" />
                        </svg>
                    </button>
                    <button
                        class="tool-btn"
                        :class="{ active: viewMode === 'split' }"
                        title="分屏"
                        @click="viewMode = 'split'"
                    >
                        <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <rect x="3" y="3" width="18" height="18" rx="2" />
                            <line x1="12" y1="3" x2="12" y2="21" />
                        </svg>
                    </button>

                    <div class="divider" />

                    <!-- AI 整理按钮 -->
                    <button
                        v-if="!store.isRefining"
                        class="tool-btn ai-btn"
                        title="AI 整理"
                        @click="onAiRefine"
                    >
                        <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <polygon
                                points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"
                            />
                        </svg>
                        <span>AI 整理</span>
                    </button>
                    <button
                        v-else
                        class="tool-btn ai-btn refining"
                        title="停止整理"
                        @click="store.stopRefine()"
                    >
                        <span class="spinner" />
                        <span>停止</span>
                    </button>

                    <!-- 撤销 AI 整理 -->
                    <button
                        v-if="store.beforeRefineContent !== null"
                        class="tool-btn"
                        title="撤销 AI 整理"
                        @click="store.undoRefine()"
                    >
                        <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <polyline points="1 4 1 10 7 10" />
                            <path d="M3.51 15a9 9 0 1 0 .49-3" />
                        </svg>
                    </button>

                    <!-- 跳转对话 -->
                    <button
                        class="tool-btn"
                        title="带入对话讨论"
                        @click="sendToChat"
                    >
                        <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <path
                                d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                            />
                        </svg>
                    </button>

                    <div class="save-status">{{ saveLabel }}</div>
                </div>
            </div>

            <!-- 编辑区 -->
            <div class="editor-body" :class="viewMode">
                <textarea
                    v-if="viewMode !== 'preview'"
                    v-model="store.currentContent"
                    class="md-textarea"
                    placeholder="支持 Markdown…"
                    spellcheck="false"
                    @input="scheduleSave"
                />
                <div
                    v-if="viewMode !== 'edit'"
                    class="md-preview markdown-body"
                    v-html="renderedHtml"
                />
            </div>
        </template>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch } from "vue";
import type { Ref } from "vue";
import MarkdownIt from "markdown-it";
import hljs from "highlight.js";
import { useNoteStore } from "@/stores/note";
import { useChatStore } from "@/stores/chat";

const store = useNoteStore();
const chatStore = useChatStore();
const currentView = inject<Ref<string>>("currentView");
const isDesktop = inject<Ref<boolean>>("isDesktop", ref(false));

type ViewMode = "edit" | "preview" | "split";
const viewMode = ref<ViewMode>("edit");

const md = new MarkdownIt({
    html: false,
    linkify: true,
    typographer: true,
    breaks: true,
    highlight(str: string, lang: string): string {
        const validLang = lang && hljs.getLanguage(lang) ? lang : "";
        const highlighted = validLang
            ? hljs.highlight(str, { language: validLang, ignoreIllegals: true }).value
            : md.utils.escapeHtml(str);
        return `<pre class="hljs"><code class="hljs-code">${highlighted}</code></pre>`;
    },
});

const renderedHtml = computed(() => md.render(store.currentContent || ""));

// ── 保存 ────────────────────────────────────────────────────────
let saveTimer: ReturnType<typeof setTimeout> | null = null;
const lastSaved = ref<Date | null>(null);

const saveLabel = computed(() => {
    if (store.isSaving) return "保存中…";
    if (!lastSaved.value) return "";
    const diff = Math.floor((Date.now() - lastSaved.value.getTime()) / 1000);
    if (diff < 5) return "已保存";
    return "";
});

function scheduleSave() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => autoSave(), 1500);
}

async function autoSave() {
    if (!store.currentNoteId) return;
    await store.saveCurrentNote();
    lastSaved.value = new Date();
}

// 切换笔记时重置保存状态
watch(
    () => store.currentNoteId,
    () => {
        lastSaved.value = null;
    }
);

// ── AI 整理 ─────────────────────────────────────────────────────
async function onAiRefine() {
    await store.aiRefine();
    lastSaved.value = null;
}

// ── 跳转对话 ────────────────────────────────────────────────────
async function sendToChat() {
    if (!store.currentContent.trim()) return;
    const content = `请帮我整理以下备忘录内容：\n\n---\n\n${store.currentContent}`;
    await chatStore.newConversation();
    await chatStore.sendMessage(content);
    if (currentView) currentView.value = "chat";
}
</script>

<style scoped>
.note-editor {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg-main);
}

.empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: var(--text-muted);
}
.empty-state p {
    font-size: 14px;
}

.toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border-light);
    flex-shrink: 0;
}

.toolbar.desktop {
    padding-top: 34px;
    min-height: 62px;
    -webkit-app-region: drag;
}

.title-input {
    flex: 1;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    background: none;
    border: none;
    outline: none;
    min-width: 0;
    -webkit-app-region: no-drag;
}
.title-input::placeholder {
    color: var(--text-muted);
    font-weight: 400;
}

.toolbar-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
}

.divider {
    width: 1px;
    height: 18px;
    background: var(--border);
    margin: 0 4px;
}

.tool-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    height: 34px;
    min-width: 34px;
    padding: 0 10px;
    background: none;
    border: none;
    border-radius: 6px;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13px;
    transition: background 0.12s, color 0.12s;
    -webkit-app-region: no-drag;
}
.tool-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}
.tool-btn.active {
    background: var(--bg-active);
    color: var(--text-primary);
}

.ai-btn {
    color: var(--accent);
}
.ai-btn:hover {
    background: var(--accent-light);
    color: var(--accent);
}
.ai-btn.refining {
    opacity: 0.8;
}

.spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid var(--accent);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
}
@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.save-status {
    font-size: 12px;
    color: var(--text-muted);
    min-width: 40px;
}

/* ── 编辑区 ── */
.editor-body {
    flex: 1;
    display: flex;
    overflow: hidden;
}

.editor-body.edit .md-textarea {
    width: 100%;
}
.editor-body.preview .md-preview {
    width: 100%;
}
.editor-body.split .md-textarea,
.editor-body.split .md-preview {
    width: 50%;
}
.editor-body.split .md-textarea {
    border-right: 1px solid var(--border-light);
}

.md-textarea {
    flex: 1;
    resize: none;
    border: none;
    outline: none;
    padding: 20px 24px;
    font-size: 14px;
    line-height: 1.7;
    font-family: "JetBrains Mono", "Fira Mono", monospace;
    color: var(--text-primary);
    background: var(--bg-main);
    tab-size: 2;
}

.md-preview {
    flex: 1;
    overflow-y: auto;
    padding: 20px 28px;
    font-size: 14px;
    line-height: 1.75;
    color: var(--text-primary);
}

/* 复用 ChatView 里的 markdown-body 样式，此处补充基础样式确保预览可读 */
.md-preview :deep(h1),
.md-preview :deep(h2),
.md-preview :deep(h3) {
    font-weight: 600;
    margin: 1em 0 0.4em;
    color: var(--text-primary);
}
.md-preview :deep(p) {
    margin: 0.5em 0;
}
.md-preview :deep(ul),
.md-preview :deep(ol) {
    padding-left: 1.5em;
    margin: 0.4em 0;
}
.md-preview :deep(li) {
    margin: 0.2em 0;
}
.md-preview :deep(code) {
    background: var(--code-inline-bg);
    color: var(--code-inline-color);
    border-radius: 4px;
    padding: 0 4px;
    font-size: 0.9em;
}
.md-preview :deep(pre) {
    background: var(--code-block-bg);
    border-radius: 8px;
    padding: 12px 16px;
    overflow-x: auto;
}
.md-preview :deep(pre code) {
    background: none;
    color: var(--code-block-text);
}

.md-preview :deep(pre.hljs) {
    margin: 0.8em 0;
    border: 1px solid var(--border-light);
}
.md-preview :deep(code.hljs-code) {
    display: block;
    white-space: pre;
    font-family: "JetBrains Mono", "Fira Mono", Menlo, Monaco, Consolas, monospace;
    font-size: 12.5px;
    line-height: 1.65;
}
.md-preview :deep(.hljs-comment),
.md-preview :deep(.hljs-quote) { color: #7a6e5e; font-style: italic; }
.md-preview :deep(.hljs-keyword),
.md-preview :deep(.hljs-selector-tag),
.md-preview :deep(.hljs-built_in),
.md-preview :deep(.hljs-name) { color: #c97eb0; }
.md-preview :deep(.hljs-string),
.md-preview :deep(.hljs-addition) { color: #9fbe8c; }
.md-preview :deep(.hljs-number),
.md-preview :deep(.hljs-regexp) { color: #c4956a; }
.md-preview :deep(blockquote) {
    border-left: 3px solid var(--blockquote-border);
    padding-left: 12px;
    color: var(--text-secondary);
    margin: 0.5em 0;
}
.md-preview :deep(hr) {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1em 0;
}
</style>
