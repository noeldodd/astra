<template>
  <div 
    class="question-card"
    :class="[
      `risk-${riskLevel}`,
      { 'has-timeout': hasTimeout }
    ]"
  >
    <!-- Risk indicator -->
    <div class="risk-indicator" v-if="riskLevel !== 'low'">
      <span class="risk-icon">{{ riskIcon }}</span>
      <span class="risk-label">{{ riskLabel }}</span>
    </div>

    <!-- Question text -->
    <div class="question-text">
      {{ question }}
    </div>

    <!-- Disclaimer (for medical/financial/legal) -->
    <div v-if="disclaimer" class="disclaimer">
      <div class="disclaimer-icon">⚠️</div>
      <div class="disclaimer-text">{{ disclaimer }}</div>
    </div>

    <!-- Amount indicator (for financial) -->
    <div v-if="amount" class="amount-indicator">
      <span class="amount-label">Amount:</span>
      <span class="amount-value">${{ formatAmount(amount) }}</span>
    </div>

    <!-- Interaction UI based on question type -->
    <div class="interaction-area">
      <!-- Approval buttons (Yes/No) -->
      <div v-if="questionType === 'approval'" class="approval-buttons">
        <button
          v-for="action in suggestedActions"
          :key="action"
          @click="submitResponse(action)"
          class="action-button"
          :class="getButtonClass(action)"
        >
          {{ action }}
        </button>
      </div>

      <!-- Information input -->
      <div v-else-if="questionType === 'information'" class="information-input">
        <input
          v-if="domain === 'text'"
          v-model="inputValue"
          type="text"
          placeholder="Enter your answer..."
          @keyup.enter="submitInput"
          class="text-input"
        />
        <input
          v-else-if="domain === 'number'"
          v-model.number="inputValue"
          type="number"
          placeholder="Enter number..."
          @keyup.enter="submitInput"
          class="number-input"
        />
        <input
          v-else-if="domain === 'date'"
          v-model="inputValue"
          type="date"
          @change="submitInput"
          class="date-input"
        />
        <textarea
          v-else
          v-model="inputValue"
          placeholder="Enter your response..."
          rows="3"
          class="textarea-input"
        />
        
        <div class="input-actions">
          <button @click="submitInput" class="submit-button">Submit</button>
          <button v-if="!requireExplicit" @click="skipQuestion" class="skip-button">Skip</button>
        </div>
      </div>

      <!-- Multiple choice -->
      <div v-else-if="questionType === 'choice'" class="choice-buttons">
        <button
          v-for="(choice, index) in suggestedActions"
          :key="index"
          @click="submitResponse(choice)"
          class="choice-button"
        >
          {{ choice }}
        </button>
      </div>

      <!-- Open-ended -->
      <div v-else class="open-ended-input">
        <textarea
          v-model="inputValue"
          placeholder="Enter your response..."
          rows="4"
          class="textarea-input"
        />
        <div class="input-actions">
          <button @click="submitInput" class="submit-button">Submit</button>
        </div>
      </div>
    </div>

    <!-- Timeout indicator -->
    <div v-if="hasTimeout && timeoutMs" class="timeout-indicator">
      <div class="timeout-bar" :style="{ width: `${timeoutProgress}%` }"></div>
      <div class="timeout-text">
        {{ timeoutRemaining }}s remaining
        <span v-if="defaultAction"> (will {{ defaultAction }})</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const props = defineProps({
  interactionId: String,
  planId: String,
  question: String,
  questionType: String,      // approval, information, choice, open_ended
  riskLevel: String,          // low, medium, high, critical
  timeoutMs: Number,
  defaultAction: String,
  requireExplicit: Boolean,
  suggestedActions: Array,
  disclaimer: String,
  amount: Number,
  domain: String
})

const { sendInteractionResponse } = useWebSocket()

const inputValue = ref('')
const timeoutProgress = ref(100)
const timeoutRemaining = ref(0)
let timeoutInterval = null

// Computed
const hasTimeout = computed(() => props.timeoutMs && props.timeoutMs > 0)

const riskIcon = computed(() => {
  switch (props.riskLevel) {
    case 'critical': return '🚨'
    case 'high': return '⚠️'
    case 'medium': return '⚡'
    default: return '💬'
  }
})

const riskLabel = computed(() => {
  switch (props.riskLevel) {
    case 'critical': return 'CRITICAL DECISION'
    case 'high': return 'Important Decision'
    case 'medium': return 'Needs Approval'
    default: return 'Question'
  }
})

// Methods
function submitResponse(action) {
  sendInteractionResponse(props.interactionId, {
    action,
    value: action.toLowerCase()
  })
}

function submitInput() {
  if (!inputValue.value && props.requireExplicit) {
    return // Don't allow empty on required
  }

  sendInteractionResponse(props.interactionId, {
    action: 'input',
    value: inputValue.value
  })
}

function skipQuestion() {
  sendInteractionResponse(props.interactionId, {
    action: 'skip',
    value: null
  })
}

function getButtonClass(action) {
  const lower = action.toLowerCase()
  if (lower.includes('yes') || lower.includes('approve') || lower.includes('proceed')) {
    return 'button-approve'
  }
  if (lower.includes('no') || lower.includes('cancel')) {
    return 'button-cancel'
  }
  return 'button-neutral'
}

function formatAmount(amount) {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount)
}

// Timeout handling
onMounted(() => {
  if (hasTimeout.value) {
    const startTime = Date.now()
    const endTime = startTime + props.timeoutMs
    
    timeoutRemaining.value = Math.ceil(props.timeoutMs / 1000)
    
    timeoutInterval = setInterval(() => {
      const now = Date.now()
      const remaining = endTime - now
      
      if (remaining <= 0) {
        clearInterval(timeoutInterval)
        timeoutProgress.value = 0
        timeoutRemaining.value = 0
        // Timeout will be handled by backend
      } else {
        timeoutProgress.value = (remaining / props.timeoutMs) * 100
        timeoutRemaining.value = Math.ceil(remaining / 1000)
      }
    }, 100)
  }
})

onUnmounted(() => {
  if (timeoutInterval) {
    clearInterval(timeoutInterval)
  }
})
</script>

<style scoped>
.question-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 24px;
  margin: 16px 0;
  color: white;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
}

.question-card.risk-high {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.question-card.risk-critical {
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
  border: 3px solid #ff4757;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 8px 16px rgba(255, 71, 87, 0.4); }
  50% { box-shadow: 0 8px 24px rgba(255, 71, 87, 0.8); }
}

.risk-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  font-size: 14px;
}

.risk-icon {
  font-size: 20px;
}

.question-text {
  font-size: 18px;
  font-weight: 500;
  margin-bottom: 20px;
  line-height: 1.5;
}

.disclaimer {
  background: rgba(0, 0, 0, 0.3);
  border-left: 4px solid #ffd93d;
  padding: 12px;
  margin: 16px 0;
  border-radius: 4px;
  display: flex;
  gap: 12px;
}

.disclaimer-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.disclaimer-text {
  font-size: 13px;
  line-height: 1.6;
}

.amount-indicator {
  background: rgba(0, 0, 0, 0.2);
  padding: 12px;
  border-radius: 8px;
  margin: 12px 0;
  font-size: 16px;
}

.amount-value {
  font-weight: 700;
  font-size: 24px;
  margin-left: 8px;
}

.interaction-area {
  margin-top: 20px;
}

.approval-buttons,
.choice-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.action-button,
.choice-button {
  flex: 1;
  min-width: 120px;
  padding: 14px 24px;
  font-size: 16px;
  font-weight: 600;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  text-transform: capitalize;
}

.button-approve {
  background: #2ecc71;
  color: white;
}

.button-approve:hover {
  background: #27ae60;
  transform: scale(1.05);
}

.button-cancel {
  background: #e74c3c;
  color: white;
}

.button-cancel:hover {
  background: #c0392b;
  transform: scale(1.05);
}

.button-neutral {
  background: #95a5a6;
  color: white;
}

.button-neutral:hover {
  background: #7f8c8d;
  transform: scale(1.05);
}

.choice-button {
  background: rgba(255, 255, 255, 0.9);
  color: #333;
}

.choice-button:hover {
  background: white;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.information-input,
.open-ended-input {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.text-input,
.number-input,
.date-input,
.textarea-input {
  padding: 12px;
  font-size: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.95);
  color: #333;
  font-family: inherit;
}

.text-input:focus,
.number-input:focus,
.date-input:focus,
.textarea-input:focus {
  outline: none;
  border-color: #fff;
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.3);
}

.input-actions {
  display: flex;
  gap: 12px;
}

.submit-button {
  flex: 1;
  padding: 14px;
  background: #2ecc71;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.submit-button:hover {
  background: #27ae60;
  transform: scale(1.02);
}

.skip-button {
  padding: 14px 24px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.skip-button:hover {
  background: rgba(255, 255, 255, 0.3);
}

.timeout-indicator {
  margin-top: 16px;
  position: relative;
}

.timeout-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 2px;
  transition: width 0.1s linear;
}

.timeout-text {
  margin-top: 8px;
  font-size: 13px;
  opacity: 0.9;
  text-align: center;
}
</style>