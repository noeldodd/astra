<template>
  <div class="h-screen bg-gray-950 text-white flex flex-col">
    <!-- Top Bar -->
    <header class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
      <div class="flex items-center gap-4">
        <h1 class="text-2xl font-bold">🤖 JARVIS</h1>
        <div class="flex gap-2">
          <StatusPip status="active" label="Core" icon="⚙️" :mode="'compact'" />
          <StatusPip status="success" label="Search" icon="🔍" :mode="'compact'" />
        </div>
      </div>
      <div class="flex items-center gap-4">
        <span class="text-sm text-gray-400">Command Center</span>
      </div>
    </header>

    <!-- Main Content Grid -->
    <div class="flex-1 flex gap-4 p-4 overflow-hidden">
      
      <!-- Left Sidebar: System Status -->
      <div 
        :class="[
          'transition-all duration-300',
          panelStore.leftMode === 'minimized' ? 'w-16' : 
          panelStore.leftMode === 'compact' ? 'w-64' : 'w-80'
        ]"
      >
        <div class="panel h-full p-4">
          <h3 class="text-sm font-bold mb-2">System</h3>
          <div v-if="panelStore.leftMode !== 'minimized'" class="space-y-2 text-xs">
            <div class="flex items-center gap-2">
              <StatusPip status="active" :mode="'compact'" />
              <span>Active</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Center: Chat Interface (Flex-grow to fill) -->
      <div class="flex-1 min-w-0">
        <ChatInterface />
      </div>

      <!-- Right Sidebar: Planning -->
      <div 
        :class="[
          'transition-all duration-300',
          panelStore.rightMode === 'minimized' ? 'w-16' : 
          panelStore.rightMode === 'compact' ? 'w-64' : 'w-96'
        ]"
      >
        <div class="panel h-full p-4">
          <h3 class="text-sm font-bold mb-2">Planning</h3>
          <div v-if="panelStore.rightMode !== 'minimized'">
            <p class="text-xs text-gray-400">No active plan</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom: Activity Stream -->
    <footer 
      :class="[
        'transition-all duration-300',
        panelStore.bottomMode === 'minimized' ? 'h-12' : 
        panelStore.bottomMode === 'compact' ? 'h-24' : 'h-48'
      ]"
    >
      <div class="panel w-full h-full p-4">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-sm font-bold">Activity</h3>
          <button 
            @click="togglePanel('bottom')"
            class="text-xs text-gray-400 hover:text-white"
          >
            {{ panelStore.bottomMode === 'minimized' ? '▲' : '▼' }}
          </button>
        </div>
        <div v-if="panelStore.bottomMode !== 'minimized'" class="text-xs text-gray-400">
          <div>System ready</div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePanelStore } from '@/stores/panels'
import ChatInterface from '@/components/core/ChatInterface.vue'
import StatusPip from '@/components/shared/StatusPip.vue'

const panelStore = usePanelStore()

function togglePanel(side) {
  panelStore.togglePanel(side)
}
</script>

<style scoped>
.panel {
  @apply bg-gray-900 rounded-lg overflow-hidden transition-all duration-300;
}
</style>