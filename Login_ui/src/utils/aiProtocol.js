import { AI_PROTOCOL_VERSION } from '@/config/ai'

function toPlainQuery(query) {
  const result = {}

  if (!query || typeof query !== 'object') {
    return result
  }

  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return
    }

    if (Array.isArray(value)) {
      result[key] = value.map(item => String(item))
      return
    }

    result[key] = String(value)
  })

  return result
}

function toPreviewText(value, limit = 320) {
  if (!value) {
    return ''
  }

  const normalized = String(value)
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  if (!normalized) {
    return ''
  }

  if (normalized.length <= limit) {
    return normalized
  }

  return `${normalized.slice(0, limit).trim()}…`
}

export function buildAiHostSnapshot({
  route,
  userInfo,
  currentTab,
  searchKeyword,
  viewingNoteId,
  selectedWorkspaceId,
  editingNotebookId,
  editingSpaceId,
  resource,
  authToken
}) {
  return {
    version: AI_PROTOCOL_VERSION,
    timestamp: new Date().toISOString(),
    route: {
      name: route?.name || null,
      path: route?.path || null,
      query: toPlainQuery(route?.query)
    },
    page: {
      tab: currentTab || null,
      searchKeyword: searchKeyword || null,
      viewingNoteId: viewingNoteId || null,
      selectedWorkspaceId: selectedWorkspaceId || null,
      editingNotebookId: editingNotebookId || null,
      editingSpaceId: editingSpaceId || null
    },
    resource: resource
      ? {
          kind: resource.kind || null,
          id: resource.id || null,
          title: resource.title || null,
          fileType: resource.fileType || null,
          status: resource.status || null,
          noteId: resource.noteId || null,
          questionId: resource.questionId || null,
          notebookId: resource.notebookId || null,
          spaceId: resource.spaceId || null,
          contentPreview: toPreviewText(resource.contentPreview || resource.content || ''),
          contentLength: resource.contentLength || 0,
          commentCount: resource.commentCount || 0,
          answerCount: resource.answerCount || 0,
          isDirty: Boolean(resource.isDirty),
          updatedAt: resource.updatedAt || null,
          selectedText: toPreviewText(resource.selectedText || '', 160),
          tags: Array.isArray(resource.tags) ? resource.tags.slice(0, 10) : []
        }
      : null,
    session: {
      authToken: authToken || null
    },
    user: {
      id: userInfo?.id || null,
      username: userInfo?.username || null,
      role: userInfo?.role || null
    },
    permissions: {
      canAccessWriteActions: userInfo?.role === 'Admin' || userInfo?.role === 'User'
    }
  }
}

export function isAiHostMessage(message) {
  return Boolean(message && message.version === AI_PROTOCOL_VERSION && typeof message.type === 'string')
}

export function isAllowedRouteTarget(target) {
  if (!target || typeof target !== 'object') {
    return false
  }

  const path = typeof target.path === 'string' ? target.path : ''
  const routeName = typeof target.routeName === 'string' ? target.routeName : ''

  if (!path && !routeName) {
    return false
  }

  return !/^javascript:/i.test(path) && !/^https?:\/\//i.test(path)
}

export function buildRouteTarget(target) {
  if (!isAllowedRouteTarget(target)) {
    return null
  }

  return {
    routeName: target.routeName || null,
    path: target.path || null,
    params: target.params && typeof target.params === 'object' ? target.params : {},
    query: target.query && typeof target.query === 'object' ? target.query : {}
  }
}
