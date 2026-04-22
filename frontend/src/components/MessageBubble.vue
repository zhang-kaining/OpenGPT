<template>
    <div class="message-row" :class="message.role">
        <div class="message-inner">
            <!-- AI 消息：左对齐，无气泡 -->
            <template v-if="message.role === 'assistant'">
                <div class="assistant-avatar">
                    <img src="/hamster.svg" alt="AI" />
                </div>
                <div class="assistant-content">
                    <!-- 搜索中状态 -->
                    <div v-if="message.searching" class="searching-indicator">
                        <div class="search-spinner"><span></span></div>
                        <span class="search-text"
                            >正在搜索{{
                                message.searchQuery
                                    ? "：" + message.searchQuery
                                    : "..."
                            }}</span
                        >
                    </div>
                    <div
                        v-if="message.toolCall && !message.searching"
                        class="searching-indicator tool-call-indicator"
                    >
                        <div class="search-spinner"><span></span></div>
                        <span class="search-text">{{ message.toolCall }}</span>
                    </div>

                    <MessageStructuredContent
                        v-if="message.content && messageRenderMode === 'structured'"
                        :content="message.content"
                    />
                    <MessageMarkdownContent
                        v-else-if="message.content"
                        :content="message.content"
                    />

                    <!-- 等待动画（还没有内容时） -->
                    <div
                        v-if="
                            message.streaming &&
                            !message.searching &&
                            !message.content
                        "
                        class="thinking-indicator"
                    >
                        <div class="thinking-bars">
                            <span></span><span></span><span></span><span></span>
                        </div>
                        <span class="thinking-label">思考中</span>
                    </div>

                    <!-- 引用来源 -->
                    <CitationList :citations="message.citations" />

                    <!-- 操作按钮 + Token 消耗 -->
                    <div
                        v-if="!message.streaming && message.content"
                        class="message-actions"
                    >
                        <button
                            class="msg-action-btn"
                            :class="{ copied: copied }"
                            title="复制"
                            @click="copyContent"
                        >
                            <svg
                                v-if="copied"
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2.5"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            >
                                <polyline points="20 6 9 17 4 12" />
                            </svg>
                            <svg
                                v-else
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2"
                            >
                                <rect
                                    x="9"
                                    y="9"
                                    width="13"
                                    height="13"
                                    rx="2"
                                    ry="2"
                                />
                                <path
                                    d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                                />
                            </svg>
                        </button>
                        <button class="msg-action-btn" title="点赞">
                            <svg
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2"
                            >
                                <path
                                    d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"
                                />
                                <path
                                    d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"
                                />
                            </svg>
                        </button>
                        <button class="msg-action-btn" title="点踩">
                            <svg
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2"
                            >
                                <path
                                    d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"
                                />
                                <path
                                    d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"
                                />
                            </svg>
                        </button>
                        <!-- Token 消耗 -->
                        <div
                            v-if="message.usage"
                            class="token-usage"
                            :title="usageDetail"
                        >
                            <svg
                                width="12"
                                height="12"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2"
                            >
                                <circle cx="12" cy="12" r="10" />
                                <polyline points="12 6 12 12 16 14" />
                            </svg>
                            <span>{{ message.usage.total_tokens }} tokens</span>
                        </div>
                    </div>
                </div>
            </template>

            <!-- 用户消息：右对齐，有气泡 -->
            <template v-else>
                <div class="user-message-wrap">
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
                    <div class="user-avatar">
                        <img :src="userAvatar" alt="用户" />
                    </div>
                </div>
            </template>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { Message } from "@/types";
import CitationList from "./CitationList.vue";
import MessageMarkdownContent from "./MessageMarkdownContent.vue";
import MessageStructuredContent from "./MessageStructuredContent.vue";
import { messageRenderMode } from "@/composables/useMessageRenderMode";
import { userAvatar } from "@/composables/useAvatar";

const props = defineProps<{ message: Message }>();
const copied = ref(false);

const usageDetail = computed(() => {
    const u = props.message.usage;
    if (!u) return "";
    return `输入: ${u.prompt_tokens}  输出: ${u.completion_tokens}  合计: ${u.total_tokens}`;
});

async function copyContent() {
    const text = props.message.content;
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            // 降级方案：execCommand
            const el = document.createElement("textarea");
            el.value = text;
            el.style.cssText = "position:fixed;opacity:0;pointer-events:none";
            document.body.appendChild(el);
            el.select();
            document.execCommand("copy");
            document.body.removeChild(el);
        }
        copied.value = true;
        setTimeout(() => {
            copied.value = false;
        }, 2000);
    } catch {}
}

function openImage(src: string) {
    window.open(src, "_blank");
}
</script>

<style scoped>
.message-row {
    width: 100%;
    padding: 8px 0;
    animation: fade-up 0.3s ease both;
}

.message-inner {
    max-width: 90%;
    margin: 0 auto;
    padding: 0 16px;
}

/* User message right-aligned */
.message-row.user .message-inner {
    display: flex;
    justify-content: flex-end;
}

.user-message {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
    width: fit-content;
    max-width: 100%;
}

.user-message-wrap {
    display: flex;
    align-items: flex-start; /* flex-start = 头像顶部与气泡顶部对齐，再配合 margin-top 微调 */
    gap: 8px;
    max-width: 80%;
}

.user-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    overflow: hidden;
    flex-shrink: 0;
    background: var(--surface-2);
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border);
    margin-top: 4px; /* 气泡 padding-top(11px) + 首行中心(~13px) - 头像半径(20px) ≈ 4px */
}

.user-avatar img {
    width: 75%;
    height: 75%;
    object-fit: cover;
    display: block;
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
    transition: opacity 0.15s, transform 0.15s;
}
.user-image:hover {
    opacity: 0.9;
    transform: scale(1.02);
}

.user-bubble {
    background: var(--bg-message-user);
    padding: 11px 17px;
    border-radius: 18px 18px 4px 18px;
    font-size: 15.5px;
    line-height: 1.65;
    word-break: break-word;
    white-space: pre-wrap;
    color: var(--text-primary);
    border: 1px solid var(--border);
    /* Subtle inner top highlight */
    background-image: linear-gradient(
        160deg,
        rgba(255, 235, 205, 0.04) 0%,
        transparent 50%
    );
}

/* AI message left-aligned */
.message-row.assistant .message-inner {
    display: flex;
    align-items: flex-start;
    gap: 10px;
}

/* 对话框的头像 */
.assistant-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--accent-light);
    border: 1px solid rgba(224, 149, 74, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: -6px; /* 控制头像和首行的对齐 */
    overflow: hidden;
    box-shadow: 0 0 12px rgba(224, 149, 74, 0.08);
}

.assistant-avatar img {
    width: 75%;
    height: 75%;
    object-fit: cover;
    display: block;
}

.assistant-content {
    flex: 1;
    min-width: 0;
    padding-top: 0;
}

.assistant-content :deep(.msg-structured-content > :first-child) {
    margin-top: 0;
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
    background: rgba(224, 149, 74, 0.07);
    border-color: rgba(224, 149, 74, 0.2);
    color: var(--accent);
}

/* Search spinner dots */
.search-spinner {
    display: flex;
    align-items: center;
    gap: 3px;
    flex-shrink: 0;
}
.search-spinner::before,
.search-spinner::after,
.search-spinner span {
    content: "";
    display: block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--text-secondary);
    animation: bounce 1.2s ease-in-out infinite;
}
.search-spinner::before {
    animation-delay: 0s;
}
.search-spinner span {
    animation-delay: 0.2s;
}
.search-spinner::after {
    animation-delay: 0.4s;
}

/* Thinking indicator */
.thinking-indicator {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 7px 14px 7px 12px;
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
    background: var(--accent);
    animation: bar-pulse 1.2s ease-in-out infinite;
    opacity: 0.7;
}
.thinking-bars span:nth-child(1) {
    height: 8px;
    animation-delay: 0s;
}
.thinking-bars span:nth-child(2) {
    height: 12px;
    animation-delay: 0.15s;
}
.thinking-bars span:nth-child(3) {
    height: 16px;
    animation-delay: 0.3s;
}
.thinking-bars span:nth-child(4) {
    height: 10px;
    animation-delay: 0.45s;
}

@keyframes bar-pulse {
    0%,
    100% {
        opacity: 0.25;
        transform: scaleY(0.55);
    }
    50% {
        opacity: 0.9;
        transform: scaleY(1);
    }
}

@keyframes bounce {
    0%,
    60%,
    100% {
        transform: translateY(0);
        opacity: 0.35;
    }
    30% {
        transform: translateY(-4px);
        opacity: 1;
    }
}

.message-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    margin-top: 8px;
    opacity: 0;
    transition: opacity 0.18s;
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
    color: var(--accent);
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

/* Classic markdown mode */
:deep(.citation-ref) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    background: var(--accent-light);
    color: var(--accent);
    border-radius: 50%;
    font-size: 0.68em;
    font-weight: 700;
    cursor: pointer;
    vertical-align: super;
    margin: 0 1px;
    transition: background 0.15s, color 0.15s;
    text-decoration: none;
}

:deep(.code-block-wrapper) {
    margin: 12px 0;
    overflow: hidden;
    font-size: 0;
}

:deep(.code-block-header) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 6px 7px 14px;
    background: var(--code-block-header);
    border: 1px solid var(--code-block-border);
    border-bottom: none;
    border-radius: 10px 10px 0 0;
    user-select: none;
    font-size: 13px;
}

:deep(.code-lang) {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 12.5px;
    font-family: "SF Mono", "Fira Code", "Cascadia Code", ui-monospace, monospace;
    color: var(--text-secondary);
    font-weight: 500;
    letter-spacing: 0.2px;
}

:deep(.code-lang-chevron) {
    opacity: 0.5;
    flex-shrink: 0;
}

:deep(.code-actions) {
    display: inline-flex;
    align-items: center;
    gap: 2px;
}

:deep(.code-icon-btn) {
    display: inline-flex;
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
    flex-shrink: 0;
}
:deep(.code-icon-btn:hover) {
    background: var(--surface-3);
    color: var(--text-secondary);
}
:deep(.code-icon-btn.copied) {
    color: #6bbf7a;
}
:deep(.code-icon-btn.active) {
    color: var(--accent);
    background: var(--accent-light);
}

:deep(.code-block-wrapper) pre.hljs {
    margin: 0;
    padding: 14px 18px;
    overflow-x: auto;
    font-size: 13.5px;
    line-height: 1.7;
    background: var(--code-block-bg);
    border: 1px solid var(--code-block-border);
    border-radius: 0 0 10px 10px;
}
:deep(.code-block-wrapper) code.hljs-code {
    font-family: "SF Mono", "Fira Code", "Cascadia Code", ui-monospace, monospace;
    color: var(--code-block-text);
    background: transparent;
    padding: 0;
}

:deep(.hljs-comment),
:deep(.hljs-quote) { color: #7a6e5e; font-style: italic; }
:deep(.hljs-keyword),
:deep(.hljs-selector-tag),
:deep(.hljs-built_in),
:deep(.hljs-name),
:deep(.hljs-tag) { color: #c97eb0; }
:deep(.hljs-string),
:deep(.hljs-addition) { color: #9fbe8c; }
:deep(.hljs-title),
:deep(.hljs-section),
:deep(.hljs-attribute),
:deep(.hljs-literal),
:deep(.hljs-template-tag),
:deep(.hljs-template-variable),
:deep(.hljs-type) { color: #9fbe8c; }
:deep(.hljs-deletion),
:deep(.hljs-selector-attr),
:deep(.hljs-selector-pseudo),
:deep(.hljs-meta) { color: #b08898; }
:deep(.hljs-doctag) { color: #7a9abf; }
:deep(.hljs-attr) { color: #b8a86a; }
:deep(.hljs-symbol),
:deep(.hljs-bullet),
:deep(.hljs-link) { color: #7dc4b8; }
:deep(.hljs-emphasis) { font-style: italic; }
:deep(.hljs-strong) { font-weight: bold; }
:deep(.hljs-number),
:deep(.hljs-regexp) { color: #c4956a; }
:deep(.hljs-variable),
:deep(.hljs-params) { color: #e4d9c8; }
:deep(.hljs-function) { color: #82aadf; }
:deep(.hljs-class .hljs-title),
:deep(.hljs-title.class_) { color: #e8c06a; font-weight: 600; }
:deep(.hljs-punctuation),
:deep(.hljs-operator) { color: #9a9080; }

</style>
