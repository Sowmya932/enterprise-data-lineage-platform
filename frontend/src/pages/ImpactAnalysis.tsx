import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  Divider,
  Grid,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import ImpactDependencyGraph from '../components/impact/ImpactDependencyGraph';
import ImpactSummaryCards from '../components/impact/ImpactSummaryCards';
import SeverityBadge from '../components/SeverityBadge';
import { recordRecentImpact } from '../services/activityService';
import { analyzeColumnImpact, analyzeTableImpact } from '../services/impactService';
import { logger } from '../services/logger';
import { searchColumns, searchTables } from '../services/searchService';
import type {
  ColumnImpactResponse,
  ImpactedColumnDetail,
  MetadataAsset,
  TableImpactResponse,
} from '../types/api';

type AnalysisMode = 'table' | 'column';

const severityScale = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const;

function toTableAsset(tableName: string): MetadataAsset {
  return {
    id: `table-${tableName}`,
    type: 'table',
    title: tableName,
    tableName,
  };
}

function toColumnAsset(item: ImpactedColumnDetail): MetadataAsset {
  return {
    id: `column-${item.table}-${item.column}`,
    type: 'column',
    title: item.column,
    subtitle: `Table: ${item.table}`,
    tableName: item.table,
    columnName: item.column,
  };
}

function toDagAsset(dagId: string): MetadataAsset {
  return {
    id: `dag-${dagId}`,
    type: 'dag',
    title: dagId,
    dagId,
  };
}

function ImpactAnalysis(): JSX.Element {
  const navigate = useNavigate();

  const [mode, setMode] = useState<AnalysisMode>('table');
  const [tableName, setTableName] = useState('');
  const [columnName, setColumnName] = useState('');
  const [maxDepth, setMaxDepth] = useState(10);

  const [tableOptions, setTableOptions] = useState<string[]>([]);
  const [columnOptions, setColumnOptions] = useState<string[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tableResult, setTableResult] = useState<TableImpactResponse | null>(null);
  const [columnResult, setColumnResult] = useState<ColumnImpactResponse | null>(null);

  const affectedColumns = columnResult?.affected_columns ?? [];
  const affectedTables = tableResult?.affected_tables ?? columnResult?.affected_tables ?? [];
  const impactedDags = tableResult?.impacted_dags ?? columnResult?.impacted_dags ?? [];
  const severity = tableResult?.severity ?? columnResult?.severity ?? 'NONE';

  const maxDependencyDepth = useMemo(() => {
    if (tableResult) {
      return tableResult.lineage_chain.reduce((max, edge) => Math.max(max, edge.depth), 0);
    }
    if (columnResult) {
      return columnResult.affected_columns.reduce((max, edge) => Math.max(max, edge.depth), 0);
    }
    return 0;
  }, [tableResult, columnResult]);

  const totalImpactedAssets = useMemo(() => {
    const tableSet = new Set(affectedTables);
    const columnSet = new Set(affectedColumns.map((item) => `${item.table}.${item.column}`));
    return tableSet.size + columnSet.size;
  }, [affectedColumns, affectedTables]);

  const criticalDependencies = useMemo(() => {
    if (tableResult) {
      return tableResult.lineage_chain.filter((edge) => edge.depth >= 3).length;
    }
    return affectedColumns.filter((column) => column.depth >= 3).length;
  }, [tableResult, affectedColumns]);

  const hasResult = Boolean(tableResult || columnResult);

  const loadTableSuggestions = async (input: string): Promise<void> => {
    const query = input.trim();
    if (query.length < 2) {
      setTableOptions([]);
      return;
    }
    try {
      const response = await searchTables({ query, limit: 8, offset: 0 });
      setTableOptions(response.items.map((item) => item.name));
    } catch {
      setTableOptions([]);
    }
  };

  const loadColumnSuggestions = async (input: string): Promise<void> => {
    const query = input.trim();
    if (query.length < 2) {
      setColumnOptions([]);
      return;
    }
    try {
      const response = await searchColumns({ query, limit: 8, offset: 0 });
      setColumnOptions(response.items.map((item) => item.name));
    } catch {
      setColumnOptions([]);
    }
  };

  const navigateToMetadata = (asset: MetadataAsset): void => {
    navigate('/search', {
      state: {
        prefillAsset: asset,
        prefillQuery: asset.title,
      },
    });
  };

  const validate = (): string | null => {
    if (mode === 'table' && !tableName.trim()) {
      return 'Table name is required for table impact analysis.';
    }

    if (mode === 'column' && !columnName.trim()) {
      return 'Column name is required for column impact analysis.';
    }

    if (maxDepth < 1 || maxDepth > 50) {
      return 'Max depth must be between 1 and 50.';
    }

    return null;
  };

  const handleAnalyze = async (): Promise<void> => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (mode === 'table') {
        const response = await analyzeTableImpact(tableName.trim(), maxDepth);
        setTableResult(response);
        setColumnResult(null);
        recordRecentImpact({
          mode,
          target: tableName.trim(),
          severity: response.severity,
        });
      } else {
        const response = await analyzeColumnImpact(columnName.trim(), {
          table: tableName.trim() || undefined,
          maxDepth,
        });
        setColumnResult(response);
        setTableResult(null);
        recordRecentImpact({
          mode,
          target: columnName.trim(),
          severity: response.severity,
        });
      }

      logger.info('Impact analysis completed', {
        mode,
        table: tableName,
        column: columnName,
        maxDepth,
      });
    } catch (analysisError) {
      const message = analysisError instanceof Error ? analysisError.message : 'Impact analysis failed.';
      setError(message);
      setTableResult(null);
      setColumnResult(null);
      logger.error('Impact analysis failed', {
        message,
        mode,
        table: tableName,
        column: columnName,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-section">
      <Box>
        <Typography variant="h5" fontWeight={700} sx={{ mb: 0.75 }}>
          Impact Analysis Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Evaluate blast radius for table and column changes before deployment.
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={2}>
            <TextField
              select
              fullWidth
              label="Mode"
              value={mode}
              onChange={(event) => {
                setMode(event.target.value as AnalysisMode);
                setError(null);
              }}
            >
              <MenuItem value="table">Table Impact</MenuItem>
              <MenuItem value="column">Column Impact</MenuItem>
            </TextField>
          </Grid>

          <Grid item xs={12} md={4}>
            <Autocomplete
              freeSolo
              options={tableOptions}
              inputValue={tableName}
              onInputChange={(_, value) => {
                setTableName(value);
                void loadTableSuggestions(value);
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label={mode === 'column' ? 'Table Name (Optional Scope)' : 'Table Name'}
                  placeholder="ex: mart_sales"
                />
              )}
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <Autocomplete
              freeSolo
              options={columnOptions}
              inputValue={columnName}
              onInputChange={(_, value) => {
                setColumnName(value);
                void loadColumnSuggestions(value);
              }}
              disabled={mode !== 'column'}
              renderInput={(params) => (
                <TextField {...params} label="Column Name" placeholder="ex: revenue" />
              )}
            />
          </Grid>

          <Grid item xs={12} md={1.5}>
            <TextField
              fullWidth
              type="number"
              label="Max Depth"
              value={maxDepth}
              inputProps={{ min: 1, max: 50 }}
              onChange={(event) => setMaxDepth(Number(event.target.value))}
            />
          </Grid>

          <Grid item xs={12} md={1.5}>
            <Button
              fullWidth
              variant="contained"
              onClick={() => {
                void handleAnalyze();
              }}
              disabled={loading}
              sx={{ height: 56 }}
            >
              {loading ? 'Analyzing...' : 'Analyze'}
            </Button>
          </Grid>
        </Grid>

        {error ? (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        ) : null}
      </Paper>

      <ImpactSummaryCards
        totalImpactedAssets={totalImpactedAssets}
        totalImpactedDags={impactedDags.length}
        criticalDependencies={criticalDependencies}
      />

      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25} alignItems={{ sm: 'center' }}>
          <Typography variant="subtitle2" color="text.secondary">
            Severity Level
          </Typography>
          <SeverityBadge severity={severity} />
          <Divider orientation="vertical" flexItem sx={{ display: { xs: 'none', sm: 'block' } }} />
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {severityScale.map((level) => (
              <Chip
                key={level}
                label={level}
                variant={severity === level ? 'filled' : 'outlined'}
                color={severity === level ? 'primary' : 'default'}
                size="small"
              />
            ))}
          </Stack>
          {hasResult ? (
            <Typography variant="body2" color="text.secondary" sx={{ ml: { sm: 'auto' } }}>
              Max dependency depth: {maxDependencyDepth}
            </Typography>
          ) : null}
        </Stack>
      </Paper>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, height: '100%' }}>
            <Typography variant="subtitle1" fontWeight={700}>
              Affected Tables ({affectedTables.length})
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
              {affectedTables.map((table) => (
                <Chip
                  key={table}
                  label={table}
                  clickable
                  onClick={() => navigateToMetadata(toTableAsset(table))}
                />
              ))}
              {!affectedTables.length ? (
                <Typography variant="body2" color="text.secondary">
                  No impacted tables found.
                </Typography>
              ) : null}
            </Stack>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, height: '100%' }}>
            <Typography variant="subtitle1" fontWeight={700}>
              Impacted DAGs ({impactedDags.length})
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
              {impactedDags.map((dag) => (
                <Chip key={dag} label={dag} color="info" clickable onClick={() => navigateToMetadata(toDagAsset(dag))} />
              ))}
              {!impactedDags.length ? (
                <Typography variant="body2" color="text.secondary">
                  No impacted DAGs found.
                </Typography>
              ) : null}
            </Stack>
          </Paper>
        </Grid>
      </Grid>

      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="subtitle1" fontWeight={700}>
          Affected Columns ({affectedColumns.length})
        </Typography>
        {affectedColumns.length ? (
          <Table size="small" sx={{ mt: 1 }}>
            <TableHead>
              <TableRow>
                <TableCell>Table</TableCell>
                <TableCell>Column</TableCell>
                <TableCell>Dependency Depth</TableCell>
                <TableCell>Transformation</TableCell>
                <TableCell>Severity</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {affectedColumns.map((item, index) => (
                <TableRow key={`${item.table}-${item.column}-${index}`}>
                  <TableCell>
                    <Button size="small" onClick={() => navigateToMetadata(toTableAsset(item.table))}>
                      {item.table}
                    </Button>
                  </TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => navigateToMetadata(toColumnAsset(item))}>
                      {item.column}
                    </Button>
                  </TableCell>
                  <TableCell>{item.depth}</TableCell>
                  <TableCell>{item.transformation_type}</TableCell>
                  <TableCell>
                    <SeverityBadge severity={severity} compact />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            Run column impact analysis to list impacted columns.
          </Typography>
        )}
      </Paper>

      <ImpactDependencyGraph tableResult={tableResult} columnResult={columnResult} />
    </section>
  );
}

export default ImpactAnalysis;
