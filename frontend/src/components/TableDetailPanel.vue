<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { ColumnInfo, TableInfo } from '../services/api'
import { useSchemaCanvasStore } from '../stores/schemaCanvas'

const store = useSchemaCanvasStore()

// Edit states
const isEditingDescription = ref(false)
const editingColumnName = ref<string | null>(null)

// Edit forms
const tableDescForm = reactive({
  description: ''
})

const columnDescForm = reactive({
  description: ''
})

// New relationship form
const showRelationshipForm = ref(false)
const newRelationship = reactive({
  from_column: '',
  to_table: '',
  to_column: '',
  description: ''
})

// Computed
const table = computed(() => store.selectedTable)
const columns = computed(() => store.selectedTableColumns)
const isOpen = computed(() => store.isDetailPanelOpen)

const availableTables = computed(() => {
  return store.allTables.filter(t => t.name !== table.value?.name)
})

const targetTableColumns = computed(() => {
  if (!newRelationship.to_table) return []
  return store.tableColumnsCache[newRelationship.to_table] || []
})

// Watchers
watch(() => store.selectedTable, (newTable) => {
  if (newTable) {
    tableDescForm.description = newTable.description || ''
  }
  isEditingDescription.value = false
  editingColumnName.value = null
})

watch(() => newRelationship.to_table, async (tableName) => {
  if (tableName && !store.tableColumnsCache[tableName]) {
    await store.loadTableColumns(tableName)
  }
  newRelationship.to_column = ''
})

// Methods
function closePanel() {
  store.closeDetailPanel()
}

function startEditDescription() {
  tableDescForm.description = table.value?.description || ''
  isEditingDescription.value = true
}

function cancelEditDescription() {
  isEditingDescription.value = false
}

async function saveDescription() {
  if (!table.value) return
  
  try {
    await store.updateTableDescription(table.value.name, tableDescForm.description)
    isEditingDescription.value = false
  } catch (error) {
    alert('테이블 설명 저장에 실패했습니다.')
  }
}

function startEditColumn(columnName: string) {
  const col = columns.value.find(c => c.name === columnName)
  if (col) {
    columnDescForm.description = col.description || ''
    editingColumnName.value = columnName
  }
}

function cancelEditColumn() {
  editingColumnName.value = null
}

async function saveColumnDescription(columnName: string) {
  if (!table.value) return
  
  try {
    await store.updateColumnDescription(table.value.name, columnName, columnDescForm.description)
    editingColumnName.value = null
  } catch (error) {
    alert('컬럼 설명 저장에 실패했습니다.')
  }
}

function toggleRelationshipForm() {
  showRelationshipForm.value = !showRelationshipForm.value
  if (showRelationshipForm.value) {
    resetRelationshipForm()
  }
}

function resetRelationshipForm() {
  newRelationship.from_column = ''
  newRelationship.to_table = ''
  newRelationship.to_column = ''
  newRelationship.description = ''
}

async function addRelationship() {
  if (!table.value || !newRelationship.from_column || !newRelationship.to_table || !newRelationship.to_column) {
    return
  }
  
  try {
    await store.addRelationship({
      from_table: table.value.name,
      from_schema: table.value.schema || 'public',
      from_column: newRelationship.from_column,
      to_table: newRelationship.to_table,
      to_schema: 'public',
      to_column: newRelationship.to_column,
      description: newRelationship.description
    })
    
    resetRelationshipForm()
    showRelationshipForm.value = false
  } catch (error) {
    alert('릴레이션 추가에 실패했습니다.')
  }
}

function getColumnIcon(col: ColumnInfo): string {
  if (col.name.toLowerCase() === 'id') return '🔑'
  if (col.name.endsWith('_id')) return '🔗'
  return '📝'
}

function getColumnTypeDisplay(dtype: string): string {
  return dtype.toUpperCase()
}
</script>

<template>
  <Transition name="slide">
    <div v-if="isOpen && table" class="detail-panel">
      <!-- Header -->
      <div class="detail-panel__header">
        <div class="detail-panel__title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="3" y1="9" x2="21" y2="9"></line>
            <line x1="9" y1="21" x2="9" y2="9"></line>
          </svg>
          <span>{{ table.name }}</span>
        </div>
        <button class="detail-panel__close" @click="closePanel">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      
      <!-- Content -->
      <div class="detail-panel__content">
        <!-- Table Info Section -->
        <section class="detail-section">
          <div class="detail-section__header">
            <h3>테이블 정보</h3>
            <span class="detail-section__badge">{{ table.schema }}</span>
          </div>
          
          <!-- Description -->
          <div class="detail-field">
            <label>설명</label>
            <div v-if="isEditingDescription" class="detail-field__edit">
              <textarea 
                v-model="tableDescForm.description"
                placeholder="테이블 설명을 입력하세요..."
                rows="3"
              ></textarea>
              <div class="detail-field__actions">
                <button class="btn btn--primary btn--sm" @click="saveDescription">저장</button>
                <button class="btn btn--ghost btn--sm" @click="cancelEditDescription">취소</button>
              </div>
            </div>
            <div v-else class="detail-field__display" @click="startEditDescription">
              <span v-if="table.description">{{ table.description }}</span>
              <span v-else class="placeholder">설명을 추가하려면 클릭하세요</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
            </div>
          </div>
        </section>
        
        <!-- Columns Section -->
        <section class="detail-section">
          <div class="detail-section__header">
            <h3>컬럼 ({{ columns.length }})</h3>
          </div>
          
          <div class="columns-list">
            <div 
              v-for="col in columns" 
              :key="col.name"
              class="column-item"
              :class="{ 
                'is-pk': col.name.toLowerCase() === 'id',
                'is-fk': col.name.endsWith('_id') && col.name.toLowerCase() !== 'id'
              }"
            >
              <div class="column-item__header">
                <span class="column-item__icon">{{ getColumnIcon(col) }}</span>
                <span class="column-item__name">{{ col.name }}</span>
                <span class="column-item__type">{{ getColumnTypeDisplay(col.dtype) }}</span>
                <span v-if="!col.nullable" class="column-item__required" title="NOT NULL">*</span>
              </div>
              
              <div v-if="editingColumnName === col.name" class="column-item__edit">
                <textarea 
                  v-model="columnDescForm.description"
                  placeholder="컬럼 설명..."
                  rows="2"
                ></textarea>
                <div class="column-item__actions">
                  <button class="btn btn--primary btn--xs" @click="saveColumnDescription(col.name)">저장</button>
                  <button class="btn btn--ghost btn--xs" @click="cancelEditColumn">취소</button>
                </div>
              </div>
              <div v-else class="column-item__desc" @click="startEditColumn(col.name)">
                <span v-if="col.description">{{ col.description }}</span>
                <span v-else class="placeholder">설명 추가...</span>
              </div>
            </div>
          </div>
        </section>
        
        <!-- Relationships Section -->
        <section class="detail-section">
          <div class="detail-section__header">
            <h3>릴레이션</h3>
            <button 
              class="btn btn--primary btn--sm"
              @click="toggleRelationshipForm"
            >
              {{ showRelationshipForm ? '취소' : '+ 추가' }}
            </button>
          </div>
          
          <!-- Add Relationship Form -->
          <div v-if="showRelationshipForm" class="relationship-form">
            <div class="form-group">
              <label>From 컬럼</label>
              <select v-model="newRelationship.from_column">
                <option value="">선택하세요</option>
                <option v-for="col in columns" :key="col.name" :value="col.name">
                  {{ col.name }}
                </option>
              </select>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>To 테이블</label>
                <select v-model="newRelationship.to_table">
                  <option value="">선택하세요</option>
                  <option v-for="t in availableTables" :key="t.name" :value="t.name">
                    {{ t.name }}
                  </option>
                </select>
              </div>
              
              <div class="form-group">
                <label>To 컬럼</label>
                <select v-model="newRelationship.to_column" :disabled="!newRelationship.to_table">
                  <option value="">선택하세요</option>
                  <option v-for="col in targetTableColumns" :key="col.name" :value="col.name">
                    {{ col.name }}
                  </option>
                </select>
              </div>
            </div>
            
            <div class="form-group">
              <label>설명 (선택)</label>
              <input 
                v-model="newRelationship.description"
                type="text"
                placeholder="릴레이션 설명..."
              />
            </div>
            
            <button 
              class="btn btn--primary btn--block"
              @click="addRelationship"
              :disabled="!newRelationship.from_column || !newRelationship.to_table || !newRelationship.to_column"
            >
              릴레이션 추가
            </button>
          </div>
          
          <!-- Existing Relationships -->
          <div class="relationships-list">
            <div 
              v-for="rel in store.userRelationships.filter(r => r.from_table === table.name || r.to_table === table.name)" 
              :key="`${rel.from_table}-${rel.from_column}-${rel.to_table}`"
              class="relationship-item"
            >
              <div class="relationship-item__info">
                <span class="relationship-item__from">{{ rel.from_table }}.{{ rel.from_column }}</span>
                <span class="relationship-item__arrow">→</span>
                <span class="relationship-item__to">{{ rel.to_table }}.{{ rel.to_column }}</span>
              </div>
              <button 
                class="relationship-item__remove"
                @click="store.removeRelationship(rel)"
                title="삭제"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
            
            <div v-if="store.userRelationships.filter(r => r.from_table === table.name || r.to_table === table.name).length === 0" class="empty-state">
              이 테이블과 연결된 릴레이션이 없습니다
            </div>
          </div>
        </section>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.detail-panel {
  width: 380px;
  height: 100%;
  background: #25262b;
  border-left: 1px solid #373a40;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Slide transition */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

/* Header */
.detail-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #2c2e33;
  border-bottom: 1px solid #373a40;
}

.detail-panel__title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
}

.detail-panel__title svg {
  color: #228be6;
}

.detail-panel__close {
  background: none;
  border: none;
  color: #909296;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.15s;
}

.detail-panel__close:hover {
  background: #373a40;
  color: #fff;
}

/* Content */
.detail-panel__content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* Sections */
.detail-section {
  margin-bottom: 24px;
}

.detail-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.detail-section__header h3 {
  font-size: 0.8rem;
  font-weight: 600;
  color: #909296;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-section__badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  background: #373a40;
  border-radius: 4px;
  color: #909296;
}

/* Fields */
.detail-field {
  margin-bottom: 16px;
}

.detail-field label {
  display: block;
  font-size: 0.75rem;
  color: #5c5f66;
  margin-bottom: 6px;
}

.detail-field__display {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #2c2e33;
  border: 1px solid #373a40;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s;
  font-size: 0.875rem;
  color: #c1c2c5;
}

.detail-field__display:hover {
  border-color: #228be6;
}

.detail-field__display svg {
  color: #5c5f66;
}

.detail-field__display .placeholder {
  color: #5c5f66;
  font-style: italic;
}

.detail-field__edit textarea {
  width: 100%;
  padding: 10px;
  background: #1a1b1e;
  border: 1px solid #228be6;
  border-radius: 6px;
  color: #c1c2c5;
  font-size: 0.875rem;
  resize: vertical;
  font-family: inherit;
}

.detail-field__actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

/* Columns List */
.columns-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.column-item {
  background: #2c2e33;
  border: 1px solid #373a40;
  border-radius: 6px;
  padding: 10px 12px;
  transition: border-color 0.15s;
}

.column-item:hover {
  border-color: #4dabf7;
}

.column-item.is-pk {
  border-left: 3px solid #ffd43b;
}

.column-item.is-fk {
  border-left: 3px solid #228be6;
}

.column-item__header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.column-item__icon {
  font-size: 0.8rem;
}

.column-item__name {
  flex: 1;
  font-size: 0.85rem;
  font-weight: 500;
  color: #fff;
}

.column-item__type {
  font-size: 0.7rem;
  color: #5c5f66;
  background: #1a1b1e;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
}

.column-item__required {
  color: #ff6b6b;
  font-weight: bold;
}

.column-item__desc {
  margin-top: 6px;
  padding: 6px 8px;
  background: #25262b;
  border-radius: 4px;
  font-size: 0.8rem;
  color: #909296;
  cursor: pointer;
}

.column-item__desc:hover {
  background: #373a40;
}

.column-item__desc .placeholder {
  font-style: italic;
  color: #5c5f66;
}

.column-item__edit {
  margin-top: 8px;
}

.column-item__edit textarea {
  width: 100%;
  padding: 8px;
  background: #1a1b1e;
  border: 1px solid #228be6;
  border-radius: 4px;
  color: #c1c2c5;
  font-size: 0.8rem;
  resize: none;
  font-family: inherit;
}

.column-item__actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

/* Relationship Form */
.relationship-form {
  background: #1a1b1e;
  border: 1px solid #373a40;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  font-size: 0.75rem;
  color: #909296;
  margin-bottom: 6px;
}

.form-group select,
.form-group input {
  width: 100%;
  padding: 8px 10px;
  background: #25262b;
  border: 1px solid #373a40;
  border-radius: 6px;
  color: #c1c2c5;
  font-size: 0.85rem;
}

.form-group select:focus,
.form-group input:focus {
  border-color: #228be6;
  outline: none;
}

.form-group select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-row {
  display: flex;
  gap: 12px;
}

.form-row .form-group {
  flex: 1;
}

/* Relationships List */
.relationships-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.relationship-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #2c2e33;
  border: 1px solid #373a40;
  border-radius: 6px;
}

.relationship-item__info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
}

.relationship-item__from,
.relationship-item__to {
  color: #4dabf7;
  font-weight: 500;
}

.relationship-item__arrow {
  color: #5c5f66;
}

.relationship-item__remove {
  background: none;
  border: none;
  color: #5c5f66;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.15s;
}

.relationship-item__remove:hover {
  background: #ff6b6b;
  color: #fff;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 20px;
  color: #5c5f66;
  font-size: 0.85rem;
  font-style: italic;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.btn--primary {
  background: #228be6;
  color: #fff;
}

.btn--primary:hover {
  background: #1c7ed6;
}

.btn--primary:disabled {
  background: #373a40;
  color: #5c5f66;
  cursor: not-allowed;
}

.btn--ghost {
  background: transparent;
  color: #909296;
  border: 1px solid #373a40;
}

.btn--ghost:hover {
  background: #373a40;
  color: #c1c2c5;
}

.btn--sm {
  padding: 6px 12px;
  font-size: 0.8rem;
}

.btn--xs {
  padding: 4px 8px;
  font-size: 0.75rem;
}

.btn--block {
  width: 100%;
}
</style>

