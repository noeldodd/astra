<template>
  <div class="flex flex-col h-screen bg-gray-900 text-white">
    <!-- Header -->
    <div class="bg-gray-800 p-4 border-b border-gray-700">
      <h1 class="text-xl font-bold">🤖 JARVIS</h1>
    </div>

    <!-- Messages -->
    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <div 
        v-for="msg in messages" 
        :key="msg.id"
        :class="msg.type === 'user' ? 'text-right' : 'text-left'"
      >
        <div 
          :class="[
            'inline-block max-w-lg p-3 rounded-lg',
            msg.type === 'user' 
              ? 'bg-blue-600' 
              : 'bg-gray-700'
          ]"
        >
          {{ msg.content }}
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="p-4 bg-gray-800 border-t border-gray-700">
      <div class="flex gap-2">
        <input
          v-model="inputText"
          @keyup.enter="sendMessage"
          type="text"
          placeholder="Ask JARVIS anything..."
          class="flex-1 bg-gray-700 text-white rounded-lg px-4 py-2"
        />
        <button 
          @click="sendMessage"
          class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg"
        >
          Send
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useChatStore } from '@/stores/chat'

const inputText = ref('')
const { sendMessage: wsSend } = useWebSocket()
const chatStore = useChatStore()

const messages = computed(() => chatStore.messages)

function sendMessage() {
  if (!inputText.value.trim()) return
  
  wsSend({
    type: 'user_message',
    content: inputText.value
  })
  
  inputText.value = ''
}
</script>