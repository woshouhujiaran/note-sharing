<template>
  <transition name="ai-panel-fade">
    <div v-if="visible" class="ai-panel-shell">
      <section class="ai-panel">
        <header class="ai-panel-header">
          <div class="ai-panel-title-group">
            <div class="ai-panel-title-row">
              <span class="ai-panel-title">AI 助手</span>
              <span class="ai-panel-badge">{{ pageModeLabel }}</span>
            </div>
            <p class="ai-panel-subtitle">{{ contextSummary }}</p>
          </div>

          <button type="button" class="ai-close-button" @click="closePanel">收起</button>
        </header>

        <div v-if="suggestions.length" class="ai-suggestion-strip">
          <div class="ai-suggestion-title">你可以直接问</div>
          <div class="ai-suggestion-list">
            <button
              v-for="item in suggestions"
              :key="item.key"
              type="button"
              class="ai-suggestion-chip"
              @click="useSuggestion(item)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <div class="ai-chat-log" ref="logRef">
          <div v-if="messages.length === 0" class="ai-empty-state">
            <strong>纯净聊天框</strong>
            <span>先点上方推荐词，或直接输入你的问题。</span>
          </div>

          <article v-for="item in messages" :key="item.id" :class="['ai-message', item.role]">
            <div class="ai-message-role">{{ item.roleLabel }}</div>
            <div class="ai-message-content">{{ item.content }}</div>
            <div v-if="item.citations && item.citations.length" class="ai-message-citations">
              <span
                v-for="citation in item.citations.slice(0, 3)"
                :key="citation.noteId || citation.questionId || citation.url || citation.title"
                class="ai-message-citation"
              >
                {{ citation.title || citation.url || citation.summary || '引用' }}
              </span>
            </div>
            <div v-if="item.role === 'assistant' && item.prompt" class="ai-message-actions">
              <button type="button" class="ai-message-action" @click="retryPrompt(item.prompt)">
                重新生成
              </button>
            </div>
            <div class="ai-message-meta">
              {{ item.timeLabel }}
            </div>
          </article>
        </div>

        <form class="ai-composer" @submit.prevent="sendMessage">
          <textarea
            v-model="draft"
            class="ai-input"
            rows="3"
            placeholder="直接提问，AI 只会根据当前页面上下文回答"
          ></textarea>
          <div class="ai-composer-actions">
            <button type="button" class="ai-secondary-button" :disabled="!messages.length && !draft" @click="clearMessages">
              清空
            </button>
            <button type="submit" class="ai-send-button" :disabled="(!draft.trim() && !isStreaming) || !aiEnabled">
              {{ isStreaming ? '停止' : '发送' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </transition>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { getAiBffOrigin } from '@/config/ai'
import { buildAiHostSnapshot, buildRouteTarget } from '@/utils/aiProtocol'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  context: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:visible'])

const router = useRouter()
const userStore = useUserStore()
const { userInfo } = storeToRefs(userStore)

const aiEnabled = ref(true)
const draft = ref('')
const messages = ref([])
const logRef = ref(null)
const isStreaming = ref(false)
const streamAbortController = ref(null)
const pendingRewriteRequests = new Map()

const pageContext = computed(() => props.context || {})
const resourceContext = computed(() => pageContext.value.resource || {})
const currentTab = computed(() => pageContext.value.page?.tab || pageContext.value.currentTab || '')
const pageMode = computed(() => {
  const explicitMode = String(pageContext.value.page?.mode || '').toLowerCase()
  if (explicitMode) {
    return explicitMode
  }

  const resourceKind = String(resourceContext.value.kind || '').toLowerCase()
  if (currentTab.value === 'workspace' && (resourceKind === 'note-editor' || pageContext.value.editingNotebookId || pageContext.value.editingSpaceId)) {
    return 'edit'
  }

  if (currentTab.value === 'note-detail' || currentTab.value === 'qa-detail') {
    return 'view'
  }

  return 'browse'
})

const pageModeLabel = computed(() => {
  if (pageMode.value === 'edit') return '编辑态'
  if (pageMode.value === 'view') return '浏览态'
  return '浏览/搜索'
})

const contextSummary = computed(() => {
  const resource = resourceContext.value || {}
  const pageLabel = currentTab.value || 'unknown'
  const resourceLabel = resource.title
    ? `${resource.kind || 'resource'} · ${resource.title}`
    : pageContext.value.searchKeyword
      ? `关键词 · ${pageContext.value.searchKeyword}`
      : resource.noteId
        ? `笔记 ${resource.noteId}`
        : resource.questionId
          ? `问答 ${resource.questionId}`
          : '无资源'

  return `${pageLabel} · ${resourceLabel}`
})

const suggestions = computed(() => {
  const resource = resourceContext.value || {}
  const title = resource.title || pageContext.value.page?.label || pageContext.value.searchKeyword || '当前内容'
  const searchKeyword = pageContext.value.searchKeyword || '当前关键词'
  const hotTopic = pageContext.value.searchKeyword || resource.title || '当前最热内容'
  const selectedText = String(resource.selectedText || '').trim()

  if (pageMode.value === 'edit') {
    const rewritePrompt = selectedText
      ? `请改写我当前选中的这段文本，保持原意但让表达更清晰：${selectedText}`
      : `请改写我正在编辑的这篇笔记《${title}》中的内容，保持原意并提升表达。`
    return [
      { key: 'rewrite', label: '改写这段', prompt: rewritePrompt },
      { key: 'title', label: '起标题', prompt: `请根据我正在编辑的笔记《${title}》生成 3 个标题候选，并说明各自适合的场景。` },
      { key: 'outline', label: '生成提纲', prompt: `请把我正在编辑的笔记《${title}》整理成一个清晰的层级提纲。` },
      { key: 'evidence', label: '补充论据', prompt: `请为我正在编辑的笔记《${title}》补充可引用的论据、例子或待验证点。` }
    ]
  }

  if (currentTab.value === 'note-detail') {
    return [
      { key: 'summary', label: '总结', prompt: `请总结当前笔记《${title}》，先给核心观点，再给 3 条可执行建议。` },
      { key: 'keywords', label: '提炼关键词', prompt: `请提炼当前笔记《${title}》的关键词，并按重要性排序。` },
      { key: 'similar', label: '寻找相似文章', prompt: `请根据当前笔记《${title}》寻找相似文章或相近主题的笔记，并说明相似点。` },
      { key: 'logic', label: '指出漏洞', prompt: `请指出当前笔记《${title}》可能存在的逻辑漏洞、缺失信息或表达不清的地方。` }
    ]
  }

  if (currentTab.value === 'qa-detail') {
    return [
      { key: 'summary', label: '总结', prompt: `请总结当前问答《${title}》，梳理问题、答案和讨论结论。` },
      { key: 'answer', label: '回答思路', prompt: `请基于当前问答《${title}》给出一个更清晰的回答思路，分点说明。` },
      { key: 'similar', label: '相似问题', prompt: `请根据当前问答《${title}》找相似问题，并说明为什么相关。` },
      { key: 'followup', label: '补充追问', prompt: `请围绕当前问答《${title}》给出 3 个高质量追问，帮助补全上下文。` }
    ]
  }

  if (currentTab.value === 'search') {
    return [
      { key: 'narrow', label: '缩小范围', prompt: `请基于我当前的搜索词“${searchKeyword}”帮我缩小搜索范围，给出更准确的检索方向。` },
      { key: 'related', label: '找更相关的笔记', prompt: `请围绕搜索词“${searchKeyword}”给我找更相关的笔记，并说明筛选理由。` },
      { key: 'next', label: '换个关键词', prompt: `请基于搜索词“${searchKeyword}”推荐 3 个更适合继续搜索的关键词。` }
    ]
  }

  return [
    { key: 'hot-note', label: '查相关笔记', prompt: `请帮我查有关“${hotTopic}”的笔记，并按相关度列出最值得看的 3 条。` },
    { key: 'hot-qa', label: '找相关问答', prompt: `请帮我找和“${hotTopic}”相关的问答，并说明每条为什么相关。` },
    { key: 'hot-explain', label: '解释热词', prompt: `请解释“${hotTopic}”相关内容，并给出适合继续追问的方向。` }
  ]
})

let requestSeq = 0

function nowLabel() {
  return new Date().toLocaleTimeString()
}

function scrollToBottom() {
  nextTick(() => {
    if (!logRef.value) return
    logRef.value.scrollTop = logRef.value.scrollHeight
  })
}

function appendMessage(role, content, extra = {}) {
  const roleLabel = role === 'assistant' ? 'AI' : '你'
  messages.value.push({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    roleLabel,
    content,
    timeLabel: nowLabel(),
    ...extra
  })
  scrollToBottom()
}

function appendAssistantMessage(prompt = '') {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  messages.value.push({
    id,
    role: 'assistant',
    roleLabel: 'AI',
    content: '',
    timeLabel: nowLabel(),
    source: 'BFF',
    prompt,
    citations: [],
    route: null
  })
  scrollToBottom()
  return id
}

function updateAssistantMessage(messageId, patch = {}) {
  const index = messages.value.findIndex(item => item.id === messageId)
  if (index === -1) return
  messages.value[index] = {
    ...messages.value[index],
    ...patch
  }
  scrollToBottom()
}

function getAiToken() {
  return localStorage.getItem('token') || ''
}

function buildAiHeaders() {
  const headers = {
    'Content-Type': 'application/json'
  }

  const token = getAiToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  return headers
}

function parseSseEventBlock(block) {
  const rawLine = block
    .split('\n')
    .map(line => line.trim())
    .find(line => line.startsWith('data:'))

  if (!rawLine) return null
  const data = rawLine.slice(5).trim()
  if (!data) return null

  try {
    return JSON.parse(data)
  } catch {
    return null
  }
}

function tryRouteTarget(target) {
  const routeTarget = buildRouteTarget(target)
  if (!routeTarget) return
  if (routeTarget.path) {
    router.push({ path: routeTarget.path, query: routeTarget.query, params: routeTarget.params })
    return
  }
  if (routeTarget.routeName) {
    router.push({ name: routeTarget.routeName, query: routeTarget.query, params: routeTarget.params })
  }
}

async function streamChatFromBff(message, assistantMessageId) {
  const response = await fetch(`${getAiBffOrigin().replace(/\/$/, '')}/api/v1/agent/chat/stream`, {
    method: 'POST',
    headers: buildAiHeaders(),
    body: JSON.stringify({
      message,
      context: buildAiHostSnapshot({
        route: pageContext.value.route,
        userInfo: pageContext.value.user || userInfo.value,
        currentTab: pageContext.value.currentTab || pageContext.value.page?.tab,
        pageMode: pageMode.value,
        searchKeyword: pageContext.value.searchKeyword,
        viewingNoteId: pageContext.value.viewingNoteId,
        selectedWorkspaceId: pageContext.value.selectedWorkspaceId,
        editingNotebookId: pageContext.value.editingNotebookId,
        editingSpaceId: pageContext.value.editingSpaceId,
        resource: pageContext.value.resource,
        authToken: getAiToken(),
        permissions: pageContext.value.permissions || {
          canAccessWriteActions: pageMode.value === 'edit'
        }
      }),
      mode: 'local'
    }),
    signal: streamAbortController.value?.signal
  })

  if (!response.ok) {
    const body = await response.text().catch(() => '')
    const error = new Error(body || `BFF ${response.status}`)
    error.status = response.status
    throw error
  }

  if (!response.body) {
    return response.json()
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let finalResult = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''

    for (const block of blocks) {
      const evt = parseSseEventBlock(block)
      if (!evt) continue

      if (evt.delta) {
        const current = messages.value.find(item => item.id === assistantMessageId)
        updateAssistantMessage(assistantMessageId, {
          content: `${current?.content || ''}${evt.delta}`,
          source: 'BFF'
        })
      }

      if (evt.done) {
        finalResult = evt
      }
    }
  }

  if (buffer.trim()) {
    const evt = parseSseEventBlock(buffer)
    if (evt?.delta) {
      const current = messages.value.find(item => item.id === assistantMessageId)
      updateAssistantMessage(assistantMessageId, {
        content: `${current?.content || ''}${evt.delta}`,
        source: 'BFF'
      })
    }
    if (evt?.done) {
      finalResult = evt
    }
  }

  return finalResult || {
    answer: messages.value.find(item => item.id === assistantMessageId)?.content || '',
    citations: [],
    route: null
  }
}

function finalizeAssistantMessage(assistantMessageId, result) {
  if (!assistantMessageId) return
  const existing = messages.value.find(item => item.id === assistantMessageId)
  if (!existing) return

  updateAssistantMessage(assistantMessageId, {
    content: result?.answer || existing.content || '',
    citations: result?.citations || existing.citations || [],
    route: result?.route || existing.route || null,
    rewriteApplied: result?.rewriteApplied || existing.rewriteApplied || false
  })

  if (result?.route) {
    tryRouteTarget(result.route)
  }
}

function buildFallbackReply(prompt) {
  const resource = resourceContext.value || {}
  const title = resource.title || pageContext.value.searchKeyword || '当前内容'

  if (/改写|rewrite/i.test(prompt)) {
    return pageMode.value === 'edit'
      ? `当前编辑器暂时没有接入直接改写能力，请稍后重试，或者刷新工作区后再发起改写。`
      : '当前处于浏览态，不能直接改写正文。请先进入编辑页后再继续。'
  }

  if (/标题|title/i.test(prompt)) {
    return `标题候选：1. ${title} 的结构化整理 2. ${title} 的可执行清单 3. ${title} 的知识摘要`
  }

  if (/关键词|keywords/i.test(prompt)) {
    return '关键词：知识整理、页面上下文、笔记检索、AI 协作、站内引用'
  }

  if (/相似|similar/i.test(prompt)) {
    return `我会先基于 ${title} 做相似内容判断。当前处于本地演示模式，返回的是稳定占位结果。`
  }

  if (/总结|摘要|summary/i.test(prompt)) {
    return `已读取当前内容《${title}》，下一步可以继续做标题生成、关键词抽取或补充引用来源。`
  }

  return `本地演示已收到：${prompt}`
}

function isRewritePrompt(prompt) {
  return /改写|润色|重写|rewrite|polish/i.test(String(prompt || ''))
}

function requestWorkspaceRewrite(prompt) {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined') {
      reject(new Error('当前环境不支持工作区改写'))
      return
    }

    const requestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    const timeoutId = window.setTimeout(() => {
      pendingRewriteRequests.delete(requestId)
      reject(new Error('工作区改写超时，请稍后重试'))
    }, 120000)

    pendingRewriteRequests.set(requestId, {
      resolve: (payload) => {
        window.clearTimeout(timeoutId)
        pendingRewriteRequests.delete(requestId)
        resolve(payload)
      },
      reject: (error) => {
        window.clearTimeout(timeoutId)
        pendingRewriteRequests.delete(requestId)
        reject(error)
      }
    })

    window.dispatchEvent(new CustomEvent('folio-ai-rewrite-request', {
      detail: {
        requestId,
        prompt,
        instruction: prompt,
        resource: resourceContext.value,
        pageMode: pageMode.value
      }
    }))
  })
}

function handleWorkspaceRewriteResult(event) {
  const detail = event?.detail
  if (!detail?.requestId) return

  const pending = pendingRewriteRequests.get(detail.requestId)
  if (!pending) return

  if (detail.ok) {
    pending.resolve(detail.result || { ok: true })
    return
  }

  pending.reject(new Error(detail.error || '工作区改写失败'))
}

async function runPrompt(prompt) {
  const content = String(prompt || '').trim()
  if (!content || !aiEnabled.value || isStreaming.value) {
    return
  }

  appendMessage('user', content)
  draft.value = ''

  if (isRewritePrompt(content) && pageMode.value === 'edit') {
    const assistantMessageId = appendAssistantMessage(content)
    try {
      updateAssistantMessage(assistantMessageId, {
        content: '正在把改写应用到当前工作区...',
        source: 'workspace'
      })
      const result = await requestWorkspaceRewrite(content)
      if (result?.ok) {
        updateAssistantMessage(assistantMessageId, {
          content: result.summary || '已改写并应用到工作区，你可以撤销本次改写，或继续提出更具体的要求。',
          source: 'workspace',
          rewriteApplied: true,
          citations: [],
          route: null
        })
      } else {
        updateAssistantMessage(assistantMessageId, {
          content: result?.reason ? `改写未执行：${result.reason}` : '改写未执行，请稍后重试。',
          source: 'workspace'
        })
      }
    } catch (error) {
      updateAssistantMessage(assistantMessageId, {
        content: error?.message || '改写失败，请稍后重试。',
        source: 'workspace'
      })
    }
    return
  }

  const assistantMessageId = appendAssistantMessage(content)
  streamAbortController.value = new AbortController()
  isStreaming.value = true
  requestSeq += 1
  const currentRequestSeq = requestSeq

  try {
    const result = await streamChatFromBff(content, assistantMessageId)
    if (currentRequestSeq === requestSeq) {
      finalizeAssistantMessage(assistantMessageId, result)
    }
  } catch (error) {
    const fallback = buildFallbackReply(content)
    updateAssistantMessage(assistantMessageId, {
      content: error?.status === 403 ? '当前页不允许执行该操作，请切换到编辑页后再试。' : fallback,
      source: '本地'
    })
  } finally {
    streamAbortController.value = null
    isStreaming.value = false
  }
}

function useSuggestion(item) {
  if (!item || !item.prompt || isStreaming.value) return
  draft.value = item.prompt
  runPrompt(item.prompt)
}

function retryPrompt(prompt) {
  if (!prompt || isStreaming.value || !aiEnabled.value) {
    return
  }

  draft.value = prompt
  runPrompt(prompt)
}

function sendMessage() {
  if (isStreaming.value) {
    if (streamAbortController.value) {
      streamAbortController.value.abort()
    }
    isStreaming.value = false
    return
  }

  runPrompt(draft.value)
}

function clearMessages() {
  if (streamAbortController.value) {
    streamAbortController.value.abort()
    streamAbortController.value = null
  }
  isStreaming.value = false
  messages.value = []
}

function closePanel() {
  emit('update:visible', false)
}

watch(
  () => props.visible,
  (value) => {
    if (value) {
      scrollToBottom()
    }
  }
)

onMounted(() => {
  scrollToBottom()
  if (typeof window !== 'undefined') {
    window.addEventListener('folio-ai-rewrite-result', handleWorkspaceRewriteResult)
  }
})

onBeforeUnmount(() => {
  if (streamAbortController.value) {
    streamAbortController.value.abort()
    streamAbortController.value = null
  }
  if (typeof window !== 'undefined') {
    window.removeEventListener('folio-ai-rewrite-result', handleWorkspaceRewriteResult)
    pendingRewriteRequests.forEach(({ reject }) => reject(new Error('AI 助手已关闭')))
    pendingRewriteRequests.clear()
  }
})
</script>

<style scoped>
.ai-panel-shell {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2200;
  width: min(460px, calc(100vw - 32px));
  pointer-events: none;
}

.ai-panel {
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 620px;
  max-height: calc(100vh - 120px);
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(15, 23, 42, 0.99)),
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.18), transparent 55%);
  color: #e2e8f0;
  box-shadow: 0 26px 80px rgba(15, 23, 42, 0.34);
  backdrop-filter: blur(18px);
  overflow: hidden;
}

.ai-panel-header,
.ai-suggestion-strip,
.ai-chat-log,
.ai-composer {
  padding-left: 18px;
  padding-right: 18px;
}

.ai-panel-header {
  padding-top: 18px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.ai-panel-title-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-panel-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ai-panel-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.ai-panel-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  color: #cbd5e1;
  font-size: 12px;
}

.ai-panel-subtitle {
  margin: 0;
  color: #94a3b8;
  font-size: 12px;
}

.ai-close-button {
  border: none;
  cursor: pointer;
  transition: transform 0.15s ease, opacity 0.15s ease, background 0.15s ease;
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  color: #e2e8f0;
  font-size: 12px;
}

.ai-suggestion-strip {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-suggestion-title {
  font-size: 12px;
  color: #94a3b8;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ai-suggestion-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ai-suggestion-chip {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
}

.ai-suggestion-chip:hover {
  background: rgba(255, 255, 255, 0.1);
}

.ai-chat-log {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
  min-height: 260px;
  flex: 1;
}

.ai-message {
  padding: 12px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.62);
  border: 1px solid rgba(148, 163, 184, 0.12);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-message.user {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.2);
}

.ai-message-role,
.ai-message-meta {
  font-size: 11px;
  color: #94a3b8;
}

.ai-message-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  color: #f8fafc;
}

.ai-message-citations {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ai-message-citation {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid rgba(148, 163, 184, 0.14);
  font-size: 11px;
  color: #cbd5e1;
}

.ai-message-actions {
  display: flex;
  justify-content: flex-end;
}

.ai-message-action {
  border: none;
  background: transparent;
  color: #86efac;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.ai-message-action:hover {
  text-decoration: underline;
}

.ai-empty-state {
  padding: 18px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px dashed rgba(148, 163, 184, 0.22);
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #cbd5e1;
}

.ai-empty-state strong {
  color: #f8fafc;
}

.ai-composer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 0;
  padding-bottom: 18px;
}

.ai-input {
  width: 100%;
  resize: none;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.72);
  color: #f8fafc;
  padding: 12px;
  outline: none;
  font-size: 13px;
  line-height: 1.6;
}

.ai-input::placeholder {
  color: #64748b;
}

.ai-composer-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.ai-secondary-button,
.ai-send-button {
  height: 32px;
  padding: 0 12px;
  border-radius: 10px;
  font-size: 12px;
  border: none;
  cursor: pointer;
}

.ai-secondary-button {
  background: rgba(148, 163, 184, 0.14);
  color: #e2e8f0;
}

.ai-send-button {
  background: linear-gradient(135deg, #22c55e, #16a34a);
  color: #f8fafc;
}

.ai-send-button:disabled,
.ai-secondary-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ai-panel-fade-enter-active,
.ai-panel-fade-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.ai-panel-fade-enter-from,
.ai-panel-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 720px) {
  .ai-panel-shell {
    right: 12px;
    bottom: 12px;
    width: calc(100vw - 24px);
  }

  .ai-panel {
    min-height: 560px;
  }
}
</style>
