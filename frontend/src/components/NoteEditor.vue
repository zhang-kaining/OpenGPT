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
                    ref="textareaRef"
                    v-model="store.currentContent"
                    class="md-textarea"
                    placeholder="支持 Markdown…"
                    spellcheck="false"
                    @paste="handleEditorPaste"
                    @input="scheduleSave"
                />
                <div
                    v-if="viewMode !== 'edit'"
                    ref="previewRef"
                    class="md-preview markdown-body"
                    @mousedown="handlePreviewMouseDown"
                    v-html="renderedHtml"
                />
            </div>
        </template>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch, nextTick, onBeforeUnmount } from "vue";
import type { Ref } from "vue";
import MarkdownIt from "markdown-it";
import hljs from "highlight.js";
import { useNoteStore } from "@/stores/note";
import { useChatStore } from "@/stores/chat";
import { uploadNoteImage } from "@/services/api";
import { authToken } from "@/composables/useAuth";

const store = useNoteStore();
const chatStore = useChatStore();
const currentView = inject<Ref<string>>("currentView");
const isDesktop = inject<Ref<boolean>>("isDesktop", ref(false));
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const previewRef = ref<HTMLElement | null>(null);

type ViewMode = "edit" | "preview" | "split";
const viewMode = ref<ViewMode>("edit");

type ParsedNoteImage = {
    index: number;
    alt: string;
    url: string;
    width: number | null;
    start: number;
    end: number;
};

type ResizeState = {
    index: number;
    startX: number;
    startWidth: number;
};

const IMAGE_SYNTAX_RE = /!\[([^\]]*)\]\(([^)\s]+)\)\s*(?:\{width=(\d+)\})?/g;
const activeResize = ref<ResizeState | null>(null);

function escapeHtml(text: string): string {
    return md.utils.escapeHtml(text);
}

function buildAuthedImageUrl(url: string): string {
    const token = authToken.value;
    if (!token) return url;
    const separator = url.includes("?") ? "&" : "?";
    return `${url}${separator}token=${encodeURIComponent(token)}`;
}

function parseNoteImages(content: string): ParsedNoteImage[] {
    const images: ParsedNoteImage[] = [];
    IMAGE_SYNTAX_RE.lastIndex = 0;
    let match: RegExpExecArray | null;
    let index = 0;
    while ((match = IMAGE_SYNTAX_RE.exec(content))) {
        images.push({
            index,
            alt: match[1] || "图片",
            url: match[2],
            width: match[3] ? Number(match[3]) : null,
            start: match.index,
            end: match.index + match[0].length,
        });
        index += 1;
    }
    return images;
}

function replaceImageMarkupWithWidth(content: string, targetIndex: number, width: number): string {
    let seen = 0;
    return content.replace(IMAGE_SYNTAX_RE, (full, alt: string, url: string) => {
        if (seen !== targetIndex) {
            seen += 1;
            return full;
        }
        seen += 1;
        return `![${alt}](${url}){width=${width}}`;
    });
}

function clampImageWidth(width: number): number {
    return Math.max(120, Math.min(1200, Math.round(width)));
}

async function readImageWidth(file: File): Promise<number> {
    const objectUrl = URL.createObjectURL(file);
    try {
        const width = await new Promise<number>((resolve, reject) => {
            const image = new Image();
            image.onload = () => resolve(image.naturalWidth || 480);
            image.onerror = () => reject(new Error("图片读取失败"));
            image.src = objectUrl;
        });
        return clampImageWidth(Math.min(width, 720));
    } finally {
        URL.revokeObjectURL(objectUrl);
    }
}

function insertTextAtCursor(text: string) {
    const textarea = textareaRef.value;
    const current = store.currentContent || "";
    if (!textarea) {
        store.currentContent = current + text;
        scheduleSave();
        return;
    }
    const start = textarea.selectionStart ?? current.length;
    const end = textarea.selectionEnd ?? current.length;
    store.currentContent = current.slice(0, start) + text + current.slice(end);
    scheduleSave();
    nextTick(() => {
        const nextPos = start + text.length;
        textarea.focus();
        textarea.setSelectionRange(nextPos, nextPos);
    });
}

async function handleEditorPaste(e: ClipboardEvent) {
    if (!store.currentNoteId) return;
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles: File[] = [];
    for (const item of items) {
        if (item.type.startsWith("image/")) {
            const file = item.getAsFile();
            if (file) imageFiles.push(file);
        }
    }
    if (!imageFiles.length) return;
    e.preventDefault();
    try {
        const snippets: string[] = [];
        for (const [i, file] of imageFiles.entries()) {
            const uploaded = await uploadNoteImage(store.currentNoteId, file);
            const width = await readImageWidth(file);
            const alt = imageFiles.length > 1 ? `图片${i + 1}` : "图片";
            snippets.push(`![${alt}](${uploaded.url}){width=${width}}`);
        }
        const prefix = store.currentContent && !store.currentContent.endsWith("\n") ? "\n" : "";
        const suffix = "\n";
        insertTextAtCursor(`${prefix}${snippets.join("\n\n")}${suffix}`);
    } catch (error) {
        alert(error instanceof Error ? error.message : "图片上传失败");
    }
}

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
        const label = validLang || "text";
        return (
            `<div class="code-block-wrapper">` +
            `<div class="code-block-header">` +
            `<span class="code-lang">` +
            `${label}` +
            `<svg class="code-lang-chevron" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>` +
            `</span>` +
            `</div>` +
            `<pre class="hljs"><code class="hljs-code">${highlighted}</code></pre>` +
            `</div>`
        );
    },
});

const renderedHtml = computed(() => {
    const source = store.currentContent || "";
    const images = parseNoteImages(source);
    if (!images.length) {
        return md.render(source);
    }
    let cursor = 0;
    let normalized = "";
    for (const image of images) {
        normalized += source.slice(cursor, image.start);
        normalized += `NOTE_IMAGE_PLACEHOLDER_${image.index}`;
        cursor = image.end;
    }
    normalized += source.slice(cursor);

    let html = md.render(normalized);
    for (const image of images) {
        const widthStyle = image.width
            ? `width:${image.width}px;max-width:100%;`
            : "max-width:100%;";
        const replacement =
            `<span class="note-image-block" contenteditable="false">` +
            `<span class="note-image-frame">` +
            `<img class="note-inline-image" src="${escapeHtml(buildAuthedImageUrl(image.url))}" alt="${escapeHtml(image.alt)}" data-note-image-index="${image.index}" style="${widthStyle}" />` +
            `<span class="note-image-resize-handle" data-note-image-index="${image.index}" title="拖拽调整图片宽度"></span>` +
            `</span>` +
            `</span>`;
        html = html.replace(`NOTE_IMAGE_PLACEHOLDER_${image.index}`, replacement);
    }
    return html;
});

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

function handlePreviewMouseDown(e: MouseEvent) {
    const target = e.target as HTMLElement | null;
    const handle = target?.closest(".note-image-resize-handle") as HTMLElement | null;
    if (!handle) return;
    const index = Number(handle.dataset.noteImageIndex);
    if (Number.isNaN(index)) return;
    const image = previewRef.value?.querySelector(`img[data-note-image-index="${index}"]`) as HTMLImageElement | null;
    if (!image) return;
    e.preventDefault();
    activeResize.value = {
        index,
        startX: e.clientX,
        startWidth: image.getBoundingClientRect().width,
    };
    window.addEventListener("mousemove", handlePreviewMouseMove);
    window.addEventListener("mouseup", handlePreviewMouseUp);
}

function handlePreviewMouseMove(e: MouseEvent) {
    if (!activeResize.value || !previewRef.value) return;
    const nextWidth = clampImageWidth(
        activeResize.value.startWidth + (e.clientX - activeResize.value.startX)
    );
    Array.from(
        previewRef.value.querySelectorAll(`img[data-note-image-index="${activeResize.value.index}"]`)
    ).forEach((node) => {
        const image = node as HTMLImageElement;
            image.style.width = `${nextWidth}px`;
            image.style.maxWidth = "100%";
        });
}

function handlePreviewMouseUp(e: MouseEvent) {
    if (!activeResize.value) return;
    const nextWidth = clampImageWidth(
        activeResize.value.startWidth + (e.clientX - activeResize.value.startX)
    );
    store.currentContent = replaceImageMarkupWithWidth(
        store.currentContent || "",
        activeResize.value.index,
        nextWidth
    );
    scheduleSave();
    activeResize.value = null;
    window.removeEventListener("mousemove", handlePreviewMouseMove);
    window.removeEventListener("mouseup", handlePreviewMouseUp);
}

onBeforeUnmount(() => {
    window.removeEventListener("mousemove", handlePreviewMouseMove);
    window.removeEventListener("mouseup", handlePreviewMouseUp);
});

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
    color: var(--text-primary);
}
.md-preview :deep(ul),
.md-preview :deep(ol) {
    padding-left: 1.5em;
    margin: 0.4em 0;
}
.md-preview :deep(li) {
    margin: 0.2em 0;
    color: var(--text-primary);
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

.md-preview :deep(.code-block-wrapper) {
    margin: 0.9em 0;
    overflow: hidden;
    font-size: 0;
}

.md-preview :deep(.code-block-header) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    background: var(--code-block-header);
    border: 1px solid var(--code-block-border);
    border-bottom: none;
    border-radius: 10px 10px 0 0;
    user-select: none;
    font-size: 13px;
}

.md-preview :deep(.code-lang) {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12.5px;
    font-family: "SF Mono", "Fira Code", "Cascadia Code", ui-monospace, monospace;
    color: var(--text-primary);
    font-weight: 600;
    letter-spacing: 0.2px;
}

.md-preview :deep(.code-lang-chevron) {
    opacity: 0.45;
    flex-shrink: 0;
}

.md-preview :deep(.code-block-wrapper pre.hljs) {
    margin: 0;
    padding: 14px 18px;
    overflow-x: auto;
    font-size: 13.5px;
    line-height: 1.7;
    background: #f5f5f7;
    border: 1px solid #e2e2e8;
    border-radius: 0 0 10px 10px;
}

.md-preview :deep(.code-block-wrapper code.hljs-code) {
    display: block;
    white-space: pre;
    background: transparent;
    padding: 0;
    font-family: "SF Mono", "Fira Code", "Cascadia Code", ui-monospace, monospace;
    font-size: 13.5px;
    line-height: 1.7;
    color: #2b2b2b;
}
.md-preview :deep(.hljs-comment),
.md-preview :deep(.hljs-quote) { color: #8b8b96; font-style: italic; }
.md-preview :deep(.hljs-keyword),
.md-preview :deep(.hljs-selector-tag),
.md-preview :deep(.hljs-built_in),
.md-preview :deep(.hljs-name),
.md-preview :deep(.hljs-tag) { color: #d14d8b; }
.md-preview :deep(.hljs-string),
.md-preview :deep(.hljs-addition),
.md-preview :deep(.hljs-title),
.md-preview :deep(.hljs-section),
.md-preview :deep(.hljs-attribute),
.md-preview :deep(.hljs-literal),
.md-preview :deep(.hljs-template-tag),
.md-preview :deep(.hljs-template-variable),
.md-preview :deep(.hljs-type) { color: #589a52; }
.md-preview :deep(.hljs-number),
.md-preview :deep(.hljs-regexp),
.md-preview :deep(.hljs-symbol),
.md-preview :deep(.hljs-bullet) { color: #c28735; }
.md-preview :deep(blockquote) {
    border-left: 3px solid var(--blockquote-border);
    padding-left: 12px;
    color: var(--text-primary);
    margin: 0.5em 0;
}
.md-preview :deep(hr) {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1em 0;
}

.md-preview :deep(.note-image-block) {
    display: inline-flex;
    margin: 0.85em 0;
}

.md-preview :deep(.note-image-frame) {
    position: relative;
    display: inline-flex;
    max-width: 100%;
}

.md-preview :deep(.note-inline-image) {
    display: block;
    height: auto;
    max-width: 100%;
    border-radius: 10px;
    border: 1px solid var(--border-light);
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.md-preview :deep(.note-image-resize-handle) {
    position: absolute;
    top: 0;
    right: -8px;
    width: 14px;
    height: 100%;
    cursor: ew-resize;
}

.md-preview :deep(.note-image-resize-handle::before) {
    content: "";
    position: absolute;
    top: 50%;
    right: 2px;
    transform: translateY(-50%);
    width: 4px;
    height: 42px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.16);
}

.md-preview :deep(.note-image-frame:hover .note-image-resize-handle::before) {
    background: var(--accent);
}
</style>
