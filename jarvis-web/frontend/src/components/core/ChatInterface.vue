<template>
  <div class="h-full flex flex-col bg-gray-900 rounded-lg overflow-hidden">
    <!-- Connection Status Bar -->
    <div 
      v-if="!isConnected"
      class="bg-yellow-900/50 border-b border-yellow-700 px-4 py-2 text-sm text-yellow-200"
    >
      <span v-if="isConnecting">🔄 Connecting to JARVIS...</span>
      <span v-else>⚠️ Not connected - Click to retry</span>
    </div>

    <!-- Messages Area -->
    <div 
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar"
    >
      <!-- Welcome message if no messages -->
      <div v-if="messages.length === 0" class="text-center text-gray-400 py-12">
        <div class="text-4xl mb-4">🤖</div>
        <div class="text-lg">Welcome to JARVIS</div>
        <div class="text-sm mt-2">
          {{ isConnected ? 'Connected - Type a message to get started' : 'Connecting...' }}
        </div>
      </div>

      <!-- Messages -->
      <div 
        v-for="msg in messages" 
        :key="msg.id"
        :class="msg.type === 'user' ? 'text-right' : 'text-left'"
      >
        <div 
          :class="[
            'inline-block max-w-lg p-3 rounded-lg',
            msg.type === 'user' 
              ? 'bg-blue-600 text-white' 
              : msg.type === 'system'
              ? 'bg-purple-900/50 border border-purple-700 text-purple-200 text-sm'
              : 'bg-gray-700 text-white'
          ]"
        >
          {{ msg.content }}
        </div>
        <div class="text-xs text-gray-500 mt-1">
          {{ formatTime(msg.timestamp) }}
        </div>
      </div>
    </div>

    <!-- Input Bar -->
    <div class="bg-gray-800 border-t border-gray-700 p-4">
      <div class="flex items-center gap-3">
        <input
          v-model="inputText"
          @keyup.enter="send"
          :disabled="!isConnected"
          type="text"
          placeholder="Ask JARVIS anything..."
          class="flex-1 bg-gray-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          @click="send"
          :disabled="!isConnected || !inputText.trim()"
          class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed px-6 py-3 rounded-lg font-medium transition-all"
        >
          Send
        </button>
      </div>
      
      <!-- Connection Status -->
      <div class="mt-2 flex items-center gap-2 text-xs">
        <div 
          :class="[
            'w-2 h-2 rounded-full',
            isConnected ? 'bg-green-500' : isConnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
          ]"
        ></div>
        <span class="text-gray-400">
          {{ isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected' }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { useWebSocket } from '@/composables/useWebSocket'

const chatStore = useChatStore()
const authStore = useAuthStore()
const { isConnected, isConnecting, connect, sendMessage } = useWebSocket()

const messages = computed(() => chatStore.messages)
const messagesContainer = ref(null)
const inputText = ref('')

// Connect on mount
onMounted(() => {
  if (authStore.token) {
    connect(authStore.token)
  }
})

// Auto-scroll to bottom on new messages
watch(messages, async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: 'smooth'
    })
  }
})

function send() {
  if (!inputText.value.trim() || !isConnected.value) return
  
  sendMessage(inputText.value)
  inputText.value = ''
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString()
}
</script>