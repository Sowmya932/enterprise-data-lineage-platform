import {
  Chip,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import type { MetadataAsset } from '../../types/api';

interface SearchResultsListProps {
  results: MetadataAsset[];
  selectedAssetId?: string;
  onSelect: (asset: MetadataAsset) => void;
}

const colorByType: Record<MetadataAsset['type'], 'primary' | 'success' | 'warning'> = {
  table: 'success',
  column: 'primary',
  dag: 'warning',
};

function SearchResultsList({ results, selectedAssetId, onSelect }: SearchResultsListProps): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ px: 2, py: 1.25, borderBottom: '1px solid', borderColor: 'divider' }}
      >
        <Typography variant="subtitle1" fontWeight={700}>
          Search Results
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {results.length} item(s)
        </Typography>
      </Stack>

      <List disablePadding>
        {results.map((asset) => (
          <ListItem key={asset.id} disablePadding>
            <ListItemButton selected={selectedAssetId === asset.id} onClick={() => onSelect(asset)}>
              <ListItemText
                primary={asset.title}
                secondary={asset.subtitle}
                primaryTypographyProps={{ fontWeight: 600 }}
              />
              <Chip label={asset.type.toUpperCase()} color={colorByType[asset.type]} size="small" />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Paper>
  );
}

export default SearchResultsList;
