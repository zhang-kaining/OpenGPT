<template>
  <Teleport to="body">
    <Transition name="confirm-fade">
      <div
        v-if="confirmVisible"
        class="confirm-overlay"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        @click.self="onCancel"
      >
        <div class="confirm-card">
          <h2 :id="titleId" class="confirm-title">{{ confirmTitle }}</h2>
          <p class="confirm-message">{{ confirmMessage }}</p>
          <div class="confirm-actions">
            <button type="button" class="btn btn-cancel" @click="onCancel">
              {{ cancelButtonText }}
            </button>
            <button
              type="button"
              class="btn btn-primary"
              :class="{ danger: confirmDanger }"
              @click="onOk"
            >
              {{ confirmButtonText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { watch, nextTick, onUnmounted } from 'vue'
import {
  confirmVisible,
  confirmTitle,
  confirmMessage,
  confirmDanger,
  confirmButtonText,
  cancelButtonText,
  resolveConfirm,
} from '@/composables/useConfirmDialog'

const titleId = 'confirm-dialog-title'

function onCancel() {
  resolveConfirm(false)
}

function onOk() {
  resolveConfirm(true)
}

function onEscape(e: KeyboardEvent) {
  if (e.key === 'Escape' && confirmVisible.value) {
    e.preventDefault()
    onCancel()
  }
}

watch(confirmVisible, (v) => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = v ? 'hidden' : ''
  if (v) {
    window.addEventListener('keydown', onEscape)
    nextTick(() => {
      const el = document.querySelector('.confirm-card .btn-primary') as HTMLButtonElement | null
      el?.focus()
    })
  } else {
    window.removeEventListener('keydown', onEscape)
  }
})

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
  text-align: left;
}

.confirm-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  margin-bottom: 6px;
}

.confirm-message {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
  margin-bottom: 14px;
  white-space: pre-wrap;
}

.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.btn {
  min-height: 32px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: background 0.12s, color 0.12s, opacity 0.12s;
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

.btn-primary.danger {
  background: var(--danger);
}

.btn-primary.danger:hover {
  filter: brightness(1.06);
}

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
