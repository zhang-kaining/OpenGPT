<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <img src="/hamster.svg" alt="logo" width="56" height="56" />
      </div>
      <h1>{{ isRegister ? '创建账号' : '登录 OpenGPT' }}</h1>

      <form @submit.prevent="handleSubmit">
        <div class="field">
          <label>用户名</label>
          <input
            v-model="username"
            type="text"
            placeholder="输入用户名"
            autocomplete="username"
            required
            minlength="2"
          />
        </div>

        <div v-if="isRegister" class="field">
          <label>昵称（可选）</label>
          <input
            v-model="displayName"
            type="text"
            placeholder="显示名称"
          />
        </div>

        <div class="field">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="输入密码"
            autocomplete="current-password"
            required
            minlength="6"
          />
        </div>

        <div v-if="isRegister" class="field">
          <label>确认密码</label>
          <input
            v-model="confirmPassword"
            type="password"
            placeholder="再次输入密码"
            required
          />
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '请稍候...' : (isRegister ? '注册' : '登录') }}
        </button>
      </form>

      <div class="switch-mode">
        <span v-if="!isRegister">
          还没有账号？
          <button class="link-btn" @click="switchMode">注册</button>
        </span>
        <span v-else>
          已有账号？
          <button class="link-btn" @click="switchMode">登录</button>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import * as api from '@/services/api'
import { setAuth } from '@/composables/useAuth'

const emit = defineEmits<{ (e: 'success'): void }>()

const isRegister = ref(false)
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const displayName = ref('')
const error = ref('')
const loading = ref(false)

function switchMode() {
  isRegister.value = !isRegister.value
  error.value = ''
}

async function handleSubmit() {
  error.value = ''

  if (isRegister.value && password.value !== confirmPassword.value) {
    error.value = '两次密码不一致'
    return
  }

  loading.value = true
  try {
    let result: { token: string; user: any }
    if (isRegister.value) {
      result = await api.register(username.value, password.value, displayName.value)
    } else {
      result = await api.login(username.value, password.value)
    }
    setAuth(result.token, result.user)
    emit('success')
  } catch (e: any) {
    error.value = e.message || '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  width: 100%;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-main);
  padding: 20px;
}

.login-card {
  width: 380px;
  max-width: 100%;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 40px 32px 32px;
  box-shadow: var(--modal-shadow);
}

.login-logo {
  text-align: center;
  margin-bottom: 8px;
}

h1 {
  text-align: center;
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 28px;
}

.field {
  margin-bottom: 16px;
}

.field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.field input {
  width: 100%;
  padding: 10px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 15px;
  outline: none;
  transition: border-color 0.15s;
}
.field input:focus {
  border-color: var(--accent);
}
.field input::placeholder {
  color: var(--text-muted);
}

.error-msg {
  color: var(--danger);
  font-size: 13px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 6px;
}

.submit-btn {
  width: 100%;
  padding: 12px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.submit-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.switch-mode {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: var(--text-secondary);
}

.link-btn {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}
.link-btn:hover {
  text-decoration: underline;
}
</style>
