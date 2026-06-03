import {
  Chip,
  Divider,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { MetadataAsset, MetadataDetails } from '../../types/api';

interface MetadataDetailsPanelProps {
  asset: MetadataAsset | null;
  details: MetadataDetails | null;
  onNavigateAsset: (asset: MetadataAsset) => void;
}

function buildLinkedAsset(type: MetadataAsset['type'], value: string): MetadataAsset {
  if (type === 'table') {
    return { id: `table-${value}`, type, title: value, tableName: value };
  }
  if (type === 'dag') {
    return { id: `dag-${value}`, type, title: value, dagId: value };
  }
  const [tableName, columnName] = value.split('.');
  return {
    id: `column-${tableName ?? ''}-${columnName ?? value}`,
    type,
    title: columnName ?? value,
    subtitle: tableName ? `Table: ${tableName}` : undefined,
    tableName,
    columnName: columnName ?? value,
  };
}

function MetadataDetailsPanel({ asset, details, onNavigateAsset }: MetadataDetailsPanelProps): JSX.Element {
  if (!asset || !details) {
    return (
      <Paper variant="outlined" sx={{ borderRadius: 2, p: 2.5 }}>
        <Typography variant="subtitle1" fontWeight={700}>
          Metadata Details
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Select a table, column, or DAG from search results to inspect metadata details.
        </Typography>
      </Paper>
    );
  }

  const title = asset.type === 'table' ? 'Table Details' : asset.type === 'column' ? 'Column Details' : 'DAG Details';

  const lineageRows: Array<{ key: string; source: string; target: string; dagId?: string | null }> =
    'dag' in details
      ? details.lineage_relationships.table_level.slice(0, 8).map((item) => ({
          key: `dag-lineage-${item.id}`,
          source: item.source_table,
          target: item.target_table,
          dagId: item.dag_id,
        }))
      : details.lineage_relationships.slice(0, 8).map((item, index) => ({
          key: `lineage-${item.source_table}-${item.target_table}-${index}`,
          source: item.source_table,
          target: item.target_table,
          dagId: item.dag_id,
        }));

  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, p: 2.5 }}>
      <Stack spacing={2}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="subtitle1" fontWeight={700}>
            {title}
          </Typography>
          <Chip label={asset.type.toUpperCase()} size="small" />
        </Stack>

        {'table' in details ? (
          <Stack spacing={1}>
            <Typography variant="body2">Table: {details.table.name}</Typography>
            <Typography variant="body2" color="text.secondary">
              Schema: {details.table.schema_name ?? 'N/A'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Columns: {details.columns.length}
            </Typography>
          </Stack>
        ) : null}

        {'column_name' in details ? (
          <Stack spacing={1}>
            <Typography variant="body2">Column: {details.column_name}</Typography>
            <Typography variant="body2" color="text.secondary">
              Matched Tables: {details.matched_tables.join(', ') || 'N/A'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Column Records: {details.column_records.length}
            </Typography>
          </Stack>
        ) : null}

        {'dag' in details ? (
          <Stack spacing={1}>
            <Typography variant="body2">DAG: {details.dag.dag_id}</Typography>
            <Typography variant="body2" color="text.secondary">
              Tasks: {details.tasks.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Related Tables: {details.dependencies.related_tables.join(', ') || 'N/A'}
            </Typography>
          </Stack>
        ) : null}

        <Divider />

        <Typography variant="body2" fontWeight={700}>
          Related Lineage Relationships
        </Typography>
        <Table size="small" sx={{ '& td, & th': { py: 0.75 } }}>
          <TableHead>
            <TableRow>
              <TableCell>Source</TableCell>
              <TableCell>Target</TableCell>
              <TableCell>DAG</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {lineageRows.map((item) => (
              <TableRow key={item.key}>
                <TableCell>
                  <Typography
                    variant="body2"
                    color="primary"
                    sx={{ cursor: 'pointer' }}
                    onClick={() => onNavigateAsset(buildLinkedAsset('table', item.source))}
                  >
                    {item.source}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography
                    variant="body2"
                    color="primary"
                    sx={{ cursor: 'pointer' }}
                    onClick={() => onNavigateAsset(buildLinkedAsset('table', item.target))}
                  >
                    {item.target}
                  </Typography>
                </TableCell>
                <TableCell>
                  {item.dagId ? (
                    <Typography
                      variant="body2"
                      color="primary"
                      sx={{ cursor: 'pointer' }}
                      onClick={() => onNavigateAsset(buildLinkedAsset('dag', item.dagId as string))}
                    >
                      {item.dagId}
                    </Typography>
                  ) : (
                    '-'
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Stack>
    </Paper>
  );
}

export default MetadataDetailsPanel;
