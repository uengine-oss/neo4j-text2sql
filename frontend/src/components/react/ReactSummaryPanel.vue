<template>
    <div class="summary-panel">
        <div class="status-banner">
            <div class="status-text">
                <span :class="['status-label', statusClass]">
                    <span class="status-icon">{{ statusIcon }}</span>
                    {{ statusLabel }}
                </span>
                <span v-if="currentStep" class="step-indicator">Step {{ currentStep }}</span>
            </div>
            <div class="status-meta">
                <div class="meta-item">
                    <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd"
                            d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"
                            clip-rule="evenodd" />
                    </svg>
                    <span>남은 호출: <strong>{{ remainingToolCalls }}</strong></span>
                </div>
                <div v-if="latestToolName" class="meta-item tool-name">
                    <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                        <path
                            d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                    </svg>
                    <span>최근 도구: <strong>{{ latestToolName }}</strong></span>
                </div>
                <div v-if="sqlCompleteness" class="meta-item completeness">
                    <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clip-rule="evenodd" />
                    </svg>
                    <span>완성도: <strong>{{ sqlCompleteness.confidence_level }}</strong></span>
                </div>
                <div v-if="truncatedMissingInfo" class="meta-item missing-info" :title="sqlCompleteness?.missing_info">
                    <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd"
                            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z"
                            clip-rule="evenodd" />
                    </svg>
                    <span>누락: <strong>{{ truncatedMissingInfo }}</strong></span>
                </div>
                <div v-if="warnings.length" class="meta-item warning">
                    <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd"
                            d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                            clip-rule="evenodd" />
                    </svg>
                    <span>경고: <strong>{{ warnings.length }}</strong>건</span>
                </div>
            </div>
        </div>

        <div class="sql-section" v-if="partialSql">
            <div class="section-header">
                <h3>현재 SQL 스냅샷</h3>
                <button class="btn-copy" type="button" @click="copyPartialSql">
                    복사
                </button>
            </div>
            <div class="sql-code-container">
                <TransitionGroup name="sql-line" tag="pre" class="sql-code">
                    <code v-for="line in displayLines" :key="`line-${line.id}`" :class="['sql-line', line.status]">{{
                        line.content }}</code>
                </TransitionGroup>
            </div>
        </div>

        <div class="sql-section" v-if="finalSql">
            <div class="section-header">
                <h3>최종 SQL</h3>
                <button class="btn-copy" type="button" @click="copyFinalSql">
                    복사
                </button>
            </div>
            <pre><code>{{ finalSql }}</code></pre>
        </div>

        <div class="sql-section" v-if="validatedSql && validatedSql !== finalSql">
            <div class="section-header">
                <h3>검증된 SQL</h3>
                <button class="btn-copy" type="button" @click="copyValidatedSql">
                    복사
                </button>
            </div>
            <pre><code>{{ validatedSql }}</code></pre>
        </div>

        <div class="warning-section" v-if="warnings.length">
            <h3>경고</h3>
            <ul>
                <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
            </ul>
        </div>

        <div class="metadata-section" v-if="collectedMetadata">
            <details>
                <summary>수집된 메타데이터 보기</summary>
                <pre><code>{{ collectedMetadata }}</code></pre>
            </details>
        </div>

        <div class="result-section" v-if="executionResult">
            <ResultTable :data="executionResult" />
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ResultTable from '../ResultTable.vue'
import type { ReactExecutionResult, ReactStepModel } from '../../services/api'

const props = defineProps<{
    status: 'idle' | 'running' | 'needs_user_input' | 'completed' | 'error'
    partialSql: string | null
    finalSql: string | null
    validatedSql: string | null
    warnings: string[]
    executionResult: ReactExecutionResult | null
    collectedMetadata: string
    remainingToolCalls: number
    currentStep?: number
    isRunning?: boolean
    latestStep?: ReactStepModel | null
}>()

interface SqlLine {
    id: string
    content: string
    status: 'unchanged' | 'added' | 'removed' | 'modified'
}

const previousSql = ref<string>('')
const lineIdCounter = ref(0)
const displayLines = ref<SqlLine[]>([])

// SQL 라인 diff 계산
function computeDiff(oldSql: string, newSql: string): SqlLine[] {
    const oldLines = oldSql ? oldSql.split('\n') : []
    const newLines = newSql ? newSql.split('\n') : []
    const result: SqlLine[] = []

    // 간단한 라인 기반 diff
    const oldSet = new Set(oldLines)
    const newSet = new Set(newLines)

    // 삭제된 라인 (빨간색으로 표시 후 제거)
    const removedLines: SqlLine[] = []
    for (const line of oldLines) {
        if (!newSet.has(line)) {
            removedLines.push({
                id: `removed-${lineIdCounter.value++}`,
                content: line,
                status: 'removed'
            })
        }
    }

    // 새로운 라인들 처리
    for (const line of newLines) {
        if (!oldSet.has(line)) {
            // 새로 추가된 라인 (초록색)
            result.push({
                id: `added-${lineIdCounter.value++}`,
                content: line,
                status: 'added'
            })
        } else if (removedLines.length > 0 && removedLines[0].content.trim() === line.trim()) {
            // 변경된 라인 (노란색)
            result.push({
                id: `modified-${lineIdCounter.value++}`,
                content: line,
                status: 'modified'
            })
            removedLines.shift()
        } else {
            // 변경되지 않은 라인
            result.push({
                id: `unchanged-${lineIdCounter.value++}`,
                content: line,
                status: 'unchanged'
            })
        }
    }

    // 삭제된 라인을 마지막에 추가 (애니메이션 후 사라짐)
    return [...removedLines, ...result]
}

// partialSql 변경 감지
watch(() => props.partialSql, (newSql, oldSql) => {
    if (!newSql) {
        displayLines.value = []
        return
    }

    const prevSql = oldSql || previousSql.value
    if (prevSql !== newSql) {
        const diffResult = computeDiff(prevSql, newSql)
        displayLines.value = diffResult

        // 삭제된 라인을 1초 후에 제거
        setTimeout(() => {
            displayLines.value = displayLines.value.filter(line => line.status !== 'removed')
        }, 1000)

        // 2초 후 하이라이트 제거 (added, modified -> unchanged)
        setTimeout(() => {
            displayLines.value = displayLines.value.map(line => ({
                ...line,
                status: line.status === 'removed' ? 'removed' : 'unchanged'
            }))
        }, 2500)

        previousSql.value = newSql
    }
}, { immediate: true })

const statusLabel = computed(() => {
    switch (props.status) {
        case 'running':
            return '에이전트 실행 중'
        case 'needs_user_input':
            return '추가 입력 대기 중'
        case 'completed':
            return '완료'
        case 'error':
            return '오류 발생'
        default:
            return '대기'
    }
})

const statusClass = computed(() => {
    switch (props.status) {
        case 'running':
            return 'running'
        case 'needs_user_input':
            return 'waiting'
        case 'completed':
            return 'completed'
        case 'error':
            return 'error'
        default:
            return 'idle'
    }
})

const statusIcon = computed(() => {
    switch (props.status) {
        case 'running':
            return '⚡'
        case 'needs_user_input':
            return '💬'
        case 'completed':
            return '✓'
        case 'error':
            return '✕'
        default:
            return '○'
    }
})

const latestToolName = computed(() => {
    return props.latestStep?.tool_call?.name ?? null
})

const sqlCompleteness = computed(() => {
    return props.latestStep?.sql_completeness ?? null
})

const truncatedMissingInfo = computed(() => {
    if (!sqlCompleteness.value?.missing_info) return ''
    const info = sqlCompleteness.value.missing_info
    const maxLength = 30
    if (info.length > maxLength) {
        return info.substring(0, maxLength) + '...'
    }
    return info
})

function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text)
    alert('클립보드에 복사되었습니다!')
}

function copyPartialSql() {
    if (props.partialSql) {
        copyToClipboard(props.partialSql)
    }
}

function copyFinalSql() {
    if (props.finalSql) {
        copyToClipboard(props.finalSql)
    }
}

function copyValidatedSql() {
    if (props.validatedSql) {
        copyToClipboard(props.validatedSql)
    }
}
</script>

<style scoped>
.summary-panel {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.status-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 1.5rem 2rem;
    flex-wrap: wrap;
    gap: 1.5rem;
}

.status-text {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.status-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    border-radius: 12px;
    font-weight: 600;
    font-size: 1rem;
}

.status-icon {
    font-size: 1.2rem;
}

.status-label.idle {
    background: rgba(107, 114, 128, 0.2);
    color: #9ca3af;
}

.status-label.running {
    background: rgba(59, 130, 246, 0.2);
    color: #93c5fd;
    animation: statusPulse 2s ease-in-out infinite;
}

.status-label.waiting {
    background: rgba(234, 179, 8, 0.2);
    color: #fbbf24;
}

.status-label.completed {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
}

.status-label.error {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
}

@keyframes statusPulse {

    0%,
    100% {
        box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4);
    }

    50% {
        box-shadow: 0 0 0 6px rgba(59, 130, 246, 0);
    }
}

.step-indicator {
    padding: 0.5rem 1rem;
    background: rgba(99, 102, 241, 0.15);
    border: 2px solid rgba(99, 102, 241, 0.4);
    border-radius: 20px;
    color: #a5b4fc;
    font-weight: 600;
    font-size: 0.9rem;
}

.status-meta {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    align-items: center;
}

.meta-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.95rem;
    max-width: 250px;
    white-space: nowrap;
    overflow: hidden;
}

.meta-item span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.meta-item svg {
    color: rgba(255, 255, 255, 0.4);
    flex-shrink: 0;
}

.meta-item.warning {
    color: #fbbf24;
}

.meta-item.warning svg {
    color: #fbbf24;
}

.meta-item.tool-name {
    color: #a5b4fc;
}

.meta-item.tool-name svg {
    color: #a5b4fc;
}

.meta-item.completeness {
    color: #86efac;
}

.meta-item.completeness svg {
    color: #86efac;
}

.meta-item.missing-info {
    color: #93c5fd;
    cursor: help;
    max-width: 200px;
}

.meta-item.missing-info svg {
    color: #93c5fd;
}

.meta-item strong {
    color: rgba(255, 255, 255, 0.9);
    font-weight: 700;
}

.sql-section {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.25rem 1.5rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
}

.section-header h3 {
    margin: 0;
    color: white;
    font-size: 1.1rem;
    font-weight: 600;
}

.btn-copy {
    padding: 0.5rem 1rem;
    background: rgba(255, 255, 255, 0.2);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
    transition: all 0.3s;
}

.btn-copy:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: translateY(-1px);
}

.sql-code-container {
    background: #1e1e1e;
    overflow-x: auto;
    max-height: 400px;
    overflow-y: auto;
}

.sql-code {
    padding: 1.5rem;
    margin: 0;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 0.95rem;
    line-height: 1.6;
    white-space: pre-wrap;
    color: #d4d4d4;
    display: block;
}

.sql-line {
    display: block;
    padding: 0.1rem 0.5rem;
    margin: 0.05rem 0;
    border-radius: 3px;
    transition: all 0.5s ease-out;
    color: #9cdcfe;
}

.sql-line.unchanged {
    background: transparent;
}

.sql-line.added {
    background: rgba(34, 197, 94, 0.25);
    border-left: 3px solid #22c55e;
    animation: slideInGreen 0.5s ease-out, glowGreen 1.5s ease-in-out;
}

.sql-line.removed {
    background: rgba(239, 68, 68, 0.25);
    border-left: 3px solid #ef4444;
    text-decoration: line-through;
    opacity: 0.7;
    animation: slideOutRed 0.8s ease-out forwards;
}

.sql-line.modified {
    background: rgba(234, 179, 8, 0.25);
    border-left: 3px solid #eab308;
    animation: slideInYellow 0.5s ease-out, glowYellow 1.5s ease-in-out;
}

/* 라인 추가 애니메이션 */
@keyframes slideInGreen {
    0% {
        opacity: 0;
        transform: translateX(-20px);
        background: rgba(34, 197, 94, 0.6);
    }

    100% {
        opacity: 1;
        transform: translateX(0);
        background: rgba(34, 197, 94, 0.25);
    }
}

@keyframes glowGreen {
    0% {
        box-shadow: 0 0 10px rgba(34, 197, 94, 0.6);
    }

    50% {
        box-shadow: 0 0 20px rgba(34, 197, 94, 0.4);
    }

    100% {
        box-shadow: none;
    }
}

/* 라인 삭제 애니메이션 */
@keyframes slideOutRed {
    0% {
        opacity: 1;
        transform: translateX(0);
        background: rgba(239, 68, 68, 0.4);
        max-height: 100px;
        margin: 0.05rem 0;
        padding: 0.1rem 0.5rem;
    }

    50% {
        opacity: 0.5;
        background: rgba(239, 68, 68, 0.6);
    }

    100% {
        opacity: 0;
        transform: translateX(20px);
        background: rgba(239, 68, 68, 0);
        max-height: 0;
        margin: 0;
        padding: 0 0.5rem;
    }
}

/* 라인 수정 애니메이션 */
@keyframes slideInYellow {
    0% {
        opacity: 0;
        transform: scale(0.98);
        background: rgba(234, 179, 8, 0.5);
    }

    100% {
        opacity: 1;
        transform: scale(1);
        background: rgba(234, 179, 8, 0.25);
    }
}

@keyframes glowYellow {
    0% {
        box-shadow: 0 0 10px rgba(234, 179, 8, 0.5);
    }

    50% {
        box-shadow: 0 0 15px rgba(234, 179, 8, 0.3);
    }

    100% {
        box-shadow: none;
    }
}

/* TransitionGroup 애니메이션 */
.sql-line-enter-active {
    transition: all 0.5s ease-out;
}

.sql-line-leave-active {
    transition: all 0.8s ease-out;
    position: absolute;
}

.sql-line-enter-from {
    opacity: 0;
    transform: translateX(-20px);
}

.sql-line-leave-to {
    opacity: 0;
    transform: translateX(20px);
}

.sql-line-move {
    transition: transform 0.5s ease-out;
}

pre {
    background: #1e1e1e;
    padding: 1.5rem;
    margin: 0;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 0.95rem;
    line-height: 1.6;
    white-space: pre-wrap;
    overflow-x: auto;
    color: #d4d4d4;
    max-height: 400px;
}

pre code {
    color: #9cdcfe;
}

.warning-section {
    background: rgba(234, 179, 8, 0.1);
    border-left: 4px solid #eab308;
    padding: 1.5rem;
    border-radius: 12px;
}

.warning-section h3 {
    margin: 0 0 1rem 0;
    color: #fbbf24;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.warning-section h3::before {
    content: '⚠️';
    font-size: 1.2rem;
}

.warning-section ul {
    margin: 0;
    padding-left: 1.5rem;
    color: rgba(255, 255, 255, 0.8);
    line-height: 1.6;
}

.warning-section li {
    margin-bottom: 0.5rem;
}

.metadata-section details {
    background: rgba(255, 255, 255, 0.03);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    overflow: hidden;
}

.metadata-section summary {
    padding: 1.25rem 1.5rem;
    cursor: pointer;
    color: #a5b4fc;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.02);
    transition: background 0.3s;
    user-select: none;
}

.metadata-section summary:hover {
    background: rgba(255, 255, 255, 0.05);
}

.metadata-section pre {
    margin: 0;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.result-section {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 1.5rem;
}

/* 반응형 - 메타 아이템 크기 조정 */
@media (max-width: 1200px) {
    .meta-item {
        max-width: 180px;
        font-size: 0.85rem;
    }

    .meta-item.missing-info {
        max-width: 150px;
    }

    .status-meta {
        gap: 1rem;
    }
}

@media (max-width: 768px) {
    .meta-item {
        max-width: 150px;
        font-size: 0.8rem;
    }

    .meta-item.missing-info {
        max-width: 120px;
    }

    .status-meta {
        gap: 0.75rem;
    }
}
</style>
