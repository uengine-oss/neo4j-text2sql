<template>
    <div class="step-timeline">
        <!-- 스텝 네비게이션 -->
        <div class="step-nav">
            <button class="nav-btn" @click="prevStep" :disabled="currentStepIndex === 0" type="button">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd"
                        d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
                        clip-rule="evenodd" />
                </svg>
            </button>

            <div class="step-indicators">
                <button v-for="(step, index) in sortedSteps" :key="step.iteration" type="button" class="step-indicator"
                    :class="{ active: index === currentStepIndex }" @click="currentStepIndex = index">
                    <span class="step-number">{{ step.iteration }}</span>
                    <span class="step-label">Step {{ step.iteration }}</span>
                </button>
            </div>

            <button class="nav-btn" @click="nextStep" :disabled="currentStepIndex === sortedSteps.length - 1"
                type="button">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd"
                        d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                        clip-rule="evenodd" />
                </svg>
            </button>
        </div>

        <!-- 현재 스텝 카드 -->
        <transition name="slide" mode="out-in">
            <div v-if="currentStep" :key="currentStep.iteration" class="step-card">
                <!-- 스텝 헤더 -->
                <div class="step-header">
                    <div class="step-meta">
                        <h2 class="step-title">
                            <span class="step-icon">🔄</span>
                            STEP {{ currentStep.iteration }}
                        </h2>
                        <span class="tool-badge">{{ currentStep.tool_call.name }}</span>
                    </div>
                    <div class="completeness-badge" :class="{
                        complete: currentStep.sql_completeness.is_complete,
                        incomplete: !currentStep.sql_completeness.is_complete
                    }">
                        <span class="badge-icon">{{ currentStep.sql_completeness.is_complete ? '✓' : '⋯' }}</span>
                        <span>{{ currentStep.sql_completeness.is_complete ? 'SQL 완성' : 'SQL 구성 중' }}</span>
                    </div>
                </div>

                <!-- SQL 하이라이트 영역 -->
                <div class="sql-highlight">
                    <div class="sql-header">
                        <h3>
                            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                                <path
                                    d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" />
                            </svg>
                            생성된 SQL
                        </h3>
                        <button class="btn-copy" @click="copySql(currentStep.partial_sql)" type="button">
                            복사
                        </button>
                    </div>
                    <div class="sql-content">
                        <pre><code>{{ currentStep.partial_sql || 'SQL이 아직 생성되지 않았습니다...' }}</code></pre>
                    </div>
                    <div v-if="sqlChange" class="sql-change-indicator">
                        <span class="change-badge">✨ 이전 스텝에서 변경됨</span>
                    </div>
                </div>

                <!-- 추론 과정 -->
                <div class="reasoning-section">
                    <h3>
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd"
                                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                                clip-rule="evenodd" />
                        </svg>
                        AI의 사고 과정
                    </h3>
                    <p class="reasoning-text">{{ currentStep.reasoning || '설명 없음' }}</p>
                </div>

                <!-- 추가 정보 (접힌 상태) -->
                <details class="details-section">
                    <summary>
                        <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd"
                                d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                                clip-rule="evenodd" />
                        </svg>
                        상세 정보 보기
                    </summary>

                    <div class="details-content">
                        <!-- SQL 완성도 -->
                        <div class="detail-block">
                            <h4>SQL 완성도</h4>
                            <div class="completeness-info">
                                <div class="info-row">
                                    <span class="label">상태:</span>
                                    <span class="value">{{ currentStep.sql_completeness.is_complete ? '완성' : '미완성'
                                    }}</span>
                                </div>
                                <div class="info-row">
                                    <span class="label">신뢰도:</span>
                                    <span class="value">{{ currentStep.sql_completeness.confidence_level }}</span>
                                </div>
                                <div v-if="currentStep.sql_completeness.missing_info" class="info-row">
                                    <span class="label">누락 정보:</span>
                                    <span class="value">{{ currentStep.sql_completeness.missing_info }}</span>
                                </div>
                            </div>
                        </div>

                        <!-- 도구 호출 -->
                        <div class="detail-block">
                            <h4>도구 호출 정보</h4>
                            <div class="tool-info">
                                <div class="info-row">
                                    <span class="label">도구명:</span>
                                    <span class="value code">{{ currentStep.tool_call.name }}</span>
                                </div>
                                <details class="nested-details">
                                    <summary>파라미터</summary>
                                    <pre><code>{{ formatJson(currentStep.tool_call.parameters) }}</code></pre>
                                </details>
                                <details v-if="currentStep.tool_result" class="nested-details">
                                    <summary>실행 결과</summary>
                                    <pre><code>{{ currentStep.tool_result }}</code></pre>
                                </details>
                            </div>
                        </div>

                        <!-- 메타데이터 -->
                        <div v-if="currentStep.metadata_xml" class="detail-block">
                            <details class="nested-details">
                                <summary>추출된 메타데이터 (XML)</summary>
                                <pre><code>{{ currentStep.metadata_xml }}</code></pre>
                            </details>
                        </div>

                        <!-- 원본 LLM 출력 -->
                        <div class="detail-block">
                            <details class="nested-details">
                                <summary>원본 LLM 응답</summary>
                                <pre><code>{{ currentStep.llm_output }}</code></pre>
                            </details>
                        </div>
                    </div>
                </details>
            </div>
        </transition>
    </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ReactStepModel } from '../../services/api'

const props = defineProps<{
    steps: ReactStepModel[]
    isRunning?: boolean
}>()

const currentStepIndex = ref(0)

const sortedSteps = computed(() => [...props.steps].sort((a, b) => a.iteration - b.iteration))

const currentStep = computed(() => sortedSteps.value[currentStepIndex.value] || null)

const sqlChange = computed(() => {
    if (currentStepIndex.value === 0) return false
    const prevStep = sortedSteps.value[currentStepIndex.value - 1]
    return prevStep && prevStep.partial_sql !== currentStep.value?.partial_sql
})

function formatJson(value: unknown): string {
    try {
        return JSON.stringify(value, null, 2)
    } catch (error) {
        return String(value)
    }
}

function prevStep() {
    if (currentStepIndex.value > 0) {
        currentStepIndex.value--
    }
}

function nextStep() {
    if (currentStepIndex.value < sortedSteps.value.length - 1) {
        currentStepIndex.value++
    }
}

function copySql(sql: string) {
    if (sql) {
        navigator.clipboard.writeText(sql)
    }
}
</script>

<style scoped>
.step-timeline {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

/* 스텝 네비게이션 */
.step-nav {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 1rem 1.5rem;
    border-radius: 16px;
}

.nav-btn {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border: 2px solid rgba(255, 255, 255, 0.15);
    background: rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    color: rgba(255, 255, 255, 0.6);
}

.nav-btn:hover:not(:disabled) {
    border-color: rgba(99, 102, 241, 0.5);
    background: rgba(99, 102, 241, 0.15);
    color: #a5b4fc;
    transform: scale(1.05);
}

.nav-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}

.step-indicators {
    flex: 1;
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    padding: 0.25rem 0;
}

.step-indicators::-webkit-scrollbar {
    height: 4px;
}

.step-indicators::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.4);
    border-radius: 2px;
}

.step-indicator {
    flex-shrink: 0;
    padding: 0.75rem 1.25rem;
    background: rgba(255, 255, 255, 0.03);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
}

.step-indicator .step-number {
    font-size: 1.1rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.8);
}

.step-indicator .step-label {
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.5);
}

.step-indicator.active {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border-color: transparent;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
}

.step-indicator.active .step-number,
.step-indicator.active .step-label {
    color: white;
}

.step-indicator:hover:not(.active) {
    border-color: rgba(99, 102, 241, 0.5);
    background: rgba(99, 102, 241, 0.1);
    transform: translateY(-2px);
}

/* 스텝 카드 */
.step-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 2rem;
    animation: fadeIn 0.3s ease-out;
}

.step-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.step-meta {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.step-title {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.step-icon {
    font-size: 1.5rem;
    animation: rotate 2s linear infinite;
}

@keyframes rotate {
    from {
        transform: rotate(0deg);
    }

    to {
        transform: rotate(360deg);
    }
}

.tool-badge {
    padding: 0.5rem 1rem;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #a5b4fc;
    border-radius: 20px;
    font-size: 0.875rem;
    font-weight: 600;
}

.completeness-badge {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.25rem;
    border-radius: 12px;
    font-weight: 600;
}

.completeness-badge.complete {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: #86efac;
}

.completeness-badge.incomplete {
    background: rgba(234, 179, 8, 0.15);
    border: 1px solid rgba(234, 179, 8, 0.3);
    color: #fbbf24;
}

.badge-icon {
    font-size: 1.2rem;
}

/* SQL 하이라이트 */
.sql-highlight {
    margin-bottom: 2rem;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.5), 0 8px 24px rgba(99, 102, 241, 0.2);
    animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {

    0%,
    100% {
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.5), 0 8px 24px rgba(99, 102, 241, 0.2);
    }

    50% {
        box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.6), 0 8px 24px rgba(139, 92, 246, 0.3);
    }
}

.sql-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.25rem 1.5rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
}

.sql-header h3 {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 0;
    color: white;
    font-size: 1.1rem;
    font-weight: 600;
}

.sql-header svg {
    color: white;
}

.btn-copy {
    padding: 0.5rem 1rem;
    background: rgba(255, 255, 255, 0.2);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.3s;
}

.btn-copy:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: translateY(-1px);
}

.sql-content {
    background: #0d0d1a;
    padding: 1.5rem;
    max-height: 400px;
    overflow: auto;
}

.sql-content pre {
    margin: 0;
    color: #d4d4d4;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.95rem;
    line-height: 1.6;
    white-space: pre-wrap;
}

.sql-content code {
    color: #93c5fd;
}

.sql-change-indicator {
    padding: 0.75rem 1.5rem;
    background: rgba(234, 179, 8, 0.15);
    border-top: 1px solid rgba(234, 179, 8, 0.3);
}

.change-badge {
    color: #fbbf24;
    font-weight: 600;
    font-size: 0.875rem;
}

/* 추론 섹션 */
.reasoning-section {
    background: rgba(234, 179, 8, 0.1);
    border: 1px solid rgba(234, 179, 8, 0.2);
    border-left: 3px solid #eab308;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}

.reasoning-section h3 {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 0 0 1rem 0;
    color: #fbbf24;
    font-size: 1.1rem;
    font-weight: 600;
}

.reasoning-section svg {
    color: #eab308;
}

.reasoning-text {
    margin: 0;
    color: rgba(255, 255, 255, 0.85);
    line-height: 1.7;
    white-space: pre-wrap;
}

/* 상세 정보 섹션 */
.details-section {
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    overflow: hidden;
}

.details-section summary {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 1.25rem 1.5rem;
    background: rgba(255, 255, 255, 0.02);
    cursor: pointer;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.7);
    transition: all 0.3s;
    user-select: none;
}

.details-section summary:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #a5b4fc;
}

.details-section summary svg {
    transition: transform 0.3s;
}

.details-section[open] summary svg {
    transform: rotate(180deg);
}

.details-content {
    padding: 1.5rem;
    background: rgba(0, 0, 0, 0.2);
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.detail-block {
    padding: 1.25rem;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 8px;
    border-left: 4px solid #6366f1;
}

.detail-block h4 {
    margin: 0 0 1rem 0;
    color: rgba(255, 255, 255, 0.9);
    font-size: 1rem;
    font-weight: 600;
}

.completeness-info,
.tool-info {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.info-row {
    display: flex;
    gap: 0.75rem;
    align-items: baseline;
}

.info-row .label {
    font-weight: 600;
    color: rgba(255, 255, 255, 0.5);
    min-width: 80px;
}

.info-row .value {
    color: rgba(255, 255, 255, 0.9);
}

.info-row .value.code {
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    background: rgba(99, 102, 241, 0.15);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.875rem;
    color: #a5b4fc;
}

.nested-details {
    margin-top: 0.75rem;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    overflow: hidden;
}

.nested-details summary {
    padding: 0.75rem 1rem;
    background: rgba(255, 255, 255, 0.02);
    cursor: pointer;
    font-weight: 500;
    color: #a5b4fc;
    transition: background 0.3s;
}

.nested-details summary:hover {
    background: rgba(99, 102, 241, 0.1);
}

.nested-details pre {
    margin: 0;
    padding: 1rem;
    background: #0d0d1a;
    color: #d4d4d4;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.875rem;
    line-height: 1.6;
    overflow-x: auto;
    white-space: pre-wrap;
}

/* 트랜지션 */
.slide-enter-active,
.slide-leave-active {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-enter-from {
    opacity: 0;
    transform: translateX(30px);
}

.slide-leave-to {
    opacity: 0;
    transform: translateX(-30px);
}

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>
