// src/stores/chat.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref([])
  const pendingApproval = ref(null)
  
  // Getters
  const messageCount = computed(() => messages.value.length)
  
  const userMessages = computed(() => 
    messages.value.filter(m => m.type === 'user')
  )
  
  const assistantMessages = computed(() =>
    messages.value.filter(m => m.type === 'assistant')
  )
  
  // Actions
  function addMessage(message) {
    messages.value.push({
      id: Date.now() + Math.random(),
      ...message,
      timestamp: message.timestamp || new Date().toISOString()
    })
  }
  
  function addSystemMessage(content) {
    addMessage({
      type: 'system',
      content: content
    })
  }
  
  function setPendingApproval(plan) {
    pendingApproval.value = plan
  }
  
  function clearPendingApproval() {
    pendingApproval.value = null
  }
  
  function clearMessages() {
    messages.value = []
  }
  
  return {
    // State
    messages,
    pendingApproval,
    
    // Getters
    messageCount,
    userMessages,
    assistantMessages,
    
    // Actions
    addMessage,
    addSystemMessage,
    setPendingApproval,
    clearPendingApproval,
    clearMessages
  }
})