// src/stores/planning.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePlanningStore = defineStore('planning', () => {
  // State
  const activePlan = ref(null)
  const planHistory = ref([])
  const pendingApproval = ref(null)
  
  // Getters
  const hasPendingApproval = computed(() => !!pendingApproval.value)
  const hasActivePlan = computed(() => !!activePlan.value)
  
  const activePlanProgress = computed(() => {
    if (!activePlan.value) return 0
    const steps = activePlan.value.steps || []
    if (steps.length === 0) return 0
    
    const completed = steps.filter(s => s.status === 'completed').length
    return Math.round((completed / steps.length) * 100)
  })
  
  // Actions
  function handlePlanningEvent(eventType, data) {
    console.log('[Planning]', eventType, data)
    
    switch (eventType) {
      case 'planning.plan_created':
        handlePlanCreated(data)
        break
      
      case 'planning.plan_approved':
        handlePlanApproved(data)
        break
      
      case 'planning.plan_rejected':
        handlePlanRejected(data)
        break
      
      case 'planning.plan_started':
        handlePlanStarted(data)
        break
      
      case 'planning.step_started':
        handleStepStarted(data)
        break
      
      case 'planning.step_progress':
        handleStepProgress(data)
        break
      
      case 'planning.step_completed':
        handleStepCompleted(data)
        break
      
      case 'planning.step_failed':
        handleStepFailed(data)
        break
      
      case 'planning.plan_completed':
        handlePlanCompleted(data)
        break
      
      case 'planning.plan_failed':
        handlePlanFailed(data)
        break
    }
  }
  
  function handlePlanCreated(data) {
    pendingApproval.value = {
      id: data.plan_id,
      description: data.description,
      steps: data.steps || [],
      created_at: new Date().toISOString()
    }
  }
  
  function handlePlanApproved(data) {
    pendingApproval.value = null
  }
  
  function handlePlanRejected(data) {
    pendingApproval.value = null
  }
  
  function handlePlanStarted(data) {
    activePlan.value = {
      id: data.plan_id,
      description: data.description,
      steps: data.steps || [],
      status: 'in_progress',
      started_at: new Date().toISOString()
    }
  }
  
  function handleStepStarted(data) {
    if (!activePlan.value) return
    
    const step = activePlan.value.steps.find(s => s.id === data.step_id)
    if (step) {
      step.status = 'in_progress'
      step.description = data.description
      step.started_at = new Date().toISOString()
    }
  }
  
  function handleStepProgress(data) {
    if (!activePlan.value) return
    
    const step = activePlan.value.steps.find(s => s.id === data.step_id)
    if (step) {
      step.progress = data.progress
      step.currentAction = data.current_action
    }
  }
  
  function handleStepCompleted(data) {
    if (!activePlan.value) return
    
    const step = activePlan.value.steps.find(s => s.id === data.step_id)
    if (step) {
      step.status = 'completed'
      step.result = data.result
      step.completed_at = new Date().toISOString()
      step.duration_ms = data.duration_ms
    }
  }
  
  function handleStepFailed(data) {
    if (!activePlan.value) return
    
    const step = activePlan.value.steps.find(s => s.id === data.step_id)
    if (step) {
      step.status = 'failed'
      step.error = data.error
      step.failed_at = new Date().toISOString()
    }
  }
  
  function handlePlanCompleted(data) {
    if (!activePlan.value) return
    
    activePlan.value.status = 'completed'
    activePlan.value.completed_at = new Date().toISOString()
    
    // Move to history
    planHistory.value.unshift({ ...activePlan.value })
    
    // Keep only last 10
    if (planHistory.value.length > 10) {
      planHistory.value = planHistory.value.slice(0, 10)
    }
    
    // Clear active after a delay
    setTimeout(() => {
      activePlan.value = null
    }, 5000)
  }
  
  function handlePlanFailed(data) {
    if (!activePlan.value) return
    
    activePlan.value.status = 'failed'
    activePlan.value.error = data.error
    activePlan.value.failed_at = new Date().toISOString()
    
    // Move to history
    planHistory.value.unshift({ ...activePlan.value })
    
    // Clear active
    setTimeout(() => {
      activePlan.value = null
    }, 5000)
  }
  
  function clearActivePlan() {
    activePlan.value = null
  }
  
  function clearPendingApproval() {
    pendingApproval.value = null
  }
  
  return {
    // State
    activePlan,
    planHistory,
    pendingApproval,
    
    // Getters
    hasPendingApproval,
    hasActivePlan,
    activePlanProgress,
    
    // Actions
    handlePlanningEvent,
    clearActivePlan,
    clearPendingApproval
  }
})