<template>
  <Teleport to="body">
    <Transition name="confirm-fade">
      <div
        v-if="promptVisible"
        class="confirm-overlay"
        role="dialog"
        aria-modal="true"
        @click.self="onCancel"
      >
        <div class="confirm-card">
          <h2 class="confirm-title">{{ promptTitle }}</h2>
          <input
            ref="inputRef"
            v-model="inputValue"
            class="prompt-input"
            :placeholder="promptPlaceholder"
            maxlength="60"
            @keyup.enter="onOk"
            @keyup.esc="onCancel"
          />
          <div class="confirm-actions">
            <button type="button" class="btn btn-cancel" @click="onCancel">取消</button>
            <button type="button" class="btn btn-primary" @click="onOk">确定</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import {
  promptVisible,
  promptTitle,
  promptPlaceholder,
  promptDefaultValue,
  resolvePrompt,
} from '@/composables/useConfirmDialog'

const inputRef = ref<HTMLInputElement | null>(null)
const inputValue = ref('')

watch(promptVisible, (v) => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = v ? 'hidden' : ''
  if (v) {
    inputValue.value = promptDefaultValue.value
    window.addEventListener('keydown', onEscape)
    nextTick(() => {
      inputRef.value?.focus()
      inputRef.value?.select()
    })
  } else {
    window.removeEventListener('keydown', onEscape)
  }
})

function onEscape(e: KeyboardEvent) {
  if (e.key === 'Escape' && promptVisible.value) {
    e.preventDefault()
    onCancel()
  }
}

function onCancel() {
  resolvePrompt(null)
}

function onOk() {
  const val = inputValue.value.trim()
  resolvePrompt(val || null)
}

onUnmounted(() => {
  window.removeEventListener('keydown', onEscape)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: var(--overlay-bg);
  backdrop-filter: blur(3px);
}

.confirm-card {
  width: 100%;
  max-width: 300px;
  padding: 16px 16px 14px;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: var(--modal-shadow);
}

.confirm-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.prompt-input {
  width: 100%;
  padding: 7px 10px;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--panel-input-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  outline: none;
  transition: border-color 0.15s;
  margin-bottom: 14px;
}

.prompt-input:focus {
  border-color: var(--border-strong);
}

.prompt-input::placeholder {
  color: var(--text-muted);
}

.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.btn {
  min-height: 30px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.btn-cancel {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
}

.btn-cancel:hover {
  background: var(--surface-1);
  color: var(--text-primary);
  border-color: var(--border-strong);
}

.btn-primary {
  border: none;
  background: var(--accent);
  color: #fff;
}

.btn-primary:hover {
  background: var(--accent-hover);
}

/* reuse same fade from ConfirmDialog */
.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.15s ease;
}

.confirm-fade-enter-active .confirm-card,
.confirm-fade-leave-active .confirm-card {
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}

.confirm-fade-enter-from .confirm-card,
.confirm-fade-leave-to .confirm-card {
  opacity: 0;
  transform: scale(0.98) translateY(4px);
}
</style>
