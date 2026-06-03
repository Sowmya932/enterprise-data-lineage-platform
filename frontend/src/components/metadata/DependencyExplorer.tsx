import { Chip, Divider, Grid, Paper, Stack, Typography } from '@mui/material';
import type { MetadataAsset } from '../../types/api';

export interface DependencyExplorerData {
  upstream: string[];
  downstream: string[];
  relatedDags: string[];
  impactSummary: string[];
}

interface DependencyExplorerProps {
  data: DependencyExplorerData;
  onNavigateAsset: (asset: MetadataAsset) => void;
}

function toAssetFromToken(token: string): MetadataAsset {
  if (token.includes('.')) {
    const [tableName, columnName] = token.split('.');
    return {
      id: `column-${tableName ?? ''}-${columnName ?? token}`,
      type: 'column',
      title: columnName ?? token,
      subtitle: tableName ? `Table: ${tableName}` : undefined,
      tableName,
      columnName: columnName ?? token,
    };
  }

  if (token.startsWith('dag:')) {
    const dagId = token.replace('dag:', '');
    return {
      id: `dag-${dagId}`,
      type: 'dag',
      title: dagId,
      dagId,
    };
  }

  return {
    id: `table-${token}`,
    type: 'table',
    title: token,
    tableName: token,
  };
}

function DependencySection({
  title,
  items,
  onNavigateAsset,
}: {
  title: string;
  items: string[];
  onNavigateAsset: (asset: MetadataAsset) => void;
}): JSX.Element {
  return (
    <Stack spacing={1}>
      <Typography variant="body2" fontWeight={700}>
        {title}
      </Typography>
      <Stack direction="row" gap={1} flexWrap="wrap">
        {items.length ? (
          items.map((item) => (
            <Chip
              key={`${title}-${item}`}
              label={item}
              variant="outlined"
              clickable
              onClick={() => onNavigateAsset(toAssetFromToken(item))}
            />
          ))
        ) : (
          <Typography variant="caption" color="text.secondary">
            No items found
          </Typography>
        )}
      </Stack>
    </Stack>
  );
}

function DependencyExplorer({ data, onNavigateAsset }: DependencyExplorerProps): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, p: 2.5 }}>
      <Stack spacing={2}>
        <Typography variant="subtitle1" fontWeight={700}>
          Dependency Explorer
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <DependencySection title="Upstream Dependencies" items={data.upstream} onNavigateAsset={onNavigateAsset} />
          </Grid>
          <Grid item xs={12} md={6}>
            <DependencySection title="Downstream Dependencies" items={data.downstream} onNavigateAsset={onNavigateAsset} />
          </Grid>
          <Grid item xs={12} md={6}>
            <DependencySection
              title="Related DAGs"
              items={data.relatedDags.map((dag) => `dag:${dag}`)}
              onNavigateAsset={onNavigateAsset}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <Stack spacing={1}>
              <Typography variant="body2" fontWeight={700}>
                Impact Information
              </Typography>
              {data.impactSummary.length ? (
                data.impactSummary.map((item) => (
                  <Typography key={item} variant="body2" color="text.secondary">
                    {item}
                  </Typography>
                ))
              ) : (
                <Typography variant="caption" color="text.secondary">
                  No impact metadata available
                </Typography>
              )}
            </Stack>
          </Grid>
        </Grid>
        <Divider />
        <Typography variant="caption" color="text.secondary">
          Click any dependency chip to continue exploring the chain.
        </Typography>
      </Stack>
    </Paper>
  );
}

export default DependencyExplorer;
