import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useInteractionStore = defineStore('interaction', () => {
  const pendingQuestion = ref(null)
  const interactionHistory = ref([])

  function setPendingQuestion(data) {
    pendingQuestion.value = data
  }

  function clearPendingQuestion() {
    if (pendingQuestion.value) {
      interactionHistory.value.push(pendingQuestion.value)
    }
    pendingQuestion.value = null
  }

  return {
    pendingQuestion,
    interactionHistory,
    setPendingQuestion,
    clearPendingQuestion
  }
})