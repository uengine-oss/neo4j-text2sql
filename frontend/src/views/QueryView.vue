<template>
  <div class="query-view">
    <div class="header">
      <h1>🤖 Neo4j Text2SQL</h1>
      <p>자연어로 데이터베이스에 질문하세요</p>
    </div>

    <QueryInput @submit="handleQuery" :loading="queryStore.loading" />

    <div v-if="queryStore.error" class="error-message">
      <strong>오류:</strong> {{ queryStore.error }}
    </div>

    <!-- Error SQL preview -->
    <div v-if="queryStore.errorSql" class="sql-section" style="margin-top: 1rem;">
      <div class="section-header">
        <h3>실행 시도한 SQL (오류 발생)</h3>
        <button @click="copyErrorSql" class="btn-copy">복사</button>
      </div>
      <pre><code>{{ queryStore.errorSql }}</code></pre>
    </div>

    <div v-if="queryStore.loading" class="loading">
      <div class="spinner"></div>
      <p>SQL 생성 및 실행 중...</p>
    </div>

    <div v-if="queryStore.hasResult" class="results">
      <!-- SQL -->
      <div class="sql-section">
        <div class="section-header">
          <h3>생성된 SQL</h3>
          <button @click="copySql" class="btn-copy">복사</button>
        </div>
        <pre><code>{{ queryStore.currentResponse?.sql }}</code></pre>
      </div>

      <!-- Provenance -->
      <div class="provenance-section">
        <details>
          <summary><strong>출처 정보 (Provenance)</strong></summary>
          <div class="provenance-content">
            <div>
              <strong>사용된 테이블:</strong>
              <span class="tags">
                <span v-for="table in queryStore.currentResponse?.provenance.tables" :key="table" class="tag">
                  {{ table }}
                </span>
              </span>
            </div>
            <div>
              <strong>사용된 컬럼:</strong>
              <span class="tags">
                <span v-for="col in queryStore.currentResponse?.provenance.columns.slice(0, 10)" :key="col" class="tag">
                  {{ col }}
                </span>
              </span>
            </div>
            <div>
              <strong>벡터 매칭 점수:</strong>
              <span class="tags">
                <span v-for="match in queryStore.currentResponse?.provenance.vector_matches" :key="match.node" class="tag">
                  {{ match.node }} ({{ match.score.toFixed(2) }})
                </span>
              </span>
            </div>
          </div>
        </details>
      </div>

      <!-- Performance -->
      <div class="perf-section">
        <div class="perf-item">
          <span>임베딩:</span> <strong>{{ queryStore.currentResponse?.perf.embedding_ms.toFixed(0) }}ms</strong>
        </div>
        <div class="perf-item">
          <span>그래프 검색:</span> <strong>{{ queryStore.currentResponse?.perf.graph_search_ms.toFixed(0) }}ms</strong>
        </div>
        <div class="perf-item">
          <span>LLM:</span> <strong>{{ queryStore.currentResponse?.perf.llm_ms.toFixed(0) }}ms</strong>
        </div>
        <div class="perf-item">
          <span>SQL 실행:</span> <strong>{{ queryStore.currentResponse?.perf.sql_ms.toFixed(0) }}ms</strong>
        </div>
        <div class="perf-item total">
          <span>총:</span> <strong>{{ queryStore.currentResponse?.perf.total_ms.toFixed(0) }}ms</strong>
        </div>
      </div>

      <!-- Results Table -->
      <ResultTable v-if="queryStore.currentResponse" :data="queryStore.currentResponse.table" />

      <!-- Charts -->
      <ChartViewer 
        v-if="queryStore.currentResponse && queryStore.currentResponse.charts.length > 0"
        :charts="queryStore.currentResponse.charts"
        :table-data="queryStore.currentResponse.table"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import ChartViewer from '../components/ChartViewer.vue'
import QueryInput from '../components/QueryInput.vue'
import ResultTable from '../components/ResultTable.vue'
import { useQueryStore } from '../stores/query'

const queryStore = useQueryStore()

async function handleQuery(question: string) {
  await queryStore.ask(question)
}

function copySql() {
  if (queryStore.currentResponse?.sql) {
    navigator.clipboard.writeText(queryStore.currentResponse.sql)
    alert('SQL이 클립보드에 복사되었습니다!')
  }
}

function copyErrorSql() {
  if (queryStore.errorSql) {
    navigator.clipboard.writeText(queryStore.errorSql)
    alert('오류 SQL이 클립보드에 복사되었습니다!')
  }
}
</script>

<style scoped>
.query-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 2rem;
}

.header {
  text-align: center;
  margin-bottom: 3rem;
}

.header h1 {
  margin: 0 0 0.5rem 0;
  font-size: 2.5rem;
  color: #333;
}

.header p {
  margin: 0;
  font-size: 1.1rem;
  color: #666;
}

.error-message {
  background: #ffebee;
  border-left: 4px solid #f44336;
  padding: 1rem;
  margin-bottom: 2rem;
  border-radius: 4px;
  color: #c62828;
}

.loading {
  text-align: center;
  padding: 3rem;
}

.spinner {
  width: 50px;
  height: 50px;
  margin: 0 auto 1rem;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #4CAF50;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.results {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.sql-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h3 {
  margin: 0;
  color: #333;
}

.btn-copy {
  padding: 0.5rem 1rem;
  background: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-copy:hover {
  background: #1976D2;
}

.sql-section pre {
  background: #f5f5f5;
  padding: 1rem;
  border-radius: 4px;
  overflow-x: auto;
  margin: 0;
}

.sql-section code {
  font-family: 'Courier New', monospace;
  font-size: 0.95rem;
  line-height: 1.5;
}

.provenance-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.provenance-section details summary {
  cursor: pointer;
  user-select: none;
  color: #333;
}

.provenance-content {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.provenance-content > div {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tag {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: #e3f2fd;
  border-radius: 12px;
  font-size: 0.85rem;
  color: #1976D2;
}

.perf-section {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.perf-item {
  flex: 1;
  min-width: 150px;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.perf-item.total {
  background: #e8f5e9;
  border: 2px solid #4CAF50;
}

.perf-item span {
  color: #666;
  font-size: 0.9rem;
}

.perf-item strong {
  color: #333;
  font-size: 1.1rem;
}
</style>

