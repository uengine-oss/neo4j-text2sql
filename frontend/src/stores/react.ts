import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
    apiService,
    type ReactExecutionResult,
    type ReactRequest,
    type ReactResponseModel,
    type ReactStepModel
} from '../services/api'

type ReactStatus = 'idle' | 'running' | 'needs_user_input' | 'completed' | 'error'
type ReactPhase = 'idle' | 'thinking' | 'acting' | 'observing'

export interface QueryHistoryItem {
    id: string
    question: string
    timestamp: number
    success: boolean
    finalSql?: string
}

const QUERY_HISTORY_KEY = 'react_query_history'
const MAX_HISTORY_ITEMS = 20

function loadQueryHistory(): QueryHistoryItem[] {
    try {
        const stored = localStorage.getItem(QUERY_HISTORY_KEY)
        if (stored) {
            return JSON.parse(stored) as QueryHistoryItem[]
        }
    } catch (e) {
        console.warn('Failed to load query history:', e)
    }
    return []
}

function saveQueryHistory(history: QueryHistoryItem[]): void {
    try {
        localStorage.setItem(QUERY_HISTORY_KEY, JSON.stringify(history))
    } catch (e) {
        console.warn('Failed to save query history:', e)
    }
}

function sortSteps(steps: ReactStepModel[]): ReactStepModel[] {
    return [...steps].sort((a, b) => a.iteration - b.iteration)
}

function mergeSteps(existing: ReactStepModel[], incoming: ReactStepModel[]): ReactStepModel[] {
    const byIteration = new Map<number, ReactStepModel>()
    for (const step of existing) {
        byIteration.set(step.iteration, step)
    }
    for (const step of incoming) {
        byIteration.set(step.iteration, step)
    }
    return sortSteps(Array.from(byIteration.values()))
}

export const useReactStore = defineStore('react', () => {
    const currentQuestion = ref('')
    const status = ref<ReactStatus>('idle')
    const currentPhase = ref<ReactPhase>('idle')
    const steps = ref<ReactStepModel[]>([])
    const partialSql = ref<string>('')
    const finalSql = ref<string | null>(null)
    const validatedSql = ref<string | null>(null)
    const executionResult = ref<ReactExecutionResult | null>(null)
    const collectedMetadata = ref<string>('')
    const warnings = ref<string[]>([])
    const error = ref<string | null>(null)
    const sessionState = ref<string | null>(null)
    const questionToUser = ref<string | null>(null)
    const remainingToolCalls = ref<number>(0)
    const maxToolCalls = ref<number>(30)
    const abortController = ref<AbortController | null>(null)
    
    // 쿼리 히스토리
    const queryHistory = ref<QueryHistoryItem[]>(loadQueryHistory())

    const isRunning = computed(() => status.value === 'running')
    const isWaitingUser = computed(() => status.value === 'needs_user_input')
    const hasSteps = computed(() => steps.value.length > 0)
    const hasExecutionResult = computed(() => executionResult.value !== null)
    const latestStep = computed(() =>
        steps.value.length > 0 ? steps.value[steps.value.length - 1] : null
    )
    const latestPartialSql = computed(() => latestStep.value?.partial_sql || partialSql.value)
    
    // 성공한 쿼리만 필터링 (최근 순으로 정렬)
    const successfulQueries = computed(() => 
        queryHistory.value
            .filter(q => q.success)
            .sort((a, b) => b.timestamp - a.timestamp)
    )
    
    // 최근 쿼리 (성공/실패 무관)
    const recentQueries = computed(() => 
        queryHistory.value
            .sort((a, b) => b.timestamp - a.timestamp)
            .slice(0, 10)
    )

    function resetState() {
        steps.value = []
        partialSql.value = ''
        finalSql.value = null
        validatedSql.value = null
        executionResult.value = null
        collectedMetadata.value = ''
        warnings.value = []
        error.value = null
        sessionState.value = null
        questionToUser.value = null
        remainingToolCalls.value = 0
        currentPhase.value = 'idle'
    }
    
    function addToHistory(question: string, success: boolean, sql?: string) {
        // 중복 제거 (같은 질문이 있으면 업데이트)
        const existingIndex = queryHistory.value.findIndex(
            q => q.question.trim().toLowerCase() === question.trim().toLowerCase()
        )
        
        const newItem: QueryHistoryItem = {
            id: Date.now().toString(),
            question: question.trim(),
            timestamp: Date.now(),
            success,
            finalSql: sql
        }
        
        if (existingIndex !== -1) {
            // 기존 항목 업데이트
            queryHistory.value[existingIndex] = newItem
        } else {
            // 새 항목 추가
            queryHistory.value.unshift(newItem)
        }
        
        // 최대 개수 제한
        if (queryHistory.value.length > MAX_HISTORY_ITEMS) {
            queryHistory.value = queryHistory.value.slice(0, MAX_HISTORY_ITEMS)
        }
        
        saveQueryHistory(queryHistory.value)
    }
    
    function removeFromHistory(id: string) {
        queryHistory.value = queryHistory.value.filter(q => q.id !== id)
        saveQueryHistory(queryHistory.value)
    }
    
    function clearHistory() {
        queryHistory.value = []
        saveQueryHistory([])
    }

    function cancelOngoing() {
        if (abortController.value) {
            abortController.value.abort()
            abortController.value = null
        }
    }

    function applyStateSnapshot(snapshot?: Record<string, any>) {
        if (!snapshot) return
        if (typeof snapshot.remaining_tool_calls === 'number') {
            remainingToolCalls.value = snapshot.remaining_tool_calls
        }
        if (typeof snapshot.partial_sql === 'string') {
            partialSql.value = snapshot.partial_sql
        }
    }

    function upsertStep(step: ReactStepModel) {
        steps.value = mergeSteps(steps.value, [step])
    }

    function applyResponse(response: ReactResponseModel) {
        steps.value = mergeSteps(steps.value, response.steps)
        collectedMetadata.value = response.collected_metadata
        partialSql.value = response.partial_sql
        remainingToolCalls.value = response.remaining_tool_calls
        sessionState.value = response.session_state ?? null
        questionToUser.value = response.question_to_user ?? null
        warnings.value = response.warnings ?? []
        if (response.final_sql !== undefined) {
            finalSql.value = response.final_sql ?? null
        }
        if (response.validated_sql !== undefined) {
            validatedSql.value = response.validated_sql ?? null
        }
        executionResult.value = response.execution_result ?? null
    }

    async function consumeStream(request: ReactRequest, controller: AbortController) {
        try {
            currentPhase.value = 'thinking'
            for await (const event of apiService.reactStream(request, { signal: controller.signal })) {
                switch (event.event) {
                    case 'step': {
                        // Phase 업데이트: step을 받으면 acting -> observing
                        currentPhase.value = 'acting'
                        upsertStep(event.step)
                        applyStateSnapshot(event.state)
                        // tool_result가 있으면 observing 완료, 다음 thinking으로
                        if (event.step.tool_result) {
                            currentPhase.value = 'observing'
                            // 잠시 후 thinking으로 전환 (시각적 효과)
                            setTimeout(() => {
                                if (status.value === 'running') {
                                    currentPhase.value = 'thinking'
                                }
                            }, 500)
                        }
                        break
                    }
                    case 'needs_user_input': {
                        applyResponse(event.response)
                        status.value = 'needs_user_input'
                        currentPhase.value = 'idle'
                        return
                    }
                    case 'completed': {
                        applyResponse(event.response)
                        status.value = 'completed'
                        currentPhase.value = 'idle'
                        // 성공한 쿼리를 히스토리에 추가
                        addToHistory(
                            currentQuestion.value, 
                            true, 
                            event.response.final_sql ?? undefined
                        )
                        return
                    }
                    case 'error': {
                        error.value = event.message
                        status.value = 'error'
                        currentPhase.value = 'idle'
                        return
                    }
                    default:
                        break
                }
            }
        } catch (err: any) {
            if (controller.signal.aborted) {
                return
            }
            console.error('ReAct 스트리밍 중 오류', err)
            error.value = err?.message ?? 'ReAct 실행 중 오류가 발생했습니다.'
            status.value = 'error'
            currentPhase.value = 'idle'
        }
    }

    async function start(
        question: string,
        options?: {
            maxToolCalls?: number
            maxSqlSeconds?: number
        }
    ) {
        cancelOngoing()
        resetState()
        currentQuestion.value = question
        status.value = 'running'
        currentPhase.value = 'thinking'
        error.value = null
        maxToolCalls.value = options?.maxToolCalls || 30
        remainingToolCalls.value = maxToolCalls.value

        const controller = new AbortController()
        abortController.value = controller
        await consumeStream(
            {
                question,
                max_tool_calls: options?.maxToolCalls,
                max_sql_seconds: options?.maxSqlSeconds
            },
            controller
        )
        if (abortController.value === controller) {
            abortController.value = null
        }
    }

    async function continueWithResponse(userResponse: string) {
        if (!sessionState.value) {
            throw new Error('세션 상태가 없습니다.')
        }
        cancelOngoing()
        status.value = 'running'
        error.value = null
        questionToUser.value = null

        const controller = new AbortController()
        abortController.value = controller
        await consumeStream(
            {
                question: currentQuestion.value,
                session_state: sessionState.value,
                user_response: userResponse
            },
            controller
        )
        if (abortController.value === controller) {
            abortController.value = null
        }
    }

    function cancel() {
        cancelOngoing()
        status.value = 'idle'
    }

    function clear() {
        cancelOngoing()
        resetState()
        currentQuestion.value = ''
        status.value = 'idle'
    }

    return {
        currentQuestion,
        status,
        currentPhase,
        steps,
        partialSql,
        finalSql,
        validatedSql,
        executionResult,
        collectedMetadata,
        warnings,
        error,
        sessionState,
        questionToUser,
        remainingToolCalls,
        maxToolCalls,
        isRunning,
        isWaitingUser,
        hasSteps,
        hasExecutionResult,
        latestStep,
        latestPartialSql,
        // 쿼리 히스토리
        queryHistory,
        successfulQueries,
        recentQueries,
        addToHistory,
        removeFromHistory,
        clearHistory,
        // 액션
        start,
        continueWithResponse,
        cancel,
        clear
    }
})

