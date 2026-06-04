import type { MetadataAsset } from '../types/api';

const MAX_ITEMS = 8;

interface ActivityState {
  recentSearches: RecentSearchEntry[];
  recentImpacts: RecentImpactEntry[];
  recentLineageViews: RecentLineageEntry[];
}

export interface RecentSearchEntry {
  id: string;
  label: string;
  type: MetadataAsset['type'];
  timestamp: string;
}

export interface RecentImpactEntry {
  id: string;
  label: string;
  severity: string;
  timestamp: string;
}

export interface RecentLineageEntry {
  id: string;
  label: string;
  direction: 'upstream' | 'downstream';
  timestamp: string;
}

const STORAGE_KEY = 'lineage-platform-activity';

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) {
      return false;
    }
    seen.add(item.id);
    return true;
  });
}

function keepLatest<T extends { timestamp: string }>(items: T[]): T[] {
  return [...items].sort((left, right) => right.timestamp.localeCompare(left.timestamp)).slice(0, MAX_ITEMS);
}

function safeParse(raw: string | null): ActivityState {
  if (!raw) {
    return {
      recentSearches: [],
      recentImpacts: [],
      recentLineageViews: [],
    };
  }

  try {
    const parsed = JSON.parse(raw) as Partial<ActivityState>;
    return {
      recentSearches: parsed.recentSearches ?? [],
      recentImpacts: parsed.recentImpacts ?? [],
      recentLineageViews: parsed.recentLineageViews ?? [],
    };
  } catch {
    return {
      recentSearches: [],
      recentImpacts: [],
      recentLineageViews: [],
    };
  }
}

function readState(): ActivityState {
  if (!isBrowser()) {
    return {
      recentSearches: [],
      recentImpacts: [],
      recentLineageViews: [],
    };
  }

  return safeParse(window.localStorage.getItem(STORAGE_KEY));
}

function writeState(next: ActivityState): void {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

export function getRecentActivity(): ActivityState {
  return readState();
}

export function recordRecentSearch(asset: MetadataAsset): void {
  const state = readState();
  const entry: RecentSearchEntry = {
    id: `${asset.type}:${asset.title.toLowerCase()}`,
    label: asset.subtitle ? `${asset.title} (${asset.subtitle})` : asset.title,
    type: asset.type,
    timestamp: new Date().toISOString(),
  };

  writeState({
    ...state,
    recentSearches: keepLatest(uniqueById([entry, ...state.recentSearches])),
  });
}

export function recordRecentImpact(params: { mode: 'table' | 'column'; target: string; severity: string }): void {
  const state = readState();
  const entry: RecentImpactEntry = {
    id: `${params.mode}:${params.target.toLowerCase()}`,
    label: `${params.mode === 'table' ? 'Table' : 'Column'}: ${params.target}`,
    severity: params.severity,
    timestamp: new Date().toISOString(),
  };

  writeState({
    ...state,
    recentImpacts: keepLatest(uniqueById([entry, ...state.recentImpacts])),
  });
}

export function recordRecentLineageView(params: {
  tableName: string;
  direction: 'upstream' | 'downstream';
}): void {
  const state = readState();
  const entry: RecentLineageEntry = {
    id: `${params.direction}:${params.tableName.toLowerCase()}`,
    label: params.tableName,
    direction: params.direction,
    timestamp: new Date().toISOString(),
  };

  writeState({
    ...state,
    recentLineageViews: keepLatest(uniqueById([entry, ...state.recentLineageViews])),
  });
}
