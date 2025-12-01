// src/stores/chat.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isTyping = ref(false)

  function addMessage(message) {
    messages.value.push({
      id: message.id || Date.now(),
      role: message.role || 'user',
      content: message.content,
      timestamp: message.timestamp || new Date().toISOString()
    })
  }

  function addUserMessage(content) {
    addMessage({
      role: 'user',
      content: content
    })
  }

  function addAssistantMessage(content) {
    addMessage({
      role: 'assistant',
      content: content
    })
  }

    function addSystemMessage(content) {
    addMessage({
      role: 'system',
      content: content
    })
  }

  function clearMessages() {
    messages.value = []
  }

  function setTyping(typing) {
    isTyping.value = typing
  }

  const lastMessage = computed(() => {
    return messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  })

  const messageCount = computed(() => messages.value.length)

  return {
    // State
    messages,
    isTyping,

    // Computed
    lastMessage,
    messageCount,

    // Actions
    addMessage,
    addUserMessage,
    addAssistantMessage,
    addSystemMessage,
    clearMessages,
    setTyping
  }
})