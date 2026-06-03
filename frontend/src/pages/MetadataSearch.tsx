import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Alert,
  Autocomplete,
  Box,
  CircularProgress,
  FormControlLabel,
  Grid,
  LinearProgress,
  Pagination,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import DependencyExplorer, { type DependencyExplorerData } from '../components/metadata/DependencyExplorer';
import MetadataDetailsPanel from '../components/metadata/MetadataDetailsPanel';
import SearchResultsList from '../components/metadata/SearchResultsList';
import {
  getColumnMetadataDetails,
  getDagMetadataDetails,
  getTableMetadataDetails,
  searchMetadataAssets,
} from '../services/metadataSearchService';
import type {
  ColumnMetadataDetails,
  DagMetadataDetails,
  MetadataAsset,
  MetadataAssetType,
  MetadataDetails,
  MetadataSearchBundle,
  MetadataSuggestion,
  TableMetadataDetails,
} from '../types/api';

const PAGE_SIZE = 8;

interface MetadataPrefillState {
  prefillAsset?: MetadataAsset;
  prefillQuery?: string;
}

const emptyBundle: MetadataSearchBundle = {
  query: '',
  results: [],
  byType: { tables: [], columns: [], dags: [] },
  suggestions: [],
  total: 0,
};

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(value);
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debounced;
}

function normalizeDependencyData(details: MetadataDetails | null): DependencyExplorerData {
  if (!details) {
    return {
      upstream: [],
      downstream: [],
      relatedDags: [],
      impactSummary: [],
    };
  }

  if ('table' in details) {
    return {
      upstream: details.dependencies.upstream.upstream_tables,
      downstream: details.dependencies.downstream.downstream_tables,
      relatedDags: details.related_dags.map((dag) => dag.dag_id),
      impactSummary: [
        `Severity: ${details.impact_metadata.severity}`,
        `Impacted DAGs: ${details.impact_metadata.impacted_dags.length}`,
        `Affected Tables: ${details.impact_metadata.affected_tables.length}`,
      ],
    };
  }

  if ('column_name' in details) {
    return {
      upstream: details.dependencies.upstream.upstream_columns,
      downstream: details.dependencies.downstream.downstream_columns,
      relatedDags: details.related_dags.map((dag) => dag.dag_id),
      impactSummary: [
        `Severity: ${details.impact_metadata.severity}`,
        `Impacted DAGs: ${details.impact_metadata.impacted_dags.length}`,
        `Affected Columns: ${details.impact_metadata.affected_columns.length}`,
      ],
    };
  }

  return {
    upstream: details.dependencies.related_tables,
    downstream: details.dependencies.related_tables,
    relatedDags: details.related_dags.map((dag) => dag.dag_id),
    impactSummary: [
      `Related Tables: ${details.impact_metadata.total_related_tables}`,
      `Task Dependencies: ${details.dependencies.task_dependency_count}`,
    ],
  };
}

async function fetchMetadataDetails(asset: MetadataAsset): Promise<MetadataDetails> {
  if (asset.type === 'table' && asset.tableName) {
    return getTableMetadataDetails(asset.tableName);
  }

  if (asset.type === 'column' && asset.columnName) {
    return getColumnMetadataDetails(asset.columnName, { tableName: asset.tableName });
  }

  if (asset.type === 'dag' && asset.dagId) {
    return getDagMetadataDetails(asset.dagId);
  }

  throw new Error('Unable to identify selected asset.');
}

function MetadataSearch(): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState('');
  const debouncedQuery = useDebouncedValue(searchInput, 400);

  const [includeTypes, setIncludeTypes] = useState<Record<MetadataAssetType, boolean>>({
    table: true,
    column: true,
    dag: true,
  });

  const [bundle, setBundle] = useState<MetadataSearchBundle>(emptyBundle);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [selectedAsset, setSelectedAsset] = useState<MetadataAsset | null>(null);
  const [details, setDetails] = useState<MetadataDetails | null>(null);
  const [page, setPage] = useState(1);

  const includedTypes = useMemo(
    () => (Object.keys(includeTypes) as MetadataAssetType[]).filter((type) => includeTypes[type]),
    [includeTypes],
  );

  const suggestions = bundle.suggestions;

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setBundle(emptyBundle);
      setSearchError(null);
      return;
    }

    if (includedTypes.length === 0) {
      setBundle(emptyBundle);
      setSearchError('Select at least one filter (Tables, Columns, or DAGs).');
      return;
    }

    let isStale = false;

    const runSearch = async (): Promise<void> => {
      setLoadingSearch(true);
      setSearchError(null);
      try {
        const nextBundle = await searchMetadataAssets({
          query: debouncedQuery,
          include: includedTypes,
          limitPerType: 40,
        });

        if (!isStale) {
          setBundle(nextBundle);
          setPage(1);
        }
      } catch (error) {
        if (!isStale) {
          const message = error instanceof Error ? error.message : 'Failed to search metadata.';
          setSearchError(message);
          setBundle(emptyBundle);
        }
      } finally {
        if (!isStale) {
          setLoadingSearch(false);
        }
      }
    };

    void runSearch();

    return () => {
      isStale = true;
    };
  }, [debouncedQuery, includedTypes]);

  const paginatedResults = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return bundle.results.slice(start, start + PAGE_SIZE);
  }, [bundle.results, page]);

  const pageCount = Math.max(1, Math.ceil(bundle.results.length / PAGE_SIZE));

  const dependencyData = useMemo(() => normalizeDependencyData(details), [details]);

  const handleSelectAsset = async (asset: MetadataAsset): Promise<void> => {
    setSelectedAsset(asset);
    setLoadingDetails(true);

    try {
      const payload = await fetchMetadataDetails(asset);
      setDetails(payload as TableMetadataDetails | ColumnMetadataDetails | DagMetadataDetails);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load asset details.';
      setSearchError(message);
      setDetails(null);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleSuggestionSelect = (value: string): void => {
    setSearchInput(value);
  };

  const handleSuggestionChange = async (suggestion: MetadataSuggestion | null): Promise<void> => {
    if (!suggestion) {
      return;
    }
    setSearchInput(suggestion.label);
    await handleSelectAsset(suggestion.asset);
  };

  useEffect(() => {
    const state = location.state as MetadataPrefillState | null;
    if (!state?.prefillAsset) {
      return;
    }

    if (state.prefillQuery) {
      setSearchInput(state.prefillQuery);
    }

    void handleSelectAsset(state.prefillAsset);
    navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  return (
    <section className="page-section">
      <Box>
        <Typography variant="h5" fontWeight={700} sx={{ mb: 0.75 }}>
          Metadata Search & Dependency Explorer
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Search tables, columns, and DAGs globally, inspect metadata details, and traverse dependency chains.
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Stack spacing={2}>
          <Autocomplete
            freeSolo
            options={suggestions}
            getOptionLabel={(option) => (typeof option === 'string' ? option : option.label)}
            inputValue={searchInput}
            onInputChange={(_, value) => handleSuggestionSelect(value)}
            onChange={(_, value) => {
              if (typeof value === 'string') {
                handleSuggestionSelect(value);
                return;
              }
              void handleSuggestionChange(value);
            }}
            loading={loadingSearch}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Global Search"
                placeholder="Search metadata assets..."
                InputProps={{
                  ...params.InputProps,
                  endAdornment: (
                    <>
                      {loadingSearch ? <CircularProgress color="inherit" size={18} /> : null}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                }}
              />
            )}
            renderOption={(props, option) => (
              <Box component="li" {...props} key={option.id}>
                <Stack>
                  <Typography variant="body2" fontWeight={600}>
                    {option.label}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {option.type.toUpperCase()} {option.description ? `- ${option.description}` : ''}
                  </Typography>
                </Stack>
              </Box>
            )}
          />

          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <FormControlLabel
              control={
                <Switch
                  checked={includeTypes.table}
                  onChange={(event) =>
                    setIncludeTypes((current) => ({ ...current, table: event.target.checked }))
                  }
                />
              }
              label="Tables"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={includeTypes.column}
                  onChange={(event) =>
                    setIncludeTypes((current) => ({ ...current, column: event.target.checked }))
                  }
                />
              }
              label="Columns"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={includeTypes.dag}
                  onChange={(event) =>
                    setIncludeTypes((current) => ({ ...current, dag: event.target.checked }))
                  }
                />
              }
              label="DAGs"
            />
          </Stack>

          {loadingSearch ? <LinearProgress /> : null}
          {searchError ? <Alert severity="error">{searchError}</Alert> : null}
        </Stack>
      </Paper>

      <Grid container spacing={2}>
        <Grid item xs={12} lg={4}>
          {bundle.results.length ? (
            <Stack spacing={1.5}>
              <SearchResultsList
                results={paginatedResults}
                selectedAssetId={selectedAsset?.id}
                onSelect={(asset) => {
                  void handleSelectAsset(asset);
                }}
              />
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="caption" color="text.secondary">
                  Showing {paginatedResults.length} of {bundle.results.length} fetched results
                </Typography>
                <Pagination
                  page={page}
                  count={pageCount}
                  size="small"
                  onChange={(_, nextPage) => setPage(nextPage)}
                />
              </Stack>
            </Stack>
          ) : debouncedQuery.trim() && !loadingSearch ? (
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
              <Typography variant="subtitle1" fontWeight={700}>
                No Results Found
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Try another keyword, broaden filters, or search by exact table, column, or DAG name.
              </Typography>
            </Paper>
          ) : (
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
              <Typography variant="subtitle1" fontWeight={700}>
                Start Searching
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Type at least one character to fetch metadata suggestions and search results.
              </Typography>
            </Paper>
          )}
        </Grid>

        <Grid item xs={12} lg={8}>
          <Stack spacing={2}>
            {loadingDetails ? <LinearProgress /> : null}
            <MetadataDetailsPanel
              asset={selectedAsset}
              details={details}
              onNavigateAsset={(asset) => {
                void handleSelectAsset(asset);
              }}
            />
            <DependencyExplorer
              data={dependencyData}
              onNavigateAsset={(asset) => {
                void handleSelectAsset(asset);
              }}
            />
          </Stack>
        </Grid>
      </Grid>
    </section>
  );
}

export default MetadataSearch;
