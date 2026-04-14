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

export function buildAiHostSnapshot({
  route,
  userInfo,
  currentTab,
  searchKeyword,
  viewingNoteId,
  selectedWorkspaceId,
  editingNotebookId,
  editingSpaceId
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
