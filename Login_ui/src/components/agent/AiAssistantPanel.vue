<template>
  <transition name="ai-panel-fade">
    <div v-if="visible" class="ai-panel-shell">
      <section class="ai-panel">
        <header class="ai-panel-header">
          <div class="ai-panel-title-group">
            <div class="ai-panel-title-row">
              <span class="ai-panel-title">AI 助手</span>
              <span class="ai-panel-badge" :class="{ 'is-active': aiEnabled }">
                {{ aiEnabled ? '已启用' : '已关闭' }}
              </span>
            </div>
            <p class="ai-panel-subtitle">
              宿主控制 · {{ activeModeLabel }} · {{ shellStatusLabel }}
            </p>
          </div>

          <div class="ai-panel-actions">
            <button type="button" class="ai-mode-button" :class="{ active: activeMode === 'local' }" @click="activeMode = 'local'">
              本地演示
            </button>
            <button
              type="button"
              class="ai-mode-button"
              :class="{ active: activeMode === 'iframe', disabled: !shellUrl }"
              :disabled="!shellUrl"
              @click="switchToIframe"
            >
              iframe 壳
            </button>
            <button type="button" class="ai-close-button" @click="closePanel">收起</button>
          </div>
        </header>

        <div class="ai-panel-toolbar">
          <label class="ai-toggle">
            <input v-model="aiEnabled" type="checkbox" />
            <span class="ai-toggle-track">
              <span class="ai-toggle-thumb"></span>
            </span>
            <span class="ai-toggle-label">功能开关</span>
          </label>

          <button type="button" class="ai-secondary-button" @click="syncContextToFrame">
            推送上下文
          </button>
          <button type="button" class="ai-secondary-button" @click="clearMessages">
            清空会话
          </button>
        </div>

        <div class="ai-quick-actions">
          <button
            v-for="action in quickActions"
            :key="action.key"
            type="button"
            class="ai-chip"
            @click="triggerQuickAction(action)"
          >
            {{ action.label }}
          </button>
        </div>

        <div class="ai-context-card">
          <div class="ai-context-title">当前上下文</div>
          <div class="ai-context-grid">
            <div class="ai-context-item">
              <span class="label">页面</span>
              <span class="value">{{ contextSummary.pageLabel }}</span>
            </div>
            <div class="ai-context-item">
              <span class="label">路线</span>
              <span class="value">{{ contextSummary.routeLabel }}</span>
            </div>
            <div class="ai-context-item">
              <span class="label">资源</span>
              <span class="value">{{ contextSummary.resourceLabel }}</span>
            </div>
            <div class="ai-context-item">
              <span class="label">角色</span>
              <span class="value">{{ contextSummary.roleLabel }}</span>
            </div>
          </div>
        </div>

        <div v-if="activeMode === 'iframe'" class="ai-frame-panel">
          <div v-if="shellUrl" class="ai-frame-wrapper">
            <iframe
              ref="shellFrameRef"
              class="ai-frame"
              :src="shellUrl"
              title="AI Assistant Shell"
              sandbox="allow-scripts allow-forms"
            ></iframe>
          </div>
          <div v-else class="ai-empty-state">
            <strong>iframe 壳未配置</strong>
            <span>请先设置 `VUE_APP_AI_BFF_ORIGIN` 后再启用 iframe 模式。</span>
          </div>
        </div>

        <template v-else>
          <div class="ai-chat-log" ref="logRef">
            <article v-for="item in messages" :key="item.id" :class="['ai-message', item.role]">
              <div class="ai-message-role">{{ item.roleLabel }}</div>
              <div class="ai-message-content">{{ item.content }}</div>
              <div class="ai-message-meta">{{ item.timeLabel }}</div>
            </article>

            <div v-if="messages.length === 0" class="ai-empty-state">
              <strong>可用的稳定函数</strong>
              <span>标题生成、当前页摘要、关键词抽取、相似问题提示，都会在本地模式下稳定返回。</span>
            </div>
          </div>

          <form class="ai-composer" @submit.prevent="sendMessage">
            <textarea
              v-model="draft"
              class="ai-input"
              rows="3"
              placeholder="输入一句话，让 AI 基于当前页面帮你处理"
            ></textarea>
            <div class="ai-composer-actions">
              <button type="button" class="ai-secondary-button" @click="draft = suggestDraft()">示例文本</button>
              <button type="submit" class="ai-send-button" :disabled="!draft.trim() || !aiEnabled">
                发送
              </button>
            </div>
          </form>
        </template>
      </section>
    </div>
  </transition>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { AI_MESSAGE_TYPES, AI_PROTOCOL_VERSION, AI_STORAGE_KEYS, getAiBffOrigin, getAiShellUrl, getAiTargetOrigin, isValidAiOrigin } from '@/config/ai'
import { buildAiHostSnapshot, buildRouteTarget, isAiHostMessage } from '@/utils/aiProtocol'

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

const aiEnabled = ref(localStorage.getItem(AI_STORAGE_KEYS.enabled) !== 'false')
const activeMode = ref(localStorage.getItem(AI_STORAGE_KEYS.shellMode) || 'local')
const draft = ref('')
const messages = ref([])
const logRef = ref(null)
const shellFrameRef = ref(null)
const configuredOrigin = computed(() => getAiBffOrigin())
const shellUrl = computed(() => (aiEnabled.value ? getAiShellUrl() : ''))

const contextSummary = computed(() => {
  const ctx = props.context || {}
  return {
    pageLabel: ctx.pageLabel || ctx.currentTab || '未知页面',
    routeLabel: ctx.route?.path || ctx.route?.name || '未识别',
    resourceLabel: ctx.viewingNoteId
      ? `笔记 ${ctx.viewingNoteId}`
      : ctx.selectedWorkspaceId
        ? `空间 ${ctx.selectedWorkspaceId}`
        : ctx.editingNotebookId
          ? `编辑器 ${ctx.editingNotebookId}`
          : '无',
    roleLabel: ctx.user?.role || userInfo.value?.role || 'User'
  }
})

const activeModeLabel = computed(() => (activeMode.value === 'iframe' ? 'iframe 宿主' : '本地演示'))
const shellStatusLabel = computed(() => (configuredOrigin.value ? 'BFF 已配置' : 'BFF 未配置'))

const quickActions = computed(() => {
  const actions = [
    { key: 'title', label: '生成标题', prompt: '请根据当前页面内容生成三个标题候选。' },
    { key: 'summary', label: '总结当前页', prompt: '请总结当前页面上下文，并给出下一步建议。' },
    { key: 'keywords', label: '提炼关键词', prompt: '请抽取当前页面的关键词，并按重要性排序。' },
    { key: 'similar', label: '相似问题', prompt: '请给出当前页面相关的相似问题提示。' }
  ]

  return actions
})

const stopScrollToken = ref(0)
let frameMessageHandler = null
let aiContextTimer = null

function nowLabel() {
  return new Date().toLocaleTimeString()
}

function appendMessage(role, content) {
  const roleLabel = role === 'assistant' ? 'AI' : '你'
  messages.value.push({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    roleLabel,
    content,
    timeLabel: nowLabel()
  })
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (!logRef.value) return
    logRef.value.scrollTop = logRef.value.scrollHeight
  })
}

function summarizeContext() {
  const ctx = props.context || {}
  const routePath = ctx.route?.path || '未知路由'
  const tab = ctx.currentTab || ctx.page?.tab || '未设置'
  const noteId = ctx.viewingNoteId ? String(ctx.viewingNoteId) : '无'
  const workspace = ctx.selectedWorkspaceId ? String(ctx.selectedWorkspaceId) : '无'
  const role = ctx.user?.role || userInfo.value?.role || 'User'

  return `当前页面是 ${tab}，路由是 ${routePath}，笔记 ID ${noteId}，空间 ID ${workspace}，用户角色 ${role}。`
}

function buildMockReply(prompt) {
  const base = summarizeContext()

  if (/标题|起标题|title/i.test(prompt)) {
    return [
      '标题候选 1：',
      `${contextSummary.value.pageLabel} 的结构化整理`,
      '标题候选 2：',
      `${contextSummary.value.pageLabel} 的可执行清单`,
      '标题候选 3：',
      `${contextSummary.value.pageLabel} 的知识摘要`
    ].join('\n')
  }

  if (/关键词|keywords/i.test(prompt)) {
    return [
      '关键词：',
      '知识整理',
      '页面上下文',
      '笔记检索',
      'AI 协作',
      '站内引用'
    ].join('，')
  }

  if (/相似|问题/i.test(prompt)) {
    return `我会先基于 ${contextSummary.value.routeLabel} 做相似问题判断。当前处于本地演示模式，返回的是稳定占位结果。`
  }

  if (/总结|摘要|summary/i.test(prompt)) {
    return `已读取宿主上下文：${base}下一步可以继续做标题生成、关键词抽取或补充引用来源。`
  }

  return `本地演示已收到：${prompt}\n\n${base}如果 BFF 已配置，我会把同一条消息以 postMessage 发送给 iframe/后端。`
}

function syncContextToFrame() {
  if (!aiEnabled.value || activeMode.value !== 'iframe') {
    return
  }

  const frame = shellFrameRef.value
  if (!frame || !frame.contentWindow) {
    return
  }

  const snapshot = buildAiHostSnapshot({
    route: props.context?.route,
    userInfo: props.context?.user || userInfo.value,
    currentTab: props.context?.currentTab,
    searchKeyword: props.context?.searchKeyword,
    viewingNoteId: props.context?.viewingNoteId,
    selectedWorkspaceId: props.context?.selectedWorkspaceId,
    editingNotebookId: props.context?.editingNotebookId,
    editingSpaceId: props.context?.editingSpaceId
  })

  frame.contentWindow.postMessage(
    {
      version: AI_PROTOCOL_VERSION,
      type: AI_MESSAGE_TYPES.CONTEXT,
      payload: snapshot
    },
    getAiTargetOrigin()
  )
}

function closePanel() {
  emit('update:visible', false)
}

function clearMessages() {
  messages.value = []
}

function suggestDraft() {
  return `请围绕 ${contextSummary.value.pageLabel}，生成一个更清晰的 AI 任务请求。`
}

function triggerQuickAction(action) {
  if (!aiEnabled.value) {
    return
  }

  draft.value = action.prompt
  sendMessage()
}

function sendMessage() {
  const content = draft.value.trim()
  if (!content || !aiEnabled.value) {
    return
  }

  appendMessage('user', content)
  draft.value = ''

  if (activeMode.value === 'iframe' && shellUrl.value) {
    const frame = shellFrameRef.value
    if (frame && frame.contentWindow) {
      frame.contentWindow.postMessage(
        {
          version: AI_PROTOCOL_VERSION,
          type: AI_MESSAGE_TYPES.CHAT,
          payload: {
            message: content,
            context: buildAiHostSnapshot({
              route: props.context?.route,
              userInfo: props.context?.user || userInfo.value,
              currentTab: props.context?.currentTab,
              searchKeyword: props.context?.searchKeyword,
              viewingNoteId: props.context?.viewingNoteId,
              selectedWorkspaceId: props.context?.selectedWorkspaceId,
              editingNotebookId: props.context?.editingNotebookId,
              editingSpaceId: props.context?.editingSpaceId
            })
          }
        },
        getAiTargetOrigin()
      )
    }
  }

  appendMessage('assistant', buildMockReply(content))
}

function switchToIframe() {
  if (!shellUrl.value) {
    return
  }
  activeMode.value = 'iframe'
}

watch(aiEnabled, (value) => {
  localStorage.setItem(AI_STORAGE_KEYS.enabled, String(value))
  if (!value) {
    activeMode.value = 'local'
    localStorage.setItem(AI_STORAGE_KEYS.shellMode, 'local')
  }
})

watch(activeMode, (value) => {
  localStorage.setItem(AI_STORAGE_KEYS.shellMode, value)
  if (value === 'iframe') {
    syncContextToFrame()
  }
})

watch(
  () => props.visible,
  (value) => {
    if (value) {
      syncContextToFrame()
    }
  }
)

onMounted(() => {
  frameMessageHandler = (event) => {
    if (!isValidAiOrigin(event.origin)) {
      return
    }

    if (!isAiHostMessage(event.data)) {
      return
    }

    if (event.data.type === AI_MESSAGE_TYPES.READY) {
      syncContextToFrame()
      return
    }

    if (event.data.type === AI_MESSAGE_TYPES.ROUTE) {
      const target = buildRouteTarget(event.data.payload)
      if (!target) {
        return
      }

      if (target.path) {
        router.push({ path: target.path, query: target.query, params: target.params })
      } else if (target.routeName) {
        router.push({ name: target.routeName, query: target.query, params: target.params })
      }
    }
  }

  window.addEventListener('message', frameMessageHandler)
  aiContextTimer = setInterval(() => {
    if (activeMode.value === 'iframe' && aiEnabled.value) {
      syncContextToFrame()
    }
  }, 5000)
})

onBeforeUnmount(() => {
  if (frameMessageHandler) {
    window.removeEventListener('message', frameMessageHandler)
    frameMessageHandler = null
  }

  if (aiContextTimer) {
    clearInterval(aiContextTimer)
    aiContextTimer = null
  }
})
</script>

<style scoped>
.ai-panel-shell {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2200;
  width: min(420px, calc(100vw - 32px));
  pointer-events: none;
}

.ai-panel {
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 560px;
  max-height: calc(100vh - 120px);
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(15, 23, 42, 0.98)),
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.25), transparent 55%);
  color: #e2e8f0;
  box-shadow: 0 26px 80px rgba(15, 23, 42, 0.34);
  backdrop-filter: blur(18px);
  overflow: hidden;
}

.ai-panel-header,
.ai-panel-toolbar,
.ai-quick-actions,
.ai-context-card,
.ai-chat-log,
.ai-composer,
.ai-frame-panel {
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

.ai-panel-badge.is-active {
  background: rgba(34, 197, 94, 0.18);
  color: #bbf7d0;
}

.ai-panel-subtitle {
  margin: 0;
  color: #94a3b8;
  font-size: 12px;
}

.ai-panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.ai-mode-button,
.ai-close-button,
.ai-secondary-button,
.ai-send-button,
.ai-chip {
  border: none;
  cursor: pointer;
  transition: transform 0.15s ease, opacity 0.15s ease, background 0.15s ease;
}

.ai-mode-button,
.ai-close-button {
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  color: #e2e8f0;
  font-size: 12px;
}

.ai-mode-button.active {
  background: rgba(34, 197, 94, 0.18);
  color: #dcfce7;
}

.ai-mode-button.disabled {
  opacity: 0.45;
}

.ai-close-button {
  background: rgba(244, 63, 94, 0.16);
}

.ai-panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ai-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  user-select: none;
  cursor: pointer;
}

.ai-toggle input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.ai-toggle-track {
  width: 42px;
  height: 24px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.28);
  position: relative;
  flex-shrink: 0;
}

.ai-toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f8fafc;
  transition: transform 0.18s ease;
}

.ai-toggle input:checked + .ai-toggle-track {
  background: rgba(34, 197, 94, 0.42);
}

.ai-toggle input:checked + .ai-toggle-track .ai-toggle-thumb {
  transform: translateX(18px);
}

.ai-toggle-label {
  font-size: 12px;
  color: #cbd5e1;
}

.ai-secondary-button,
.ai-send-button {
  height: 32px;
  padding: 0 12px;
  border-radius: 10px;
  font-size: 12px;
}

.ai-secondary-button {
  background: rgba(148, 163, 184, 0.14);
  color: #e2e8f0;
}

.ai-send-button {
  background: linear-gradient(135deg, #22c55e, #16a34a);
  color: #f8fafc;
}

.ai-quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ai-chip {
  height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #e2e8f0;
  font-size: 12px;
}

.ai-context-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-context-title {
  font-size: 12px;
  color: #94a3b8;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ai-context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.ai-context-item {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.58);
  border: 1px solid rgba(148, 163, 184, 0.12);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ai-context-item .label {
  font-size: 11px;
  color: #94a3b8;
}

.ai-context-item .value {
  font-size: 12px;
  color: #e2e8f0;
  word-break: break-all;
}

.ai-frame-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 300px;
  padding-bottom: 18px;
}

.ai-frame-wrapper {
  flex: 1;
  min-height: 360px;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(15, 23, 42, 0.5);
}

.ai-frame {
  width: 100%;
  height: 100%;
  min-height: 360px;
  border: 0;
  background: #020617;
}

.ai-chat-log {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
  min-height: 220px;
  max-height: 280px;
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

.ai-send-button:disabled {
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
    min-height: 520px;
  }

  .ai-context-grid {
    grid-template-columns: 1fr;
  }

  .ai-panel-header {
    flex-direction: column;
  }

  .ai-panel-actions {
    justify-content: flex-start;
  }
}
</style>
