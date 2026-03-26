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
                @click="setThemeMode(opt.value)"
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
          <div class="setting-group">
            <div class="setting-label">用户头像</div>
            <div class="avatar-options">
              <button
                v-for="(src, idx) in avatarPresets"
                :key="idx"
                class="avatar-option"
                :class="{ active: userAvatar === src }"
                @click="setUserAvatar(src)"
              >
                <img :src="src" alt="preset-avatar" />
              </button>
              <label class="avatar-upload">
                上传
                <input type="file" accept="image/*" @change="onAvatarUpload" />
              </label>
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

        <!-- 对话模型 -->
        <div v-if="activeTab === 'llm'" class="tab-content env-tab">
          <p class="tab-desc">
            对话模型配置保存在后端 SQLite <code>data/settings.db</code>（表 <code>app_settings</code>）。
            仅支持 OpenAI 兼容与 Azure，至少保存一条后问答才可用。
          </p>

          <div class="llm-section">
            <div class="llm-section-title">对话模型（OpenAI 兼容 / Azure）</div>
            <p class="llm-section-hint"><strong>至少保存一条提供方</strong>后，问答与备忘录 AI 才会调用模型；此前仅填全局 Azure 字段也不会自动生效。可添加多个；问答页下拉切换。OpenAI 兼容填 base_url + api_key + model；Azure 填 endpoint + deployment（api_version / api_key 可选）。</p>
            <div v-for="(row, idx) in llmRows" :key="idx" class="llm-card">
              <div class="llm-card-head">
                <span class="llm-card-label">提供方 {{ idx + 1 }}</span>
                <div class="llm-card-actions">
                  <button type="button" class="btn-secondary mini" :disabled="!!llmSavingByIndex[idx]" @click="saveOneLlmProvider(idx)">
                    {{ llmSavingByIndex[idx] ? '校验中...' : '校验并保存' }}
                  </button>
                  <button type="button" class="btn-text danger" :disabled="!!llmSavingByIndex[idx]" @click="removeLlmRow(idx)">删除</button>
                </div>
              </div>
              <div class="llm-fields">
                <label class="llm-field"><span>类型</span>
                  <select v-model="row.kind" class="pw-input" @change="onLlmKindChange(idx)">
                    <option value="openai">OpenAI 兼容</option>
                    <option value="azure">Azure OpenAI</option>
                  </select>
                </label>
                <label class="llm-field"><span>名称（唯一）</span><input v-model="row.name" class="pw-input" placeholder="例如 deepseek-chat" autocomplete="off" /></label>
                <template v-if="row.kind === 'openai'">
                  <label class="llm-field span-2"><span>Base URL</span><input v-model="row.base_url" class="pw-input" placeholder="https://api.example.com/v1" autocomplete="off" /></label>
                  <label class="llm-field"><span>API Key</span><input v-model="row.api_key" class="pw-input" type="password" autocomplete="off" /></label>
                  <label class="llm-field"><span>Model</span><input v-model="row.model" class="pw-input" placeholder="模型名" autocomplete="off" /></label>
                </template>
                <template v-else>
                  <p class="llm-kind-hint">
                    Azure 模式不使用 base_url；使用 endpoint + deployment。此处可填单提供方覆盖值，不填则沿用「环境变量」里的全局 Azure 配置。
                  </p>
                  <label class="llm-field span-2"><span>Endpoint</span><input v-model="row.endpoint" class="pw-input" placeholder="https://xxx.openai.azure.com" autocomplete="off" /></label>
                  <label class="llm-field"><span>API Version</span><input v-model="row.api_version" class="pw-input" placeholder="2024-06-01" autocomplete="off" /></label>
                  <label class="llm-field"><span>API Key</span><input v-model="row.api_key" class="pw-input" type="password" placeholder="可选，可沿用下方全局 Azure 配置" autocomplete="off" /></label>
                  <label class="llm-field span-2"><span>部署名称（Deployment）</span><input v-model="row.deployment" class="pw-input" placeholder="例如 gpt-4o（可覆盖默认）" autocomplete="off" /></label>
                </template>
              </div>
              <div v-if="llmRowMsgByIndex[idx]" class="save-result" :class="llmRowOkByIndex[idx] ? 'ok' : 'err'">
                {{ llmRowMsgByIndex[idx] }}
              </div>
            </div>
            <button type="button" class="btn-secondary llm-add-btn" @click="addLlmRow">添加提供方</button>
            <label class="llm-active-row">
              <span class="env-label">默认提供方（对话页初始选中）</span>
              <select
                v-model="runtimeForm.active_llm_provider_id"
                class="pw-input env-input"
                :disabled="savingActiveLlmId"
                @change="saveActiveLlmProviderId"
              >
                <option value="">自动（列表第一项）</option>
                <option v-for="id in activeLlmIdOptions" :key="id" :value="id">{{ id }}</option>
              </select>
              <span v-if="savingActiveLlmId" class="mini-hint">默认提供方保存中...</span>
            </label>
          </div>
          <div class="llm-section">
            <div class="llm-section-title">Azure 全局默认（可选）</div>
            <p class="llm-section-hint">当 Azure 提供方未填写 endpoint / api_version / api_key / deployment 时，才回退到这里。</p>
            <div class="llm-fields">
              <label class="llm-field span-2"><span>Endpoint</span><input v-model="runtimeForm.azure_openai_endpoint" class="pw-input" placeholder="https://xxx.openai.azure.com" autocomplete="off" /></label>
              <label class="llm-field"><span>API Version</span><input v-model="runtimeForm.azure_openai_api_version" class="pw-input" placeholder="2024-06-01" autocomplete="off" /></label>
              <label class="llm-field"><span>默认部署名称（对话）</span><input v-model="runtimeForm.azure_openai_deployment" class="pw-input" placeholder="例如 gpt-4o" autocomplete="off" /></label>
              <label class="llm-field span-2"><span>API Key</span><input v-model="runtimeForm.azure_openai_api_key" class="pw-input" type="password" autocomplete="off" /></label>
            </div>
          </div>

          <details class="llm-json-advanced">
            <summary>高级：直接编辑 llm_providers_json</summary>
            <textarea
              v-model="runtimeForm.llm_providers_json"
              class="json-editor env-input"
              rows="6"
              spellcheck="false"
              @change="parseProvidersFromForm"
            />
          </details>

          <div class="action-row">
            <button class="btn-secondary" type="button" @click="loadRuntimeSettings">重新加载</button>
          </div>
          <div
            v-if="runtimeSaveMsg"
            class="save-result"
            :class="runtimeSaveMsg.includes('失败') ? 'err' : 'ok'"
          >
            {{ runtimeSaveMsg }}
          </div>
        </div>

        <!-- 向量模型 -->
        <div v-if="activeTab === 'embedding'" class="tab-content env-tab">
          <p class="tab-desc">
            mem0 向量配置与对话模型分开维护；仅支持 OpenAI 兼容与 Azure。
            向量模型/维度修改后建议重启后端。
          </p>
          <div class="llm-section">
            <div class="llm-section-title">向量模型（OpenAI 兼容 / Azure）</div>
            <div v-for="(row, idx) in embeddingRows" :key="idx" class="llm-card">
              <div class="llm-card-head">
                <span class="llm-card-label">提供方 {{ idx + 1 }}</span>
                <div class="llm-card-actions">
                  <button type="button" class="btn-secondary mini" :disabled="!!embeddingSavingByIndex[idx]" @click="saveOneEmbeddingProvider(idx)">
                    {{ embeddingSavingByIndex[idx] ? '校验中...' : '校验并保存' }}
                  </button>
                  <button type="button" class="btn-text danger" :disabled="!!embeddingSavingByIndex[idx]" @click="removeEmbeddingRow(idx)">删除</button>
                </div>
              </div>
              <div class="llm-fields">
                <label class="llm-field"><span>类型</span>
                  <select v-model="row.kind" class="pw-input" @change="onEmbeddingKindChange(idx)">
                    <option value="openai">OpenAI 兼容</option>
                    <option value="azure">Azure OpenAI</option>
                  </select>
                </label>
                <label class="llm-field"><span>名称（唯一）</span><input v-model="row.name" class="pw-input" placeholder="例如 emb-openai" autocomplete="off" /></label>
                <label class="llm-field"><span>Dimensions</span><input v-model="row.dimensions" class="pw-input" placeholder="可选，如 1024" autocomplete="off" /></label>
                <template v-if="row.kind === 'openai'">
                  <label class="llm-field span-2"><span>Base URL</span><input v-model="row.base_url" class="pw-input" placeholder="https://api.example.com/v1" autocomplete="off" /></label>
                  <label class="llm-field"><span>API Key</span><input v-model="row.api_key" class="pw-input" type="password" autocomplete="off" /></label>
                  <label class="llm-field"><span>Model</span><input v-model="row.model" class="pw-input" placeholder="text-embedding-3-small" autocomplete="off" /></label>
                </template>
                <template v-else>
                  <p class="llm-kind-hint">
                    Azure 向量模型也不使用 base_url；使用 endpoint + deployment。
                  </p>
                  <label class="llm-field span-2"><span>Endpoint</span><input v-model="row.endpoint" class="pw-input" placeholder="https://xxx.openai.azure.com" autocomplete="off" /></label>
                  <label class="llm-field"><span>API Version</span><input v-model="row.api_version" class="pw-input" placeholder="2024-06-01" autocomplete="off" /></label>
                  <label class="llm-field"><span>API Key</span><input v-model="row.api_key" class="pw-input" type="password" autocomplete="off" /></label>
                  <label class="llm-field span-2"><span>部署名称（Deployment）</span><input v-model="row.deployment" class="pw-input" placeholder="例如 text-embedding-3-small" autocomplete="off" /></label>
                </template>
              </div>
              <div v-if="embeddingRowMsgByIndex[idx]" class="save-result" :class="embeddingRowOkByIndex[idx] ? 'ok' : 'err'">
                {{ embeddingRowMsgByIndex[idx] }}
              </div>
            </div>
            <button type="button" class="btn-secondary llm-add-btn" @click="addEmbeddingRow">添加向量提供方</button>
            <label class="llm-active-row">
              <span class="env-label">默认向量提供方（mem0 使用）</span>
              <select
                v-model="runtimeForm.active_embedding_provider_id"
                class="pw-input env-input"
                :disabled="savingActiveEmbeddingId"
                @change="saveActiveEmbeddingProviderId"
              >
                <option value="">自动（列表第一项）</option>
                <option v-for="id in activeEmbeddingIdOptions" :key="id" :value="id">{{ id }}</option>
              </select>
              <span v-if="savingActiveEmbeddingId" class="mini-hint">默认向量提供方保存中...</span>
            </label>
          </div>

          <details class="llm-json-advanced">
            <summary>高级：直接编辑 embedding_providers_json</summary>
            <textarea
              v-model="runtimeForm.embedding_providers_json"
              class="json-editor env-input"
              rows="6"
              spellcheck="false"
              @change="parseEmbeddingsFromForm"
            />
          </details>
          <div class="action-row">
            <button class="btn-secondary" type="button" @click="loadRuntimeSettings">重新加载</button>
          </div>
        </div>

        <!-- 系统配置 -->
        <div v-if="activeTab === 'env'" class="tab-content env-tab">
          <p class="tab-desc">
            所有配置都保存在服务端数据库；这里按功能拆分展示，不再使用“环境变量”概念。
          </p>
          <div class="llm-section">
            <div class="llm-section-title">基础配置</div>
            <div class="env-grid">
              <div v-for="key in basicConfigKeys" :key="key" class="env-grid-row">
                <label class="env-label">
                  <span class="env-label-main">{{ getConfigLabel(key) }}</span>
                  <span class="env-hint-dot" :title="getConfigTooltip(key)">?</span>
                </label>
                <div class="env-input-wrap">
                  <input
                    v-model="runtimeForm[key]"
                    class="pw-input env-input"
                    :type="isRuntimeSecretKey(key) ? 'password' : 'text'"
                    :list="key === 'feishu_default_open_id' && feishuRecipients.length ? 'feishu-openid-list' : undefined"
                    autocomplete="off"
                  />
                  <template v-if="key === 'feishu_default_open_id'">
                    <div class="env-inline-actions">
                      <button class="btn-secondary mini" type="button" :disabled="loadingFeishuRecipients" @click="loadFeishuRecipients">
                        {{ loadingFeishuRecipients ? '拉取中...' : '拉取可见成员' }}
                      </button>
                    </div>
                    <datalist v-if="feishuRecipients.length" id="feishu-openid-list">
                      <option v-for="u in feishuRecipients" :key="u.open_id" :value="u.open_id">
                        {{ u.name }}
                      </option>
                    </datalist>
                    <div v-if="feishuRecipientsMsg" class="env-inline-msg" :class="feishuRecipientsOk ? 'ok' : 'err'">
                      {{ feishuRecipientsMsg }}
                    </div>
                  </template>
                </div>
              </div>
            </div>
            <div v-if="!basicConfigKeys.length" class="empty-hint">暂无基础配置项</div>
          </div>
          <details class="llm-section">
            <summary class="llm-section-title">高级运维（谨慎修改）</summary>
            <div class="env-grid">
              <div v-for="key in advancedOpsConfigKeys" :key="key" class="env-grid-row">
                <label class="env-label" :class="{ 'env-label-warn': key === 'db_path' }">
                  <span class="env-label-main">{{ getConfigLabel(key) }}</span>
                  <span class="env-hint-dot" :title="getConfigTooltip(key)">?</span>
                </label>
                <input
                  v-model="runtimeForm[key]"
                  class="pw-input env-input"
                  :type="isRuntimeSecretKey(key) ? 'password' : 'text'"
                  autocomplete="off"
                />
              </div>
            </div>
            <div v-if="!advancedOpsConfigKeys.length" class="empty-hint">暂无高级运维项</div>
            <p v-if="advancedOpsConfigKeys.includes('db_path')" class="db-path-warn">修改 <code>db_path</code> 会更换 SQLite 文件位置，需自行迁移数据；保存时会二次确认。</p>
          </details>
          <details class="llm-section migration-section">
            <summary class="llm-section-title">迁移兼容（非迁移勿改）</summary>
            <p class="migration-warn">仅在旧记忆数据迁移期间使用，日常运行请保持默认值。</p>
            <div class="env-grid">
              <div v-for="key in migrationCompatConfigKeys" :key="key" class="env-grid-row">
                <label class="env-label env-label-warn">
                  <span class="env-label-main">{{ getConfigLabel(key) }}</span>
                  <span class="env-hint-dot" :title="getConfigTooltip(key)">?</span>
                </label>
                <input
                  v-model="runtimeForm[key]"
                  class="pw-input env-input"
                  :type="isRuntimeSecretKey(key) ? 'password' : 'text'"
                  autocomplete="off"
                />
              </div>
            </div>
            <div v-if="!migrationCompatConfigKeys.length" class="empty-hint">暂无迁移兼容项</div>
          </details>
          <div class="action-row">
            <button class="btn-secondary" type="button" @click="loadRuntimeSettings">重新加载</button>
            <button class="btn-primary" type="button" :disabled="savingRuntime" @click="saveRuntimeSettings">
              {{ savingRuntime ? '保存中...' : '保存' }}
            </button>
          </div>
          <div
            v-if="runtimeSaveMsg"
            class="save-result"
            :class="runtimeSaveMsg.includes('失败') ? 'err' : 'ok'"
          >
            {{ runtimeSaveMsg }}
          </div>
        </div>

        <!-- Skills Tab -->
        <div v-if="activeTab === 'skills'" class="tab-content">
          <p class="tab-desc">技能是预置的工具和行为指令，按需启用。</p>
          <div v-if="skillsMsg" class="save-result" :class="skillsMsgOk ? 'ok' : 'err'">
            {{ skillsMsg }}
          </div>
          <div v-if="loadingSkills" class="loading-hint">加载中...</div>
          <div v-else class="skill-list">
            <div v-for="skill in skills" :key="skill.name" class="skill-item">
              <div class="skill-info">
                <div class="skill-name">{{ skill.name }}</div>
                <div class="skill-desc">{{ skill.description }}</div>
                <div v-if="skill.available === false" class="skill-unavailable">
                  {{ skill.unavailable_reason || '当前配置不可用' }}
                </div>
                <div v-if="skill.tools.length" class="skill-tools">
                  <span v-for="t in skill.tools" :key="t" class="tool-tag">{{ t }}</span>
                </div>
              </div>
              <label class="toggle">
                <input
                  type="checkbox"
                  :checked="skill.enabled"
                  :disabled="togglingSkill === skill.name || (skill.available === false && !skill.enabled)"
                  @change="onSkillCheckboxChange(skill.name, $event)"
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
import { themeMode, setThemeMode } from '@/composables/useTheme'
import type { ThemeMode } from '@/composables/useTheme'
import { avatarPresets, userAvatar, setUserAvatar, uploadUserAvatar } from '@/composables/useAvatar'
import { openConfirm } from '@/composables/useConfirmDialog'
import * as api from '@/services/api'

const props = defineProps<{ visible: boolean }>()
defineEmits(['close'])

const tabs = [
  { id: 'general', label: '通用' },
  { id: 'llm', label: '对话模型' },
  { id: 'embedding', label: '向量模型' },
  { id: 'env', label: '系统配置' },
  { id: 'skills', label: '技能 Skills' },
  { id: 'mcp', label: 'MCP 工具' },
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
  available?: boolean
  unavailable_reason?: string
}

interface FeishuRecipient {
  open_id: string
  name: string
}

const skills = ref<SkillInfo[]>([])
const loadingSkills = ref(false)
const togglingSkill = ref<string | null>(null)
const skillsMsg = ref('')
const skillsMsgOk = ref(false)
const feishuRecipients = ref<FeishuRecipient[]>([])
const loadingFeishuRecipients = ref(false)
const feishuRecipientsMsg = ref('')
const feishuRecipientsOk = ref(false)

async function loadSkills() {
  loadingSkills.value = true
  try {
    const res = await fetch('/api/settings/skills')
    skills.value = await res.json()
  } finally {
    loadingSkills.value = false
  }
}

function onSkillCheckboxChange(name: string, e: Event) {
  const t = e.target
  if (t instanceof HTMLInputElement) void toggleSkill(name, t.checked)
}

async function toggleSkill(name: string, enabled: boolean) {
  togglingSkill.value = name
  skillsMsg.value = ''
  try {
    const res = await fetch(`/api/settings/skills/${name}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`)
    }
    const skill = skills.value.find(s => s.name === name)
    if (skill) skill.enabled = !!data.enabled
    skillsMsgOk.value = true
    skillsMsg.value = `已${data.enabled ? '启用' : '禁用'} ${name}`
  } catch (e: any) {
    // 后端失败时，立即回滚为后端真实状态，避免“前端看起来开了但实际不可用”
    await loadSkills()
    skillsMsgOk.value = false
    skillsMsg.value = e?.message || '技能状态更新失败'
  } finally {
    togglingSkill.value = null
  }
}

async function loadFeishuRecipients() {
  loadingFeishuRecipients.value = true
  feishuRecipientsMsg.value = ''
  try {
    // 先把当前表单中的飞书关键字段落库，避免“界面已改但拉取仍用旧配置”
    const patch: Record<string, unknown> = {
      feishu_app_id: (runtimeForm.value.feishu_app_id || '').trim() || null,
      feishu_default_open_id: (runtimeForm.value.feishu_default_open_id || '').trim() || null,
    }
    const sec = (runtimeForm.value.feishu_app_secret || '').trim()
    if (sec && sec !== '***') {
      patch.feishu_app_secret = sec
    }
    await api.putRuntimeSettings(patch)

    const items = await api.fetchFeishuRecipients()
    feishuRecipients.value = items
    const current = String(runtimeForm.value.feishu_default_open_id || '').trim()
    const hasCurrent = !!items.find((u) => u.open_id === current)
    if (items.length === 1 && !hasCurrent) {
      // 只有一个可见成员时自动回填，避免“拉取成功但上方仍显示旧值”的错觉
      runtimeForm.value.feishu_default_open_id = items[0].open_id
    } else if (items.length > 0 && !hasCurrent) {
      // 当前值不在可见列表里时，默认切到第一项，减少发送到历史错误 OpenID 的风险
      runtimeForm.value.feishu_default_open_id = items[0].open_id
    }
    feishuRecipientsOk.value = true
    feishuRecipientsMsg.value = `已拉取 ${items.length} 个可见成员`
  } catch (e: any) {
    feishuRecipients.value = []
    feishuRecipientsOk.value = false
    feishuRecipientsMsg.value = e?.message || '拉取失败'
  } finally {
    loadingFeishuRecipients.value = false
  }
}

// ── Change Password ──────────────────────────────────────────────────────────

const oldPw = ref('')
const newPw = ref('')
const confirmPw = ref('')
const pwError = ref('')
const pwSuccess = ref(false)
const pwLoading = ref(false)

async function onAvatarUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    await uploadUserAvatar(file)
  } catch (err: unknown) {
    pwError.value = err instanceof Error ? err.message : '头像上传失败'
  } finally {
    input.value = ''
  }
}

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

const RUNTIME_KEYS_MANAGED_ELSEWHERE = new Set([
  'llm_providers_json',
  'active_llm_provider_id',
  'embedding_providers_json',
  'active_embedding_provider_id',
  'azure_openai_api_key',
  'azure_openai_endpoint',
  'azure_openai_api_version',
  'azure_openai_deployment',
  'azure_openai_embedding_deployment',
  'embedding_provider',
  'embedding_api_key',
  'embedding_base_url',
  'embedding_model',
  'user_id',
])

interface LlmProviderRow {
  id: string
  name: string
  kind: 'openai' | 'azure'
  base_url: string
  endpoint: string
  api_version: string
  api_key: string
  model: string
  deployment: string
}

function emptyLlmRow(): LlmProviderRow {
  return {
    id: '',
    name: '',
    kind: 'openai',
    base_url: '',
    endpoint: '',
    api_version: '',
    api_key: '',
    model: '',
    deployment: '',
  }
}

interface EmbeddingProviderRow {
  id: string
  name: string
  kind: 'openai' | 'azure'
  base_url: string
  endpoint: string
  api_version: string
  api_key: string
  model: string
  deployment: string
  dimensions: string
}

function emptyEmbeddingRow(): EmbeddingProviderRow {
  return {
    id: '',
    name: '',
    kind: 'openai',
    base_url: '',
    endpoint: '',
    api_version: '',
    api_key: '',
    model: '',
    deployment: '',
    dimensions: '',
  }
}

const runtimeForm = ref<Record<string, string>>({})
const llmRows = ref<LlmProviderRow[]>([emptyLlmRow()])
const embeddingRows = ref<EmbeddingProviderRow[]>([emptyEmbeddingRow()])
const initialDbPath = ref('')

const BASIC_CONFIG_KEYS = [
  'tavily_api_key',
  'feishu_app_id',
  'feishu_app_secret',
  'feishu_default_open_id',
  'max_registered_users',
]

const ADVANCED_OPS_CONFIG_KEYS = [
//   'feishu_default_folder_token',
  'feishu_wiki_node_token',
  'feishu_wiki_base_url',
  'db_path',
  'sqlite_timeout_seconds',
  'jwt_secret',
  'mem0_dir',
]

const MIGRATION_COMPAT_CONFIG_KEYS = [
  'memory_enable_legacy_read',
  'memory_dual_write_legacy',
  'memory_legacy_model',
  'memory_legacy_collection',
  'memory_legacy_path',
]

const CONFIG_META: Record<string, { label: string; desc: string; usage: string }> = {
  tavily_api_key: {
    label: 'Tavily 搜索密钥',
    desc: '联网搜索功能使用的 API Key。',
    usage: '需要网页搜索时填写；不填则禁用搜索工具。',
  },
  feishu_app_id: {
    label: '飞书 App ID',
    desc: '飞书应用身份标识。',
    usage: '配合飞书密钥一起填写后，助手可调用飞书能力。',
  },
  feishu_app_secret: {
    label: '飞书 App Secret',
    desc: '飞书应用密钥。',
    usage: '与 App ID 成对使用，请妥善保管。',
  },
  feishu_default_open_id: {
    label: '飞书默认接收人 OpenID',
    desc: '未指定接收人时，默认消息目标。',
    usage: '可选；填后发送消息可省略接收人。',
  },
  feishu_default_folder_token: {
    label: '飞书默认文件夹 Token',
    desc: '创建文档时使用的默认目录。',
    usage: '可选；用于自动归档文档。',
  },
  feishu_wiki_node_token: {
    label: '飞书知识库节点 Token',
    desc: '写入飞书知识库时使用的节点。',
    usage: '仅在知识库写入场景需要。',
  },
  feishu_wiki_base_url: {
    label: '飞书知识库地址',
    desc: '飞书知识库页面基础地址。',
    usage: '用于生成可点击链接，通常为团队 wiki 根地址。',
  },
  user_id: {
    label: '默认用户 ID',
    desc: '系统内部使用的默认用户标识。',
    usage: '单用户场景一般保持默认即可。',
  },
  max_registered_users: {
    label: '最大注册用户数',
    desc: '允许注册的账户数量上限。',
    usage: '达到上限后将拒绝新用户注册。',
  },
  db_path: {
    label: '主数据库路径',
    desc: '对话与业务数据 SQLite 文件路径。',
    usage: '修改后需自行迁移旧数据，避免数据丢失。',
  },
  sqlite_timeout_seconds: {
    label: 'SQLite 超时（秒）',
    desc: '数据库锁等待超时时间。',
    usage: '并发较高可适当调大，如 30 或 60。',
  },
  jwt_secret: {
    label: 'JWT 签名密钥',
    desc: '登录令牌签名用密钥。',
    usage: '建议使用高强度随机字符串并定期轮换。',
  },
  mem0_dir: {
    label: 'mem0 数据目录',
    desc: 'mem0 存储历史与索引的位置。',
    usage: '留空将使用默认目录 ~/.mem0。',
  },
  memory_enable_legacy_read: {
    label: '兼容读取旧记忆',
    desc: '是否读取旧版记忆数据（0 关 / 1 开）。',
    usage: '迁移期可开；稳定后建议关。',
  },
  memory_dual_write_legacy: {
    label: '双写旧记忆',
    desc: '是否同时写入旧版记忆（0 关 / 1 开）。',
    usage: '仅迁移阶段短期开启。',
  },
  memory_legacy_model: {
    label: '旧记忆向量模型',
    desc: '旧版记忆系统使用的 embedding 模型名。',
    usage: '仅兼容旧链路时需要维护。',
  },
  memory_legacy_collection: {
    label: '旧记忆集合名',
    desc: '旧版向量库中的集合名称。',
    usage: '需与旧数据中的集合名一致。',
  },
  memory_legacy_path: {
    label: '旧记忆存储路径',
    desc: '旧版记忆向量数据目录。',
    usage: '用于读取历史数据；新部署可不改。',
  },
}

const sortedRuntimeKeys = computed(() =>
  Object.keys(runtimeForm.value)
    .filter((k) => !RUNTIME_KEYS_MANAGED_ELSEWHERE.has(k))
    .sort(),
)

function mergeKnownWithDynamic(known: string[], dynamic: string[]): string[] {
  const set = new Set<string>(known)
  for (const k of dynamic) set.add(k)
  return Array.from(set)
}

function getConfigLabel(key: string): string {
  return CONFIG_META[key]?.label ?? key
}

function getConfigTooltip(key: string): string {
  const m = CONFIG_META[key]
  if (!m) return `配置项：${key}`
  return `${m.label}\n\n含义：${m.desc}\n使用：${m.usage}`
}

const basicConfigKeys = computed(() =>
  mergeKnownWithDynamic(
    BASIC_CONFIG_KEYS,
    sortedRuntimeKeys.value.filter((k) =>
      k.startsWith('tavily_') || k === 'feishu_app_id' || k === 'feishu_app_secret' || k === 'max_registered_users',
    ),
  ),
)

const advancedOpsConfigKeys = computed(() =>
  mergeKnownWithDynamic(
    ADVANCED_OPS_CONFIG_KEYS,
    sortedRuntimeKeys.value.filter(
      (k) =>
        (k.startsWith('feishu_') && !basicConfigKeys.value.includes(k))
        || ['db_path', 'sqlite_timeout_seconds', 'jwt_secret', 'mem0_dir'].includes(k),
    ),
  ),
)

const migrationCompatConfigKeys = computed(() =>
  mergeKnownWithDynamic(
    MIGRATION_COMPAT_CONFIG_KEYS,
    sortedRuntimeKeys.value.filter((k) => k.startsWith('memory_')),
  ),
)

const activeLlmIdOptions = computed(() =>
  llmRows.value.map((r) => r.id.trim()).filter(Boolean),
)
const activeEmbeddingIdOptions = computed(() =>
  embeddingRows.value.map((r) => r.id.trim()).filter(Boolean),
)

const savingRuntime = ref(false)
const runtimeSaveMsg = ref('')
const savingActiveLlmId = ref(false)
const savingActiveEmbeddingId = ref(false)
const llmSavingByIndex = ref<Record<number, boolean>>({})
const llmRowMsgByIndex = ref<Record<number, string>>({})
const llmRowOkByIndex = ref<Record<number, boolean>>({})
const embeddingSavingByIndex = ref<Record<number, boolean>>({})
const embeddingRowMsgByIndex = ref<Record<number, string>>({})
const embeddingRowOkByIndex = ref<Record<number, boolean>>({})

function isRuntimeSecretKey(k: string) {
  const lk = k.toLowerCase()
  return lk.endsWith('_key') || lk.endsWith('_secret') || lk.includes('password')
}

function parseProvidersFromForm() {
  const raw = (runtimeForm.value.llm_providers_json || '').trim() || '[]'
  try {
    const p = JSON.parse(raw) as unknown
    if (!Array.isArray(p) || p.length === 0) {
      llmRows.value = [emptyLlmRow()]
      return
    }
    llmRows.value = p.map((x: Record<string, unknown>) => ({
      id: String(x.id ?? ''),
      name: String(x.name ?? x.id ?? ''),
      kind: x.kind === 'azure' ? 'azure' : 'openai',
      base_url: String(x.base_url ?? ''),
      endpoint: String(x.endpoint ?? ''),
      api_version: String(x.api_version ?? ''),
      api_key: String(x.api_key ?? ''),
      model: String(x.model ?? ''),
      deployment: String(x.deployment ?? ''),
    }))
  } catch {
    llmRows.value = [emptyLlmRow()]
  }
}

function buildLlmProviderPayload(row: LlmProviderRow): Record<string, string> {
  const uniqueName = row.name.trim()
  const o: Record<string, string> = {
    id: uniqueName,
    name: uniqueName,
    kind: row.kind,
  }
  if (row.kind === 'openai') {
    if (row.base_url.trim()) o.base_url = row.base_url.trim()
    if (row.api_key.trim()) o.api_key = row.api_key.trim()
    if (row.model.trim()) o.model = row.model.trim()
  } else {
    if (row.endpoint.trim()) o.endpoint = row.endpoint.trim()
    if (row.api_version.trim()) o.api_version = row.api_version.trim()
    if (row.api_key.trim()) o.api_key = row.api_key.trim()
    if (row.deployment.trim()) o.deployment = row.deployment.trim()
  }
  return o
}

function syncLlmRowsToFormJson() {
  const list = llmRows.value
    .filter((r) => r.name.trim())
    .map((r) => buildLlmProviderPayload(r))
  runtimeForm.value.llm_providers_json = JSON.stringify(list)
}

function addLlmRow() {
  llmRows.value.push(emptyLlmRow())
}

async function removeLlmRow(i: number) {
  const removed = llmRows.value[i]
  if (!removed) return
  llmRows.value.splice(i, 1)
  syncLlmRowsToFormJson()
  const remainingIds = llmRows.value.map((r) => r.name.trim()).filter(Boolean)
  const activeNow = (runtimeForm.value.active_llm_provider_id || '').trim()
  const nextActive = activeNow && !remainingIds.includes(activeNow) ? (remainingIds[0] || null) : (activeNow || null)
  try {
    await api.putRuntimeSettings({
      llm_providers_json: runtimeForm.value.llm_providers_json || '[]',
      active_llm_provider_id: nextActive,
    })
    runtimeSaveMsg.value = `已删除模型：${removed.name || removed.id || '未命名'}`
    window.dispatchEvent(new Event('mygpt-llm-providers-updated'))
    await loadRuntimeSettings()
  } catch (e: unknown) {
    runtimeSaveMsg.value = e instanceof Error ? e.message : '删除失败'
    await loadRuntimeSettings()
  }
}

function parseEmbeddingsFromForm() {
  const raw = (runtimeForm.value.embedding_providers_json || '').trim() || '[]'
  try {
    const p = JSON.parse(raw) as unknown
    if (!Array.isArray(p) || p.length === 0) {
      embeddingRows.value = [emptyEmbeddingRow()]
      return
    }
    embeddingRows.value = p.map((x: Record<string, unknown>) => ({
      id: String(x.id ?? ''),
      name: String(x.name ?? x.id ?? ''),
      kind: x.kind === 'azure' ? 'azure' : 'openai',
      base_url: String(x.base_url ?? ''),
      endpoint: String(x.endpoint ?? ''),
      api_version: String(x.api_version ?? ''),
      api_key: String(x.api_key ?? ''),
      model: String(x.model ?? ''),
      deployment: String(x.deployment ?? ''),
      dimensions: String(x.dimensions ?? ''),
    }))
  } catch {
    embeddingRows.value = [emptyEmbeddingRow()]
  }
}

function buildEmbeddingProviderPayload(row: EmbeddingProviderRow): Record<string, string | number> {
  const uniqueName = row.name.trim()
  const o: Record<string, string | number> = {
    id: uniqueName,
    name: uniqueName,
    kind: row.kind,
  }
  if (row.kind === 'openai') {
    if (row.base_url.trim()) o.base_url = row.base_url.trim()
    if (row.api_key.trim()) o.api_key = row.api_key.trim()
    if (row.model.trim()) o.model = row.model.trim()
  } else {
    if (row.endpoint.trim()) o.endpoint = row.endpoint.trim()
    if (row.api_version.trim()) o.api_version = row.api_version.trim()
    if (row.api_key.trim()) o.api_key = row.api_key.trim()
    if (row.deployment.trim()) o.deployment = row.deployment.trim()
  }
  if (row.dimensions.trim()) {
    const dim = parseInt(row.dimensions.trim(), 10)
    if (Number.isFinite(dim) && dim > 0) o.dimensions = dim
  }
  return o
}

function syncEmbeddingRowsToFormJson() {
  const list = embeddingRows.value
    .filter((r) => r.name.trim())
    .map((r) => buildEmbeddingProviderPayload(r))
  runtimeForm.value.embedding_providers_json = JSON.stringify(list)
}

function upsertById(list: Record<string, unknown>[], item: Record<string, unknown>) {
  const id = String(item.id || '')
  const next = list.filter((x) => String(x.id || '') !== id)
  next.push(item)
  return next
}

function hasDuplicateLlmName(name: string, idx: number): boolean {
  const target = name.trim()
  if (!target) return false
  return llmRows.value.some((r, i) => i !== idx && r.name.trim() === target)
}

function normalizeDim(v: unknown): number | null {
  const s = String(v ?? '').trim()
  if (!s) return null
  const n = parseInt(s, 10)
  return Number.isFinite(n) && n > 0 ? n : null
}

async function saveOneLlmProvider(idx: number) {
  const row = llmRows.value[idx]
  if (!row || !row.name.trim()) {
    llmRowOkByIndex.value[idx] = false
    llmRowMsgByIndex.value[idx] = '名称不能为空'
    return
  }
  if (hasDuplicateLlmName(row.name, idx)) {
    llmRowOkByIndex.value[idx] = false
    llmRowMsgByIndex.value[idx] = '名称重复：每个模型提供方名称必须唯一'
    return
  }
  const provider = buildLlmProviderPayload(row)
  llmSavingByIndex.value[idx] = true
  llmRowMsgByIndex.value[idx] = ''
  try {
    await api.validateProvider('llm', provider, {
      azure_openai_endpoint: runtimeForm.value.azure_openai_endpoint || '',
      azure_openai_api_version: runtimeForm.value.azure_openai_api_version || '',
      azure_openai_api_key: runtimeForm.value.azure_openai_api_key || '',
      azure_openai_deployment: runtimeForm.value.azure_openai_deployment || '',
    })
    // 以服务端最新配置为准合并，避免本地 runtimeForm 过期导致覆盖他人/另一条配置
    const latest = await api.fetchRuntimeSettings()
    const latestRaw = String(latest.llm_providers_json || '[]')
    const current = JSON.parse(latestRaw || '[]') as Record<string, unknown>[]
    const providers = upsertById(Array.isArray(current) ? current : [], provider)
    const values: Record<string, unknown> = {
      llm_providers_json: JSON.stringify(providers),
      active_llm_provider_id: runtimeForm.value.active_llm_provider_id || String(provider.id),
      azure_openai_endpoint: runtimeForm.value.azure_openai_endpoint || null,
      azure_openai_api_version: runtimeForm.value.azure_openai_api_version || null,
      azure_openai_api_key: runtimeForm.value.azure_openai_api_key === '***' ? undefined : (runtimeForm.value.azure_openai_api_key || null),
      azure_openai_deployment: runtimeForm.value.azure_openai_deployment || null,
    }
    Object.keys(values).forEach((k) => values[k] === undefined && delete values[k])
    await api.putRuntimeSettings(values)
    llmRowOkByIndex.value[idx] = true
    llmRowMsgByIndex.value[idx] = '校验通过并已保存'
    window.dispatchEvent(new Event('mygpt-llm-providers-updated'))
    await reloadAllSettingsData()
  } catch (e: unknown) {
    llmRowOkByIndex.value[idx] = false
    llmRowMsgByIndex.value[idx] = e instanceof Error ? e.message : '保存失败'
  } finally {
    llmSavingByIndex.value[idx] = false
  }
}

async function onLlmKindChange(idx: number) {
  const row = llmRows.value[idx]
  // 新增行尚未命名时，不自动触发保存，避免打断填写流程
  if (!row || !row.name.trim()) return
  await saveOneLlmProvider(idx)
}

async function saveOneEmbeddingProvider(idx: number) {
  const row = embeddingRows.value[idx]
  if (!row || !row.name.trim()) {
    embeddingRowOkByIndex.value[idx] = false
    embeddingRowMsgByIndex.value[idx] = '名称不能为空'
    return
  }
  const provider = buildEmbeddingProviderPayload(row)
  embeddingSavingByIndex.value[idx] = true
  embeddingRowMsgByIndex.value[idx] = ''
  try {
    const latest = await api.fetchRuntimeSettings()
    const latestRaw = String(latest.embedding_providers_json || '[]')
    const currentRaw = JSON.parse(latestRaw || '[]') as Record<string, unknown>[]
    const currentList = Array.isArray(currentRaw) ? currentRaw : []
    const oldProvider = currentList.find((x) => String(x.id || '') === String(provider.id))
    const oldDim = normalizeDim(oldProvider?.dimensions ?? oldProvider?.embedding_dims)
    const newDim = normalizeDim((provider as Record<string, unknown>).dimensions)
    const dimChanged = oldProvider && oldDim !== newDim

    await api.validateProvider('embedding', provider, {
      azure_openai_endpoint: runtimeForm.value.azure_openai_endpoint || '',
      azure_openai_api_version: runtimeForm.value.azure_openai_api_version || '',
      azure_openai_api_key: runtimeForm.value.azure_openai_api_key || '',
      azure_openai_embedding_deployment: runtimeForm.value.azure_openai_embedding_deployment || '',
    })

    if (dimChanged) {
      const ok = await openConfirm({
        title: '检测到向量维度变更',
        message: `提供方 ${String(provider.id)} 的维度从 ${oldDim ?? '自动'} 变为 ${newDim ?? '自动'}。\n是否清理旧向量目录？`,
        confirmText: '清理旧目录',
      })
      if (ok && oldProvider) {
        await api.cleanupEmbeddingStore(oldProvider)
      }
    }

    const providers = upsertById(currentList, provider)
    const values: Record<string, unknown> = {
      embedding_providers_json: JSON.stringify(providers),
      active_embedding_provider_id: runtimeForm.value.active_embedding_provider_id || String(provider.id),
      azure_openai_endpoint: runtimeForm.value.azure_openai_endpoint || null,
      azure_openai_api_version: runtimeForm.value.azure_openai_api_version || null,
      azure_openai_api_key: runtimeForm.value.azure_openai_api_key === '***' ? undefined : (runtimeForm.value.azure_openai_api_key || null),
      azure_openai_embedding_deployment: runtimeForm.value.azure_openai_embedding_deployment || null,
    }
    Object.keys(values).forEach((k) => values[k] === undefined && delete values[k])
    await api.putRuntimeSettings(values)
    embeddingRowOkByIndex.value[idx] = true
    embeddingRowMsgByIndex.value[idx] = '校验通过并已保存'
    await reloadAllSettingsData()
  } catch (e: unknown) {
    embeddingRowOkByIndex.value[idx] = false
    embeddingRowMsgByIndex.value[idx] = e instanceof Error ? e.message : '保存失败'
  } finally {
    embeddingSavingByIndex.value[idx] = false
  }
}

async function onEmbeddingKindChange(idx: number) {
  const row = embeddingRows.value[idx]
  // 新增行尚未命名时，不自动触发保存，避免打断填写流程
  if (!row || !row.name.trim()) return
  await saveOneEmbeddingProvider(idx)
}

function addEmbeddingRow() {
  embeddingRows.value.push(emptyEmbeddingRow())
}

async function removeEmbeddingRow(i: number) {
  const removed = embeddingRows.value[i]
  if (!removed) return
  embeddingRows.value.splice(i, 1)
  syncEmbeddingRowsToFormJson()
  const remainingIds = embeddingRows.value.map((r) => r.name.trim()).filter(Boolean)
  const activeNow = (runtimeForm.value.active_embedding_provider_id || '').trim()
  const nextActive = activeNow && !remainingIds.includes(activeNow) ? (remainingIds[0] || null) : (activeNow || null)
  try {
    await api.putRuntimeSettings({
      embedding_providers_json: runtimeForm.value.embedding_providers_json || '[]',
      active_embedding_provider_id: nextActive,
    })
    runtimeSaveMsg.value = `已删除向量模型：${removed.name || removed.id || '未命名'}`
    await loadRuntimeSettings()
  } catch (e: unknown) {
    runtimeSaveMsg.value = e instanceof Error ? e.message : '删除失败'
    await loadRuntimeSettings()
  }
}

async function loadRuntimeSettings() {
  try {
    const d = await api.fetchRuntimeSettings()
    const next: Record<string, string> = {}
    for (const k of Object.keys(d).sort()) {
      const v = d[k as keyof typeof d]
      if (v === null || v === undefined) next[k] = ''
      else if (typeof v === 'boolean') next[k] = v ? 'true' : 'false'
      else next[k] = String(v)
    }
    if (!('llm_providers_json' in next)) next.llm_providers_json = '[]'
    if (!('active_llm_provider_id' in next)) next.active_llm_provider_id = ''
    if (!('embedding_providers_json' in next)) next.embedding_providers_json = '[]'
    if (!('active_embedding_provider_id' in next)) next.active_embedding_provider_id = ''
    runtimeForm.value = next
    initialDbPath.value = next.db_path ?? ''
    parseProvidersFromForm()
    parseEmbeddingsFromForm()
  } catch (e: unknown) {
    runtimeSaveMsg.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function reloadAllSettingsData() {
  await Promise.all([
    loadRuntimeSettings(),
    loadSkills(),
    loadMcpConfig(),
  ])
}

async function saveActiveLlmProviderId() {
  savingActiveLlmId.value = true
  runtimeSaveMsg.value = ''
  try {
    await api.putRuntimeSettings({
      active_llm_provider_id: (runtimeForm.value.active_llm_provider_id || '').trim() || null,
    })
    runtimeSaveMsg.value = '默认提供方已保存'
    window.dispatchEvent(new Event('mygpt-llm-providers-updated'))
    await reloadAllSettingsData()
  } catch (e: unknown) {
    runtimeSaveMsg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    savingActiveLlmId.value = false
  }
}

async function saveActiveEmbeddingProviderId() {
  savingActiveEmbeddingId.value = true
  runtimeSaveMsg.value = ''
  try {
    await api.putRuntimeSettings({
      active_embedding_provider_id: (runtimeForm.value.active_embedding_provider_id || '').trim() || null,
    })
    runtimeSaveMsg.value = '默认向量提供方已保存'
    await reloadAllSettingsData()
  } catch (e: unknown) {
    runtimeSaveMsg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    savingActiveEmbeddingId.value = false
  }
}

async function saveRuntimeSettings() {
  syncLlmRowsToFormJson()
  syncEmbeddingRowsToFormJson()
  const curDb = (runtimeForm.value.db_path || '').trim()
  if (curDb && curDb !== (initialDbPath.value || '').trim()) {
    const ok = await openConfirm({
      title: '确认修改数据库路径',
      message:
        '将使用新的 SQLite 路径；原库中的对话与账号不会自动迁移。确定要继续吗？',
      confirmText: '仍要保存',
    })
    if (!ok) return
  }

  savingRuntime.value = true
  runtimeSaveMsg.value = ''
  try {
    const values: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(runtimeForm.value)) {
      if (v === '***') continue
      if (v.trim() === '') {
        values[k] = null
        continue
      }
      if (k === 'max_registered_users') {
        const n = parseInt(v, 10)
        values[k] = Number.isFinite(n) ? n : null
        continue
      }
      if (k === 'sqlite_timeout_seconds') {
        values[k] = parseFloat(v)
        continue
      }
      values[k] = v
    }
    await api.putRuntimeSettings(values)
    runtimeSaveMsg.value = '已保存。可刷新对话页以下拉更新模型列表。'
    await loadRuntimeSettings()
  } catch (e: unknown) {
    runtimeSaveMsg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    savingRuntime.value = false
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    loadSkills()
    loadMcpConfig()
    loadRuntimeSettings()
    mcpSaveResult.value = null
    runtimeSaveMsg.value = ''
    oldPw.value = ''
    newPw.value = ''
    confirmPw.value = ''
    pwError.value = ''
    pwSuccess.value = false
  }
})

watch(activeTab, async (tab) => {
  if (!props.visible) return
  if (tab === 'skills') {
    await loadSkills()
    return
  }
  if (tab === 'mcp') {
    await loadMcpConfig()
    return
  }
  if (tab === 'llm' || tab === 'embedding' || tab === 'env') {
    await loadRuntimeSettings()
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
  width: min(820px, 96vw);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--modal-shadow);
}
.env-hint {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
  white-space: pre-wrap;
  margin-bottom: 12px;
  border: 1px solid var(--border-light);
  line-height: 1.45;
}
.env-grid {
  display: grid;
  grid-template-columns: minmax(140px, 220px) 1fr;
  gap: 8px 12px;
  align-items: start;
  max-height: 48vh;
  overflow-y: auto;
  padding-right: 4px;
}
.env-grid-row {
  display: contents;
}
.env-label {
  font-size: 12px;
  color: var(--text-secondary);
  padding-top: 8px;
  word-break: break-all;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.env-label-main {
  font-weight: 600;
  color: var(--text-primary);
}
.env-hint-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--bg-hover);
  border: 1px solid var(--border-light);
  color: var(--text-muted);
  font-size: 11px;
  cursor: help;
}
.env-input {
  width: 100%;
  box-sizing: border-box;
}
.env-input-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.env-inline-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.env-inline-msg {
  font-size: 12px;
}
.env-inline-msg.ok {
  color: var(--accent);
}
.env-inline-msg.err {
  color: var(--danger, #c0392b);
}
.env-label-warn {
  color: var(--danger, #c0392b);
  font-weight: 600;
}
.db-path-warn {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 8px 0 0;
  line-height: 1.45;
}
.llm-section {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--bg-hover);
}
.llm-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}
.migration-section {
  border-color: rgba(239, 68, 68, 0.35);
}
.migration-warn {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--danger, #c0392b);
}
.llm-section-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin: 0 0 12px;
  line-height: 1.45;
}
.llm-card {
  background: var(--panel-bg);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
}
.llm-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.llm-card-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.llm-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.btn-text {
  background: none;
  border: none;
  font-size: 12px;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 4px 8px;
  border-radius: 6px;
}
.btn-secondary.mini {
  padding: 5px 8px;
  font-size: 12px;
}
.btn-text:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.btn-text.danger {
  color: var(--danger, #c0392b);
}
.btn-text:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.llm-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 10px;
}
.llm-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}
.llm-kind-hint {
  grid-column: span 2;
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.4;
}
.llm-field.span-2 {
  grid-column: span 2;
}
.llm-add-btn {
  margin-bottom: 12px;
}
.llm-active-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mini-hint {
  font-size: 12px;
  color: var(--text-muted);
}
.llm-json-advanced {
  margin-bottom: 14px;
  font-size: 12px;
  color: var(--text-secondary);
}
.llm-json-advanced summary {
  cursor: pointer;
  margin-bottom: 8px;
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
  flex-wrap: nowrap;
  overflow-x: visible;
  gap: 4px;
  padding: 12px 24px 0;
  border-bottom: 1px solid var(--border-light);
  align-items: flex-end;
  min-height: 48px;
}

.tab-btn {
  padding: 8px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  flex: 0 0 auto;
  white-space: nowrap;
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

.skill-unavailable {
  margin-top: 4px;
  font-size: 12px;
  color: var(--danger, #c0392b);
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

.avatar-options {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.avatar-option {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 2px solid transparent;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  background: var(--surface-1);
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-option img {
  width: 90%;
  height: 90%;
  object-fit: cover;
  display: block;
}
.avatar-option.active {
  border-color: var(--accent);
}
.avatar-upload {
  font-size: 12px;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
}
.avatar-upload input {
  display: none;
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
  min-height: 42px;
  height: 42px;
  box-sizing: border-box;
  line-height: 1.2;
  outline: none;
  transition: border-color 0.15s;
}
select.pw-input {
  padding-top: 0;
  padding-bottom: 0;
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
