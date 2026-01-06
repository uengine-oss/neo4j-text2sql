<template>
    <div class="react-view">
        <!-- 고정 헤더 영역 -->
        <div class="header-section">
            <div class="header-content">
                <h1 class="page-title">🧠 Neo4j ReAct Text2SQL</h1>
                <div class="status-indicator" v-if="reactStore.isRunning || reactStore.status !== 'idle'">
                    <span :class="['status-dot', reactStore.status]"></span>
                    <span class="status-text">{{ statusLabel }}</span>
                    <span v-if="reactStore.isRunning" class="live-badge">LIVE</span>
                </div>
            </div>
            <div v-if="reactStore.error" class="error-message">
                <strong>오류:</strong> {{ reactStore.error }}
            </div>
        </div>

        <!-- 메인 컨텐츠 영역 -->
        <div class="main-content">
            <!-- 입력 상태: 쿼리 입력만 표시 -->
            <div v-if="!hasExecutionData" class="input-only-view">
                <div class="centered-input">
                    <ReactInput 
                        :loading="reactStore.isRunning" 
                        :waiting-for-user="reactStore.isWaitingUser"
                        :question-to-user="reactStore.questionToUser" 
                        :current-question="reactStore.currentQuestion"
                        @start="handleStart" 
                        @respond="handleRespond" 
                        @cancel="handleCancel" 
                    />
                </div>
            </div>

            <!-- 실행 중 또는 완료: 좌우 분할 레이아웃 -->
            <div v-else class="split-layout">
                <!-- 좌측: 스텝 진행 상황 -->
                <div class="left-panel">
                    <div class="panel-header">
                        <h2>
                            <span class="panel-icon">🔄</span>
                            ReAct 진행 과정
                        </h2>
                        <div class="step-counter" v-if="reactStore.hasSteps">
                            Step {{ reactStore.steps.length }}
                        </div>
                    </div>
                    
                    <div class="panel-content">
                        <!-- 로딩 상태 -->
                        <div v-if="reactStore.isRunning && !reactStore.hasSteps" class="loading-state">
                            <div class="thinking-animation">
                                <span class="dot"></span>
                                <span class="dot"></span>
                                <span class="dot"></span>
                            </div>
                            <p>AI가 사고를 시작하고 있습니다...</p>
                        </div>

                        <!-- 스텝 타임라인 -->
                        <div v-else class="steps-container">
                            <TransitionGroup name="step-anim" tag="div" class="steps-list">
                                <div 
                                    v-for="step in sortedSteps" 
                                    :key="step.iteration"
                                    class="step-card"
                                    :class="{ 
                                        current: isCurrentStep(step),
                                        expanded: expandedSteps.has(step.iteration)
                                    }"
                                >
                                    <!-- 스텝 헤더 -->
                                    <div class="step-header" @click="toggleStep(step.iteration)">
                                        <div class="step-number">{{ step.iteration }}</div>
                                        <div class="step-info">
                                            <div class="step-phase">
                                                <span class="phase-badge thinking">💭 Thinking</span>
                                                <span class="phase-arrow">→</span>
                                                <span class="phase-badge acting">⚡ {{ step.tool_call.name }}</span>
                                                <span v-if="step.tool_result" class="phase-arrow">→</span>
                                                <span v-if="step.tool_result" class="phase-badge observing">👁️ Done</span>
                                            </div>
                                        </div>
                                        <div class="step-status">
                                            <span v-if="isCurrentStep(step) && reactStore.isRunning" class="processing">
                                                <span class="pulse"></span>
                                            </span>
                                            <span v-else-if="step.tool_result" class="completed">✓</span>
                                        </div>
                                    </div>

                                    <!-- 스텝 상세 내용 -->
                                    <div class="step-body">
                                        <!-- Thinking -->
                                        <div class="step-section thinking">
                                            <div class="section-label">
                                                <span class="label-icon">💭</span>
                                                Reasoning
                                            </div>
                                            <p class="reasoning-text" :class="{ typing: isCurrentStep(step) && !step.tool_result }">
                                                {{ step.reasoning || 'AI가 사고 중...' }}
                                            </p>
                                        </div>

                                        <!-- Acting -->
                                        <div class="step-section acting">
                                            <div class="section-label">
                                                <span class="label-icon">⚡</span>
                                                Tool Call
                                            </div>
                                            <div class="tool-info">
                                                <code class="tool-name">{{ step.tool_call.name }}</code>
                                                <span class="tool-params">{{ formatParams(step.tool_call.parameters) }}</span>
                                            </div>
                                        </div>

                                        <!-- Observation -->
                                        <div v-if="step.tool_result || isCurrentStep(step)" class="step-section observing">
                                            <div class="section-label">
                                                <span class="label-icon">👁️</span>
                                                Observation
                                            </div>
                                            <div v-if="step.tool_result" class="tool-result">
                                                <pre><code>{{ truncateResult(step.tool_result, expandedSteps.has(step.iteration)) }}</code></pre>
                                                <button 
                                                    v-if="isResultLong(step.tool_result)" 
                                                    class="toggle-result-btn"
                                                    type="button"
                                                    @click.stop="toggleStep(step.iteration)"
                                                >
                                                    {{ expandedSteps.has(step.iteration) ? '접기' : '더 보기' }}
                                                </button>
                                            </div>
                                            <div v-else class="waiting-result">
                                                <span class="loading-dots"><span></span><span></span><span></span></span>
                                                도구 실행 중...
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </TransitionGroup>
                        </div>
                    </div>
                </div>

                <!-- 우측: SQL 및 상태 패널 -->
                <div class="right-panel">
                    <!-- 현재 상태 -->
                    <div class="status-card">
                        <div class="card-header">
                            <h3>📊 실행 상태</h3>
                        </div>
                        <div class="card-body">
                            <div class="stat-row">
                                <span class="stat-label">Phase</span>
                                <span class="phase-chip" :class="reactStore.currentPhase">{{ phaseLabel }}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">Steps</span>
                                <span class="stat-value">{{ reactStore.steps.length }}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">남은 호출</span>
                                <span class="stat-value">{{ reactStore.remainingToolCalls }} / {{ reactStore.maxToolCalls }}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
                            </div>
                        </div>
                    </div>

                    <!-- SQL 미리보기 -->
                    <div class="sql-card">
                        <div class="card-header">
                            <h3>📝 현재 SQL</h3>
                            <button v-if="currentSql" class="copy-btn" type="button" @click="copySql">복사</button>
                        </div>
                        <div class="card-body">
                            <div v-if="currentSql" class="sql-preview">
                                <pre><code>{{ currentSql }}</code></pre>
                            </div>
                            <div v-else class="sql-placeholder">
                                <span class="placeholder-icon">💭</span>
                                <span>SQL 생성 대기 중...</span>
                            </div>
                            
                            <!-- 완성도 정보 -->
                            <div v-if="latestCompleteness" class="completeness-info">
                                <div class="completeness-row">
                                    <span>완성도:</span>
                                    <span :class="['confidence', getConfidenceClass(latestCompleteness.confidence_level)]">
                                        {{ latestCompleteness.confidence_level }}
                                    </span>
                                </div>
                                <div v-if="latestCompleteness.missing_info" class="missing-info">
                                    <span class="missing-label">누락:</span>
                                    <span>{{ latestCompleteness.missing_info }}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 사용자 입력 대기 -->
                    <div v-if="reactStore.isWaitingUser" class="user-input-card">
                        <div class="card-header warning">
                            <h3>💬 사용자 입력 필요</h3>
                        </div>
                        <div class="card-body">
                            <p class="question-text">{{ reactStore.questionToUser }}</p>
                            <div class="input-group">
                                <input 
                                    v-model="userResponse" 
                                    type="text" 
                                    class="response-input"
                                    placeholder="답변을 입력하세요..."
                                    @keyup.enter="submitResponse"
                                />
                                <button class="submit-btn" type="button" @click="submitResponse">답변</button>
                            </div>
                        </div>
                    </div>

                    <!-- 완료 상태: 결과 표시 -->
                    <div v-if="reactStore.status === 'completed'" class="result-card">
                        <div class="card-header success">
                            <h3>✓ 완료</h3>
                        </div>
                        <div class="card-body">
                            <div v-if="reactStore.executionResult" class="execution-result">
                                <div class="result-stats">
                                    <span>{{ reactStore.executionResult.row_count }}개 행</span>
                                    <span>{{ reactStore.executionResult.execution_time_ms.toFixed(1) }}ms</span>
                                </div>
                            </div>
                            <div v-if="reactStore.warnings.length" class="warnings">
                                <div v-for="warning in reactStore.warnings" :key="warning" class="warning-item">
                                    ⚠️ {{ warning }}
                                </div>
                            </div>
                            <button class="new-query-btn" type="button" @click="startNewQuery">
                                새 쿼리 시작
                            </button>
                        </div>
                    </div>

                    <!-- 액션 버튼 -->
                    <div v-if="reactStore.isRunning" class="action-card">
                        <button class="cancel-btn" type="button" @click="handleCancel">
                            ✕ 실행 중단
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import ReactInput from '../components/react/ReactInput.vue'
import { useReactStore } from '../stores/react'
import type { ReactStepModel } from '../services/api'

const reactStore = useReactStore()

const userResponse = ref('')
const expandedSteps = ref<Set<number>>(new Set())

// 실행 데이터가 있는지 확인
const hasExecutionData = computed(() =>
    reactStore.hasSteps || reactStore.partialSql || reactStore.finalSql || reactStore.isRunning
)

// 정렬된 스텝
const sortedSteps = computed(() => 
    [...reactStore.steps].sort((a, b) => a.iteration - b.iteration)
)

// 현재 SQL
const currentSql = computed(() => 
    reactStore.finalSql || reactStore.latestPartialSql || ''
)

// 최신 완성도 정보
const latestCompleteness = computed(() => 
    reactStore.latestStep?.sql_completeness ?? null
)

// 진행률
const progressPercent = computed(() => {
    const max = reactStore.maxToolCalls || 30
    const used = max - reactStore.remainingToolCalls
    return Math.min(100, (used / max) * 100)
})

// 상태 레이블
const statusLabel = computed(() => {
    switch (reactStore.status) {
        case 'running': return '실행 중'
        case 'needs_user_input': return '입력 대기'
        case 'completed': return '완료'
        case 'error': return '오류'
        default: return '대기'
    }
})

// 페이즈 레이블
const phaseLabel = computed(() => {
    switch (reactStore.currentPhase) {
        case 'thinking': return '🤔 Thinking'
        case 'acting': return '⚡ Acting'
        case 'observing': return '👁️ Observing'
        default: return '⏸️ Idle'
    }
})

function isCurrentStep(step: ReactStepModel): boolean {
    return sortedSteps.value.length > 0 && 
           step.iteration === sortedSteps.value[sortedSteps.value.length - 1].iteration
}

function toggleStep(iteration: number) {
    if (expandedSteps.value.has(iteration)) {
        expandedSteps.value.delete(iteration)
    } else {
        expandedSteps.value.add(iteration)
    }
}

function formatParams(params: Record<string, any>): string {
    try {
        const entries = Object.entries(params)
        if (entries.length === 0) return ''
        const formatted = entries
            .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
            .join(', ')
        return formatted.length > 80 ? formatted.slice(0, 80) + '...' : formatted
    } catch {
        return ''
    }
}

function truncateResult(result: string, expanded: boolean): string {
    if (expanded) return result
    const lines = result.split('\n')
    if (lines.length > 6) {
        return lines.slice(0, 6).join('\n') + '\n...'
    }
    if (result.length > 300) {
        return result.slice(0, 300) + '...'
    }
    return result
}

function isResultLong(result: string): boolean {
    return result.split('\n').length > 6 || result.length > 300
}

function getConfidenceClass(level: string): string {
    const lower = level.toLowerCase()
    if (lower.includes('high')) return 'high'
    if (lower.includes('medium')) return 'medium'
    return 'low'
}

function copySql() {
    if (currentSql.value) {
        navigator.clipboard.writeText(currentSql.value)
    }
}

async function handleStart(
    question: string,
    options: { maxToolCalls: number; maxSqlSeconds: number }
) {
    expandedSteps.value.clear()
    await reactStore.start(question, options)
}

async function handleRespond(answer: string) {
    await reactStore.continueWithResponse(answer)
}

async function submitResponse() {
    if (userResponse.value.trim()) {
        await reactStore.continueWithResponse(userResponse.value.trim())
        userResponse.value = ''
    }
}

function handleCancel() {
    reactStore.cancel()
}

function startNewQuery() {
    reactStore.clear()
    expandedSteps.value.clear()
}

// 새 스텝이 추가될 때 스크롤
watch(() => reactStore.steps.length, async () => {
    await nextTick()
    const container = document.querySelector('.steps-container')
    if (container) {
        container.scrollTop = container.scrollHeight
    }
})
</script>

<style scoped>
.react-view {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: linear-gradient(180deg, #0a0a1a 0%, #1a1a2e 100%);
    color: rgba(255, 255, 255, 0.9);
    overflow: hidden;
}

/* 헤더 */
.header-section {
    flex-shrink: 0;
    padding: 1rem 2rem;
    background: rgba(0, 0, 0, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.page-title {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 1rem;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 20px;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #6b7280;
}

.status-dot.running {
    background: #3b82f6;
    animation: pulse 1.5s ease-in-out infinite;
}

.status-dot.completed { background: #22c55e; }
.status-dot.error { background: #ef4444; }
.status-dot.needs_user_input { background: #eab308; }

@keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.5); }
    50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0); }
}

.status-text {
    font-size: 0.85rem;
    font-weight: 500;
}

.live-badge {
    background: #ef4444;
    color: white;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.15rem 0.4rem;
    border-radius: 8px;
    animation: blink 1s ease-in-out infinite;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

.error-message {
    margin-top: 0.75rem;
    padding: 0.75rem 1rem;
    background: rgba(239, 68, 68, 0.15);
    border-left: 3px solid #ef4444;
    border-radius: 6px;
    color: #fca5a5;
    font-size: 0.9rem;
}

/* 메인 컨텐츠 */
.main-content {
    flex: 1;
    overflow: hidden;
}

/* 입력만 표시 */
.input-only-view {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: 2rem;
}

.centered-input {
    width: 100%;
    max-width: 900px;
}

/* 좌우 분할 레이아웃 */
.split-layout {
    display: grid;
    grid-template-columns: 1fr 380px;
    height: 100%;
    gap: 0;
}

/* 좌측 패널 */
.left-panel {
    display: flex;
    flex-direction: column;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    overflow: hidden;
}

.panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.panel-header h2 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.panel-icon {
    font-size: 1.1rem;
}

.step-counter {
    padding: 0.25rem 0.75rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
}

.panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
}

.panel-content::-webkit-scrollbar {
    width: 6px;
}

.panel-content::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.4);
    border-radius: 3px;
}

/* 로딩 상태 */
.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    text-align: center;
}

.thinking-animation {
    display: flex;
    gap: 8px;
    margin-bottom: 1.5rem;
}

.thinking-animation .dot {
    width: 12px;
    height: 12px;
    background: #6366f1;
    border-radius: 50%;
    animation: bounce 1.4s ease-in-out infinite;
}

.thinking-animation .dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-animation .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
    0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
    40% { transform: scale(1.2); opacity: 1; }
}

.loading-state p {
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.95rem;
}

/* 스텝 목록 */
.steps-container {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.step-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.3s ease;
}

.step-card.current {
    border-color: rgba(99, 102, 241, 0.5);
    box-shadow: 0 0 20px rgba(99, 102, 241, 0.15);
}

.step-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.875rem 1rem;
    background: rgba(255, 255, 255, 0.02);
    cursor: pointer;
    transition: background 0.2s ease;
}

.step-header:hover {
    background: rgba(255, 255, 255, 0.05);
}

.step-number {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 700;
    flex-shrink: 0;
}

.step-info {
    flex: 1;
    min-width: 0;
}

.step-phase {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.phase-badge {
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
}

.phase-badge.thinking {
    background: rgba(234, 179, 8, 0.2);
    color: #fbbf24;
}

.phase-badge.acting {
    background: rgba(99, 102, 241, 0.2);
    color: #a5b4fc;
}

.phase-badge.observing {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
}

.phase-arrow {
    color: rgba(255, 255, 255, 0.3);
    font-size: 0.75rem;
}

.step-status {
    flex-shrink: 0;
}

.processing {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
}

.processing .pulse {
    width: 10px;
    height: 10px;
    background: #3b82f6;
    border-radius: 50%;
    animation: pulse 1s ease-in-out infinite;
}

.completed {
    color: #22c55e;
    font-weight: 700;
}

/* 스텝 본문 */
.step-body {
    padding: 0 1rem 1rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.step-section {
    padding: 0.75rem;
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.2);
}

.step-section.thinking { border-left: 3px solid #eab308; }
.step-section.acting { border-left: 3px solid #6366f1; }
.step-section.observing { border-left: 3px solid #22c55e; }

.section-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.5);
    margin-bottom: 0.5rem;
}

.label-icon {
    font-size: 0.8rem;
}

.reasoning-text {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.6;
    color: rgba(255, 255, 255, 0.85);
    white-space: pre-wrap;
}

.reasoning-text.typing::after {
    content: '▌';
    animation: cursor-blink 1s step-end infinite;
    color: #eab308;
}

@keyframes cursor-blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

.tool-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.tool-name {
    padding: 0.25rem 0.5rem;
    background: rgba(99, 102, 241, 0.2);
    border-radius: 4px;
    color: #a5b4fc;
    font-size: 0.8rem;
}

.tool-params {
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.75rem;
}

.tool-result {
    position: relative;
}

.tool-result pre {
    margin: 0;
    padding: 0.5rem;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 6px;
    max-height: 200px;
    overflow: auto;
}

.tool-result code {
    color: #86efac;
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.toggle-result-btn {
    margin-top: 0.5rem;
    padding: 0.25rem 0.5rem;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.7rem;
    cursor: pointer;
    transition: all 0.2s ease;
}

.toggle-result-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
}

.waiting-result {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.8rem;
}

.loading-dots {
    display: flex;
    gap: 4px;
}

.loading-dots span {
    width: 5px;
    height: 5px;
    background: #22c55e;
    border-radius: 50%;
    animation: dot-pulse 1.4s ease-in-out infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-pulse {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
    40% { transform: scale(1); opacity: 1; }
}

/* 우측 패널 */
.right-panel {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.2);
}

.right-panel::-webkit-scrollbar {
    width: 6px;
}

.right-panel::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.4);
    border-radius: 3px;
}

/* 카드 공통 */
.status-card, .sql-card, .user-input-card, .result-card, .action-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.card-header h3 {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 600;
}

.card-header.warning {
    background: rgba(234, 179, 8, 0.1);
    border-bottom-color: rgba(234, 179, 8, 0.2);
}

.card-header.warning h3 { color: #fbbf24; }

.card-header.success {
    background: rgba(34, 197, 94, 0.1);
    border-bottom-color: rgba(34, 197, 94, 0.2);
}

.card-header.success h3 { color: #86efac; }

.card-body {
    padding: 1rem;
}

/* 상태 카드 */
.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.stat-row:last-of-type {
    border-bottom: none;
    margin-bottom: 0.75rem;
}

.stat-label {
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.8rem;
}

.stat-value {
    font-weight: 600;
    font-size: 0.85rem;
}

.phase-chip {
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
}

.phase-chip.thinking { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }
.phase-chip.acting { background: rgba(99, 102, 241, 0.2); color: #a5b4fc; }
.phase-chip.observing { background: rgba(34, 197, 94, 0.2); color: #86efac; }
.phase-chip.idle { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }

.progress-bar {
    height: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    border-radius: 2px;
    transition: width 0.3s ease;
}

/* SQL 카드 */
.copy-btn {
    padding: 0.25rem 0.5rem;
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 4px;
    color: #a5b4fc;
    font-size: 0.7rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.copy-btn:hover {
    background: rgba(99, 102, 241, 0.3);
    color: white;
}

.sql-preview {
    max-height: 200px;
    overflow: auto;
}

.sql-preview pre {
    margin: 0;
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 8px;
}

.sql-preview code {
    color: #93c5fd;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.8rem;
    line-height: 1.5;
}

.sql-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem;
    color: rgba(255, 255, 255, 0.4);
    text-align: center;
    gap: 0.5rem;
}

.placeholder-icon {
    font-size: 1.5rem;
    animation: float 2s ease-in-out infinite;
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-5px); }
}

.completeness-info {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.completeness-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8rem;
}

.completeness-row span:first-child {
    color: rgba(255, 255, 255, 0.5);
}

.confidence {
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
}

.confidence.high { background: rgba(34, 197, 94, 0.2); color: #86efac; }
.confidence.medium { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }
.confidence.low { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }

.missing-info {
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.6);
}

.missing-label {
    color: #fbbf24;
    font-weight: 600;
    margin-right: 0.25rem;
}

/* 사용자 입력 카드 */
.question-text {
    margin: 0 0 1rem 0;
    font-size: 0.9rem;
    line-height: 1.5;
}

.input-group {
    display: flex;
    gap: 0.5rem;
}

.response-input {
    flex: 1;
    padding: 0.6rem 0.75rem;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    color: white;
    font-size: 0.85rem;
    outline: none;
}

.response-input:focus {
    border-color: rgba(99, 102, 241, 0.5);
}

.response-input::placeholder {
    color: rgba(255, 255, 255, 0.4);
}

.submit-btn {
    padding: 0.6rem 1rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.submit-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
}

/* 결과 카드 */
.execution-result {
    margin-bottom: 0.75rem;
}

.result-stats {
    display: flex;
    gap: 1rem;
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.7);
}

.warnings {
    margin-bottom: 0.75rem;
}

.warning-item {
    padding: 0.5rem;
    background: rgba(234, 179, 8, 0.1);
    border-radius: 6px;
    font-size: 0.8rem;
    color: #fbbf24;
    margin-bottom: 0.5rem;
}

.new-query-btn {
    width: 100%;
    padding: 0.75rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.new-query-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
}

/* 액션 카드 */
.action-card {
    padding: 1rem;
}

.cancel-btn {
    width: 100%;
    padding: 0.75rem;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 8px;
    color: #fca5a5;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.cancel-btn:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.5);
}

/* 스텝 애니메이션 */
.step-anim-enter-active {
    animation: step-in 0.4s ease-out;
}

.step-anim-leave-active {
    animation: step-out 0.3s ease-in;
}

@keyframes step-in {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes step-out {
    from {
        opacity: 1;
        transform: translateY(0);
    }
    to {
        opacity: 0;
        transform: translateY(20px);
    }
}

/* 반응형 */
@media (max-width: 1024px) {
    .split-layout {
        grid-template-columns: 1fr;
        grid-template-rows: 1fr auto;
    }

    .left-panel {
        border-right: none;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        max-height: 50vh;
    }

    .right-panel {
        max-height: 50vh;
    }
}

@media (max-width: 640px) {
    .header-section {
        padding: 0.75rem 1rem;
    }

    .page-title {
        font-size: 1.2rem;
    }

    .panel-header {
        padding: 0.75rem 1rem;
    }

    .step-phase {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.25rem;
    }

    .phase-arrow {
        display: none;
    }
}
</style>
