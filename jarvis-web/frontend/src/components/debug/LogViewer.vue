<template>
  <div class="log-viewer">
    <!-- Header -->
    <div class="log-header">
      <h3 class="text-lg font-semibold text-white">System Logs</h3>
      <div class="flex gap-2">
        <!-- Filter buttons -->
        <button
          v-for="level in levels"
          :key="level"
          @click="toggleLevel(level)"
          :class="[
            'px-3 py-1 rounded text-xs font-medium transition-all',
            visibleLevels.includes(level)
              ? getLevelButtonClass(level, true)
              : 'bg-gray-700 text-gray-400'
          ]"
        >
          {{ level }}
        </button>
        
        <button
          @click="clearLogs"
          class="px-3 py-1 rounded text-xs font-medium bg-red-900/50 text-red-300 hover:bg-red-900 transition-all ml-2"
        >
          Clear
        </button>
      </div>
    </div>

    <!-- Logs -->
    <div ref="logsContainer" class="log-container">
      <div
        v-for="log in filteredLogs"
        :key="log.id"
        :class="['log-entry', getLevelClass(log.level)]"
      >
        <div class="log-time">{{ formatTime(log.timestamp) }}</div>
        <div :class="['log-level', getLevelBadgeClass(log.level)]">
          {{ log.level }}
        </div>
        <div class="log-category">{{ log.category }}</div>
        <div class="log-message">{{ log.message }}</div>
      </div>
      
      <div v-if="filteredLogs.length === 0" class="text-center text-gray-500 py-8">
        No logs to display
      </div>
    </div>

    <!-- Auto-scroll toggle -->
    <div class="log-footer">
      <label class="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
        <input
          v-model="autoScroll"
          type="checkbox"
          class="rounded"
        />
        <span>Auto-scroll</span>
      </label>
      <div class="text-xs text-gray-500">
        {{ filteredLogs.length }} / {{ systemStore.logs.length }} logs
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useSystemStore } from '@/stores/system'

const systemStore = useSystemStore()

const logsContainer = ref(null)
const autoScroll = ref(true)
const visibleLevels = ref(['INFO', 'WARNING', 'ERROR', 'DEBUG'])
const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']

const filteredLogs = computed(() => {
  return systemStore.logs.filter(log => visibleLevels.value.includes(log.level))
})

function toggleLevel(level) {
  const index = visibleLevels.value.indexOf(level)
  if (index > -1) {
    visibleLevels.value.splice(index, 1)
  } else {
    visibleLevels.value.push(level)
  }
}

function clearLogs() {
  systemStore.clearLogs()
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString()
}

function getLevelClass(level) {
  switch (level) {
    case 'ERROR': return 'border-l-red-500 bg-red-950/20'
    case 'WARNING': return 'border-l-yellow-500 bg-yellow-950/20'
    case 'INFO': return 'border-l-blue-500 bg-blue-950/20'
    case 'DEBUG': return 'border-l-gray-500 bg-gray-950/20'
    default: return 'border-l-gray-600'
  }
}

function getLevelBadgeClass(level) {
  switch (level) {
    case 'ERROR': return 'bg-red-900 text-red-200'
    case 'WARNING': return 'bg-yellow-900 text-yellow-200'
    case 'INFO': return 'bg-blue-900 text-blue-200'
    case 'DEBUG': return 'bg-gray-700 text-gray-300'
    default: return 'bg-gray-800 text-gray-300'
  }
}

function getLevelButtonClass(level, active) {
  if (!active) return ''
  
  switch (level) {
    case 'ERROR': return 'bg-red-900 text-red-200'
    case 'WARNING': return 'bg-yellow-900 text-yellow-200'
    case 'INFO': return 'bg-blue-900 text-blue-200'
    case 'DEBUG': return 'bg-gray-800 text-gray-200'
    default: return 'bg-gray-700'
  }
}

// Auto-scroll
watch(filteredLogs, async () => {
  if (autoScroll.value) {
    await nextTick()
    if (logsContainer.value) {
      logsContainer.value.scrollTop = logsContainer.value.scrollHeight
    }
  }
})
</script>

<style scoped>
.log-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1f2937;
  border-radius: 8px;
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #374151;
  background: #111827;
}

.log-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.log-container::-webkit-scrollbar {
  width: 8px;
}

.log-container::-webkit-scrollbar-track {
  background: #1f2937;
}

.log-container::-webkit-scrollbar-thumb {
  background: #4b5563;
  border-radius: 4px;
}

.log-entry {
  display: grid;
  grid-template-columns: 80px 80px 120px 1fr;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 4px;
  border-left: 3px solid;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-time {
  color: #9ca3af;
  font-size: 11px;
}

.log-level {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 10px;
  text-align: center;
}

.log-category {
  color: #d1d5db;
  font-weight: 500;
}

.log-message {
  color: #e5e7eb;
  word-break: break-word;
}

.log-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid #374151;
  background: #111827;
}
</style>