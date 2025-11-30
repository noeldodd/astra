<template>
  <div class="bg-gray-800 rounded-lg p-6">
    <h2 class="text-xl font-bold mb-4">📊 Active Plan</h2>
    
    <div v-if="activePlan">
      <h3 class="text-lg mb-4">{{ activePlan.description }}</h3>
      
      <!-- Progress bar -->
      <div class="mb-6">
        <div class="flex justify-between text-sm mb-1">
          <span>Progress</span>
          <span>{{ progressPercent }}%</span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2">
          <div 
            class="bg-blue-600 h-2 rounded-full transition-all"
            :style="{ width: progressPercent + '%' }"
          ></div>
        </div>
      </div>
      
      <!-- Steps -->
      <div class="space-y-3">
        <div 
          v-for="step in activePlan.steps" 
          :key="step.id"
          class="flex items-start gap-3 p-3 bg-gray-700 rounded-lg"
        >
          <!-- Status icon -->
          <div class="mt-1">
            <span v-if="step.status === 'completed'">✅</span>
            <span v-else-if="step.status === 'in_progress'">⏳</span>
            <span v-else>⏸</span>
          </div>
          
          <!-- Description -->
          <div class="flex-1">
            <div class="font-medium">{{ step.description }}</div>
            
            <!-- Live progress for active step -->
            <div v-if="step.status === 'in_progress' && step.progress">
              <div class="mt-2 text-sm text-gray-400">
                {{ step.currentAction }}
              </div>
              <div class="w-full bg-gray-600 rounded-full h-1 mt-1">
                <div 
                  class="bg-green-500 h-1 rounded-full transition-all"
                  :style="{ width: (step.progress * 100) + '%' }"
                ></div>
              </div>
            </div>
            
            <!-- Result for completed step -->
            <div v-if="step.status === 'completed' && step.result" class="mt-2 text-sm text-gray-400">
              {{ step.result.substring(0, 100) }}...
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div v-else class="text-gray-400 text-center py-8">
      No active plan
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePlanningStore } from '@/stores/planning'

const planningStore = usePlanningStore()

const activePlan = computed(() => planningStore.activePlan)

const progressPercent = computed(() => {
  if (!activePlan.value) return 0
  const total = activePlan.value.steps.length
  const completed = activePlan.value.steps.filter(s => s.status === 'completed').length
  return Math.round((completed / total) * 100)
})
</script>