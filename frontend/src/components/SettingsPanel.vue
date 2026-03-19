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

        <!-- General Tab -->
        <div v-if="activeTab === 'general'" class="tab-content">
          <div class="setting-group">
            <div class="setting-label">外观</div>
            <div class="theme-options">
              <button
                v-for="opt in themeOptions"
                :key="opt.value"
                class="theme-option"
                :class="{ active: themeMode === opt.value }"
                @click="themeMode = opt.value"
              >
                <svg v-if="opt.value === 'light'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                </svg>
                <svg v-else-if="opt.value === 'dark'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><path d="M8 21h8M12 17v4"/>
                </svg>
                <span>{{ opt.label }}</span>
              </button>
            </div>
          </div>

          <!-- 修改密码 -->
          <div class="setting-group" style="margin-top: 16px;">
            <div class="setting-label">修改密码</div>
            <div class="pw-form">
              <input
                v-model="oldPw"
                type="password"
                placeholder="当前密码"
                class="pw-input"
              />
              <input
                v-model="newPw"
                type="password"
                placeholder="新密码（至少6位）"
                class="pw-input"
              />
              <input
                v-model="confirmPw"
                type="password"
                placeholder="确认新密码"
                class="pw-input"
              />
              <div v-if="pwError" class="pw-msg pw-error">{{ pwError }}</div>
              <div v-if="pwSuccess" class="pw-msg pw-ok">密码修改成功</div>
              <button class="btn-primary pw-submit" :disabled="pwLoading" @click="handleChangePw">
                {{ pwLoading ? '提交中...' : '修改密码' }}
              </button>
            </div>
          </div>
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
import { themeMode } from '@/composables/useTheme'
import type { ThemeMode } from '@/composables/useTheme'
import * as api from '@/services/api'

const props = defineProps<{ visible: boolean }>()
defineEmits(['close'])

const tabs = [
  { id: 'general', label: '通用' },
  { id: 'skills',  label: '技能 Skills' },
  { id: 'mcp',     label: 'MCP 工具' },
]
const activeTab = ref('general')

const themeOptions: { value: ThemeMode; label: string }[] = [
  { value: 'light', label: '亮色' },
  { value: 'dark',  label: '暗色' },
  { value: 'system', label: '跟随系统' },
]

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

// ── Change Password ──────────────────────────────────────────────────────────

const oldPw = ref('')
const newPw = ref('')
const confirmPw = ref('')
const pwError = ref('')
const pwSuccess = ref(false)
const pwLoading = ref(false)

async function handleChangePw() {
  pwError.value = ''
  pwSuccess.value = false

  if (!oldPw.value) { pwError.value = '请输入当前密码'; return }
  if (newPw.value.length < 6) { pwError.value = '新密码至少 6 个字符'; return }
  if (newPw.value !== confirmPw.value) { pwError.value = '两次新密码不一致'; return }

  pwLoading.value = true
  try {
    await api.changePassword(oldPw.value, newPw.value)
    pwSuccess.value = true
    oldPw.value = ''
    newPw.value = ''
    confirmPw.value = ''
  } catch (e: any) {
    pwError.value = e.message || '修改失败'
  } finally {
    pwLoading.value = false
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
    oldPw.value = ''
    newPw.value = ''
    confirmPw.value = ''
    pwError.value = ''
    pwSuccess.value = false
  }
})
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.settings-panel {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  width: 560px;
  max-width: 95vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--modal-shadow);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border-light);
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
  border-bottom: 1px solid var(--border-light);
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
  background: var(--surface-1);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  transition: border-color 0.15s;
}
.skill-item:hover { border-color: var(--border); }

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
  background: var(--toggle-bg);
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
  background: var(--surface-1);
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
  background: var(--panel-input-bg);
  border: 1px solid var(--border);
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
.json-editor:focus { border-color: var(--border-strong); }

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
  background: var(--surface-2);
  color: var(--text-primary);
}
.btn-secondary:hover { background: var(--surface-3); }

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

/* Theme selector */
.setting-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.setting-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}
.theme-options {
  display: flex;
  gap: 8px;
}
.theme-option {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 12px;
  background: var(--surface-1);
  border: 2px solid transparent;
  border-radius: 10px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}
.theme-option:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}
.theme-option.active {
  border-color: var(--accent);
  background: var(--accent-light);
  color: var(--text-primary);
}

/* Password form */
.pw-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pw-input {
  padding: 10px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.pw-input:focus { border-color: var(--accent); }
.pw-input::placeholder { color: var(--text-muted); }
.pw-msg {
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 6px;
}
.pw-error { color: var(--danger); background: rgba(239,68,68,0.08); }
.pw-ok { color: var(--accent); background: var(--accent-light); }
.pw-submit { margin-top: 2px; }
</style>
