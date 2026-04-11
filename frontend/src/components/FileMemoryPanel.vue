<template>
    <Teleport to="body">
        <div
            v-if="store.showFileMemoryPanel"
            class="overlay"
            @click.self="store.showFileMemoryPanel = false"
        >
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">
                        <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                        文件型记忆 (主控记忆)
                    </div>
                    <button
                        class="close-btn"
                        @click="store.showFileMemoryPanel = false"
                    >
                        <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2.5"
                        >
                            <path d="M18 6 6 18M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div class="panel-body">
                    <p class="panel-desc">
                        这是主控模型维护的长期记忆。最多 200 行，超过时优先淘汰低优先级事实。<br>
                        <strong>P1</strong>: 稳定偏好 (几乎不淘汰) | <strong>P2</strong>: 长期事实 | <strong>P3</strong>: 临时上下文
                    </p>

                    <div v-if="!store.fileMemoryLines || store.fileMemoryLines.length === 0" class="empty-state">
                        <svg
                            width="32"
                            height="32"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.5"
                        >
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        </svg>
                        <p>暂无文件型记忆</p>
                        <span>AI 尚未记录任何长期事实</span>
                    </div>

                    <div v-else class="memory-list">
                        <div class="memory-stats">
                            共 {{ store.fileMemoryLines?.length || 0 }} / 200 行
                        </div>
                        <div
                            v-for="item in sortedLines"
                            :key="item.id"
                            class="memory-item"
                        >
                            <div class="memory-meta">
                                <span :class="['priority-badge', item.priority.toLowerCase()]">{{ item.priority }}</span>
                                <span class="kind-badge">{{ item.kind }}</span>
                                <span class="time-text">{{ item.time }}</span>
                            </div>
                            
                            <div v-if="editingId === item.id" class="edit-mode">
                                <textarea v-model="editForm.text" class="edit-textarea"></textarea>
                                <div class="edit-controls">
                                    <select v-model="editForm.priority" class="edit-select">
                                        <option value="P1">P1 (最高)</option>
                                        <option value="P2">P2 (中等)</option>
                                        <option value="P3">P3 (最低)</option>
                                    </select>
                                    <input v-model="editForm.kind" type="text" class="edit-input" placeholder="类型 (如 preference)" />
                                    <div class="edit-actions">
                                        <button class="btn-cancel" @click="cancelEdit">取消</button>
                                        <button class="btn-save" @click="saveEdit(item.id)">保存</button>
                                    </div>
                                </div>
                            </div>
                            
                            <div v-else class="view-mode">
                                <span class="memory-text">{{ item.text }}</span>
                                <div class="action-buttons">
                                    <button
                                        v-if="item.priority !== 'P1'"
                                        class="action-btn"
                                        title="置顶为 P1"
                                        @click="pinLine(item.id)"
                                    >
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                                        </svg>
                                    </button>
                                    <button
                                        class="action-btn"
                                        title="编辑"
                                        @click="startEdit(item)"
                                    >
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                        </svg>
                                    </button>
                                    <button
                                        class="action-btn delete-btn"
                                        title="删除"
                                        @click="deleteLine(item.id)"
                                    >
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </Teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from "@/stores/chat"
import type { FileMemoryLine } from "@/types"

const store = useChatStore()

const sortedLines = computed(() => {
    if (!Array.isArray(store.fileMemoryLines)) return []
    // Sort by priority (P1 > P2 > P3), then by time (newest first)
    return [...store.fileMemoryLines].sort((a, b) => {
        if (a.priority !== b.priority) {
            return a.priority.localeCompare(b.priority)
        }
        return b.time.localeCompare(a.time)
    })
})

const editingId = ref<string | null>(null)
const editForm = ref({
    text: '',
    priority: 'P3',
    kind: 'fact'
})

function startEdit(item: FileMemoryLine) {
    editingId.value = item.id
    editForm.value = {
        text: item.text,
        priority: item.priority,
        kind: item.kind
    }
}

function cancelEdit() {
    editingId.value = null
}

async function saveEdit(id: string) {
    await store.updateFileMemoryLine('controller_memory', id, editForm.value.text, editForm.value.priority, editForm.value.kind)
    editingId.value = null
}

async function deleteLine(id: string) {
    if (confirm('确定要删除这条记忆吗？')) {
        await store.deleteFileMemoryLine('controller_memory', id)
    }
}

async function pinLine(id: string) {
    await store.pinFileMemoryLine('controller_memory', id)
}
</script>

<style scoped>
.overlay {
    position: fixed;
    inset: 0;
    background: var(--overlay-bg);
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
    width: 600px;
    max-width: 90vw;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--modal-shadow);
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
.close-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}

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
.empty-state p {
    font-size: 15px;
    font-weight: 500;
    color: var(--text-secondary);
}
.empty-state span {
    font-size: 13px;
    text-align: center;
}

.memory-stats {
    font-size: 12px;
    color: var(--text-muted);
    text-align: right;
    margin-bottom: 8px;
}

.memory-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.memory-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    background: var(--bg-hover);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
}

.memory-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
}

.priority-badge {
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
}
.priority-badge.p1 { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.priority-badge.p2 { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.priority-badge.p3 { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }

.kind-badge {
    background: var(--bg-secondary);
    color: var(--text-secondary);
    padding: 2px 6px;
    border-radius: 4px;
}

.time-text {
    color: var(--text-muted);
    margin-left: auto;
}

.view-mode {
    display: flex;
    align-items: flex-start;
    gap: 12px;
}

.memory-text {
    flex: 1;
    font-size: 14px;
    color: var(--text-primary);
    line-height: 1.5;
    white-space: pre-wrap;
}

.action-buttons {
    display: flex;
    gap: 4px;
}

.action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: none;
    border: none;
    border-radius: 4px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.12s;
}
.action-btn:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
}
.action-btn.delete-btn:hover {
    color: var(--danger);
    background: rgba(239, 68, 68, 0.1);
}

.edit-mode {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.edit-textarea {
    width: 100%;
    min-height: 60px;
    padding: 8px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-primary);
    font-family: inherit;
    font-size: 13px;
    resize: vertical;
}

.edit-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.edit-select, .edit-input {
    padding: 4px 8px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 12px;
}

.edit-actions {
    display: flex;
    gap: 8px;
    margin-left: auto;
}

.btn-cancel, .btn-save {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    border: none;
}
.btn-cancel {
    background: var(--bg-secondary);
    color: var(--text-primary);
}
.btn-save {
    background: var(--accent);
    color: white;
}
</style>
