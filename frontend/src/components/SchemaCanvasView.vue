<script setup lang="ts">
import { ref, onMounted, provide, computed } from 'vue'
import { VueFlow, useVueFlow, type Connection } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import TableNode from './nodes/TableNode.vue'
import TableDetailPanel from './TableDetailPanel.vue'
import { useSchemaCanvasStore } from '../stores/schemaCanvas'
import type { TableInfo } from '../services/api'

const store = useSchemaCanvasStore()
const isDragOver = ref(false)
const searchQuery = ref('')
const isConnecting = ref(false)

const { fitView, zoomIn, zoomOut } = useVueFlow()

// Node types
const nodeTypes = {
  tableNode: TableNode
}

// MiniMap node color
function getNodeColor() {
  return '#228be6'
}

// Computed
const nodesWithSelection = computed(() => {
  return store.nodes.map(node => ({
    ...node,
    class: store.selectedNodeId === node.id ? 'table-node--selected' : ''
  }))
})

// Provide handlers to child nodes
provide('onRemoveTable', (tableName: string) => {
  store.removeTableFromCanvas(tableName)
})

provide('onLoadRelated', async (tableName: string) => {
  await store.loadRelatedTables(tableName)
  setTimeout(() => fitView({ padding: 0.3 }), 150)
})

// Lifecycle
onMounted(async () => {
  await store.loadAllTables()
  await store.loadUserRelationships()
})

// Handlers
function handleSearch() {
  store.searchQuery = searchQuery.value
}

function clearSearch() {
  searchQuery.value = ''
  store.searchQuery = ''
}

async function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragOver.value = false
  
  const data = event.dataTransfer?.getData('application/json')
  if (!data) return
  
  try {
    const { table } = JSON.parse(data)
    
    // Get drop position relative to canvas
    const bounds = (event.target as HTMLElement).getBoundingClientRect()
    const position = {
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top
    }
    
    await store.addTableToCanvas(table, position)
    
    // Auto fit view
    setTimeout(() => fitView({ padding: 0.3 }), 150)
  } catch (error) {
    console.error('Failed to handle drop:', error)
  }
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragOver.value = true
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

function handleDragLeave() {
  isDragOver.value = false
}

function startDragTable(event: DragEvent, table: TableInfo) {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/json', JSON.stringify({ table }))
    event.dataTransfer.effectAllowed = 'copy'
  }
}

function onNodesChange(changes: any[]) {
  changes.forEach(change => {
    if (change.type === 'position' && change.position) {
      store.updateNodePosition(change.id, change.position)
    }
  })
}

function onNodeClick(event: any) {
  const nodeId = event.node.id
  store.selectNode(nodeId)
}

function onNodeDoubleClick(event: any) {
  const nodeId = event.node.id
  store.selectNode(nodeId)
}

function onPaneClick() {
  store.clearSelection()
}

// Handle edge connection - connect relations directly on canvas
async function onConnect(connection: Connection) {
  if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) {
    return
  }
  
  // Extract table names and column names from connection
  // Node IDs are like "table-tablename"
  // Handle IDs are like "col-columnname" or "col-columnname-out"
  const fromTable = connection.source.replace('table-', '')
  const toTable = connection.target.replace('table-', '')
  const fromColumn = connection.sourceHandle.replace('col-', '').replace('-out', '')
  const toColumn = connection.targetHandle.replace('col-', '').replace('-out', '')
  
  try {
    isConnecting.value = true
    await store.addRelationship({
      from_table: fromTable,
      from_schema: 'public',
      from_column: fromColumn,
      to_table: toTable,
      to_schema: 'public',
      to_column: toColumn,
      description: `${fromColumn} → ${toColumn}`
    })
    
    // Show success feedback
    console.log(`Relationship created: ${fromTable}.${fromColumn} → ${toTable}.${toColumn}`)
  } catch (error) {
    console.error('Failed to create relationship:', error)
    alert('릴레이션 생성에 실패했습니다.')
  } finally {
    isConnecting.value = false
  }
}

function onConnectStart() {
  isConnecting.value = true
}

function onConnectEnd() {
  isConnecting.value = false
}

async function handleAddAllToCanvas() {
  for (const table of store.tablesNotOnCanvas.slice(0, 10)) {
    await store.addTableToCanvas(table)
  }
  setTimeout(() => fitView({ padding: 0.3 }), 200)
}

function handleClearCanvas() {
  if (confirm('캔버스를 비우시겠습니까?')) {
    store.clearCanvas()
  }
}

async function handleRefresh() {
  await store.loadAllTables()
  await store.loadUserRelationships()
}
</script>

<template>
  <div class="schema-canvas-view">
    <!-- Left Panel: Table List -->
    <aside class="left-panel">
      <div class="panel-header">
        <div class="panel-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="3" y1="9" x2="21" y2="9"></line>
            <line x1="9" y1="21" x2="9" y2="9"></line>
          </svg>
          <span>테이블</span>
          <span class="panel-count">{{ store.allTables.length }}</span>
        </div>
        <button class="panel-action" @click="handleRefresh" title="새로고침">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
        </button>
      </div>
      
      <!-- Search -->
      <div class="search-box">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input 
          v-model="searchQuery"
          @input="handleSearch"
          type="text" 
          placeholder="테이블 검색..."
        />
        <button v-if="searchQuery" class="search-clear" @click="clearSearch">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      
      <!-- Tables on Canvas -->
      <div v-if="store.tablesOnCanvas.length > 0" class="table-section">
        <div class="section-header">
          <span>캔버스에 있는 테이블</span>
          <span class="section-count">{{ store.tablesOnCanvas.length }}</span>
        </div>
        <div class="table-list">
          <div 
            v-for="tableName in store.tablesOnCanvas" 
            :key="tableName"
            class="table-item table-item--on-canvas"
            @click="store.selectNode(`table-${tableName}`)"
          >
            <div class="table-item__icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="3" y1="9" x2="21" y2="9"></line>
                <line x1="9" y1="21" x2="9" y2="9"></line>
              </svg>
            </div>
            <span class="table-item__name">{{ tableName }}</span>
            <button 
              class="table-item__remove"
              @click.stop="store.removeTableFromCanvas(tableName)"
              title="캔버스에서 제거"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>
      </div>
      
      <!-- Available Tables -->
      <div class="table-section">
        <div class="section-header">
          <span>사용 가능한 테이블</span>
          <span class="section-count">{{ store.tablesNotOnCanvas.length }}</span>
        </div>
        <div class="table-list">
          <div 
            v-for="table in store.tablesNotOnCanvas" 
            :key="table.name"
            class="table-item"
            draggable="true"
            @dragstart="(e) => startDragTable(e, table)"
            @dblclick="store.addTableToCanvas(table)"
          >
            <div class="table-item__icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="3" y1="9" x2="21" y2="9"></line>
                <line x1="9" y1="21" x2="9" y2="9"></line>
              </svg>
            </div>
            <div class="table-item__info">
              <span class="table-item__name">{{ table.name }}</span>
              <span class="table-item__cols">{{ table.column_count }} cols</span>
            </div>
            <div class="table-item__drag-hint">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="9" cy="5" r="1"></circle>
                <circle cx="9" cy="12" r="1"></circle>
                <circle cx="9" cy="19" r="1"></circle>
                <circle cx="15" cy="5" r="1"></circle>
                <circle cx="15" cy="12" r="1"></circle>
                <circle cx="15" cy="19" r="1"></circle>
              </svg>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Quick Actions -->
      <div class="panel-footer">
        <button 
          v-if="store.tablesNotOnCanvas.length > 0"
          class="btn btn--ghost btn--sm btn--block"
          @click="handleAddAllToCanvas"
        >
          상위 10개 테이블 추가
        </button>
      </div>
    </aside>
    
    <!-- Main Canvas -->
    <main 
      class="canvas-area"
      :class="{ 'drop-zone-active': isDragOver }"
      @drop="handleDrop"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
    >
      <!-- Empty State -->
      <div v-if="store.nodes.length === 0" class="canvas-empty">
        <div class="canvas-empty__icon">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="3" y1="9" x2="21" y2="9"></line>
            <line x1="9" y1="21" x2="9" y2="9"></line>
          </svg>
        </div>
        <div class="canvas-empty__text">캔버스가 비어 있습니다</div>
        <div class="canvas-empty__hint">
          왼쪽에서 테이블을 드래그하거나 더블클릭하여 추가하세요
        </div>
      </div>
      
      <!-- VueFlow Canvas -->
      <VueFlow
        v-else
        :nodes="nodesWithSelection"
        :edges="store.edges"
        :node-types="nodeTypes"
        :default-viewport="{ zoom: 0.8, x: 50, y: 50 }"
        :min-zoom="0.2"
        :max-zoom="2"
        :snap-to-grid="true"
        :snap-grid="[15, 15]"
        :nodes-draggable="true"
        :nodes-connectable="true"
        :pan-on-drag="true"
        :zoom-on-scroll="true"
        :prevent-scrolling="true"
        :connect-on-click="false"
        :default-edge-options="{ type: 'smoothstep', animated: true }"
        fit-view-on-init
        @nodes-change="onNodesChange"
        @node-click="onNodeClick"
        @node-double-click="onNodeDoubleClick"
        @pane-click="onPaneClick"
        @connect="onConnect"
        @connect-start="onConnectStart"
        @connect-end="onConnectEnd"
      >
        <Background pattern-color="#2a2a3a" :gap="20" />
        <Controls position="bottom-left" />
        <MiniMap 
          :node-color="getNodeColor"
          :node-stroke-width="3"
          pannable
          zoomable
        />
      </VueFlow>
      
      <!-- Connection Mode Indicator -->
      <div v-if="isConnecting" class="connection-indicator">
        🔗 릴레이션 연결 중...
      </div>
      
      <!-- Canvas Toolbar -->
      <div v-if="store.nodes.length > 0" class="canvas-toolbar">
        <button 
          class="canvas-toolbar__btn"
          @click="zoomIn()"
          title="Zoom In"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="11" y1="8" x2="11" y2="14"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </button>
        
        <button 
          class="canvas-toolbar__btn"
          @click="zoomOut()"
          title="Zoom Out"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </button>
        
        <button 
          class="canvas-toolbar__btn"
          @click="fitView({ padding: 0.3 })"
          title="Fit View"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
          </svg>
        </button>
        
        <div class="canvas-toolbar__divider"></div>
        
        <button 
          class="canvas-toolbar__btn"
          @click="store.updateEdgesFromRelationships()"
          title="Refresh Relations"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="18" cy="5" r="3"></circle>
            <circle cx="6" cy="12" r="3"></circle>
            <circle cx="18" cy="19" r="3"></circle>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
          </svg>
        </button>
        
        <button 
          class="canvas-toolbar__btn canvas-toolbar__btn--danger"
          @click="handleClearCanvas"
          title="Clear Canvas"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
      
      <!-- Legend & Tips -->
      <div class="canvas-legend">
        <div class="legend-title">범례</div>
        <div class="legend-item">
          <span class="legend-color" style="background: #228be6;"></span>
          <span>사용자 정의 릴레이션</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--dashed"></span>
          <span>자동 감지 FK</span>
        </div>
        <div class="legend-divider"></div>
        <div class="legend-tip">
          <span class="tip-icon">💡</span>
          <span>컬럼 핸들을 드래그하여 릴레이션 연결</span>
        </div>
        <div class="legend-tip">
          <span class="tip-icon">🖱️</span>
          <span>테이블 더블클릭으로 상세 편집</span>
        </div>
      </div>
    </main>
    
    <!-- Right Panel: Table Details -->
    <TableDetailPanel />
  </div>
</template>

<style>
/* VueFlow imports */
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';
@import '@vue-flow/minimap/dist/style.css';

/* VueFlow overrides */
.vue-flow {
  background: #1a1b26 !important;
}

.vue-flow__minimap {
  background: #25262b !important;
  border: 1px solid #373a40 !important;
  border-radius: 8px !important;
}

.vue-flow__controls {
  background: #25262b !important;
  border: 1px solid #373a40 !important;
  border-radius: 8px !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
}

.vue-flow__controls-button {
  background: transparent !important;
  border: none !important;
  color: #c1c2c5 !important;
}

.vue-flow__controls-button:hover {
  background: #373a40 !important;
}

.vue-flow__controls-button svg {
  fill: #c1c2c5 !important;
}

.vue-flow__edge-textbg {
  fill: #1a1b26 !important;
}

.vue-flow__edge-text {
  fill: #c1c2c5 !important;
}

/* Selected node */
.vue-flow__node.table-node--selected {
  z-index: 10 !important;
}

/* Edge styling */
.vue-flow__edge-path {
  stroke-width: 2 !important;
}

.vue-flow__edge.animated path {
  stroke-dasharray: 5 !important;
  animation: flowEdge 0.5s linear infinite !important;
}

@keyframes flowEdge {
  to {
    stroke-dashoffset: -10;
  }
}

/* Connection line (while dragging) */
.vue-flow__connection-line {
  stroke: #228be6 !important;
  stroke-width: 2 !important;
  stroke-dasharray: 5 !important;
}

/* Handle hover effects */
.vue-flow__handle:hover {
  background: #228be6 !important;
  transform: scale(1.5) !important;
}
</style>

<style scoped>
.schema-canvas-view {
  display: flex;
  height: calc(100vh - 120px); /* Account for navbar and footer */
  width: 100%;
  background: #1a1b1e;
  overflow: hidden;
}

/* Left Panel */
.left-panel {
  width: 300px;
  min-width: 280px;
  background: #25262b;
  border-right: 1px solid #373a40;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #373a40;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  color: #fff;
}

.panel-title svg {
  color: #228be6;
}

.panel-count {
  font-size: 0.7rem;
  padding: 2px 8px;
  background: #373a40;
  border-radius: 10px;
  color: #909296;
}

.panel-action {
  background: none;
  border: none;
  color: #909296;
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.15s;
}

.panel-action:hover {
  background: #373a40;
  color: #fff;
}

/* Search */
.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #373a40;
  background: #2c2e33;
}

.search-box svg {
  color: #5c5f66;
  flex-shrink: 0;
}

.search-box input {
  flex: 1;
  background: none;
  border: none;
  color: #c1c2c5;
  font-size: 0.85rem;
  outline: none;
}

.search-box input::placeholder {
  color: #5c5f66;
}

.search-clear {
  background: none;
  border: none;
  color: #5c5f66;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.search-clear:hover {
  color: #fff;
}

/* Table Section */
.table-section {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 8px 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #5c5f66;
}

.section-count {
  font-size: 0.65rem;
  padding: 1px 6px;
  background: #373a40;
  border-radius: 8px;
  color: #909296;
}

/* Table List */
.table-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.table-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #2c2e33;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: grab;
  transition: all 0.15s;
}

.table-item:hover {
  background: #373a40;
  border-color: #4dabf7;
}

.table-item:active {
  cursor: grabbing;
}

.table-item--on-canvas {
  background: rgba(34, 139, 230, 0.15);
  border-color: rgba(34, 139, 230, 0.3);
  cursor: pointer;
}

.table-item--on-canvas:hover {
  background: rgba(34, 139, 230, 0.25);
}

.table-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #228be6;
}

.table-item__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.table-item__name {
  font-size: 0.85rem;
  color: #c1c2c5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-item__cols {
  font-size: 0.7rem;
  color: #5c5f66;
}

.table-item__drag-hint {
  color: #5c5f66;
  opacity: 0;
  transition: opacity 0.15s;
}

.table-item:hover .table-item__drag-hint {
  opacity: 1;
}

.table-item__remove {
  background: none;
  border: none;
  color: #5c5f66;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  opacity: 0;
  transition: all 0.15s;
}

.table-item:hover .table-item__remove {
  opacity: 1;
}

.table-item__remove:hover {
  background: #ff6b6b;
  color: #fff;
}

/* Panel Footer */
.panel-footer {
  padding: 12px 16px;
  border-top: 1px solid #373a40;
}

/* Canvas Area */
.canvas-area {
  flex: 1;
  position: relative;
  background: #1a1b26;
  overflow: hidden;
}

.canvas-area.drop-zone-active {
  background: rgba(34, 139, 230, 0.1);
}

.canvas-area.drop-zone-active::after {
  content: '';
  position: absolute;
  inset: 16px;
  border: 2px dashed #228be6;
  border-radius: 12px;
  pointer-events: none;
  z-index: 100;
}

/* Canvas Empty */
.canvas-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #5c5f66;
}

.canvas-empty__icon {
  margin-bottom: 16px;
  opacity: 0.3;
}

.canvas-empty__text {
  font-size: 1.2rem;
  font-weight: 500;
  color: #909296;
  margin-bottom: 8px;
}

.canvas-empty__hint {
  font-size: 0.9rem;
  color: #5c5f66;
}

/* Canvas Toolbar */
.canvas-toolbar {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 4px;
  background: #25262b;
  padding: 6px;
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
  border: 1px solid #373a40;
  z-index: 10;
}

.canvas-toolbar__btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #c1c2c5;
  cursor: pointer;
  transition: all 0.15s;
}

.canvas-toolbar__btn:hover {
  background: #373a40;
  color: #fff;
}

.canvas-toolbar__btn--danger:hover {
  background: #ff6b6b;
  color: #fff;
}

.canvas-toolbar__divider {
  width: 1px;
  background: #373a40;
  margin: 4px 0;
}

/* Connection Indicator */
.connection-indicator {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, #228be6 0%, #7c3aed 100%);
  color: white;
  padding: 8px 20px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
  box-shadow: 0 4px 16px rgba(34, 139, 230, 0.4);
  z-index: 100;
  animation: pulse-indicator 1.5s infinite;
}

@keyframes pulse-indicator {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* Canvas Legend */
.canvas-legend {
  position: absolute;
  top: 16px;
  right: 16px;
  background: #25262b;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #373a40;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

.legend-title {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #5c5f66;
  margin-bottom: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.75rem;
  color: #909296;
  margin-bottom: 4px;
}

.legend-item:last-child {
  margin-bottom: 0;
}

.legend-color {
  width: 20px;
  height: 3px;
  border-radius: 2px;
}

.legend-color--dashed {
  background: repeating-linear-gradient(
    to right,
    #868e96 0px,
    #868e96 4px,
    transparent 4px,
    transparent 8px
  );
}

.legend-divider {
  height: 1px;
  background: #373a40;
  margin: 8px 0;
}

.legend-tip {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 0.7rem;
  color: #5c5f66;
  margin-bottom: 4px;
}

.legend-tip:last-child {
  margin-bottom: 0;
}

.tip-icon {
  flex-shrink: 0;
  font-size: 0.75rem;
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

.btn--block {
  width: 100%;
}

/* Scrollbar */
.table-section::-webkit-scrollbar {
  width: 6px;
}

.table-section::-webkit-scrollbar-track {
  background: transparent;
}

.table-section::-webkit-scrollbar-thumb {
  background: #373a40;
  border-radius: 3px;
}

.table-section::-webkit-scrollbar-thumb:hover {
  background: #5c5f66;
}
</style>

