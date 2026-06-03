import { useMemo } from 'react';
import { Box, Paper, Stack, Typography } from '@mui/material';
import ReactFlow, { Background, Controls, MarkerType, MiniMap, type Edge, type Node } from 'reactflow';
import type { ColumnImpactResponse, RecursiveLineageEdge, TableImpactResponse } from '../../types/api';

type GraphNodeData = {
  label: string;
  kind: 'root' | 'table' | 'column' | 'dag';
  subtitle?: string;
};

function nodeColor(kind: GraphNodeData['kind']): string {
  if (kind === 'root') {
    return '#0f172a';
  }
  if (kind === 'table') {
    return '#0369a1';
  }
  if (kind === 'column') {
    return '#14532d';
  }
  return '#7c2d12';
}

function buildTableGraph(
  data: TableImpactResponse,
): { nodes: Node<GraphNodeData>[]; edges: Edge[] } {
  const nodes: Node<GraphNodeData>[] = [];
  const edges: Edge[] = [];
  const nodeById = new Map<string, Node<GraphNodeData>>();
  const byDepth = new Map<number, string[]>();

  const addNode = (id: string, label: string, kind: GraphNodeData['kind'], depth: number, subtitle?: string): void => {
    if (nodeById.has(id)) {
      return;
    }
    const rows = byDepth.get(depth) ?? [];
    const y = rows.length * 120;
    rows.push(id);
    byDepth.set(depth, rows);

    const node: Node<GraphNodeData> = {
      id,
      position: { x: depth * 260, y },
      data: { label, kind, subtitle },
      style: {
        border: '1px solid #d5d9df',
        borderRadius: 10,
        padding: 8,
        background: '#ffffff',
        minWidth: 170,
      },
    };
    nodeById.set(id, node);
    nodes.push(node);
  };

  const rootId = `table:${data.source_table}`;
  addNode(rootId, data.source_table, 'root', 0, 'Source Table');

  data.lineage_chain.forEach((edge: RecursiveLineageEdge, index) => {
    const sourceId = `table:${edge.source_table}`;
    const targetId = `table:${edge.target_table}`;

    addNode(sourceId, edge.source_table, edge.source_table === data.source_table ? 'root' : 'table', Math.max(0, edge.depth - 1));
    addNode(targetId, edge.target_table, 'table', edge.depth);

    const edgeId = `lineage:${sourceId}->${targetId}-${index}`;
    edges.push({
      id: edgeId,
      source: sourceId,
      target: targetId,
      label: `d${edge.depth}`,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
    });

    if (edge.dag_id) {
      const dagId = `dag:${edge.dag_id}`;
      addNode(dagId, edge.dag_id, 'dag', edge.depth, 'DAG');
      edges.push({
        id: `dag:${dagId}->${targetId}-${index}`,
        source: dagId,
        target: targetId,
        type: 'step',
      });
    }
  });

  return { nodes, edges };
}

function buildColumnGraph(
  data: ColumnImpactResponse,
): { nodes: Node<GraphNodeData>[]; edges: Edge[] } {
  const nodes: Node<GraphNodeData>[] = [];
  const edges: Edge[] = [];
  const nodeById = new Set<string>();
  const byDepth = new Map<number, number>();

  const addNode = (id: string, label: string, kind: GraphNodeData['kind'], depth: number, subtitle?: string): void => {
    if (nodeById.has(id)) {
      return;
    }
    const currentIndex = byDepth.get(depth) ?? 0;
    byDepth.set(depth, currentIndex + 1);
    nodeById.add(id);

    nodes.push({
      id,
      position: { x: depth * 260, y: currentIndex * 120 },
      data: { label, kind, subtitle },
      style: {
        border: '1px solid #d5d9df',
        borderRadius: 10,
        padding: 8,
        background: '#ffffff',
        minWidth: 170,
      },
    });
  };

  const rootLabel = data.source_table ? `${data.source_table}.${data.source_column}` : data.source_column;
  const rootId = `column-root:${rootLabel}`;
  addNode(rootId, rootLabel, 'root', 0, 'Source Column');

  data.affected_columns.forEach((column, index) => {
    const columnId = `column:${column.table}.${column.column}`;
    const tableId = `table:${column.table}`;

    addNode(columnId, `${column.table}.${column.column}`, 'column', column.depth, column.transformation_type);
    addNode(tableId, column.table, 'table', Math.max(column.depth - 1, 1), 'Affected Table');

    edges.push({
      id: `impact:${rootId}->${columnId}-${index}`,
      source: rootId,
      target: columnId,
      type: 'smoothstep',
      label: `${column.transformation_type} | d${column.depth}`,
      markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
    });
    edges.push({
      id: `belongs:${columnId}->${tableId}-${index}`,
      source: columnId,
      target: tableId,
      type: 'step',
    });
  });

  data.dag_details.forEach((dag, index) => {
    const dagId = `dag:${dag.dag_id}`;
    const tableId = `table:${dag.affected_table}`;
    addNode(dagId, dag.dag_id, 'dag', Math.max(dag.depth, 1), 'DAG');
    addNode(tableId, dag.affected_table, 'table', Math.max(dag.depth, 1));
    edges.push({
      id: `dag-edge:${dagId}->${tableId}-${index}`,
      source: dagId,
      target: tableId,
      type: 'step',
    });
  });

  return { nodes, edges };
}

interface ImpactDependencyGraphProps {
  tableResult: TableImpactResponse | null;
  columnResult: ColumnImpactResponse | null;
}

function ImpactDependencyGraph({ tableResult, columnResult }: ImpactDependencyGraphProps): JSX.Element {
  const graph = useMemo(() => {
    if (tableResult) {
      return buildTableGraph(tableResult);
    }
    if (columnResult) {
      return buildColumnGraph(columnResult);
    }
    return { nodes: [] as Node<GraphNodeData>[], edges: [] as Edge[] };
  }, [tableResult, columnResult]);

  if (!tableResult && !columnResult) {
    return (
      <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
        <Typography variant="subtitle1" fontWeight={700}>
          Impact Dependency Graph
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Run table or column impact analysis to visualize the dependency chain.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Stack spacing={1.25}>
        <Typography variant="subtitle1" fontWeight={700}>
          Impact Dependency Graph
        </Typography>
        <Box sx={{ height: 420, border: '1px solid #e5e7eb', borderRadius: 2, overflow: 'hidden' }}>
          <ReactFlow
            nodes={graph.nodes}
            edges={graph.edges}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            proOptions={{ hideAttribution: true }}
          >
            <MiniMap
              zoomable
              pannable
              nodeColor={(node) => nodeColor((node.data as GraphNodeData).kind)}
            />
            <Controls />
            <Background gap={20} size={1} />
          </ReactFlow>
        </Box>
      </Stack>
    </Paper>
  );
}

export default ImpactDependencyGraph;
