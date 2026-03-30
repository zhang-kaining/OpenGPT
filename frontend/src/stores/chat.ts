import { defineStore } from 'pinia'
import { ref, computed, reactive } from 'vue'
import type { Conversation, ConversationFolder, Message, MemoryItem, Citation } from '@/types'
import * as api from '@/services/api'
import type { LlmProviderOption } from '@/services/api'

const LLM_PROVIDER_LS_KEY = 'mygpt-selected-llm-provider-id'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const folders = ref<ConversationFolder[]>([])
  /** 新建对话（尚无 conv_id）时归入的文件夹；顶部「新对话」会置空 */
  const pendingFolderId = ref<string | null>(null)
  const expandedFolderIds = ref<Set<string>>(new Set())
  const currentConvId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const memories = ref<MemoryItem[]>([])
  const isLoading = ref(false)
  const searchQuery = ref('')
  const enableSearch = ref(true)
  const showMemoryPanel = ref(false)
  const llmProviders = ref<LlmProviderOption[]>([])
  const selectedLlmProviderId = ref('')
  const inflightByConv = ref<Record<string, {
    abort: AbortController
    userMsg: Message
    aiMsg: Message
  }>>({})
  const loadingConvIds = ref<Set<string>>(new Set())
  let tempSeq = 0

  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentConvId.value) ?? null
  )

  const filteredConversations = computed(() => {
    if (!searchQuery.value) return conversations.value
    const q = searchQuery.value.toLowerCase()
    return conversations.value.filter(c => c.title.toLowerCase().includes(q))
  })

  function setConvLoading(convId: string, loading: boolean) {
    const next = new Set(loadingConvIds.value)
    if (loading) next.add(convId)
    else next.delete(convId)
    loadingConvIds.value = next
    isLoading.value = !!(currentConvId.value && next.has(currentConvId.value))
  }

  function appendInflightIfNeeded(convId: string) {
    const inflight = inflightByConv.value[convId]
    if (!inflight) return
    if (!messages.value.some(m => m.id === inflight.userMsg.id)) {
      messages.value.push(inflight.userMsg)
    }
    if (!messages.value.some(m => m.id === inflight.aiMsg.id)) {
      messages.value.push(inflight.aiMsg)
    }
  }

  function nextTempId(prefix: string): string {
    tempSeq += 1
    return `${prefix}-${Date.now()}-${tempSeq}`
  }


  async function loadConversations() {
    conversations.value = await api.listConversations()
  }

  async function loadFolders() {
    folders.value = await api.listFolders()
  }

  async function refreshSidebar() {
    await Promise.all([loadConversations(), loadFolders()])
  }

  function toggleFolderExpanded(id: string) {
    const next = new Set(expandedFolderIds.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    expandedFolderIds.value = next
  }

  async function createFolderByName(name: string, parentId?: string | null) {
    await api.createFolder(name, parentId)
    await loadFolders()
    if (parentId) {
      const next = new Set(expandedFolderIds.value)
      next.add(parentId)
      expandedFolderIds.value = next
    }
  }

  async function removeFolder(id: string) {
    try {
      await api.deleteFolder(id)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : '删除文件夹失败')
      return
    }
    await refreshSidebar()
    const still = conversations.value.some(c => c.id === currentConvId.value)
    if (!still) {
      currentConvId.value = null
      messages.value = []
    }
  }

  async function selectConversation(id: string) {
    if (id === currentConvId.value) return
    currentConvId.value = id
    messages.value = await api.getMessages(id)
    appendInflightIfNeeded(id)
    isLoading.value = loadingConvIds.value.has(id)
  }

  async function createConversationImmediately(folderId: string | null) {
    const conv = await api.createConversation('未命名', folderId)
    conversations.value.unshift(conv)
    currentConvId.value = conv.id
    messages.value = []
    pendingFolderId.value = null
  }

  async function newConversation() {
    pendingFolderId.value = null
    try {
      await createConversationImmediately(null)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : '新建对话失败')
    }
  }

  async function newConversationInFolder(folderId: string) {
    pendingFolderId.value = folderId
    if (!expandedFolderIds.value.has(folderId)) toggleFolderExpanded(folderId)
    try {
      await createConversationImmediately(folderId)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : '新建对话失败')
    }
  }

  async function deleteConversation(id: string) {
    await api.deleteConversation(id)
    conversations.value = conversations.value.filter(c => c.id !== id)
    if (currentConvId.value === id) {
      currentConvId.value = null
      messages.value = []
    }
  }

  async function renameConversation(id: string, title: string) {
    await api.updateConversationTitle(id, title)
    const conv = conversations.value.find(c => c.id === id)
    if (conv) conv.title = title
  }

  async function sendMessage(content: string, images?: string[]) {
    if (!content.trim() && !images?.length) return
    if (isLoading.value) return
    if (!llmProviders.value.length) {
      const aiMsg: Message = {
        id: `tmp-ai-${Date.now()}`,
        conversation_id: currentConvId.value ?? '',
        role: 'assistant',
        content: '❌ 尚未配置任何对话模型。请先到「设置 -> 对话模型」添加至少一条提供方。',
        citations: null,
        created_at: new Date().toISOString(),
      }
      messages.value.push(aiMsg)
      return
    }

    // 添加用户消息（临时），images 深拷贝防止外部引用被清空
    // 用 reactive() 确保闭包里修改属性时 Vue 能检测到变化
    const userMsg = reactive<Message>({
      id: nextTempId('tmp-user'),
      conversation_id: currentConvId.value ?? '',
      role: 'user',
      content,
      images: images?.length ? [...images] : undefined,
      created_at: new Date().toISOString(),
    })
    messages.value.push(userMsg)

    // 添加 AI 消息占位
    // 用 reactive() 确保 onToken 回调里 aiMsg.content += token 能触发视图更新
    const aiMsg = reactive<Message>({
      id: nextTempId('tmp-ai'),
      conversation_id: currentConvId.value ?? '',
      role: 'assistant',
      content: '',
      citations: null,
      created_at: new Date().toISOString(),
      streaming: true,
      searching: false,
    })
    messages.value.push(aiMsg)
    const pendingKey = currentConvId.value || nextTempId('pending')
    const abort = new AbortController()
    inflightByConv.value[pendingKey] = { abort, userMsg, aiMsg }
    setConvLoading(pendingKey, true)

    try {
      await api.sendMessage(
        content,
        currentConvId.value,
        enableSearch.value,
        {
          onConvId(convId) {
            const folderForConv = pendingFolderId.value
            userMsg.conversation_id = convId
            aiMsg.conversation_id = convId
            if (inflightByConv.value[pendingKey]) {
              inflightByConv.value[convId] = inflightByConv.value[pendingKey]
              delete inflightByConv.value[pendingKey]
            }
            setConvLoading(pendingKey, false)
            setConvLoading(convId, true)
            if (!currentConvId.value) {
              pendingFolderId.value = null
              currentConvId.value = convId
              const newConv: Conversation = {
                id: convId,
                title: content.slice(0, 30),
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                folder_id: folderForConv ?? null,
              }
              conversations.value.unshift(newConv)
            }
          },
          onToken(token) {
            aiMsg.content += token
            aiMsg.searching = false
            aiMsg.toolCall = undefined
          },
          onSearching(query) {
            aiMsg.searching = true
            aiMsg.searchQuery = query
          },
          onSearchResults(_results) {
            aiMsg.searching = false
          },
          onToolCall(name, _status) {
            const labels: Record<string, string> = {
              feishu_send_message: '正在发送到飞书...',
            }
            aiMsg.toolCall = labels[name] ?? '正在调用工具...'
            aiMsg.searching = false
          },
          onDone(citations, usage) {
            aiMsg.citations = citations.length > 0 ? citations : null
            aiMsg.usage = usage ?? null
            aiMsg.streaming = false
            aiMsg.searching = false
            const convId = aiMsg.conversation_id || pendingKey
            delete inflightByConv.value[convId]
            setConvLoading(convId, false)
            // 只更新当前对话标题，不整体刷新列表（避免触发 selectConversation 副作用）
            const conv = conversations.value.find(c => c.id === convId)
            if (conv && content) {
              conv.title = content.slice(0, 30)
            }
          },
          onError(message) {
            aiMsg.content = `❌ 出错了：${message}`
            aiMsg.streaming = false
            aiMsg.searching = false
            const convId = aiMsg.conversation_id || pendingKey
            delete inflightByConv.value[convId]
            setConvLoading(convId, false)
          },
        },
        abort.signal,
        images,
        pendingFolderId.value,
        selectedLlmProviderId.value || null,
      )
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        aiMsg.content = `❌ 请求失败：${e?.message ?? '未知错误'}`
      }
      aiMsg.streaming = false
      aiMsg.searching = false
      const convId = aiMsg.conversation_id || pendingKey
      delete inflightByConv.value[convId]
      setConvLoading(convId, false)
    }
  }

  function stopGeneration() {
    if (!currentConvId.value) return
    const inflight = inflightByConv.value[currentConvId.value]
    if (inflight) {
      inflight.abort.abort()
      inflight.aiMsg.streaming = false
      inflight.aiMsg.searching = false
      delete inflightByConv.value[currentConvId.value]
      setConvLoading(currentConvId.value, false)
    }
  }

  async function loadLlmCatalog() {
    try {
      const data = await api.fetchLlmCatalog()
      llmProviders.value = data.providers || []
      const ids = new Set((data.providers || []).map((p) => p.id))
      const fromLs = (typeof localStorage !== 'undefined' && localStorage.getItem(LLM_PROVIDER_LS_KEY)) || ''
      let picked = ''
      if (fromLs && ids.has(fromLs)) picked = fromLs
      else if (data.active_id && ids.has(data.active_id)) picked = data.active_id
      else if (data.providers?.[0]?.id) picked = data.providers[0].id
      selectedLlmProviderId.value = picked
    } catch {
      llmProviders.value = []
    }
  }

  function persistLlmProviderSelection() {
    const id = selectedLlmProviderId.value
    if (typeof localStorage !== 'undefined') {
      if (id) localStorage.setItem(LLM_PROVIDER_LS_KEY, id)
      else localStorage.removeItem(LLM_PROVIDER_LS_KEY)
    }
    void api.putRuntimeSettings({ active_llm_provider_id: id || null }).catch(() => {})
  }

  async function loadMemories() {
    memories.value = await api.getMemories()
  }

  async function deleteMemory(id: string) {
    await api.deleteMemory(id)
    memories.value = memories.value.filter(m => m.id !== id)
  }

  return {
    conversations,
    folders,
    pendingFolderId,
    expandedFolderIds,
    currentConvId,
    messages,
    memories,
    isLoading,
    searchQuery,
    enableSearch,
    showMemoryPanel,
    llmProviders,
    selectedLlmProviderId,
    currentConversation,
    filteredConversations,
    loadConversations,
    loadFolders,
    refreshSidebar,
    toggleFolderExpanded,
    createFolderByName,
    removeFolder,
    selectConversation,
    newConversation,
    newConversationInFolder,
    deleteConversation,
    renameConversation,
    sendMessage,
    stopGeneration,
    loadMemories,
    deleteMemory,
    loadLlmCatalog,
    persistLlmProviderSelection,
  }
})
