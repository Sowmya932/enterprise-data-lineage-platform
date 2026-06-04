import { Skeleton } from '@mui/material';

interface SkeletonStateProps {
  rows?: number;
}

function SkeletonState({ rows = 4 }: SkeletonStateProps): JSX.Element {
  return (
    <div className="panel">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={`skeleton-${index}`} height={34} sx={{ mb: 1 }} />
      ))}
    </div>
  );
}

export default SkeletonState;
