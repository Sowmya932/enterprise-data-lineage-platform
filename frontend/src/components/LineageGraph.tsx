import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  Panel,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from 'reactflow';
import ErrorState from './ErrorState';
import LoadingState from './LoadingState';
import {
  getDownstreamLineage,
  getLineageDependencies,
  getUpstreamLineage,
} from '../services/lineageService';
import type {
  LineageDependenciesResponse,
  LineageRelationship,
  RecursiveLineageEdge,
} from '../types/api';

type GraphDirection = 'upstream' | 'downstream';
type GraphNodeKind = 'table' | 'column' | 'dag';
type GraphEdgeKind = 'table-lineage' | 'column-lineage' | 'dag-link' | 'membership';

interface GraphNodeData {
  label: string;
  kind: GraphNodeKind;
  subtitle?: string;
  tableName?: string;
}

type GraphNode = Node<GraphNodeData>;
type GraphEdge = Edge<{ kind: GraphEdgeKind }>;

type GraphBuildResult = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  tableCount: number;
  columnCount: number;
  dagCount: number;
  truncated: boolean;
};

const MAX_TABLE_NODES = 360;
const MAX_COLUMN_NODES = 760;
const MAX_DAG_NODES = 240;
const MAX_RENDER_EDGES = 3800;

function normalizeKey(value: string): string {
  return value.trim().toLowerCase();
}

function tableNodeId(tableName: string): string {
  return `table:${normalizeKey(tableName)}`;
}

function columnNodeId(tableName: string, columnName: string): string {
  return `column:${normalizeKey(tableName)}.${normalizeKey(columnName)}`;
}

function dagNodeId(dagId: string): string {
  return `dag:${normalizeKey(dagId)}`;
}

function stableNumericId(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

function toRelationship(edge: RecursiveLineageEdge): LineageRelationship {
  const identity = [
    edge.source_table,
    edge.target_table,
    edge.source_column ?? '',
    edge.column_name ?? '',
    edge.dag_id ?? '',
  ].join('|');

  return {
    id: stableNumericId(identity),
    source_table: edge.source_table,
    target_table: edge.target_table,
    source_column: edge.source_column ?? null,
    column_name: edge.column_name ?? null,
    dag_id: edge.dag_id ?? null,
    created_at: null,
  };
}

function mergeRelationships(
  current: LineageRelationship[],
  incoming: LineageRelationship[],
): LineageRelationship[] {
  const seen = new Set(
    current.map((edge) =>
      [
        normalizeKey(edge.source_table),
        normalizeKey(edge.target_table),
        normalizeKey(edge.source_column ?? ''),
        normalizeKey(edge.column_name ?? ''),
        normalizeKey(edge.dag_id ?? ''),
      ].join('|'),
    ),
  );

  const merged = [...current];
  incoming.forEach((edge) => {
    const key = [
      normalizeKey(edge.source_table),
      normalizeKey(edge.target_table),
      normalizeKey(edge.source_column ?? ''),
      normalizeKey(edge.column_name ?? ''),
      normalizeKey(edge.dag_id ?? ''),
    ].join('|');

    if (!seen.has(key)) {
      merged.push(edge);
      seen.add(key);
    }
  });

  return merged;
}

function computeTableLevels(
  tableNodes: string[],
  tableEdges: Array<{ sourceId: string; targetId: string }>,
): Map<string, number> {
  const adjacency = new Map<string, string[]>();
  const indegree = new Map<string, number>();
  const levelMap = new Map<string, number>();

  tableNodes.forEach((id) => {
    adjacency.set(id, []);
    indegree.set(id, 0);
    levelMap.set(id, 0);
  });

  tableEdges.forEach((edge) => {
    const current = adjacency.get(edge.sourceId);
    if (!current) {
      return;
    }
    current.push(edge.targetId);
    indegree.set(edge.targetId, (indegree.get(edge.targetId) ?? 0) + 1);
  });

  const queue: string[] = [];
  tableNodes.forEach((id) => {
    if ((indegree.get(id) ?? 0) === 0) {
      queue.push(id);
    }
  });

  while (queue.length > 0) {
    const nodeId = queue.shift();
    if (!nodeId) {
      continue;
    }
    const currentLevel = levelMap.get(nodeId) ?? 0;
    const neighbors = adjacency.get(nodeId) ?? [];

    neighbors.forEach((neighbor) => {
      const nextLevel = Math.max(levelMap.get(neighbor) ?? 0, currentLevel + 1);
      levelMap.set(neighbor, nextLevel);
      indegree.set(neighbor, (indegree.get(neighbor) ?? 0) - 1);
      if ((indegree.get(neighbor) ?? 0) === 0) {
        queue.push(neighbor);
      }
    });
  }

  return levelMap;
}

function buildGraphElements(data: LineageDependenciesResponse): GraphBuildResult {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  const tableNodeMap = new Map<string, GraphNode>();
  const columnNodeMap = new Map<string, GraphNode>();
  const dagNodeMap = new Map<string, GraphNode>();

  const tableEdgeMap = new Map<
    string,
    {
      sourceId: string;
      targetId: string;
      dagIds: Set<string>;
    }
  >();

  const membershipEdgeIds = new Set<string>();
  const columnEdgeIds = new Set<string>();
  const dagEdgeIds = new Set<string>();

  let truncated = false;

  data.lineage_edges.forEach((relationship) => {
    const sourceTableId = tableNodeId(relationship.source_table);
    const targetTableId = tableNodeId(relationship.target_table);

    if (!tableNodeMap.has(sourceTableId)) {
      if (tableNodeMap.size >= MAX_TABLE_NODES) {
        truncated = true;
        return;
      }
      tableNodeMap.set(sourceTableId, {
        id: sourceTableId,
        type: 'default',
        data: {
          label: relationship.source_table,
          kind: 'table',
          tableName: relationship.source_table,
        },
        position: { x: 0, y: 0 },
        className: 'lineage-node lineage-node-table',
      });
    }

    if (!tableNodeMap.has(targetTableId)) {
      if (tableNodeMap.size >= MAX_TABLE_NODES) {
        truncated = true;
        return;
      }
      tableNodeMap.set(targetTableId, {
        id: targetTableId,
        type: 'default',
        data: {
          label: relationship.target_table,
          kind: 'table',
          tableName: relationship.target_table,
        },
        position: { x: 0, y: 0 },
        className: 'lineage-node lineage-node-table',
      });
    }

    const tablePairKey = `${sourceTableId}->${targetTableId}`;
    if (!tableEdgeMap.has(tablePairKey)) {
      tableEdgeMap.set(tablePairKey, {
        sourceId: sourceTableId,
        targetId: targetTableId,
        dagIds: new Set<string>(),
      });
    }

    if (relationship.dag_id) {
      tableEdgeMap.get(tablePairKey)?.dagIds.add(relationship.dag_id);
      const dagId = dagNodeId(relationship.dag_id);
      if (!dagNodeMap.has(dagId)) {
        if (dagNodeMap.size >= MAX_DAG_NODES) {
          truncated = true;
        } else {
          dagNodeMap.set(dagId, {
            id: dagId,
            type: 'default',
            data: {
              label: relationship.dag_id,
              subtitle: 'DAG',
              kind: 'dag',
            },
            position: { x: 0, y: 0 },
            className: 'lineage-node lineage-node-dag',
          });
        }
      }

      const dagEdgeId = `dag:${dagId}->${targetTableId}`;
      if (!dagEdgeIds.has(dagEdgeId) && dagNodeMap.has(dagId)) {
        dagEdgeIds.add(dagEdgeId);
        edges.push({
          id: dagEdgeId,
          source: dagId,
          target: targetTableId,
          type: 'smoothstep',
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
          className: 'lineage-edge lineage-edge-dag',
          data: { kind: 'dag-link' },
        });
      }
    }

    if (relationship.source_column || relationship.column_name) {
      const sourceColumnName = relationship.source_column ?? 'unknown_source';
      const targetColumnName = relationship.column_name ?? 'unknown_target';
      const sourceColumnId = columnNodeId(relationship.source_table, sourceColumnName);
      const targetColumnId = columnNodeId(relationship.target_table, targetColumnName);

      if (!columnNodeMap.has(sourceColumnId)) {
        if (columnNodeMap.size >= MAX_COLUMN_NODES) {
          truncated = true;
        } else {
          columnNodeMap.set(sourceColumnId, {
            id: sourceColumnId,
            type: 'default',
            data: {
              label: sourceColumnName,
              subtitle: relationship.source_table,
              kind: 'column',
              tableName: relationship.source_table,
            },
            position: { x: 0, y: 0 },
            className: 'lineage-node lineage-node-column',
          });
        }
      }

      if (!columnNodeMap.has(targetColumnId)) {
        if (columnNodeMap.size >= MAX_COLUMN_NODES) {
          truncated = true;
        } else {
          columnNodeMap.set(targetColumnId, {
            id: targetColumnId,
            type: 'default',
            data: {
              label: targetColumnName,
              subtitle: relationship.target_table,
              kind: 'column',
              tableName: relationship.target_table,
            },
            position: { x: 0, y: 0 },
            className: 'lineage-node lineage-node-column',
          });
        }
      }

      const sourceMembershipId = `${sourceTableId}->${sourceColumnId}`;
      if (!membershipEdgeIds.has(sourceMembershipId) && columnNodeMap.has(sourceColumnId)) {
        membershipEdgeIds.add(sourceMembershipId);
        edges.push({
          id: sourceMembershipId,
          source: sourceTableId,
          target: sourceColumnId,
          type: 'step',
          className: 'lineage-edge lineage-edge-membership',
          data: { kind: 'membership' },
        });
      }

      const targetMembershipId = `${targetTableId}->${targetColumnId}`;
      if (!membershipEdgeIds.has(targetMembershipId) && columnNodeMap.has(targetColumnId)) {
        membershipEdgeIds.add(targetMembershipId);
        edges.push({
          id: targetMembershipId,
          source: targetTableId,
          target: targetColumnId,
          type: 'step',
          className: 'lineage-edge lineage-edge-membership',
          data: { kind: 'membership' },
        });
      }

      const columnEdgeId = `${sourceColumnId}->${targetColumnId}`;
      if (
        !columnEdgeIds.has(columnEdgeId) &&
        columnNodeMap.has(sourceColumnId) &&
        columnNodeMap.has(targetColumnId)
      ) {
        columnEdgeIds.add(columnEdgeId);
        edges.push({
          id: columnEdgeId,
          source: sourceColumnId,
          target: targetColumnId,
          label: relationship.dag_id ?? undefined,
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
          className: 'lineage-edge lineage-edge-column',
          data: { kind: 'column-lineage' },
        });
      }
    }
  });

  const tableNodes = Array.from(tableNodeMap.values());
  const tableEdges = Array.from(tableEdgeMap.values());
  const levelMap = computeTableLevels(
    tableNodes.map((node) => node.id),
    tableEdges,
  );

  const byLevel = new Map<number, string[]>();
  tableNodes.forEach((node) => {
    const level = levelMap.get(node.id) ?? 0;
    const entries = byLevel.get(level) ?? [];
    entries.push(node.id);
    byLevel.set(level, entries);
  });

  byLevel.forEach((nodeIds, level) => {
    nodeIds.sort();
    nodeIds.forEach((nodeId, index) => {
      const node = tableNodeMap.get(nodeId);
      if (!node) {
        return;
      }
      node.position = {
        x: level * 340,
        y: index * 220,
      };
    });
  });

  tableEdges.forEach((tableEdge) => {
    if (edges.length >= MAX_RENDER_EDGES) {
      truncated = true;
      return;
    }

    edges.push({
      id: `table:${tableEdge.sourceId}->${tableEdge.targetId}`,
      source: tableEdge.sourceId,
      target: tableEdge.targetId,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
      label: tableEdge.dagIds.size > 0 ? `${tableEdge.dagIds.size} DAG` : undefined,
      className: 'lineage-edge lineage-edge-table',
      data: { kind: 'table-lineage' },
    });
  });

  const columnsByTable = new Map<string, GraphNode[]>();
  columnNodeMap.forEach((columnNode) => {
    const parentTable = columnNode.data.tableName;
    if (!parentTable) {
      return;
    }
    const parentTableId = tableNodeId(parentTable);
    const group = columnsByTable.get(parentTableId) ?? [];
    group.push(columnNode);
    columnsByTable.set(parentTableId, group);
  });

  columnsByTable.forEach((columnNodes, parentTableId) => {
    const tableNode = tableNodeMap.get(parentTableId);
    if (!tableNode) {
      return;
    }

    columnNodes.sort((left, right) => left.data.label.localeCompare(right.data.label));
    columnNodes.forEach((columnNode, index) => {
      const columnOffset = index % 2;
      const row = Math.floor(index / 2);
      columnNode.position = {
        x: tableNode.position.x + (columnOffset === 0 ? -140 : 140),
        y: tableNode.position.y + 130 + row * 92,
      };
    });
  });

  dagNodeMap.forEach((dagNode) => {
    const relatedTableEdge = data.lineage_edges.find(
      (edge) => edge.dag_id != null && dagNodeId(edge.dag_id) === dagNode.id,
    );

    if (!relatedTableEdge) {
      return;
    }

    const targetTable = tableNodeMap.get(tableNodeId(relatedTableEdge.target_table));
    if (!targetTable) {
      return;
    }

    dagNode.position = {
      x: targetTable.position.x,
      y: targetTable.position.y - 140,
    };
  });

  nodes.push(...tableNodeMap.values());
  nodes.push(...columnNodeMap.values());
  nodes.push(...dagNodeMap.values());

  if (edges.length > MAX_RENDER_EDGES) {
    truncated = true;
    edges.splice(MAX_RENDER_EDGES);
  }

  return {
    nodes,
    edges,
    tableCount: tableNodeMap.size,
    columnCount: columnNodeMap.size,
    dagCount: dagNodeMap.size,
    truncated,
  };
}

function LineageGraphContent(): JSX.Element {
  const reactFlow = useReactFlow();
  const [graphData, setGraphData] = useState<LineageDependenciesResponse | null>(null);
  const [baseGraphData, setBaseGraphData] = useState<LineageDependenciesResponse | null>(null);
  const [graphMeta, setGraphMeta] = useState({
    tableCount: 0,
    columnCount: 0,
    dagCount: 0,
    truncated: false,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<GraphNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [focusTableName, setFocusTableName] = useState('');
  const [focusDirection, setFocusDirection] = useState<GraphDirection>('upstream');
  const [maxDepth, setMaxDepth] = useState(8);
  const [searchTerm, setSearchTerm] = useState('');
  const [expanding, setExpanding] = useState<GraphDirection | null>(null);

  const buildAndRenderGraph = useCallback(
    (nextGraphData: LineageDependenciesResponse) => {
      const built = buildGraphElements(nextGraphData);
      setNodes(built.nodes);
      setEdges(built.edges);
      setGraphMeta({
        tableCount: built.tableCount,
        columnCount: built.columnCount,
        dagCount: built.dagCount,
        truncated: built.truncated,
      });
      return built;
    },
    [setEdges, setNodes],
  );

  const loadBaseGraph = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);
    setSelectedNodeId(null);
    setSelectedTable(null);

    try {
      const dependencies = await getLineageDependencies();
      const baseline: LineageDependenciesResponse = {
        lineage_edges: dependencies.lineage_edges,
        task_edges: dependencies.task_edges,
      };

      buildAndRenderGraph(baseline);
      setGraphData(baseline);
      setBaseGraphData(baseline);

      requestAnimationFrame(() => {
        reactFlow.fitView({ padding: 0.2, duration: 350 });
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load lineage dependencies';
      setError(message);
      setGraphData(null);
      setBaseGraphData(null);
      setGraphMeta({ tableCount: 0, columnCount: 0, dagCount: 0, truncated: false });
      setNodes([]);
      setEdges([]);
    } finally {
      setLoading(false);
    }
  }, [buildAndRenderGraph, reactFlow, setEdges, setNodes]);

  useEffect(() => {
    void loadBaseGraph();
  }, [loadBaseGraph]);

  const expandFromTable = useCallback(
    async (tableName: string, direction: GraphDirection): Promise<void> => {
      const trimmedTable = tableName.trim();
      if (!trimmedTable || !graphData) {
        return;
      }

      setExpanding(direction);
      setError(null);

      try {
        const response =
          direction === 'upstream'
            ? await getUpstreamLineage(trimmedTable, maxDepth)
            : await getDownstreamLineage(trimmedTable, maxDepth);

        const lineageEdges = response.lineage_chain.map((edge) => toRelationship(edge));
        const mergedGraphData: LineageDependenciesResponse = {
          lineage_edges: mergeRelationships(graphData.lineage_edges, lineageEdges),
          task_edges: graphData.task_edges,
        };

        setGraphData(mergedGraphData);
        buildAndRenderGraph(mergedGraphData);

        requestAnimationFrame(() => {
          reactFlow.fitView({ padding: 0.2, duration: 350 });
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : `Failed to expand ${direction} lineage`;
        setError(message);
      } finally {
        setExpanding(null);
      }
    },
    [buildAndRenderGraph, graphData, maxDepth, reactFlow],
  );

  const handleFocusSubmit = useCallback(
    async (event: FormEvent): Promise<void> => {
      event.preventDefault();
      if (!focusTableName.trim()) {
        setError('Table name is required for lineage expansion.');
        return;
      }

      await expandFromTable(focusTableName, focusDirection);
    },
    [expandFromTable, focusDirection, focusTableName],
  );

  const handleNodeClick: NodeMouseHandler = useCallback(
    (event, node) => {
      setSelectedNodeId(node.id);
      if (node.data.kind === 'table' && node.data.tableName) {
        setSelectedTable(node.data.tableName);
      } else {
        setSelectedTable(null);
      }

      if (node.data.kind === 'table' && node.data.tableName) {
        const direction: GraphDirection = event.shiftKey ? 'downstream' : 'upstream';
        void expandFromTable(node.data.tableName, direction);
      }
    },
    [expandFromTable],
  );

  const decoratedNodes = useMemo(() => {
    if (!selectedNodeId) {
      return nodes;
    }

    return nodes.map((node) => {
      const connected =
        node.id === selectedNodeId ||
        edges.some((edge) => {
          return (
            (edge.source === selectedNodeId && edge.target === node.id) ||
            (edge.target === selectedNodeId && edge.source === node.id)
          );
        });

      return {
        ...node,
        selected: node.id === selectedNodeId,
        style: {
          ...node.style,
          opacity: connected ? 1 : 0.28,
        },
      };
    });
  }, [edges, nodes, selectedNodeId]);

  const decoratedEdges = useMemo(() => {
    if (!selectedNodeId) {
      return edges;
    }

    return edges.map((edge) => {
      const isConnected = edge.source === selectedNodeId || edge.target === selectedNodeId;
      const baseWidth = edge.data?.kind === 'membership' ? 1.1 : 1.8;

      return {
        ...edge,
        animated: isConnected,
        style: {
          ...edge.style,
          strokeWidth: isConnected ? baseWidth + 1.4 : baseWidth,
          opacity: isConnected ? 1 : 0.2,
        },
      };
    });
  }, [edges, selectedNodeId]);

  const graphStats = useMemo(() => {
    return {
      tableCount: graphMeta.tableCount,
      columnCount: graphMeta.columnCount,
      dagCount: graphMeta.dagCount,
      edgeCount: edges.length,
    };
  }, [edges.length, graphMeta.columnCount, graphMeta.dagCount, graphMeta.tableCount]);

  const handleSearchNode = useCallback(
    (event: FormEvent): void => {
      event.preventDefault();
      const term = searchTerm.trim().toLowerCase();
      if (!term) {
        return;
      }

      const match = nodes.find((node) => node.data.label.toLowerCase().includes(term));
      if (!match) {
        setError(`No node matches '${searchTerm.trim()}'.`);
        return;
      }

      setError(null);
      setSelectedNodeId(match.id);
      reactFlow.setCenter(match.position.x + 80, match.position.y + 40, {
        zoom: 1.35,
        duration: 450,
      });
    },
    [nodes, reactFlow, searchTerm],
  );

  const handleResetGraph = useCallback((): void => {
    if (!baseGraphData) {
      return;
    }

    setError(null);
    setSelectedNodeId(null);
    setSelectedTable(null);
    setGraphData(baseGraphData);
    buildAndRenderGraph(baseGraphData);

    requestAnimationFrame(() => {
      reactFlow.fitView({ padding: 0.2, duration: 350 });
    });
  }, [baseGraphData, buildAndRenderGraph, reactFlow]);

  const handleFitView = useCallback((): void => {
    reactFlow.fitView({ padding: 0.2, duration: 350 });
  }, [reactFlow]);

  if (loading) {
    return <LoadingState label="Building interactive lineage graph..." />;
  }

  if (error && !graphData) {
    return <ErrorState message={error} onRetry={loadBaseGraph} />;
  }

  return (
    <div className="lineage-graph-shell">
      <form className="control-form" onSubmit={(event) => void handleFocusSubmit(event)}>
        <label>
          Focus Table
          <input
            type="text"
            value={focusTableName}
            onChange={(event) => setFocusTableName(event.target.value)}
            placeholder="example: mart_sales"
          />
        </label>

        <label>
          Expansion Direction
          <select
            value={focusDirection}
            onChange={(event) => setFocusDirection(event.target.value as GraphDirection)}
          >
            <option value="upstream">Upstream</option>
            <option value="downstream">Downstream</option>
          </select>
        </label>

        <label>
          Max Depth
          <input
            type="number"
            min={1}
            max={50}
            value={maxDepth}
            onChange={(event) => setMaxDepth(Number(event.target.value))}
          />
        </label>

        <button type="submit" disabled={expanding != null}>
          {expanding ? 'Expanding...' : 'Expand Lineage'}
        </button>
      </form>

      <div className="lineage-graph-toolbar panel">
        <form className="lineage-inline-form" onSubmit={handleSearchNode}>
          <label>
            Search Node
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="table, column, or dag"
            />
          </label>
          <button type="submit" className="lineage-toolbar-button">
            Search
          </button>
        </form>

        <div className="lineage-toolbar-actions">
          <button type="button" className="button-secondary" onClick={handleResetGraph}>
            Reset Graph
          </button>
          <button type="button" className="button-secondary" onClick={handleFitView}>
            Fit View
          </button>
        </div>
      </div>

      {error ? <ErrorState message={error} /> : null}

      <div className="lineage-stat-row">
        <span>Tables: {graphStats.tableCount}</span>
        <span>Columns: {graphStats.columnCount}</span>
        <span>DAGs: {graphStats.dagCount}</span>
        <span>Edges: {graphStats.edgeCount}</span>
      </div>

      <div className="lineage-help-text">
        <p>Click a table node to expand upstream lineage. Shift+Click a table node to expand downstream lineage.</p>
        <p>Selecting a node highlights connected edges and neighbors for impact tracing.</p>
      </div>

      <div className="lineage-graph-canvas">
        <ReactFlow
          nodes={decoratedNodes}
          edges={decoratedEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          panOnDrag
          zoomOnScroll
          zoomOnPinch
          zoomOnDoubleClick
          minZoom={0.2}
          maxZoom={1.9}
          onlyRenderVisibleElements
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#c6d5e8" gap={20} size={1.1} />
          <MiniMap
            zoomable
            pannable
            nodeColor={(node) => {
              if (node.data.kind === 'dag') {
                return '#f29f67';
              }
              if (node.data.kind === 'column') {
                return '#2f7dc5';
              }
              return '#1f9d8f';
            }}
            maskColor="rgba(20, 44, 72, 0.12)"
          />
          <Controls showInteractive={false} />
          <Panel position="bottom-right" className="lineage-selected-panel">
            <p>Selected: {selectedNodeId ?? 'none'}</p>
            {selectedTable ? (
              <div className="lineage-selected-actions">
                <button
                  type="button"
                  className="button-secondary"
                  disabled={expanding != null}
                  onClick={() => void expandFromTable(selectedTable, 'upstream')}
                >
                  Upstream
                </button>
                <button
                  type="button"
                  className="button-secondary"
                  disabled={expanding != null}
                  onClick={() => void expandFromTable(selectedTable, 'downstream')}
                >
                  Downstream
                </button>
              </div>
            ) : null}
          </Panel>
        </ReactFlow>
      </div>

      {graphMeta.truncated ? (
        <div className="state-box">
          <p>
            Graph rendering limits were reached for performance safety. Use Focus Table with depth control
            to inspect specific branches.
          </p>
        </div>
      ) : null}
    </div>
  );
}

function LineageGraph(): JSX.Element {
  return (
    <ReactFlowProvider>
      <LineageGraphContent />
    </ReactFlowProvider>
  );
}

export default LineageGraph;
