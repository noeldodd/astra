// src/stores/websocket.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from './auth'
import { useChatStore } from './chat'
import { useInteractionStore } from './interaction'
import { usePlanningStore } from './planning'

export const useWebSocketStore = defineStore('websocket', () => {
  const ws = ref(null)
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = ref(1000) // Start with 1 second

  // WebSocket URL (uses proxy in dev, direct in prod)
  const wsUrl = computed(() => {
    // In development with Vite proxy
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/ws`
  })

  function connect(token) {
    if (!token) {
      console.error('[WS] No token provided')
      return
    }

    if (ws.value && (ws.value.readyState === WebSocket.CONNECTING || ws.value.readyState === WebSocket.OPEN)) {
      console.log('[WS] Already connected or connecting')
      return
    }

    console.log('[WS] Connecting to:', wsUrl.value)

    try {
      ws.value = new WebSocket(wsUrl.value)

      ws.value.onopen = () => {
        console.log('[WS] Connected!')
        isConnected.value = true
        reconnectAttempts.value = 0
        reconnectDelay.value = 1000

        // Send authentication
        sendMessage({
          type: 'auth',
          token: token
        })
      }

      ws.value.onmessage = (event) => {
        handleMessage(event)
      }

      ws.value.onerror = (error) => {
        console.error('[WS] Error:', error)
        isConnected.value = false
      }

      ws.value.onclose = () => {
        console.log('[WS] Disconnected')
        isConnected.value = false
        
        // Attempt reconnect
        if (reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++
          console.log(`[WS] Reconnecting in ${reconnectDelay.value}ms (attempt ${reconnectAttempts.value}/${maxReconnectAttempts})`)
          
          setTimeout(() => {
            const authStore = useAuthStore()
            if (authStore.token) {
              connect(authStore.token)
            }
          }, reconnectDelay.value)
          
          // Exponential backoff
          reconnectDelay.value = Math.min(reconnectDelay.value * 2, 30000)
        } else {
          console.error('[WS] Max reconnection attempts reached')
        }
      }
    } catch (error) {
      console.error('[WS] Connection failed:', error)
      isConnected.value = false
    }
  }

  function disconnect() {
    if (ws.value) {
      console.log('[WS] Disconnecting...')
      reconnectAttempts.value = maxReconnectAttempts // Prevent auto-reconnect
      ws.value.close()
      ws.value = null
      isConnected.value = false
    }
  }

  function sendMessage(message) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      console.error('[WS] Cannot send message - not connected')
      return false
    }

    try {
      const json = JSON.stringify(message)
      console.log('[WS] Sending:', message.type, message)
      ws.value.send(json)
      return true
    } catch (error) {
      console.error('[WS] Failed to send message:', error)
      return false
    }
  }

  function handleMessage(event) {
    try {
      const message = JSON.parse(event.data)
      console.log('[WS] Message:', message.type, message)

      // Route to appropriate store based on message type
      
      // Connection established
      if (message.type === 'connection_established') {
        console.log('[WS] Connection confirmed:', message.user)
        return
      }

      // Chat messages
      if (message.type === 'assistant_message') {
        const chatStore = useChatStore()
        chatStore.addMessage({
          id: Date.now(),
          role: 'assistant',
          content: message.content,
          timestamp: message.timestamp || new Date().toISOString()
        })
        return
      }

      // Planning events
      if (message.type && message.type.startsWith('planning.')) {
        const planningStore = usePlanningStore()
        
        // Interaction needed
        if (message.type === 'planning.needs_input') {
          const interactionStore = useInteractionStore()
          interactionStore.setPendingQuestion(message.data)
          return
        }

        // Other planning events
        planningStore.handleEvent(message)
        return
      }

      // System events
      if (message.type && message.type.startsWith('system.')) {
        console.log('[WS] System event:', message)
        return
      }

      // Log events
      if (message.type && message.type.startsWith('log.')) {
        console.log('[WS] Log event:', message.data)
        return
      }

      // Error messages
      if (message.type === 'error') {
        console.error('[WS] Server error:', message.error)
        return
      }

      // Unknown message type
      console.warn('[WS] Unknown message type:', message.type, message)

    } catch (error) {
      console.error('[WS] Error handling message:', error)
    }
  }

  return {
    // State
    ws,
    isConnected,
    reconnectAttempts,
    
    // Computed
    wsUrl,
    
    // Actions
    connect,
    disconnect,
    sendMessage
  }
})