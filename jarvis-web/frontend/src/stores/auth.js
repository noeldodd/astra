// src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref(localStorage.getItem('jarvis_token') || null)
  const user = ref(JSON.parse(localStorage.getItem('jarvis_user') || 'null'))
  const isLoading = ref(false)
  const error = ref(null)
  
  // Getters
  const isAuthenticated = computed(() => !!token.value)
  const authLevel = computed(() => user.value?.auth_level || 0)
  const username = computed(() => user.value?.username || 'Guest')
  
  // Actions
  async function login(username, password) {
    isLoading.value = true
    error.value = null
    
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
      })
      
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Login failed')
      }
      
      const data = await response.json()
      
      // Store token and user
      token.value = data.access_token
      user.value = data.user
      
      // Persist to localStorage
      localStorage.setItem('jarvis_token', data.access_token)
      localStorage.setItem('jarvis_user', JSON.stringify(data.user))
      
      return true
    } catch (err) {
      error.value = err.message
      return false
    } finally {
      isLoading.value = false
    }
  }
  
  async function register(username, password, email = null) {
    isLoading.value = true
    error.value = null
    
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password, email })
      })
      
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Registration failed')
      }
      
      const data = await response.json()
      
      // Store token and user
      token.value = data.access_token
      user.value = data.user
      
      // Persist to localStorage
      localStorage.setItem('jarvis_token', data.access_token)
      localStorage.setItem('jarvis_user', JSON.stringify(data.user))
      
      return true
    } catch (err) {
      error.value = err.message
      return false
    } finally {
      isLoading.value = false
    }
  }
  
  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('jarvis_token')
    localStorage.removeItem('jarvis_user')
  }
  
  async function verifyToken() {
    if (!token.value) return false
    
    try {
      const response = await fetch('/api/auth/verify', {
        headers: {
          'Authorization': `Bearer ${token.value}`
        }
      })
      
      if (!response.ok) {
        logout()
        return false
      }
      
      return true
    } catch (err) {
      logout()
      return false
    }
  }
  
  function clearError() {
    error.value = null
  }
  
  return {
    // State
    token,
    user,
    isLoading,
    error,
    
    // Getters
    isAuthenticated,
    authLevel,
    username,
    
    // Actions
    login,
    register,
    logout,
    verifyToken,
    clearError
  }
})