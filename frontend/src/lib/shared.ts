/**
 * Shared option lists and display formatters.
 *
 * NICHES must match the backend's `Niche` choices (apps/core/choices.py): anything else is
 * rejected with a 400 when saved or used as a filter.
 */

/**
 * Every creator and brand page has the person's username in its address:
 * '/creator/dashboard' becomes '/creator/imran/dashboard'. Other addresses are returned as they are.
 */
export const withUsername = (path: string, username: string): string => {
  const m = /^\/(creator|brand)(\/.*)?$/.exec(path);
  return m ? `/${m[1]}/${encodeURIComponent(username)}${m[2] ?? ''}` : path;
};

export const accountsPath = (role: 'creator' | 'brand', username: string): string =>
  withUsername(`/${role}/accounts`, username);

export const NICHES = ['Beauty', 'Fitness', 'Food', 'Tech', 'Travel', 'Other'] as const;

export const PLATFORMS = ['YouTube', 'Instagram', 'TikTok', 'Facebook'] as const;

export const fmtNumber = (n: number): string => {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + 'K';
  return n.toString();
};

export const fmtRelativeTime = (iso: string): string => {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.round(ms / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return m + 'm ago';
  const h = Math.round(m / 60);
  if (h < 24) return h + 'h ago';
  const d = Math.round(h / 24);
  if (d < 7) return d + 'd ago';
  return new Date(iso).toLocaleDateString();
};

export const fmtDate = (iso: string): string =>
  new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });

export const currency = (n: number): string =>
  '$' + n.toLocaleString(undefined, { maximumFractionDigits: 0 });
