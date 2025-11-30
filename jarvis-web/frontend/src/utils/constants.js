// src/utils/constants.js

/**
 * Status Colors
 * Consistent color theme across all panels and states
 */
export const STATUS_COLORS = {
  // System States
  idle: '#6B7280',
  active: '#3B82F6',
  success: '#10B981',
  error: '#EF4444',
  warning: '#F59E0B',
  
  // Planning States
  planning: '#8B5CF6',
  executing: '#3B82F6',
  waiting: '#F59E0B',
  
  // Search States
  searching: '#06B6D4',
  cached: '#10B981',
  
  // Intent States
  classifying: '#8B5CF6',
  routing: '#3B82F6',
}

/**
 * Panel Modes
 */
export const PANEL_MODES = {
  MINIMIZED: 'minimized',
  COMPACT: 'compact',
  EXPANDED: 'expanded'
}

/**
 * Auth Levels
 */
export const AUTH_LEVELS = {
  GUEST: 0,
  USER: 1,
  POWER_USER: 2,
  DEVELOPER: 3,
  ADMIN: 4
}

/**
 * Auth Level Names
 */
export const AUTH_LEVEL_NAMES = {
  0: 'Guest',
  1: 'User',
  2: 'Power User',
  3: 'Developer',
  4: 'Admin'
}

/**
 * WebSocket Configuration
 */
export const WS_CONFIG = {
  // Auto-reconnect settings
  RECONNECT_INTERVAL: 3000,
  MAX_RECONNECT_ATTEMPTS: 10,
  
  // Heartbeat
  HEARTBEAT_INTERVAL: 30000,
  
  // Timeouts
  AUTH_TIMEOUT: 10000,
  MESSAGE_TIMEOUT: 30000
}

/**
 * Event Types (from backend)
 */
export const EVENT_TYPES = {
  // Planning
  PLANNING_CREATED: 'planning.plan_created',
  PLANNING_APPROVED: 'planning.plan_approved',
  PLANNING_REJECTED: 'planning.plan_rejected',
  PLANNING_STARTED: 'planning.plan_started',
  PLANNING_STEP_STARTED: 'planning.step_started',
  PLANNING_STEP_PROGRESS: 'planning.step_progress',
  PLANNING_STEP_COMPLETED: 'planning.step_completed',
  PLANNING_STEP_FAILED: 'planning.step_failed',
  PLANNING_COMPLETED: 'planning.plan_completed',
  PLANNING_FAILED: 'planning.plan_failed',
  
  // Search
  SEARCH_QUERY: 'search.query',
  SEARCH_RESULTS: 'search.results',
  SEARCH_CACHE_HIT: 'search.cache_hit',
  SEARCH_FAILED: 'search.failed',
  
  // Intent
  INTENT_CLASSIFYING: 'intent.classifying',
  INTENT_CLASSIFIED: 'intent.classified',
  INTENT_ROUTING: 'intent.routing',
  
  // Memory
  MEMORY_CREATE: 'memory.create',
  MEMORY_READ: 'memory.read',
  MEMORY_UPDATE: 'memory.update',
  MEMORY_DELETE: 'memory.delete',
  
  // System
  SYSTEM_STATUS: 'system.status',
  SYSTEM_STATE_CHANGE: 'system.state_change',
  SYSTEM_QUEUE_UPDATE: 'system.queue_update',
  
  // Logs
  LOG_ERROR: 'log.error',
  LOG_WARNING: 'log.warning',
  LOG_INFO: 'log.info',
  LOG_DEBUG: 'log.debug'
}

/**
 * Message Types (in-band)
 */
export const MESSAGE_TYPES = {
  AUTH: 'auth',
  USER_MESSAGE: 'user_message',
  ASSISTANT_MESSAGE: 'assistant_message',
  PLAN_APPROVAL: 'plan_approval',
  SYSTEM_COMMAND: 'system_command'
}

/**
 * API Endpoints
 */
export const API_ENDPOINTS = {
  LOGIN: '/api/auth/login',
  REGISTER: '/api/auth/register',
  VERIFY: '/api/auth/verify',
  STATUS: '/api/status'
}

/**
 * Default Panel Configuration
 */
export const DEFAULT_PANEL_CONFIG = {
  left: PANEL_MODES.COMPACT,
  right: PANEL_MODES.EXPANDED,
  bottom: PANEL_MODES.COMPACT,
  
  autoExpand: {
    onPlanStart: true,
    onSearch: true,
    onError: true
  }
}