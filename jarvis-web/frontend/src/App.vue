<template>
  <div class="h-screen w-screen overflow-hidden bg-gray-950">
    <CommandCenter v-if="authStore.isAuthenticated" />
    <LoginView v-else />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import CommandCenter from './layouts/CommandCenter.vue'
import LoginView from './views/LoginView.vue'

const authStore = useAuthStore()

// Verify token on app mount
onMounted(async () => {
  if (authStore.token) {
    await authStore.verifyToken()
  }
})
</script>