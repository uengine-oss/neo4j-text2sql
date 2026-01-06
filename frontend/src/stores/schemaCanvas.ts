import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { Edge, Node } from '@vue-flow/core'
import { api, type ColumnInfo, type TableInfo } from '../services/api'

export interface TableNodeData {
  tableName: string
  schema: string
  description?: string
  columns: ColumnInfo[]
  columnCount: number
}

export interface RelationshipData {
  from_table: string
  from_schema: string
  from_column: string
  to_table: string
  to_schema: string
  to_column: string
  description?: string
  relationship_type: string
}

export const useSchemaCanvasStore = defineStore('schemaCanvas', () => {
  // Canvas state
  const nodes = ref<Node<TableNodeData>[]>([])
  const edges = ref<Edge[]>([])
  
  // Table data
  const allTables = ref<TableInfo[]>([])
  const tableColumnsCache = ref<Record<string, ColumnInfo[]>>({})
  
  // Relationships
  const userRelationships = ref<RelationshipData[]>([])
  
  // UI state
  const selectedNodeId = ref<string | null>(null)
  const selectedTable = ref<TableInfo | null>(null)
  const selectedTableColumns = ref<ColumnInfo[]>([])
  const loading = ref(false)
  const isDetailPanelOpen = ref(false)
  
  // Search/filter
  const searchQuery = ref('')
  
  // Computed
  const filteredTables = computed(() => {
    if (!searchQuery.value.trim()) return allTables.value
    const query = searchQuery.value.toLowerCase()
    return allTables.value.filter(t => 
      t.name.toLowerCase().includes(query) ||
      (t.description && t.description.toLowerCase().includes(query))
    )
  })
  
  const tablesOnCanvas = computed(() => {
    return nodes.value.map(n => n.data.tableName)
  })
  
  const tablesNotOnCanvas = computed(() => {
    const onCanvas = new Set(tablesOnCanvas.value)
    return filteredTables.value.filter(t => !onCanvas.has(t.name))
  })
  
  // Actions
  async function loadAllTables() {
    loading.value = true
    try {
      const response = await api.get('/meta/tables', { params: { limit: 100 } })
      allTables.value = response.data
    } catch (error) {
      console.error('Failed to load tables:', error)
    } finally {
      loading.value = false
    }
  }
  
  async function loadTableColumns(tableName: string, schema: string = 'public'): Promise<ColumnInfo[]> {
    if (tableColumnsCache.value[tableName]) {
      return tableColumnsCache.value[tableName]
    }
    
    try {
      const response = await api.get(`/meta/tables/${tableName}/columns`, {
        params: { schema }
      })
      tableColumnsCache.value[tableName] = response.data
      return response.data
    } catch (error) {
      console.error(`Failed to load columns for ${tableName}:`, error)
      return []
    }
  }
  
  async function loadUserRelationships() {
    try {
      const response = await api.get('/schema-edit/relationships/user-added')
      userRelationships.value = response.data.relationships || []
      updateEdgesFromRelationships()
    } catch (error) {
      console.error('Failed to load relationships:', error)
    }
  }
  
  async function addTableToCanvas(table: TableInfo, position?: { x: number; y: number }) {
    // Check if already on canvas
    if (nodes.value.some(n => n.data.tableName === table.name)) {
      return
    }
    
    // Load columns
    const columns = await loadTableColumns(table.name, table.schema)
    
    // Calculate position
    const pos = position || calculateNewNodePosition()
    
    // Create node
    const newNode: Node<TableNodeData> = {
      id: `table-${table.name}`,
      type: 'tableNode',
      position: pos,
      data: {
        tableName: table.name,
        schema: table.schema,
        description: table.description,
        columns: columns,
        columnCount: table.column_count
      }
    }
    
    nodes.value.push(newNode)
    
    // Update edges for this table
    updateEdgesFromRelationships()
  }
  
  function removeTableFromCanvas(tableName: string) {
    const nodeId = `table-${tableName}`
    nodes.value = nodes.value.filter(n => n.id !== nodeId)
    edges.value = edges.value.filter(e => 
      e.source !== nodeId && e.target !== nodeId
    )
    
    if (selectedNodeId.value === nodeId) {
      selectedNodeId.value = null
      selectedTable.value = null
      isDetailPanelOpen.value = false
    }
  }
  
  function calculateNewNodePosition(): { x: number; y: number } {
    if (nodes.value.length === 0) {
      return { x: 100, y: 100 }
    }
    
    // Find rightmost position
    const maxX = Math.max(...nodes.value.map(n => n.position.x))
    const avgY = nodes.value.reduce((sum, n) => sum + n.position.y, 0) / nodes.value.length
    
    return { x: maxX + 320, y: avgY }
  }
  
  function updateNodePosition(nodeId: string, position: { x: number; y: number }) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (node) {
      node.position = position
    }
  }
  
  function selectNode(nodeId: string) {
    selectedNodeId.value = nodeId
    
    const node = nodes.value.find(n => n.id === nodeId)
    if (node) {
      const table = allTables.value.find(t => t.name === node.data.tableName)
      if (table) {
        selectedTable.value = table
        selectedTableColumns.value = node.data.columns
        isDetailPanelOpen.value = true
      }
    }
  }
  
  function clearSelection() {
    selectedNodeId.value = null
    // Don't close panel automatically
  }
  
  function closeDetailPanel() {
    isDetailPanelOpen.value = false
    selectedTable.value = null
    selectedNodeId.value = null
  }
  
  function updateEdgesFromRelationships() {
    const newEdges: Edge[] = []
    const tableNamesOnCanvas = new Set(nodes.value.map(n => n.data.tableName))
    
    // User-defined relationships
    userRelationships.value.forEach((rel, index) => {
      if (tableNamesOnCanvas.has(rel.from_table) && tableNamesOnCanvas.has(rel.to_table)) {
        newEdges.push({
          id: `rel-${rel.from_table}-${rel.from_column}-${rel.to_table}-${rel.to_column}`,
          source: `table-${rel.from_table}`,
          target: `table-${rel.to_table}`,
          sourceHandle: `col-${rel.from_column}`,
          targetHandle: `col-${rel.to_column}`,
          type: 'smoothstep',
          animated: true,
          label: rel.description || `${rel.from_column} → ${rel.to_column}`,
          style: { stroke: '#228be6', strokeWidth: 2 },
          labelStyle: { fill: '#c1c2c5', fontSize: 11 },
          labelBgStyle: { fill: '#25262b' }
        })
      }
    })
    
    // Auto-detect FK relationships from column names
    nodes.value.forEach(node => {
      const columns = node.data.columns || []
      columns.forEach(col => {
        if (col.name.endsWith('_id') && col.name !== 'id') {
          const baseName = col.name.replace(/_id$/, '')
          
          // Find potential target table
          const possibleTargets = [baseName, baseName + 's', baseName.replace(/s$/, '')]
          
          nodes.value.forEach(targetNode => {
            if (targetNode.id !== node.id && 
                possibleTargets.includes(targetNode.data.tableName.toLowerCase())) {
              const edgeId = `fk-${node.data.tableName}-${col.name}-${targetNode.data.tableName}`
              
              // Check if edge already exists
              if (!newEdges.some(e => e.id === edgeId)) {
                newEdges.push({
                  id: edgeId,
                  source: node.id,
                  target: targetNode.id,
                  sourceHandle: `col-${col.name}`,
                  targetHandle: 'col-id',
                  type: 'smoothstep',
                  style: { stroke: '#868e96', strokeWidth: 1.5, strokeDasharray: '5 5' },
                  label: baseName,
                  labelStyle: { fill: '#909296', fontSize: 10 },
                  labelBgStyle: { fill: '#25262b' }
                })
              }
            }
          })
        }
      })
    })
    
    edges.value = newEdges
  }
  
  async function addRelationship(relationship: Omit<RelationshipData, 'relationship_type'>) {
    try {
      await api.post('/schema-edit/relationships', {
        ...relationship,
        relationship_type: 'FK_TO_TABLE'
      })
      await loadUserRelationships()
    } catch (error) {
      console.error('Failed to add relationship:', error)
      throw error
    }
  }
  
  async function removeRelationship(relationship: RelationshipData) {
    try {
      await api.delete('/schema-edit/relationships', {
        params: {
          from_table: relationship.from_table,
          from_schema: relationship.from_schema,
          from_column: relationship.from_column,
          to_table: relationship.to_table,
          to_schema: relationship.to_schema,
          to_column: relationship.to_column
        }
      })
      await loadUserRelationships()
    } catch (error) {
      console.error('Failed to remove relationship:', error)
      throw error
    }
  }
  
  async function updateTableDescription(tableName: string, description: string) {
    try {
      await api.put(`/schema-edit/tables/${tableName}/description`, {
        name: tableName,
        schema: 'public',
        description
      })
      
      // Update local data
      const table = allTables.value.find(t => t.name === tableName)
      if (table) {
        table.description = description
      }
      
      const node = nodes.value.find(n => n.data.tableName === tableName)
      if (node) {
        node.data.description = description
      }
    } catch (error) {
      console.error('Failed to update table description:', error)
      throw error
    }
  }
  
  async function updateColumnDescription(tableName: string, columnName: string, description: string) {
    try {
      await api.put(`/schema-edit/tables/${tableName}/columns/${columnName}/description`, {
        table_name: tableName,
        table_schema: 'public',
        column_name: columnName,
        description
      })
      
      // Update cache
      if (tableColumnsCache.value[tableName]) {
        const col = tableColumnsCache.value[tableName].find(c => c.name === columnName)
        if (col) {
          col.description = description
        }
      }
      
      // Update node
      const node = nodes.value.find(n => n.data.tableName === tableName)
      if (node) {
        const col = node.data.columns.find(c => c.name === columnName)
        if (col) {
          col.description = description
        }
      }
      
      // Update selected table columns
      if (selectedTable.value?.name === tableName) {
        const col = selectedTableColumns.value.find(c => c.name === columnName)
        if (col) {
          col.description = description
        }
      }
    } catch (error) {
      console.error('Failed to update column description:', error)
      throw error
    }
  }
  
  function clearCanvas() {
    nodes.value = []
    edges.value = []
    selectedNodeId.value = null
    selectedTable.value = null
    isDetailPanelOpen.value = false
  }
  
  // Auto-load related tables
  async function loadRelatedTables(tableName: string) {
    const columns = tableColumnsCache.value[tableName] || []
    
    for (const col of columns) {
      if (col.name.endsWith('_id') && col.name !== 'id') {
        const baseName = col.name.replace(/_id$/, '')
        const possibleTargets = [baseName, baseName + 's', baseName.replace(/s$/, '')]
        
        const relatedTable = allTables.value.find(t => 
          possibleTargets.includes(t.name.toLowerCase())
        )
        
        if (relatedTable && !nodes.value.some(n => n.data.tableName === relatedTable.name)) {
          await addTableToCanvas(relatedTable)
        }
      }
    }
    
    // Also find tables that reference this table
    for (const otherTable of allTables.value) {
      if (otherTable.name === tableName) continue
      
      const otherColumns = tableColumnsCache.value[otherTable.name] || await loadTableColumns(otherTable.name)
      
      for (const col of otherColumns) {
        if (col.name.endsWith('_id')) {
          const baseName = col.name.replace(/_id$/, '')
          const possibleTargets = [baseName, baseName + 's', baseName.replace(/s$/, '')]
          
          if (possibleTargets.includes(tableName.toLowerCase())) {
            if (!nodes.value.some(n => n.data.tableName === otherTable.name)) {
              await addTableToCanvas(otherTable)
            }
            break
          }
        }
      }
    }
  }
  
  return {
    // State
    nodes,
    edges,
    allTables,
    tableColumnsCache,
    userRelationships,
    selectedNodeId,
    selectedTable,
    selectedTableColumns,
    loading,
    isDetailPanelOpen,
    searchQuery,
    
    // Computed
    filteredTables,
    tablesOnCanvas,
    tablesNotOnCanvas,
    
    // Actions
    loadAllTables,
    loadTableColumns,
    loadUserRelationships,
    addTableToCanvas,
    removeTableFromCanvas,
    updateNodePosition,
    selectNode,
    clearSelection,
    closeDetailPanel,
    updateEdgesFromRelationships,
    addRelationship,
    removeRelationship,
    updateTableDescription,
    updateColumnDescription,
    clearCanvas,
    loadRelatedTables
  }
})

