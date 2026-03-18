<template>
  <div class="input-area">
    <div class="input-wrapper" :class="{ focused: isFocused }">
      <!-- 图片预览区 -->
      <div v-if="pendingImages.length" class="image-previews">
        <div
          v-for="(img, i) in pendingImages"
          :key="i"
          class="image-preview-item"
        >
          <img :src="img" alt="附图" />
          <button class="remove-img-btn" @click="removeImage(i)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>

      <textarea
        ref="textareaRef"
        v-model="inputText"
        class="input-textarea"
        placeholder="给 ChatGPT 发送消息"
        rows="1"
        @keydown="handleKeydown"
        @input="autoResize"
        @focus="isFocused = true"
        @blur="isFocused = false"
        @paste="handlePaste"
        @dragover.prevent
        @drop.prevent="handleDrop"
      />

      <div class="input-bottom">
        <div class="input-tools">
          <!-- 图片上传按钮 -->
          <button class="tool-btn" title="上传图片" @click="triggerFileInput">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <circle cx="8.5" cy="8.5" r="1.5"/>
              <polyline points="21 15 16 10 5 21"/>
            </svg>
          </button>
          <input
            ref="fileInputRef"
            type="file"
            accept="image/*"
            multiple
            class="hidden-file-input"
            @change="handleFileChange"
          />
          <!-- 搜索开关 -->
          <button
            class="tool-btn search-toggle"
            :class="{ active: store.enableSearch }"
            :title="store.enableSearch ? '关闭网页搜索' : '开启网页搜索'"
            @click="store.enableSearch = !store.enableSearch"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <span>搜索</span>
          </button>
        </div>
        <!-- 发送按钮 -->
        <button
          class="send-btn"
          :class="{ active: canSend }"
          :disabled="!canSend"
          @click="handleSend"
        >
          <svg v-if="!store.isLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7"/>
          </svg>
          <div v-else class="stop-icon"></div>
        </button>
      </div>
    </div>
    <p class="input-hint">ChatGPT 可能会犯错。请核实重要信息。</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'

const store = useChatStore()
const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const isFocused = ref(false)
const pendingImages = ref<string[]>([])

const canSend = computed(() =>
  !store.isLoading && (inputText.value.trim().length > 0 || pendingImages.value.length > 0)
)

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter') return
  if (e.shiftKey || e.ctrlKey || e.altKey || e.metaKey) return
  if (e.isComposing || (e as KeyboardEvent & { keyCode?: number }).keyCode === 229) return
  e.preventDefault()
  void handleSend()
}

async function handleSend() {
  if (!canSend.value) return
  const text = inputText.value.trim()
  const imgs = [...pendingImages.value]
  inputText.value = ''
  pendingImages.value = []
  await nextTick()
  autoResize()
  await store.sendMessage(text, imgs.length ? imgs : undefined)
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function handleFileChange(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files) addFiles(Array.from(files))
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function handlePaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items
  if (!items) return
  const imageFiles: File[] = []
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) imageFiles.push(file)
    }
  }
  if (imageFiles.length) {
    e.preventDefault()
    addFiles(imageFiles)
  }
}

function handleDrop(e: DragEvent) {
  const files = e.dataTransfer?.files
  if (files) {
    const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'))
    if (imageFiles.length) addFiles(imageFiles)
  }
}

function addFiles(files: File[]) {
  for (const file of files) {
    const reader = new FileReader()
    reader.onload = (ev) => {
      const result = ev.target?.result as string
      if (result && pendingImages.value.length < 4) {
        pendingImages.value.push(result)
      }
    }
    reader.readAsDataURL(file)
  }
}

function removeImage(index: number) {
  pendingImages.value.splice(index, 1)
}
</script>

<style scoped>
.input-area {
  padding: 12px 16px 16px;
  background: var(--bg-main);
  flex-shrink: 0;
}

.input-wrapper {
  max-width: 720px;
  margin: 0 auto;
  background: var(--bg-input);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  transition: border-color 0.15s;
}
.input-wrapper.focused {
  border-color: rgba(255,255,255,0.2);
}

.image-previews {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px 0;
}

.image-preview-item {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}
.image-preview-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.remove-img-btn {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 18px;
  height: 18px;
  background: rgba(0,0,0,0.7);
  border: none;
  border-radius: 50%;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.remove-img-btn:hover { background: rgba(0,0,0,0.9); }

.input-textarea {
  width: 100%;
  background: none;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 16px;
  line-height: 1.6;
  padding: 14px 16px 4px;
  resize: none;
  min-height: 52px;
  max-height: 200px;
  font-family: inherit;
}
.input-textarea::placeholder { color: var(--text-muted); }

.input-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px 8px;
}

.input-tools {
  display: flex;
  align-items: center;
  gap: 4px;
}

.hidden-file-input {
  display: none;
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  background: none;
  border: none;
  border-radius: 20px;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.tool-btn:hover {
  background: rgba(255,255,255,0.08);
  color: var(--text-secondary);
}
.tool-btn.search-toggle.active {
  background: rgba(255,255,255,0.1);
  color: var(--text-primary);
}

.send-btn {
  width: 34px;
  height: 34px;
  background: var(--send-btn-bg);
  border: none;
  border-radius: 50%;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
  flex-shrink: 0;
}
.send-btn.active {
  background: var(--send-btn-active);
  color: #000;
}
.send-btn:disabled { cursor: not-allowed; }
.send-btn.active:hover { background: #d4d4d4; }

.stop-icon {
  width: 12px;
  height: 12px;
  background: #000;
  border-radius: 2px;
}

.input-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
}
</style>
