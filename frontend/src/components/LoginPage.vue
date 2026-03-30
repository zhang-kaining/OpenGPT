<template>
    <div class="login-page">
        <div class="login-card">
            <div class="login-logo">
                <div class="logo-ring">
                    <img src="/hamster.svg" alt="logo" width="40" height="40" />
                </div>
            </div>
            <h1>{{ isRegister ? "创建账号" : "登录 OpenGPT" }}</h1>

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
                    {{ loading ? "请稍候..." : isRegister ? "注册" : "登录" }}
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
import { ref } from "vue";
import * as api from "@/services/api";
import { setAuth } from "@/composables/useAuth";

const emit = defineEmits<{ (e: "success"): void }>();

const isRegister = ref(false);
const username = ref("");
const password = ref("");
const confirmPassword = ref("");
const displayName = ref("");
const error = ref("");
const loading = ref(false);

function switchMode() {
    isRegister.value = !isRegister.value;
    error.value = "";
}

async function handleSubmit() {
    error.value = "";

    if (isRegister.value && password.value !== confirmPassword.value) {
        error.value = "两次密码不一致";
        return;
    }

    loading.value = true;
    try {
        let result: { token: string; user: any };
        if (isRegister.value) {
            result = await api.register(
                username.value,
                password.value,
                displayName.value
            );
        } else {
            result = await api.login(username.value, password.value);
        }
        setAuth(result.token, result.user);
        emit("success");
    } catch (e: any) {
        error.value = e.message || "操作失败";
    } finally {
        loading.value = false;
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
    position: relative;
    overflow: hidden;
}

/* Atmospheric glow orbs */
.login-page::before {
    content: "";
    position: absolute;
    top: -120px;
    left: -80px;
    width: 500px;
    height: 500px;
    background: radial-gradient(
        circle,
        rgba(224, 149, 74, 0.12) 0%,
        transparent 65%
    );
    pointer-events: none;
    animation: orb-drift-a 18s ease-in-out infinite alternate;
}

.login-page::after {
    content: "";
    position: absolute;
    bottom: -100px;
    right: -60px;
    width: 420px;
    height: 420px;
    background: radial-gradient(
        circle,
        rgba(224, 149, 74, 0.08) 0%,
        transparent 65%
    );
    pointer-events: none;
    animation: orb-drift-b 22s ease-in-out infinite alternate;
}

@keyframes orb-drift-a {
    from {
        transform: translate(0, 0) scale(1);
    }
    to {
        transform: translate(40px, 30px) scale(1.1);
    }
}
@keyframes orb-drift-b {
    from {
        transform: translate(0, 0) scale(1);
    }
    to {
        transform: translate(-30px, -40px) scale(1.08);
    }
}

.login-card {
    width: 400px;
    max-width: 100%;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 44px 36px 36px;
    box-shadow: var(--modal-shadow);
    position: relative;
    z-index: 1;
    animation: fade-up 0.5s ease both;
    /* Subtle inner highlight */
    background-image: linear-gradient(
        160deg,
        rgba(255, 235, 205, 0.03) 0%,
        transparent 40%
    );
}

.login-logo {
    display: flex;
    justify-content: center;
    margin-bottom: 12px;
}

.logo-ring {
    width: 68px;
    height: 68px;
    border-radius: 50%;
    background: var(--accent-light);
    border: 1px solid rgba(224, 149, 74, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 24px rgba(224, 149, 74, 0.12);
}

h1 {
    text-align: center;
    font-size: 21px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 28px;
    letter-spacing: -0.02em;
}

.field {
    margin-bottom: 14px;
}

.field label {
    display: block;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 6px;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}

.field input {
    width: 100%;
    padding: 11px 14px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-primary);
    font-size: 15px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.field input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-glow);
}
.field input::placeholder {
    color: var(--text-muted);
}

.error-msg {
    color: var(--danger);
    font-size: 13px;
    margin-bottom: 14px;
    padding: 9px 12px;
    background: rgba(224, 88, 88, 0.09);
    border: 1px solid rgba(224, 88, 88, 0.18);
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.submit-btn {
    width: 100%;
    padding: 12px;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.18s, transform 0.12s, box-shadow 0.18s;
    letter-spacing: -0.01em;
    box-shadow: 0 2px 12px rgba(224, 149, 74, 0.3);
}
.submit-btn:hover:not(:disabled) {
    background: var(--accent-hover);
    box-shadow: 0 4px 20px rgba(224, 149, 74, 0.4);
    transform: translateY(-1px);
}
.submit-btn:active:not(:disabled) {
    transform: translateY(0);
}
.submit-btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    box-shadow: none;
}

.switch-mode {
    text-align: center;
    margin-top: 22px;
    font-size: 13px;
    color: var(--text-secondary);
}

.link-btn {
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    padding: 0;
    transition: opacity 0.15s;
}
.link-btn:hover {
    opacity: 0.8;
    text-decoration: underline;
}
</style>
