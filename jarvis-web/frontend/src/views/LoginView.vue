<template>
  <div class="h-screen w-screen flex items-center justify-center bg-gray-950">
    <div class="w-full max-w-md p-8 bg-gray-900 rounded-lg shadow-2xl">
      <!-- Header -->
      <div class="text-center mb-8">
        <div class="text-6xl mb-4">🤖</div>
        <h1 class="text-3xl font-bold mb-2">JARVIS</h1>
        <p class="text-gray-400">Command Center</p>
      </div>
      
      <!-- Error Message -->
      <div 
        v-if="authStore.error" 
        class="mb-4 p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm"
      >
        {{ authStore.error }}
      </div>
      
      <!-- Login Form -->
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <!-- Username -->
        <div>
          <label class="block text-sm font-medium mb-2">Username</label>
          <input
            v-model="username"
            type="text"
            required
            placeholder="Enter username"
            class="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
          />
        </div>
        
        <!-- Password -->
        <div>
          <label class="block text-sm font-medium mb-2">Password</label>
          <input
            v-model="password"
            type="password"
            required
            placeholder="Enter password"
            class="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
          />
        </div>
        
        <!-- Email (only for register) -->
        <div v-if="isRegisterMode">
          <label class="block text-sm font-medium mb-2">Email (optional)</label>
          <input
            v-model="email"
            type="email"
            placeholder="your@email.com"
            class="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
          />
        </div>
        
        <!-- Submit Button -->
        <button
          type="submit"
          :disabled="authStore.isLoading"
          class="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
        >
          <span v-if="authStore.isLoading">
            {{ isRegisterMode ? 'Creating Account...' : 'Logging In...' }}
          </span>
          <span v-else>
            {{ isRegisterMode ? 'Create Account' : 'Login' }}
          </span>
        </button>
      </form>
      
      <!-- Toggle Register/Login -->
      <div class="mt-6 text-center">
        <button
          @click="toggleMode"
          class="text-sm text-blue-400 hover:text-blue-300"
        >
          {{ isRegisterMode 
            ? 'Already have an account? Login' 
            : "Don't have an account? Register" 
          }}
        </button>
      </div>
      
      <!-- Quick Login (Dev Only) -->
      <div class="mt-8 pt-6 border-t border-gray-800">
        <p class="text-xs text-gray-500 mb-2 text-center">Quick Login (Default Admin)</p>
        <button
          @click="quickLogin"
          class="w-full py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm transition-colors"
        >
          Login as admin
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const email = ref('')
const isRegisterMode = ref(false)

async function handleSubmit() {
  authStore.clearError()
  
  if (isRegisterMode.value) {
    await authStore.register(username.value, password.value, email.value || null)
  } else {
    await authStore.login(username.value, password.value)
  }
}

function toggleMode() {
  isRegisterMode.value = !isRegisterMode.value
  authStore.clearError()
}

async function quickLogin() {
  username.value = 'admin'
  password.value = 'admin123'
  await authStore.login('admin', 'admin123')
}
</script>