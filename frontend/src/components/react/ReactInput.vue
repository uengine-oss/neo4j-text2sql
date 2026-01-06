<template>
    <div class="react-input">
        <!-- 헤더 (쿼리 입력 영역에만 표시) -->
        <div v-if="!waitingForUser" class="input-header">
            <h1>🧠 Neo4j ReAct Text2SQL</h1>
            <p>ReAct 에이전트의 단계별 추론 과정을 실시간으로 확인하세요</p>
        </div>

        <div v-if="!waitingForUser" class="input-container">
            <textarea v-model="question" @keydown.ctrl.enter.prevent="submitQuestion"
                placeholder="질문을 입력하세요... 예: '지난 분기 매출 Top 5 제품을 보여줘'" rows="3" :disabled="loading"></textarea>
            <div class="action-buttons">
                <button v-if="!loading" class="btn-primary" @click="submitQuestion" :disabled="!canSubmitQuestion">
                    <span class="btn-icon">🚀</span>
                    <span class="btn-text">ReAct 실행</span>
                </button>
                <button v-if="loading" class="btn-secondary" type="button" @click="emit('cancel')">
                    <span class="btn-icon">✕</span>
                    <span class="btn-text">중단</span>
                </button>
            </div>
        </div>

        <!-- 추천 쿼리 목록 -->
        <div v-if="!waitingForUser && hasQueryHistory" class="query-suggestions">
            <div class="suggestions-header">
                <div class="suggestions-title">
                    <span class="suggestions-icon">📜</span>
                    <span>이전 쿼리</span>
                </div>
                <button 
                    v-if="successfulQueries.length > 0" 
                    class="clear-history-btn" 
                    type="button" 
                    @click="handleClearHistory"
                    title="히스토리 전체 삭제"
                >
                    <span>🗑️</span>
                </button>
            </div>
            <div class="suggestions-list">
                <TransitionGroup name="suggestion">
                    <button 
                        v-for="item in displayedQueries" 
                        :key="item.id"
                        class="suggestion-item"
                        :class="{ success: item.success, failed: !item.success }"
                        type="button"
                        @click="selectQuery(item.question)"
                        :disabled="loading"
                    >
                        <span class="suggestion-status">{{ item.success ? '✓' : '✕' }}</span>
                        <span class="suggestion-text">{{ truncateQuery(item.question) }}</span>
                        <span class="suggestion-time">{{ formatTime(item.timestamp) }}</span>
                        <button 
                            class="suggestion-remove" 
                            type="button" 
                            @click.stop="removeQuery(item.id)"
                            title="삭제"
                        >×</button>
                    </button>
                </TransitionGroup>
            </div>
            <button 
                v-if="recentQueries.length > 5 && !showAllQueries" 
                class="show-more-queries" 
                type="button"
                @click="showAllQueries = true"
            >
                더 보기 ({{ recentQueries.length - 5 }}개)
            </button>
            <button 
                v-if="showAllQueries" 
                class="show-more-queries" 
                type="button"
                @click="showAllQueries = false"
            >
                접기
            </button>
        </div>

        <!-- 고급 설정 (쿼리 입력 시에만 표시) -->
        <div v-if="!waitingForUser" class="settings-section">
            <button class="settings-toggle" type="button" @click="showSettings = !showSettings">
                <span class="toggle-icon">⚙️</span>
                <span class="toggle-text">고급 설정</span>
                <span class="toggle-arrow" :class="{ expanded: showSettings }">▼</span>
            </button>
            <transition name="slide">
                <div v-if="showSettings" class="settings-panel">
                    <div class="setting-item">
                        <label for="maxToolCalls">
                            <span class="setting-label">최대 도구 호출 횟수</span>
                            <span class="setting-hint">에이전트가 사용할 수 있는 도구 호출 수 (1~100)</span>
                        </label>
                        <div class="setting-input-group">
                            <input id="maxToolCalls" v-model.number="maxToolCalls" type="number" min="1" max="100"
                                :disabled="loading" />
                            <span class="setting-unit">회</span>
                        </div>
                    </div>
                    <div class="setting-item">
                        <label for="maxSqlSeconds">
                            <span class="setting-label">SQL 실행 제한 시간</span>
                            <span class="setting-hint">최종 SQL 실행 최대 허용 시간 (1~3600초)</span>
                        </label>
                        <div class="setting-input-group">
                            <input id="maxSqlSeconds" v-model.number="maxSqlSeconds" type="number" min="1" max="3600"
                                :disabled="loading" />
                            <span class="setting-unit">초</span>
                        </div>
                    </div>
                </div>
            </transition>
        </div>

        <div v-else class="follow-up-wrapper">
            <div class="follow-up-question">
                <strong>에이전트 질문:</strong>
                <p>{{ questionToUser }}</p>
            </div>
            <div class="follow-up-container">
                <textarea v-model="userResponse" @keydown.ctrl.enter.prevent="submitUserResponse"
                    placeholder="추가 정보를 입력해주세요. (Ctrl+Enter 전송)" rows="3" :disabled="loading"></textarea>
                <div class="action-buttons">
                    <button class="btn-secondary" type="button" @click="emit('cancel')">
                        <span class="btn-icon">✕</span>
                        <span class="btn-text">중단</span>
                    </button>
                    <button class="btn-primary" @click="submitUserResponse" :disabled="!canSubmitUserResponse">
                        <span class="btn-icon">📤</span>
                        <span class="btn-text">{{ loading ? '전송 중...' : '답변 보내기' }}</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useReactStore, type QueryHistoryItem } from '../../stores/react'

export interface ReactStartOptions {
    maxToolCalls: number
    maxSqlSeconds: number
}

const emit = defineEmits<{
    start: [question: string, options: ReactStartOptions]
    respond: [answer: string]
    cancel: []
}>()

const props = defineProps<{
    loading: boolean
    waitingForUser: boolean
    questionToUser: string | null
    currentQuestion: string
}>()

const reactStore = useReactStore()

const question = ref(props.currentQuestion ?? '')
const userResponse = ref('')
const showSettings = ref(false)
const showAllQueries = ref(false)
const maxToolCalls = ref(30)
const maxSqlSeconds = ref(60)

const waitingForUser = computed(() => props.waitingForUser)

const canSubmitQuestion = computed(() => !!question.value.trim() && !props.loading)
const canSubmitUserResponse = computed(
    () => !!userResponse.value.trim() && !props.loading
)

// 쿼리 히스토리 관련
const recentQueries = computed(() => reactStore.recentQueries)
const successfulQueries = computed(() => reactStore.successfulQueries)
const hasQueryHistory = computed(() => recentQueries.value.length > 0)

const displayedQueries = computed(() => 
    showAllQueries.value ? recentQueries.value : recentQueries.value.slice(0, 5)
)

watch(
    () => props.currentQuestion,
    newVal => {
        if (!props.loading && !waitingForUser.value) {
            question.value = newVal
        }
    }
)

watch(waitingForUser, isWaiting => {
    if (!isWaiting) {
        userResponse.value = ''
    }
})

function submitQuestion() {
    if (!canSubmitQuestion.value) return
    const trimmed = question.value.trim()
    question.value = trimmed
    emit('start', trimmed, {
        maxToolCalls: maxToolCalls.value,
        maxSqlSeconds: maxSqlSeconds.value
    })
}

function submitUserResponse() {
    if (!canSubmitUserResponse.value) return
    const trimmed = userResponse.value.trim()
    userResponse.value = trimmed
    emit('respond', trimmed)
}

function selectQuery(queryText: string) {
    question.value = queryText
}

function removeQuery(id: string) {
    reactStore.removeFromHistory(id)
}

function handleClearHistory() {
    if (confirm('모든 쿼리 히스토리를 삭제하시겠습니까?')) {
        reactStore.clearHistory()
    }
}

function truncateQuery(text: string): string {
    const maxLen = 60
    return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

function formatTime(timestamp: number): string {
    const now = Date.now()
    const diff = now - timestamp
    
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)
    
    if (minutes < 1) return '방금 전'
    if (minutes < 60) return `${minutes}분 전`
    if (hours < 24) return `${hours}시간 전`
    if (days < 7) return `${days}일 전`
    
    return new Date(timestamp).toLocaleDateString('ko-KR', {
        month: 'short',
        day: 'numeric'
    })
}
</script>

<style scoped>
.react-input {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    width: 100%;
}

.input-header {
    text-align: center;
    animation: fadeInDown 0.5s ease-out;
}

.input-header h1 {
    margin: 0 0 0.75rem 0;
    font-size: 2.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.input-header p {
    margin: 0;
    font-size: 1rem;
    color: rgba(255, 255, 255, 0.6);
    line-height: 1.6;
}

@keyframes fadeInDown {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.input-container,
.follow-up-container {
    display: flex;
    flex-direction: row;
    gap: 1rem;
    align-items: stretch;
}

.follow-up-wrapper {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

textarea {
    flex: 1;
    padding: 1rem 1.25rem;
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    font-size: 1rem;
    font-family: inherit;
    resize: none;
    height: 240px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    background: rgba(0, 0, 0, 0.3);
    color: rgba(255, 255, 255, 0.9);
    line-height: 1.6;
}

textarea::placeholder {
    color: rgba(255, 255, 255, 0.4);
}

textarea:focus {
    outline: none;
    border-color: rgba(99, 102, 241, 0.5);
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15);
    background: rgba(0, 0, 0, 0.4);
}

textarea:disabled {
    background: rgba(0, 0, 0, 0.2);
    cursor: not-allowed;
    opacity: 0.7;
}

.action-buttons {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    align-items: stretch;
    min-width: 150px;
}

/* 쿼리 입력 시 (버튼 1개) - textarea와 높이 맞춤 */
.input-container .action-buttons {
    height: 240px;
}

/* 후속 질문 시 (버튼 2개) - 더 많은 공간 필요 */
.follow-up-container .action-buttons {
    min-height: 120px;
}

.follow-up-container textarea {
    min-height: 120px;
}

.btn-primary {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 1rem 0.75rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
    position: relative;
    overflow: hidden;
    white-space: nowrap;
}

.btn-primary .btn-icon {
    font-size: 1.8rem;
    line-height: 1;
}

.btn-primary .btn-text {
    font-size: 0.9rem;
    line-height: 1.3;
    font-weight: 600;
}

.btn-primary::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
    transition: left 0.5s;
}

.btn-primary:hover:not(:disabled)::before {
    left: 100%;
}

.btn-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 25px rgba(99, 102, 241, 0.5);
}

.btn-primary:active:not(:disabled) {
    transform: translateY(0);
}

.btn-primary:disabled {
    background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
    cursor: not-allowed;
    box-shadow: none;
    opacity: 0.6;
}

.btn-secondary {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 1rem 0.75rem;
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.8);
    border: 2px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    white-space: nowrap;
}

.btn-secondary .btn-icon {
    font-size: 1.5rem;
    line-height: 1;
}

.btn-secondary .btn-text {
    font-size: 0.9rem;
    line-height: 1.3;
    font-weight: 500;
}

.btn-secondary:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(239, 68, 68, 0.5);
    color: #fca5a5;
    transform: translateY(-2px);
}

.follow-up-question {
    background: rgba(234, 179, 8, 0.15);
    border-left: 4px solid #eab308;
    padding: 1.25rem;
    border-radius: 12px;
    color: #fbbf24;
}

.follow-up-question strong {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.05rem;
    color: #fbbf24;
}

.follow-up-question strong::before {
    content: '💬';
    font-size: 1.2rem;
}

.follow-up-question p {
    margin: 0.75rem 0 0 0;
    white-space: pre-wrap;
    line-height: 1.6;
    color: rgba(255, 255, 255, 0.8);
}

/* 추천 쿼리 섹션 */
.query-suggestions {
    margin-top: 1rem;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
}

.suggestions-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.suggestions-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: rgba(255, 255, 255, 0.7);
    font-size: 0.85rem;
    font-weight: 600;
}

.suggestions-icon {
    font-size: 1rem;
}

.clear-history-btn {
    padding: 0.375rem 0.5rem;
    background: transparent;
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 6px;
    color: rgba(239, 68, 68, 0.7);
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s ease;
}

.clear-history-btn:hover {
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.5);
    color: #fca5a5;
}

.suggestions-list {
    display: flex;
    flex-direction: column;
    max-height: 300px;
    overflow-y: auto;
}

.suggestions-list::-webkit-scrollbar {
    width: 4px;
}

.suggestions-list::-webkit-scrollbar-thumb {
    background: rgba(99, 102, 241, 0.4);
    border-radius: 2px;
}

.suggestion-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: transparent;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    color: rgba(255, 255, 255, 0.8);
    font-size: 0.85rem;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s ease;
}

.suggestion-item:last-child {
    border-bottom: none;
}

.suggestion-item:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.1);
}

.suggestion-item:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.suggestion-status {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    font-size: 0.7rem;
    font-weight: 700;
}

.suggestion-item.success .suggestion-status {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
}

.suggestion-item.failed .suggestion-status {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
}

.suggestion-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.suggestion-time {
    flex-shrink: 0;
    color: rgba(255, 255, 255, 0.4);
    font-size: 0.75rem;
}

.suggestion-remove {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    color: rgba(255, 255, 255, 0.4);
    font-size: 1rem;
    line-height: 1;
    cursor: pointer;
    transition: all 0.2s ease;
    opacity: 0;
}

.suggestion-item:hover .suggestion-remove {
    opacity: 1;
}

.suggestion-remove:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.5);
    color: #fca5a5;
}

.show-more-queries {
    width: 100%;
    padding: 0.625rem 1rem;
    background: rgba(99, 102, 241, 0.05);
    border: none;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    color: #a5b4fc;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
}

.show-more-queries:hover {
    background: rgba(99, 102, 241, 0.1);
    color: white;
}

/* Suggestion 트랜지션 */
.suggestion-enter-active,
.suggestion-leave-active {
    transition: all 0.3s ease;
}

.suggestion-enter-from {
    opacity: 0;
    transform: translateX(-10px);
}

.suggestion-leave-to {
    opacity: 0;
    transform: translateX(10px);
}

/* 고급 설정 섹션 */
.settings-section {
    margin-top: 0.5rem;
}

.settings-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6rem 1rem;
    background: transparent;
    border: 1px dashed rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s ease;
    width: 100%;
    justify-content: center;
}

.settings-toggle:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.3);
    color: rgba(255, 255, 255, 0.8);
}

.toggle-icon {
    font-size: 1rem;
}

.toggle-text {
    font-weight: 500;
}

.toggle-arrow {
    font-size: 0.7rem;
    transition: transform 0.2s ease;
    margin-left: auto;
}

.toggle-arrow.expanded {
    transform: rotate(180deg);
}

.settings-panel {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1rem;
    margin-top: 0.75rem;
    padding: 1.25rem;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
}

.setting-item {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.setting-item label {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
}

.setting-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
}

.setting-hint {
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.5);
}

.setting-input-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.setting-input-group input {
    flex: 1;
    padding: 0.6rem 0.75rem;
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    font-size: 0.9rem;
    font-family: inherit;
    transition: all 0.2s ease;
    background: rgba(0, 0, 0, 0.3);
    color: white;
    max-width: 120px;
}

.setting-input-group input:focus {
    outline: none;
    border-color: rgba(99, 102, 241, 0.5);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.setting-input-group input:disabled {
    background: rgba(0, 0, 0, 0.2);
    cursor: not-allowed;
    opacity: 0.6;
}

.setting-unit {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.5);
    min-width: 24px;
}

/* Slide 트랜지션 */
.slide-enter-active,
.slide-leave-active {
    transition: all 0.25s ease;
    overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
    opacity: 0;
    max-height: 0;
    margin-top: 0;
    padding: 0 1.25rem;
}

.slide-enter-to,
.slide-leave-from {
    opacity: 1;
    max-height: 200px;
}

/* 반응형 디자인 */
@media (max-width: 768px) {
    .input-header h1 {
        font-size: 1.75rem;
    }

    .input-header p {
        font-size: 0.9rem;
    }

    .input-container,
    .follow-up-container {
        flex-direction: column;
    }

    textarea {
        height: 100px;
    }

    .action-buttons {
        flex-direction: row;
        min-width: unset;
        height: auto;
    }

    .btn-primary,
    .btn-secondary {
        flex: 1;
        flex-direction: row;
        justify-content: center;
        padding: 0.85rem 1rem;
        gap: 0.75rem;
    }

    .btn-primary .btn-icon,
    .btn-secondary .btn-icon {
        font-size: 1.2rem;
    }

    .btn-primary .btn-text,
    .btn-secondary .btn-text {
        font-size: 0.9rem;
    }

    .btn-primary:hover:not(:disabled),
    .btn-secondary:hover:not(:disabled) {
        transform: translateY(-2px);
    }
}
</style>
