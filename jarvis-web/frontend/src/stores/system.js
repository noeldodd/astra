// src/stores/system.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSystemStore = defineStore('system', () => {
  // State
  const connectionStatus = ref('disconnected') // disconnected | connecting | connected
  const systemState = ref('idle') // idle | processing | error
  const queueSize = ref(0)
  const activePlans = ref(0)
  const terminalCount = ref(0)
  
  // Search tracking
  const activeSearches = ref([])
  const searchStats = ref({
    total: 0,
    cacheHits: 0,
    avgDuration: 0
  })
  
  // Intent tracking
  const lastIntent = ref(null)
  const intentStats = ref({
    total: 0,
    fastPath: 0,
    llmPath: 0
  })
  
  // Memory tracking
  const memoryOperations = ref([])
  
  // Logs
  const logs = ref([])
  const maxLogs = 100
  
  // Getters
  const isConnected = computed(() => connectionStatus.value === 'connected')
  const isProcessing = computed(() => systemState.value === 'processing')
  const hasErrors = computed(() => logs.value.some(l => l.level === 'ERROR'))
  
  const recentLogs = computed(() => logs.value.slice(0, 20))
  const errorLogs = computed(() => logs.value.filter(l => l.level === 'ERROR'))
  
  // Actions
  function setConnectionStatus(status) {
    connectionStatus.value = status
  }
  
  function handleSystemEvent(eventType, data) {
    console.log('[System]', eventType, data)
    
    switch (eventType) {
      case 'system.status':
        handleSystemStatus(data)
        break
      
      case 'system.state_change':
        handleStateChange(data)
        break
      
      case 'system.queue_update':
        handleQueueUpdate(data)
        break
    }
  }
  
  function handleSystemStatus(data) {
    systemState.value = data.state || 'idle'
    queueSize.value = data.queue_size || 0
    activePlans.value = data.active_plans || 0
    terminalCount.value = data.terminal_count || 0
  }
  
  function handleStateChange(data) {
    systemState.value = data.new_state || 'idle'
  }
  
  function handleQueueUpdate(data) {
    queueSize.value = data.queue_size || 0
  }
  
  function handleSearchEvent(eventType, data) {
    console.log('[Search]', eventType, data)
    
    switch (eventType) {
      case 'search.query':
        handleSearchQuery(data)
        break
      
      case 'search.results':
        handleSearchResults(data)
        break
      
      case 'search.cache_hit':
        handleSearchCacheHit(data)
        break
      
      case 'search.failed':
        handleSearchFailed(data)
        break
    }
  }
  
  function handleSearchQuery(data) {
    activeSearches.value.push({
      query: data.query,
      status: 'searching',
      started_at: new Date().toISOString()
    })
    
    searchStats.value.total++
  }
  
  function handleSearchResults(data) {
    const search = activeSearches.value.find(s => s.query === data.query)
    if (search) {
      search.status = 'completed'
      search.results_count = data.results_count
      search.duration_ms = data.duration_ms
      search.completed_at = new Date().toISOString()
    }
    
    // Update avg duration
    if (data.duration_ms) {
      const total = searchStats.value.total
      const current = searchStats.value.avgDuration
      searchStats.value.avgDuration = ((current * (total - 1)) + data.duration_ms) / total
    }
    
    // Clean up old searches
    if (activeSearches.value.length > 10) {
      activeSearches.value = activeSearches.value.slice(-10)
    }
  }
  
  function handleSearchCacheHit(data) {
    searchStats.value.cacheHits++
    
    const search = activeSearches.value.find(s => s.query === data.query)
    if (search) {
      search.status = 'cached'
      search.cache_hit = true
    }
  }
  
  function handleSearchFailed(data) {
    const search = activeSearches.value.find(s => s.query === data.query)
    if (search) {
      search.status = 'failed'
      search.error = data.error
    }
  }
  
  function handleIntentEvent(eventType, data) {
    console.log('[Intent]', eventType, data)
    
    switch (eventType) {
      case 'intent.classifying':
        // Intent classification started
        break
      
      case 'intent.classified':
        handleIntentClassified(data)
        break
      
      case 'intent.routing':
        // Intent being routed
        break
    }
  }
  
  function handleIntentClassified(data) {
    lastIntent.value = {
      input: data.input,
      intent: data.intent,
      confidence: data.confidence,
      fast_path_used: data.fast_path_used,
      timestamp: new Date().toISOString()
    }
    
    intentStats.value.total++
    if (data.fast_path_used) {
      intentStats.value.fastPath++
    } else {
      intentStats.value.llmPath++
    }
  }
  
  function handleMemoryEvent(eventType, data) {
    console.log('[Memory]', eventType, data)
    
    memoryOperations.value.unshift({
      type: eventType,
      data: data,
      timestamp: new Date().toISOString()
    })
    
    // Keep only last 20
    if (memoryOperations.value.length > 20) {
      memoryOperations.value = memoryOperations.value.slice(0, 20)
    }
  }
  
  function addLog(log) {
    logs.value.unshift({
      ...log,
      id: Date.now() + Math.random(),
      timestamp: log.timestamp || new Date().toISOString()
    })
    
    // Keep only max logs
    if (logs.value.length > maxLogs) {
      logs.value = logs.value.slice(0, maxLogs)
    }
  }
  
  function clearLogs() {
    logs.value = []
  }
  
  function clearSearches() {
    activeSearches.value = []
  }
  
  return {
    // State
    connectionStatus,
    systemState,
    queueSize,
    activePlans,
    terminalCount,
    activeSearches,
    searchStats,
    lastIntent,
    intentStats,
    memoryOperations,
    logs,
    
    // Getters
    isConnected,
    isProcessing,
    hasErrors,
    recentLogs,
    errorLogs,
    
    // Actions
    setConnectionStatus,
    handleSystemEvent,
    handleSearchEvent,
    handleIntentEvent,
    handleMemoryEvent,
    addLog,
    clearLogs,
    clearSearches
  }
})