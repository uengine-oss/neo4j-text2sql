<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed, inject } from 'vue'
import type { ColumnInfo } from '../../services/api'

interface TableNodeData {
  tableName: string
  schema: string
  description?: string
  columns: ColumnInfo[]
  columnCount: number
}

const props = defineProps<{
  id: string
  data: TableNodeData
  selected?: boolean
}>()

// Inject handlers from parent
const onRemoveTable = inject<(tableName: string) => void>('onRemoveTable')
const onLoadRelated = inject<(tableName: string) => void>('onLoadRelated')

// Show only first 6 columns
const displayColumns = computed(() => {
  return (props.data.columns || []).slice(0, 6)
})

const hasMoreColumns = computed(() => {
  return (props.data.columns?.length || 0) > 6
})

const moreColumnsCount = computed(() => {
  return (props.data.columns?.length || 0) - 6
})

function isPrimaryKey(colName: string): boolean {
  return colName.toLowerCase() === 'id' || colName.toLowerCase().endsWith('_id')
}

function isForeignKey(colName: string): boolean {
  return colName.endsWith('_id') && colName.toLowerCase() !== 'id'
}

function getColumnTypeShort(dtype: string): string {
  const type = dtype.toLowerCase()
  if (type.includes('varchar') || type.includes('text') || type.includes('char')) return 'str'
  if (type.includes('int') || type.includes('serial')) return 'int'
  if (type.includes('decimal') || type.includes('numeric') || type.includes('float') || type.includes('double')) return 'num'
  if (type.includes('bool')) return 'bool'
  if (type.includes('timestamp') || type.includes('datetime')) return 'ts'
  if (type.includes('date')) return 'date'
  if (type.includes('time')) return 'time'
  if (type.includes('json')) return 'json'
  if (type.includes('uuid')) return 'uuid'
  return type.substring(0, 4)
}

function handleRemove(e: Event) {
  e.stopPropagation()
  onRemoveTable?.(props.data.tableName)
}

function handleLoadRelated(e: Event) {
  e.stopPropagation()
  onLoadRelated?.(props.data.tableName)
}
</script>

<template>
  <div 
    class="table-node"
    :class="{ 'is-selected': selected }"
  >
    <!-- Header -->
    <div class="table-node__header">
      <div class="table-node__icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="3" y1="9" x2="21" y2="9"></line>
          <line x1="9" y1="21" x2="9" y2="9"></line>
        </svg>
      </div>
      <span class="table-node__name">{{ data.tableName }}</span>
      <div class="table-node__actions">
        <button 
          class="table-node__action-btn" 
          @click="handleLoadRelated"
          title="Load related tables"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="18" cy="5" r="3"></circle>
            <circle cx="6" cy="12" r="3"></circle>
            <circle cx="18" cy="19" r="3"></circle>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
          </svg>
        </button>
        <button 
          class="table-node__action-btn table-node__action-btn--remove" 
          @click="handleRemove"
          title="Remove from canvas"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>
    
    <!-- Description -->
    <div v-if="data.description" class="table-node__description">
      {{ data.description }}
    </div>
    
    <!-- Columns -->
    <div class="table-node__columns">
      <div 
        v-for="col in displayColumns" 
        :key="col.name"
        class="table-node__column"
        :class="{
          'is-pk': col.name.toLowerCase() === 'id',
          'is-fk': isForeignKey(col.name)
        }"
      >
        <!-- Left handle for incoming connections -->
        <Handle 
          :id="`col-${col.name}`"
          type="target"
          :position="Position.Left"
          class="table-node__handle table-node__handle--left"
        />
        
        <div class="table-node__column-info">
          <span class="table-node__column-icon">
            <template v-if="col.name.toLowerCase() === 'id'">🔑</template>
            <template v-else-if="isForeignKey(col.name)">🔗</template>
            <template v-else>•</template>
          </span>
          <span class="table-node__column-name">{{ col.name }}</span>
          <span class="table-node__column-type">{{ getColumnTypeShort(col.dtype) }}</span>
          <span v-if="!col.nullable" class="table-node__column-required">*</span>
        </div>
        
        <!-- Right handle for outgoing connections -->
        <Handle 
          :id="`col-${col.name}-out`"
          type="source"
          :position="Position.Right"
          class="table-node__handle table-node__handle--right"
        />
      </div>
      
      <!-- More columns indicator -->
      <div v-if="hasMoreColumns" class="table-node__more">
        +{{ moreColumnsCount }} more columns
      </div>
    </div>
    
    <!-- Footer -->
    <div class="table-node__footer">
      <span class="table-node__schema">{{ data.schema }}</span>
      <span class="table-node__count">{{ data.columnCount }} cols</span>
    </div>
  </div>
</template>

<style scoped>
.table-node {
  background: #2c2e33;
  border: 2px solid #373a40;
  border-radius: 10px;
  min-width: 220px;
  max-width: 280px;
  font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  transition: all 0.2s ease;
  overflow: hidden;
}

.table-node:hover {
  border-color: #4dabf7;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
}

.table-node.is-selected {
  border-color: #228be6;
  box-shadow: 0 0 0 3px rgba(34, 139, 230, 0.3), 0 8px 24px rgba(0, 0, 0, 0.5);
}

/* Header */
.table-node__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #339af0 0%, #228be6 100%);
  color: white;
}

.table-node__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.9;
}

.table-node__name {
  flex: 1;
  font-size: 0.9rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-node__actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.table-node:hover .table-node__actions {
  opacity: 1;
}

.table-node__action-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  transition: background 0.15s ease;
}

.table-node__action-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.table-node__action-btn--remove:hover {
  background: rgba(255, 59, 48, 0.8);
}

/* Description */
.table-node__description {
  padding: 8px 12px;
  font-size: 0.75rem;
  color: #909296;
  border-bottom: 1px solid #373a40;
  background: #25262b;
}

/* Columns */
.table-node__columns {
  padding: 6px 0;
  background: #2c2e33;
}

.table-node__column {
  display: flex;
  align-items: center;
  padding: 5px 12px;
  position: relative;
  transition: background 0.1s ease;
}

.table-node__column:hover {
  background: #373a40;
}

.table-node__column.is-pk {
  background: rgba(255, 212, 59, 0.1);
}

.table-node__column.is-fk {
  background: rgba(34, 139, 230, 0.1);
}

.table-node__column-info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.table-node__column-icon {
  font-size: 0.65rem;
  width: 14px;
  text-align: center;
  color: #909296;
}

.table-node__column.is-pk .table-node__column-icon {
  color: #ffd43b;
}

.table-node__column.is-fk .table-node__column-icon {
  color: #228be6;
}

.table-node__column-name {
  flex: 1;
  font-size: 0.8rem;
  color: #c1c2c5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-node__column-type {
  font-size: 0.7rem;
  color: #5c5f66;
  background: #25262b;
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
}

.table-node__column-required {
  color: #ff6b6b;
  font-weight: bold;
  font-size: 0.75rem;
}

/* Handles */
.table-node__handle {
  width: 10px !important;
  height: 10px !important;
  background: #373a40 !important;
  border: 2px solid #228be6 !important;
  transition: all 0.2s ease !important;
  cursor: crosshair !important;
}

.table-node__handle:hover {
  background: #228be6 !important;
  transform: scale(1.5) !important;
  box-shadow: 0 0 8px rgba(34, 139, 230, 0.6) !important;
}

.table-node__handle--left {
  left: -5px !important;
}

.table-node__handle--right {
  right: -5px !important;
}

/* Show handles more prominently on hover */
.table-node:hover .table-node__handle {
  background: #4dabf7 !important;
  border-color: #228be6 !important;
}

/* More columns */
.table-node__more {
  padding: 6px 12px;
  font-size: 0.7rem;
  color: #5c5f66;
  text-align: center;
  font-style: italic;
}

/* Footer */
.table-node__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #25262b;
  border-top: 1px solid #373a40;
}

.table-node__schema {
  font-size: 0.65rem;
  color: #5c5f66;
  background: #373a40;
  padding: 2px 6px;
  border-radius: 3px;
}

.table-node__count {
  font-size: 0.65rem;
  color: #909296;
}
</style>

