<template>
    <div class="thinking-panel">
        <!-- 현재 상태 헤더 -->
        <div class="thinking-header">
            <div class="iteration-badge" v-if="currentIteration > 0">
                <span class="iteration-number">{{ currentIteration }}</span>
                <span class="iteration-label">Iteration</span>
            </div>
            <div class="phase-indicator">
                <div class="phase-step" :class="{ active: currentPhase === 'thinking', completed: phaseCompleted('thinking') }">
                    <div class="phase-icon">💭</div>
                    <span>Thinking</span>
                </div>
                <div class="phase-connector" :class="{ active: phaseCompleted('thinking') }"></div>
                <div class="phase-step" :class="{ active: currentPhase === 'acting', completed: phaseCompleted('acting') }">
                    <div class="phase-icon">⚡</div>
                    <span>Acting</span>
                </div>
                <div class="phase-connector" :class="{ active: phaseCompleted('acting') }"></div>
                <div class="phase-step" :class="{ active: currentPhase === 'observing', completed: phaseCompleted('observing') }">
                    <div class="phase-icon">👁️</div>
                    <span>Observing</span>
                </div>
            </div>
        </div>

        <!-- ReAct 사이클 카드들 -->
        <div class="react-cycles" ref="cyclesContainer">
            <TransitionGroup name="cycle">
                <div 
                    v-for="(step, index) in displaySteps" 
                    :key="step.iteration"
                    class="react-cycle"
                    :class="{ 
                        current: index === displaySteps.length - 1 && isRunning,
                        expanded: expandedSteps.has(step.iteration)
                    }"
                >
                    <!-- 사이클 헤더 -->
                    <div class="cycle-header" @click="toggleExpand(step.iteration)">
                        <div class="cycle-title">
                            <span class="cycle-number">{{ step.iteration }}</span>
                            <span class="tool-chip">{{ step.tool_call.name }}</span>
                            <span v-if="step.sql_completeness.is_complete" class="complete-badge">✓ SQL 완성</span>
                        </div>
                        <button class="expand-btn" type="button">
                            <svg :class="{ rotated: expandedSteps.has(step.iteration) }" width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"/>
                            </svg>
                        </button>
                    </div>

                    <!-- 사이클 본문 -->
                    <div class="cycle-body">
                        <!-- THINKING 섹션 -->
                        <div class="react-section thinking-section">
                            <div class="section-header">
                                <div class="section-icon thinking">💭</div>
                                <h4>Thinking</h4>
                                <span class="section-badge thinking">Reasoning</span>
                            </div>
                            <div class="section-content">
                                <p class="reasoning-text" :class="{ typing: isCurrentStep(step) && currentPhase === 'thinking' }">
                                    {{ step.reasoning || 'AI가 사고 중...' }}
                                </p>
                            </div>
                        </div>

                        <!-- ACTING 섹션 -->
                        <div class="react-section acting-section">
                            <div class="section-header">
                                <div class="section-icon acting">⚡</div>
                                <h4>Acting</h4>
                                <span class="section-badge acting">{{ step.tool_call.name }}</span>
                            </div>
                            <div class="section-content">
                                <div class="tool-call-details">
                                    <div class="tool-params">
                                        <span class="param-label">파라미터:</span>
                                        <code class="param-value">{{ formatParams(step.tool_call.parameters) }}</code>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- OBSERVING 섹션 -->
                        <div class="react-section observing-section" v-if="step.tool_result || isCurrentStep(step)">
                            <div class="section-header">
                                <div class="section-icon observing">👁️</div>
                                <h4>Observation</h4>
                                <span class="section-badge observing">Tool Result</span>
                            </div>
                            <div class="section-content">
                                <div v-if="step.tool_result" class="observation-result">
                                    <pre><code>{{ truncateResult(step.tool_result) }}</code></pre>
                                    <button 
                                        v-if="isResultLong(step.tool_result)" 
                                        class="show-more-btn"
                                        type="button"
                                        @click.stop="toggleResultExpand(step.iteration)"
                                    >
                                        {{ expandedResults.has(step.iteration) ? '접기' : '더 보기' }}
                                    </button>
                                </div>
                                <div v-else class="observation-loading">
                                    <div class="loading-dots">
                                        <span></span><span></span><span></span>
                                    </div>
                                    <span>도구 실행 중...</span>
                                </div>
                            </div>
                        </div>

                        <!-- SQL 진행 상황 (확장 시) -->
                        <div class="sql-progress-section" v-if="expandedSteps.has(step.iteration) && step.partial_sql">
                            <div class="section-header">
                                <div class="section-icon sql">📝</div>
                                <h4>SQL Progress</h4>
                                <span class="confidence-badge" :class="getConfidenceClass(step.sql_completeness.confidence_level)">
                                    {{ step.sql_completeness.confidence_level }}
                                </span>
                            </div>
                            <div class="section-content">
                                <pre class="sql-preview"><code>{{ step.partial_sql }}</code></pre>
                                <div v-if="step.sql_completeness.missing_info" class="missing-info">
                                    <span class="missing-label">누락 정보:</span>
                                    <span class="missing-value">{{ step.sql_completeness.missing_info }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </TransitionGroup>
        </div>

        <!-- 하단 진행 상태 바 -->
        <div class="progress-footer" v-if="isRunning">
            <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
            <div class="progress-info">
                <span class="progress-text">{{ progressText }}</span>
                <span class="remaining-calls">남은 호출: {{ remainingToolCalls }}</span>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import type { ReactStepModel } from '../../services/api'

const props = defineProps<{
    steps: ReactStepModel[]
    isRunning: boolean
    remainingToolCalls: number
    maxToolCalls?: number
}>()

type Phase = 'idle' | 'thinking' | 'acting' | 'observing'

const expandedSteps = ref<Set<number>>(new Set())
const expandedResults = ref<Set<number>>(new Set())
const cyclesContainer = ref<HTMLElement | null>(null)

// 정렬된 스텝
const displaySteps = computed(() => 
    [...props.steps].sort((a, b) => a.iteration - b.iteration)
)

// 현재 iteration
const currentIteration = computed(() => 
    displaySteps.value.length > 0 
        ? displaySteps.value[displaySteps.value.length - 1].iteration 
        : 0
)

// 현재 phase 계산
const currentPhase = computed<Phase>(() => {
    if (!props.isRunning) return 'idle'
    const latestStep = displaySteps.value[displaySteps.value.length - 1]
    if (!latestStep) return 'thinking'
    
    if (!latestStep.tool_result) {
        // 도구 결과가 없으면 acting 또는 observing 중
        return latestStep.reasoning ? 'acting' : 'thinking'
    }
    // 결과가 있으면 다음 thinking으로 넘어감
    return 'thinking'
})

// 진행률 계산
const progressPercent = computed(() => {
    const max = props.maxToolCalls || 30
    const used = max - props.remainingToolCalls
    return Math.min(100, (used / max) * 100)
})

const progressText = computed(() => {
    switch (currentPhase.value) {
        case 'thinking': return '🤔 AI가 사고하는 중...'
        case 'acting': return '⚡ 도구를 실행하는 중...'
        case 'observing': return '👁️ 결과를 분석하는 중...'
        default: return '대기 중'
    }
})

function isCurrentStep(step: ReactStepModel): boolean {
    return displaySteps.value.length > 0 && 
           step.iteration === displaySteps.value[displaySteps.value.length - 1].iteration
}

function phaseCompleted(phase: Phase): boolean {
    if (!props.isRunning) return false
    const latestStep = displaySteps.value[displaySteps.value.length - 1]
    if (!latestStep) return false
    
    switch (phase) {
        case 'thinking': return !!latestStep.reasoning
        case 'acting': return !!latestStep.tool_call.name
        case 'observing': return !!latestStep.tool_result
        default: return false
    }
}

function toggleExpand(iteration: number) {
    if (expandedSteps.value.has(iteration)) {
        expandedSteps.value.delete(iteration)
    } else {
        expandedSteps.value.add(iteration)
    }
}

function toggleResultExpand(iteration: number) {
    if (expandedResults.value.has(iteration)) {
        expandedResults.value.delete(iteration)
    } else {
        expandedResults.value.add(iteration)
    }
}

function formatParams(params: Record<string, any>): string {
    try {
        const formatted = Object.entries(params)
            .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
            .join(', ')
        return formatted.length > 100 ? formatted.slice(0, 100) + '...' : formatted
    } catch {
        return JSON.stringify(params)
    }
}

function truncateResult(result: string): string {
    const lines = result.split('\n')
    if (lines.length > 10) {
        return lines.slice(0, 10).join('\n') + '\n... (더 보기 클릭)'
    }
    if (result.length > 500) {
        return result.slice(0, 500) + '... (더 보기 클릭)'
    }
    return result
}

function isResultLong(result: string): boolean {
    return result.split('\n').length > 10 || result.length > 500
}

function getConfidenceClass(level: string): string {
    const lower = level.toLowerCase()
    if (lower.includes('high')) return 'high'
    if (lower.includes('medium')) return 'medium'
    return 'low'
}

// 새 스텝이 추가되면 스크롤
watch(() => props.steps.length, async () => {
    await nextTick()
    if (cyclesContainer.value) {
        cyclesContainer.value.scrollTop = cyclesContainer.value.scrollHeight
    }
})
</script>

<style scoped>
.thinking-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: linear-gradient(180deg, #0f0f23 0%, #1a1a2e 100%);
    border-radius: 16px;
    overflow: hidden;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

/* 헤더 */
.thinking-header {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 1.25rem 1.5rem;
    background: rgba(255, 255, 255, 0.03);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.iteration-badge {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.75rem 1rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border-radius: 12px;
    min-width: 60px;
}

.iteration-number {
    font-size: 1.5rem;
    font-weight: 700;
    color: white;
    line-height: 1;
}

.iteration-label {
    font-size: 0.65rem;
    color: rgba(255, 255, 255, 0.8);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 0.25rem;
}

/* 페이즈 인디케이터 */
.phase-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.phase-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    transition: all 0.3s ease;
    opacity: 0.4;
}

.phase-step.active {
    opacity: 1;
    background: rgba(99, 102, 241, 0.2);
    animation: phasePulse 1.5s ease-in-out infinite;
}

.phase-step.completed {
    opacity: 0.8;
}

.phase-icon {
    font-size: 1.25rem;
}

.phase-step span {
    font-size: 0.7rem;
    color: rgba(255, 255, 255, 0.7);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.phase-connector {
    width: 30px;
    height: 2px;
    background: rgba(255, 255, 255, 0.15);
    border-radius: 1px;
    transition: background 0.3s ease;
}

.phase-connector.active {
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
}

@keyframes phasePulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.4); }
    50% { box-shadow: 0 0 0 8px rgba(99, 102, 241, 0); }
}

/* 사이클 컨테이너 */
.react-cycles {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.react-cycles::-webkit-scrollbar {
    width: 6px;
}

.react-cycles::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
}

.react-cycles::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.5);
    border-radius: 3px;
}

/* 사이클 카드 */
.react-cycle {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.3s ease;
}

.react-cycle.current {
    border-color: rgba(99, 102, 241, 0.5);
    box-shadow: 0 0 20px rgba(99, 102, 241, 0.15);
}

.react-cycle:hover {
    border-color: rgba(255, 255, 255, 0.15);
}

.cycle-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.875rem 1rem;
    background: rgba(255, 255, 255, 0.02);
    cursor: pointer;
    transition: background 0.2s ease;
}

.cycle-header:hover {
    background: rgba(255, 255, 255, 0.05);
}

.cycle-title {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.cycle-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border-radius: 8px;
    color: white;
    font-weight: 600;
    font-size: 0.85rem;
}

.tool-chip {
    padding: 0.25rem 0.75rem;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 20px;
    color: #a5b4fc;
    font-size: 0.75rem;
    font-weight: 500;
}

.complete-badge {
    padding: 0.25rem 0.5rem;
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.3);
    border-radius: 6px;
    color: #86efac;
    font-size: 0.7rem;
    font-weight: 600;
}

.expand-btn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.5);
    cursor: pointer;
    padding: 0.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
}

.expand-btn:hover {
    color: rgba(255, 255, 255, 0.8);
}

.expand-btn svg {
    transition: transform 0.3s ease;
}

.expand-btn svg.rotated {
    transform: rotate(180deg);
}

/* 사이클 본문 */
.cycle-body {
    padding: 0 1rem 1rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

/* ReAct 섹션 공통 */
.react-section {
    border-radius: 10px;
    overflow: hidden;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.05);
}

.section-header {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.625rem 0.875rem;
    background: rgba(255, 255, 255, 0.02);
}

.section-icon {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    font-size: 0.875rem;
}

.section-icon.thinking { background: rgba(234, 179, 8, 0.2); }
.section-icon.acting { background: rgba(99, 102, 241, 0.2); }
.section-icon.observing { background: rgba(34, 197, 94, 0.2); }
.section-icon.sql { background: rgba(59, 130, 246, 0.2); }

.section-header h4 {
    margin: 0;
    font-size: 0.8rem;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.section-badge {
    margin-left: auto;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

.section-badge.thinking {
    background: rgba(234, 179, 8, 0.2);
    color: #fbbf24;
}

.section-badge.acting {
    background: rgba(99, 102, 241, 0.2);
    color: #a5b4fc;
}

.section-badge.observing {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
}

.section-content {
    padding: 0.75rem 0.875rem;
}

/* Thinking 섹션 */
.thinking-section {
    border-left: 3px solid #eab308;
}

.reasoning-text {
    margin: 0;
    color: rgba(255, 255, 255, 0.85);
    font-size: 0.85rem;
    line-height: 1.6;
    white-space: pre-wrap;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.reasoning-text.typing::after {
    content: '▌';
    animation: blink 1s step-end infinite;
    color: #eab308;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

/* Acting 섹션 */
.acting-section {
    border-left: 3px solid #6366f1;
}

.tool-call-details {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.tool-params {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.param-label {
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.75rem;
    flex-shrink: 0;
}

.param-value {
    background: rgba(0, 0, 0, 0.3);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    color: #a5b4fc;
    font-size: 0.75rem;
    word-break: break-all;
}

/* Observing 섹션 */
.observing-section {
    border-left: 3px solid #22c55e;
}

.observation-result pre {
    margin: 0;
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 6px;
    overflow-x: auto;
    max-height: 200px;
}

.observation-result code {
    color: #86efac;
    font-size: 0.75rem;
    line-height: 1.5;
}

.show-more-btn {
    margin-top: 0.5rem;
    padding: 0.375rem 0.75rem;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.7);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s ease;
}

.show-more-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
}

.observation-loading {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.8rem;
}

.loading-dots {
    display: flex;
    gap: 4px;
}

.loading-dots span {
    width: 6px;
    height: 6px;
    background: #22c55e;
    border-radius: 50%;
    animation: dotPulse 1.4s ease-in-out infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotPulse {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
    40% { transform: scale(1); opacity: 1; }
}

/* SQL Progress 섹션 */
.sql-progress-section {
    margin-top: 0.5rem;
    border-left: 3px solid #3b82f6;
}

.sql-preview {
    margin: 0;
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.4);
    border-radius: 6px;
    overflow-x: auto;
}

.sql-preview code {
    color: #93c5fd;
    font-size: 0.8rem;
    line-height: 1.5;
}

.confidence-badge {
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 600;
}

.confidence-badge.high {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
}

.confidence-badge.medium {
    background: rgba(234, 179, 8, 0.2);
    color: #fbbf24;
}

.confidence-badge.low {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
}

.missing-info {
    margin-top: 0.5rem;
    padding: 0.5rem;
    background: rgba(234, 179, 8, 0.1);
    border-radius: 6px;
    display: flex;
    gap: 0.5rem;
    font-size: 0.75rem;
}

.missing-label {
    color: #fbbf24;
    font-weight: 600;
}

.missing-value {
    color: rgba(255, 255, 255, 0.7);
}

/* 하단 진행 바 */
.progress-footer {
    padding: 1rem 1.5rem;
    background: rgba(0, 0, 0, 0.3);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.progress-bar {
    height: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 0.75rem;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #a855f7);
    border-radius: 2px;
    transition: width 0.3s ease;
}

.progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.progress-text {
    color: rgba(255, 255, 255, 0.8);
    font-size: 0.8rem;
}

.remaining-calls {
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.75rem;
}

/* 트랜지션 */
.cycle-enter-active {
    animation: cycleIn 0.4s ease-out;
}

.cycle-leave-active {
    animation: cycleOut 0.3s ease-in;
}

@keyframes cycleIn {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes cycleOut {
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
@media (max-width: 768px) {
    .thinking-header {
        flex-direction: column;
        gap: 1rem;
        padding: 1rem;
    }

    .phase-indicator {
        flex-wrap: wrap;
        justify-content: center;
    }

    .phase-connector {
        width: 20px;
    }

    .cycle-body {
        padding: 0 0.75rem 0.75rem 0.75rem;
    }
}
</style>

