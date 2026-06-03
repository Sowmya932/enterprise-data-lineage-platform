import { Grid, Paper, Stack, Typography } from '@mui/material';

interface ImpactSummaryCardsProps {
  totalImpactedAssets: number;
  totalImpactedDags: number;
  criticalDependencies: number;
}

interface SummaryItem {
  key: string;
  title: string;
  value: number;
  accent: string;
  helper: string;
}

function ImpactSummaryCards({
  totalImpactedAssets,
  totalImpactedDags,
  criticalDependencies,
}: ImpactSummaryCardsProps): JSX.Element {
  const items: SummaryItem[] = [
    {
      key: 'assets',
      title: 'Total Impacted Assets',
      value: totalImpactedAssets,
      accent: '#0f766e',
      helper: 'Tables + columns included in blast radius',
    },
    {
      key: 'dags',
      title: 'Total Impacted DAGs',
      value: totalImpactedDags,
      accent: '#1d4ed8',
      helper: 'Pipelines that need validation or reruns',
    },
    {
      key: 'critical',
      title: 'Critical Dependencies',
      value: criticalDependencies,
      accent: '#b42318',
      helper: 'Dependencies at depth >= 3',
    },
  ];

  return (
    <Grid container spacing={2}>
      {items.map((item) => (
        <Grid item xs={12} md={4} key={item.key}>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              borderRadius: 2,
              borderTop: `4px solid ${item.accent}`,
              height: '100%',
            }}
          >
            <Stack spacing={0.75}>
              <Typography variant="body2" color="text.secondary">
                {item.title}
              </Typography>
              <Typography variant="h4" fontWeight={800}>
                {item.value.toLocaleString()}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {item.helper}
              </Typography>
            </Stack>
          </Paper>
        </Grid>
      ))}
    </Grid>
  );
}

export default ImpactSummaryCards;
