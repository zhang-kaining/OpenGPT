<template>
    <div class="chat-view" :class="{ desktop: isDesktop }">
        <!-- 顶部栏 -->
        <div class="chat-header" :class="{ desktop: isDesktop }">
            <button
                v-if="sidebarCollapsed"
                class="expand-sidebar-btn"
                title="展开侧边栏"
                @click="sidebarCollapsed = false"
            >
                <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                >
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <path d="M9 3v18" />
                </svg>
            </button>
            <div
                class="chat-title"
                :title="store.currentConversation?.title || '新对话'"
            >
                {{ store.currentConversation?.title || "新对话" }}
            </div>
        </div>
        <!-- 消息区域 -->
        <div ref="scrollEl" class="messages-container" @scroll="onScroll">
            <!-- 欢迎页 -->
            <div v-if="store.messages.length === 0" class="welcome">
                <div v-if="!isDesktop" class="welcome-logo">
                    <img src="/hamster.svg" alt="logo" width="48" height="48" />
                </div>
                <h2>
                    {{
                        isDesktop
                            ? "有什么我能帮你的吗？"
                            : "有什么可以帮忙的？"
                    }}
                </h2>

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
import { ref, watch, nextTick, inject, onMounted, onUnmounted } from "vue";
import type { Ref } from "vue";
import { useChatStore } from "@/stores/chat";
import MessageBubble from "./MessageBubble.vue";
import InputBar from "./InputBar.vue";

const store = useChatStore();
const sidebarCollapsed = inject<Ref<boolean>>("sidebarCollapsed", ref(false));
const isDesktop = inject<Ref<boolean>>("isDesktop", ref(false));
const scrollEl = ref<HTMLElement | null>(null);
const autoStickToBottom = ref(true);

interface NewsEntry {
    title: string;
    link: string;
    source: string;
    summary: string;
    published: string;
    timeAgo?: string;
}

const newsItems = ref<NewsEntry[]>([]);
const newsLoading = ref(false);

function timeAgo(iso: string): string {
    if (!iso) return "";
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins} 分钟前`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} 小时前`;
    const days = Math.floor(hrs / 24);
    return `${days} 天前`;
}

async function loadNews() {
    if (newsItems.value.length) return;
    newsLoading.value = true;
    try {
        const res = await fetch("/api/news");
        if (!res.ok) return;
        const data = await res.json();
        newsItems.value = (data.items || [])
            .slice(0, 6)
            .map((n: NewsEntry) => ({
                ...n,
                timeAgo: timeAgo(n.published),
            }));
    } catch {
        /* ignore */
    } finally {
        newsLoading.value = false;
    }
}

onMounted(() => {
    store.loadLlmCatalog();
    loadNews();
    window.addEventListener(
        "mygpt-llm-providers-updated",
        store.loadLlmCatalog
    );
});

onUnmounted(() => {
    window.removeEventListener(
        "mygpt-llm-providers-updated",
        store.loadLlmCatalog
    );
});

function useSuggestion(text: string) {
    store.sendMessage(text);
}

function scrollToBottom() {
    if (!autoStickToBottom.value) return;
    nextTick(() => {
        if (scrollEl.value) {
            scrollEl.value.scrollTop = scrollEl.value.scrollHeight;
        }
    });
}

function onScroll() {
    const el = scrollEl.value;
    if (!el) return;
    const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
    autoStickToBottom.value = gap < 40;
}

watch(() => store.messages.length, scrollToBottom);
watch(() => store.messages[store.messages.length - 1]?.content, scrollToBottom);
watch(
    () => store.currentConvId,
    () => {
        autoStickToBottom.value = true;
        scrollToBottom();
    }
);
</script>

<style scoped>
.chat-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg-main);
    min-width: 0;
    position: relative;
}
.chat-view.desktop {
    padding-top: 8px;
}

.chat-header {
    height: 52px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 16px;
    flex-shrink: 0;
    position: sticky;
    top: 0;
    z-index: 5;
    background: var(--bg-main);
    border-bottom: 1px solid var(--border-light);
}
.chat-header.desktop {
    padding-top: 28px;
    height: 62px;
    -webkit-app-region: drag;
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
    -webkit-app-region: no-drag;
}
.expand-sidebar-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}

.model-selector-wrap {
    display: none;
}

.chat-title {
    flex: 1;
    min-width: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: center;
    padding: 0 8px;
    letter-spacing: -0.01em;
}

.messages-container {
    flex: 1;
    overflow-y: auto;
    scroll-behavior: auto;
    min-height: 0;
}

/* Welcome screen */
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
    position: relative;
}

/* Ambient glow behind heading */
.welcome::before {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -60%);
    width: 400px;
    height: 300px;
    background: radial-gradient(
        ellipse,
        rgba(224, 149, 74, 0.07) 0%,
        transparent 70%
    );
    pointer-events: none;
}

.welcome-logo {
    color: var(--text-primary);
    margin-bottom: 4px;
    animation: fade-up 0.5s ease 0.05s both;
}

.welcome h2 {
    font-size: 30px;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.2;
    animation: fade-up 0.5s ease 0.1s both;
    /* Warm gradient text */
    background: linear-gradient(
        135deg,
        var(--text-primary) 30%,
        var(--accent) 100%
    );
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.news-section {
    max-width: 660px;
    width: 100%;
    margin-top: 16px;
    animation: fade-up 0.5s ease 0.2s both;
}

.news-header {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
    padding-left: 4px;
}

.news-header-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
    flex-shrink: 0;
    animation: pulse-dot 2.5s ease-in-out infinite;
    box-shadow: 0 0 6px rgba(224, 149, 74, 0.5);
}

@keyframes pulse-dot {
    0%,
    100% {
        opacity: 1;
        transform: scale(1);
    }
    50% {
        opacity: 0.4;
        transform: scale(0.8);
    }
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
    padding: 13px 15px;
    background: var(--surface-1);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    text-decoration: none;
    cursor: pointer;
    transition: background 0.2s, border-color 0.2s, transform 0.2s,
        box-shadow 0.2s;
    min-height: 76px;
    text-align: left;
    /* Staggered entrance */
    animation: fade-up 0.45s ease both;
}
.news-card:nth-child(1) {
    animation-delay: 0.25s;
}
.news-card:nth-child(2) {
    animation-delay: 0.3s;
}
.news-card:nth-child(3) {
    animation-delay: 0.35s;
}
.news-card:nth-child(4) {
    animation-delay: 0.4s;
}
.news-card:nth-child(5) {
    animation-delay: 0.45s;
}
.news-card:nth-child(6) {
    animation-delay: 0.5s;
}

.news-card:hover {
    background: var(--surface-2);
    border-color: rgba(224, 149, 74, 0.2);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
}

.news-title {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--text-primary);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.news-meta {
    display: flex;
    align-items: center;
    font-size: 11px;
    color: var(--text-muted);
}

.news-source {
    color: var(--text-secondary);
    font-weight: 600;
}

.news-dot {
    margin: 0 4px;
    opacity: 0.45;
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
.news-loading-dot:nth-child(2) {
    animation-delay: 0.16s;
}
.news-loading-dot:nth-child(3) {
    animation-delay: 0.32s;
}

@keyframes news-bounce {
    0%,
    80%,
    100% {
        opacity: 0.3;
        transform: scale(0.8);
    }
    40% {
        opacity: 1;
        transform: scale(1);
    }
}

@media (max-width: 560px) {
    .news-grid {
        grid-template-columns: 1fr;
    }
    .welcome h2 {
        font-size: 24px;
    }
}

.messages-list {
    padding: 8px 0 24px;
}
</style>
