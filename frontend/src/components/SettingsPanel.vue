<template>
  <Teleport to="body">
    <div v-if="visible" class="settings-overlay" @click.self="$emit('close')">
      <div class="settings-panel">
        <!-- Header -->
        <div class="panel-header">
          <h2>设置</h2>
          <button class="close-btn" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <!-- Tabs -->
        <div class="tabs">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            class="tab-btn"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- Skills Tab -->
        <div v-if="activeTab === 'skills'" class="tab-content">
          <p class="tab-desc">技能是预置的工具和行为指令，按需启用。</p>
          <div v-if="loadingSkills" class="loading-hint">加载中...</div>
          <div v-else class="skill-list">
            <div v-for="skill in skills" :key="skill.name" class="skill-item">
              <div class="skill-info">
                <div class="skill-name">{{ skill.name }}</div>
                <div class="skill-desc">{{ skill.description }}</div>
                <div v-if="skill.tools.length" class="skill-tools">
                  <span v-for="t in skill.tools" :key="t" class="tool-tag">{{ t }}</span>
                </div>
              </div>
              <label class="toggle">
                <input
                  type="checkbox"
                  :checked="skill.enabled"
                  :disabled="togglingSkill === skill.name"
                  @change="toggleSkill(skill.name, ($event.target as HTMLInputElement).checked)"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>
            <div v-if="!skills.length" class="empty-hint">暂无可用技能</div>
          </div>
        </div>

        <!-- MCP Tab -->
        <div v-if="activeTab === 'mcp'" class="tab-content">
          <p class="tab-desc">
            配置 MCP Server，格式与 Cursor 完全一致。
            <a href="https://github.com/modelcontextprotocol/servers" target="_blank" class="link">浏览可用 Server →</a>
          </p>

          <div class="mcp-status-bar">
            <span class="status-dot" :class="mcpStatus.available ? 'green' : 'gray'"></span>
            <span>{{ mcpStatus.available ? `已加载 ${mcpStatus.tools.length} 个工具` : '未启用' }}</span>
            <span v-if="mcpStatus.tools.length" class="tool-names">
              {{ mcpStatus.tools.join(', ') }}
            </span>
          </div>

          <div class="editor-wrap">
            <textarea
              v-model="mcpConfigText"
              class="json-editor"
              spellcheck="false"
              placeholder='{"mcpServers": {}}'
            ></textarea>
            <div v-if="jsonError" class="json-error">{{ jsonError }}</div>
          </div>

          <div class="action-row">
            <button class="btn-secondary" @click="loadMcpConfig">重置</button>
            <button class="btn-primary" :disabled="savingMcp || !!jsonError" @click="saveMcpConfig">
              {{ savingMcp ? '保存中...' : '保存并重载' }}
            </button>
          </div>

          <div v-if="mcpSaveResult" class="save-result" :class="mcpSaveResult.ok ? 'ok' : 'err'">
            {{ mcpSaveResult.msg }}
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{ visible: boolean }>()
defineEmits(['close'])

const tabs = [
  { id: 'skills', label: '技能 Skills' },
  { id: 'mcp',    label: 'MCP 工具' },
]
const activeTab = ref('skills')

// ── Skills ────────────────────────────────────────────────────────────────────

interface SkillInfo {
  name: string
  description: string
  enabled: boolean
  tools: string[]
}

const skills = ref<SkillInfo[]>([])
const loadingSkills = ref(false)
const togglingSkill = ref<string | null>(null)

async function loadSkills() {
  loadingSkills.value = true
  try {
    const res = await fetch('/api/settings/skills')
    skills.value = await res.json()
  } finally {
    loadingSkills.value = false
  }
}

async function toggleSkill(name: string, enabled: boolean) {
  togglingSkill.value = name
  try {
    await fetch(`/api/settings/skills/${name}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    const skill = skills.value.find(s => s.name === name)
    if (skill) skill.enabled = enabled
  } finally {
    togglingSkill.value = null
  }
}

// ── MCP ───────────────────────────────────────────────────────────────────────

const mcpConfigText = ref('')
const savingMcp = ref(false)
const mcpSaveResult = ref<{ ok: boolean; msg: string } | null>(null)
const mcpStatus = ref<{ available: boolean; tools: string[] }>({ available: false, tools: [] })

const jsonError = computed(() => {
  if (!mcpConfigText.value.trim()) return ''
  try {
    JSON.parse(mcpConfigText.value)
    return ''
  } catch (e: any) {
    return `JSON 格式错误: ${e.message}`
  }
})

async function loadMcpConfig() {
  const [cfg, status] = await Promise.all([
    fetch('/api/settings/mcp').then(r => r.json()),
    fetch('/api/settings/mcp/status').then(r => r.json()),
  ])
  mcpConfigText.value = JSON.stringify(cfg, null, 2)
  mcpStatus.value = status
}

async function saveMcpConfig() {
  if (jsonError.value) return
  savingMcp.value = true
  mcpSaveResult.value = null
  try {
    const config = JSON.parse(mcpConfigText.value)
    const res = await fetch('/api/settings/mcp', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config }),
    })
    const data = await res.json()
    if (res.ok) {
      mcpSaveResult.value = { ok: true, msg: `保存成功，已加载 ${data.tools_loaded} 个工具` }
      await loadMcpConfig()
    } else {
      mcpSaveResult.value = { ok: false, msg: data.detail || '保存失败' }
    }
  } catch (e: any) {
    mcpSaveResult.value = { ok: false, msg: e.message }
  } finally {
    savingMcp.value = false
  }
}

// ── 生命周期 ──────────────────────────────────────────────────────────────────

watch(() => props.visible, (val) => {
  if (val) {
    loadSkills()
    loadMcpConfig()
    mcpSaveResult.value = null
  }
})
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.settings-panel {
  background: #1e1e1e;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  width: 560px;
  max-width: 95vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 64px rgba(0,0,0,0.5);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.panel-header h2 {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
}

.close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.close-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.tabs {
  display: flex;
  gap: 4px;
  padding: 12px 24px 0;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.tab-btn {
  padding: 8px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
  margin-bottom: -1px;
}
.tab-btn:hover { color: var(--text-primary); }
.tab-btn.active { color: var(--text-primary); border-bottom-color: var(--accent); }

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tab-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.link {
  color: var(--accent);
  text-decoration: none;
}
.link:hover { text-decoration: underline; }

/* Skills */
.skill-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 10px;
  transition: border-color 0.15s;
}
.skill-item:hover { border-color: rgba(255,255,255,0.14); }

.skill-info { flex: 1; min-width: 0; }

.skill-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.skill-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.skill-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.tool-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(16, 163, 127, 0.12);
  color: var(--accent);
  border-radius: 4px;
  font-family: monospace;
}

/* Toggle Switch */
.toggle {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
  flex-shrink: 0;
}
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.15);
  border-radius: 22px;
  cursor: pointer;
  transition: background 0.2s;
}
.toggle-slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 3px;
  top: 3px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}
.toggle input:checked + .toggle-slider { background: var(--accent); }
.toggle input:checked + .toggle-slider::before { transform: translateX(18px); }
.toggle input:disabled + .toggle-slider { opacity: 0.5; cursor: not-allowed; }

/* MCP */
.mcp-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(255,255,255,0.04);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.green { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
.status-dot.gray  { background: var(--text-muted); }

.tool-names {
  font-size: 11px;
  font-family: monospace;
  color: var(--text-muted);
  word-break: break-all;
}

.editor-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.json-editor {
  width: 100%;
  min-height: 200px;
  background: #141414;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  color: var(--text-primary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 14px;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
}
.json-editor:focus { border-color: rgba(255,255,255,0.25); }

.json-error {
  font-size: 12px;
  color: var(--danger);
  padding: 0 4px;
}

.action-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-primary, .btn-secondary {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: opacity 0.15s, background 0.15s;
}
.btn-primary {
  background: var(--accent);
  color: #fff;
}
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  background: rgba(255,255,255,0.08);
  color: var(--text-primary);
}
.btn-secondary:hover { background: rgba(255,255,255,0.12); }

.save-result {
  font-size: 13px;
  padding: 10px 14px;
  border-radius: 8px;
}
.save-result.ok { background: rgba(16,163,127,0.12); color: var(--accent); }
.save-result.err { background: rgba(239,68,68,0.1); color: var(--danger); }

.loading-hint, .empty-hint {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: 24px;
}
</style>
