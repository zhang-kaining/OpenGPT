import { ref } from 'vue'

// ── 确认框 ────────────────────────────────────────────
export const confirmVisible = ref(false)
export const confirmTitle = ref('请确认')
export const confirmMessage = ref('')
export const confirmDanger = ref(true)
export const confirmButtonText = ref('确定')
export const cancelButtonText = ref('取消')

let confirmResolver: ((value: boolean) => void) | null = null

export function openConfirm(opts: {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}): Promise<boolean> {
  confirmTitle.value = opts.title ?? '请确认'
  confirmMessage.value = opts.message
  confirmDanger.value = opts.danger !== false
  confirmButtonText.value =
    opts.confirmText ?? (confirmDanger.value ? '删除' : '确定')
  cancelButtonText.value = opts.cancelText ?? '取消'
  confirmVisible.value = true
  return new Promise((resolve) => {
    confirmResolver = resolve
  })
}

export function resolveConfirm(ok: boolean) {
  confirmVisible.value = false
  confirmResolver?.(ok)
  confirmResolver = null
}

// ── 输入框 ────────────────────────────────────────────
export const promptVisible = ref(false)
export const promptTitle = ref('')
export const promptPlaceholder = ref('')
export const promptDefaultValue = ref('')

let promptResolver: ((value: string | null) => void) | null = null

export function openPrompt(opts: {
  title: string
  placeholder?: string
  defaultValue?: string
}): Promise<string | null> {
  promptTitle.value = opts.title
  promptPlaceholder.value = opts.placeholder ?? ''
  promptDefaultValue.value = opts.defaultValue ?? ''
  promptVisible.value = true
  return new Promise((resolve) => {
    promptResolver = resolve
  })
}

export function resolvePrompt(value: string | null) {
  promptVisible.value = false
  promptResolver?.(value)
  promptResolver = null
}
