// src/composables/useWebSocket.js
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { WS_CONFIG, MESSAGE_TYPES } from '@/utils/constants'
import { useChatStore } from '@/stores/chat'
import { usePlanningStore } from '@/stores/planning'
import { useSystemStore } from '@/stores/system'

const ws = ref(null)
const isConnected = ref(false)
const isConnecting = ref(false)
const reconnectAttempts = ref(0)
const reconnectTimer = ref(null)

export function useWebSocket() {
  const chatStore = useChatStore()
  const planningStore = usePlanningStore()
  const systemStore = useSystemStore()
  
  /**
   * Connect to WebSocket server
   */
  const connect = (token) => {
    if (isConnecting.value || isConnected.value) {
      console.log('[WS] Already connected or connecting')
      return
    }
    
    isConnecting.value = true
    
    // Determine WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws`
    
    console.log('[WS] Connecting to:', wsUrl)
    
    try {
      ws.value = new WebSocket(wsUrl)
      
      ws.value.onopen = () => {
        console.log('[WS] Connected!')
        isConnected.value = true
        isConnecting.value = false
        reconnectAttempts.value = 0
        
        // Send authentication
        send({
          type: MESSAGE_TYPES.AUTH,
          token: token
        })
      }
      
      ws.value.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleMessage(message)
        } catch (error) {
          console.error('[WS] Failed to parse message:', error)
        }
      }
      
      ws.value.onerror = (error) => {
        console.error('[WS] Error:', error)
        systemStore.addLog({
          level: 'ERROR',
          category: 'WEBSOCKET',
          message: 'WebSocket connection error'
        })
      }
      
      ws.value.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason)
        isConnected.value = false
        isConnecting.value = false
        
        // Attempt reconnect
        if (reconnectAttempts.value < WS_CONFIG.MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts.value++
          console.log(`[WS] Reconnecting... (attempt ${reconnectAttempts.value})`)
          
          reconnectTimer.value = setTimeout(() => {
            connect(token)
          }, WS_CONFIG.RECONNECT_INTERVAL)
        } else {
          console.error('[WS] Max reconnect attempts reached')
          systemStore.addLog({
            level: 'ERROR',
            category: 'WEBSOCKET',
            message: 'Failed to reconnect to server'
          })
        }
      }
    } catch (error) {
      console.error('[WS] Connection failed:', error)
      isConnecting.value = false
    }
  }
  
  /**
   * Disconnect from WebSocket
   */
  const disconnect = () => {
    if (reconnectTimer.value) {
      clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
    
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    
    isConnected.value = false
    isConnecting.value = false
    reconnectAttempts.value = 0
  }
  
  /**
   * Send message to server
   */
  const send = (message) => {
    if (!isConnected.value || !ws.value) {
      console.error('[WS] Cannot send - not connected')
      return false
    }
    
    try {
      ws.value.send(JSON.stringify(message))
      return true
    } catch (error) {
      console.error('[WS] Failed to send message:', error)
      return false
    }
  }
  
  /**
   * Handle incoming messages
   */
  const handleMessage = (message) => {
    console.log('[WS] Message:', message.type || message.channel)
    
    // Out-of-band events
    if (message.channel === 'oob') {
      handleOOBEvent(message)
      return
    }
    
    // In-band messages
    switch (message.type) {
      case 'connection_established':
        chatStore.addSystemMessage('Connected to JARVIS')
        systemStore.setConnectionStatus('connected')
        break
      
      case MESSAGE_TYPES.ASSISTANT_MESSAGE:
        chatStore.addMessage({
          type: 'assistant',
          content: message.content,
          timestamp: message.timestamp
        })
        break
      
      case 'plan_approval_received':
        chatStore.addSystemMessage(`Plan ${message.approved ? 'approved' : 'rejected'}`)
        break
      
      case 'error':
        systemStore.addLog({
          level: 'ERROR',
          category: 'SERVER',
          message: message.error
        })
        break
      
      default:
        console.warn('[WS] Unknown message type:', message.type)
    }
  }
  
  /**
   * Handle out-of-band events
   */
  const handleOOBEvent = (event) => {
    const eventType = event.type
    const data = event.data
    
    // Planning events
    if (eventType.startsWith('planning.')) {
      planningStore.handlePlanningEvent(eventType, data)
      return
    }
    
    // Search events
    if (eventType.startsWith('search.')) {
      systemStore.handleSearchEvent(eventType, data)
      return
    }
    
    // Intent events
    if (eventType.startsWith('intent.')) {
      systemStore.handleIntentEvent(eventType, data)
      return
    }
    
    // Memory events
    if (eventType.startsWith('memory.')) {
      systemStore.handleMemoryEvent(eventType, data)
      return
    }
    
    // System events
    if (eventType.startsWith('system.')) {
      systemStore.handleSystemEvent(eventType, data)
      return
    }
    
    // Log events
    if (eventType.startsWith('log.')) {
      systemStore.addLog({
        level: data.level,
        category: data.category,
        message: data.message,
        timestamp: event.timestamp
      })
      return
    }
  }
  
  /**
   * Send chat message
   */
  const sendMessage = (content) => {
    // Add to local chat immediately
    chatStore.addMessage({
      type: 'user',
      content: content,
      timestamp: new Date().toISOString()
    })
    
    // Send to server
    send({
      type: MESSAGE_TYPES.USER_MESSAGE,
      content: content
    })
  }
  
  /**
   * Send plan approval
   */
  const sendPlanApproval = (planId, approved) => {
    send({
      type: MESSAGE_TYPES.PLAN_APPROVAL,
      plan_id: planId,
      approved: approved
    })
  }
  
  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })
  
  return {
    // State
    isConnected: computed(() => isConnected.value),
    isConnecting: computed(() => isConnecting.value),
    
    // Methods
    connect,
    disconnect,
    send,
    sendMessage,
    sendPlanApproval
  }
}