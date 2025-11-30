// stores/panels.js
import { defineStore } from 'pinia'

export const usePanelStore = defineStore('panels', {
  state: () => ({
    leftMode: 'compact',     // minimized | compact | expanded
    rightMode: 'expanded',   // minimized | compact | expanded
    bottomMode: 'compact',   // minimized | compact | expanded
    
    // Auto-expand on activity
    autoExpand: {
      onPlanStart: true,
      onSearch: true,
      onError: true
    }
  }),
  
  actions: {
    togglePanel(side) {
      const modes = ['minimized', 'compact', 'expanded']
      const current = this[`${side}Mode`]
      const currentIndex = modes.indexOf(current)
      const nextIndex = (currentIndex + 1) % modes.length
      this[`${side}Mode`] = modes[nextIndex]
    },
    
    expandOnActivity(type) {
      if (type === 'planning' && this.autoExpand.onPlanStart) {
        this.rightMode = 'expanded'
      }
      if (type === 'search' && this.autoExpand.onSearch) {
        this.leftMode = 'expanded'
      }
      if (type === 'error' && this.autoExpand.onError) {
        this.bottomMode = 'expanded'
      }
    }
  }
})