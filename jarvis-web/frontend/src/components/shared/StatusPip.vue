<template>
  <div 
    class="flex items-center gap-2 cursor-pointer"
    @click="$emit('click')"
  >
    <!-- Pip (always visible) -->
    <div 
      :class="pipClass"
      :style="{ backgroundColor: statusColor }"
      class="transition-all duration-300"
    >
      <span v-if="mode !== 'minimized'" class="text-xs">
        {{ icon }}
      </span>
    </div>

    <!-- Label (compact+) -->
    <span 
      v-if="mode !== 'minimized'" 
      class="text-sm font-medium"
    >
      {{ label }}
    </span>

    <!-- Count badge (compact+) -->
    <span 
      v-if="mode !== 'minimized' && count > 0"
      class="text-xs bg-gray-700 px-2 py-0.5 rounded-full"
    >
      {{ count }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { STATUS_COLORS } from '@/utils/constants'

const props = defineProps({
  status: String,   // 'active', 'idle', 'error', etc.
  label: String,    // 'Search', 'Planning', etc.
  icon: String,     // '🔍', '📊', etc.
  count: Number,    // Active count
  mode: String      // 'minimized', 'compact', 'expanded'
})

const statusColor = computed(() => STATUS_COLORS[props.status] || STATUS_COLORS.idle)

const pipClass = computed(() => {
  const base = 'rounded-full flex items-center justify-center transition-all'
  
  switch (props.mode) {
    case 'minimized':
      return `${base} w-3 h-3` // Just a dot
    case 'compact':
      return `${base} w-6 h-6` // Small circle with icon
    case 'expanded':
      return `${base} w-8 h-8` // Larger with icon
    default:
      return `${base} w-6 h-6`
  }
})
</script>