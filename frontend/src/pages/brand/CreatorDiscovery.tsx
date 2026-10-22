import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { searchCreators } from '../../state/Store';
import type { CreatorProfile } from '../../types';
import {
  EmptyState, Input, Select, Button, PageHeader, ProfileTile, PlatformIcon,
  VerifiedBadge, Label, Rating,
} from '../../components/ui';
import { NICHES, PLATFORMS, fmtNumber } from '../../lib/shared';
import { Search, X, SlidersHorizontal, ArrowUpRight, ArrowLeft, ArrowRight, Users } from 'lucide-react';

/** The words the sort box shows, and what the server is asked for ("-" in front means high to low). */
const SORTS = [
  { value: 'followers', label: 'Followers (high to low)', ordering: '-followers' },
  { value: 'engagement', label: 'Engagement (high to low)', ordering: '-engagement' },
  { value: 'rating', label: 'Rating (high to low)', ordering: '-rating' },
  { value: 'rateLow', label: 'Rate (low to high)', ordering: 'rate' },
  { value: 'rateHigh', label: 'Rate (high to low)', ordering: '-rate' },
] as const;
type Sort = (typeof SORTS)[number]['value'];

const MIN_RATINGS = [
  { value: '', label: 'Any rating' },
  { value: '3', label: '3 stars and up' },
  { value: '3.5', label: '3.5 stars and up' },
  { value: '4', label: '4 stars and up' },
  { value: '4.5', label: '4.5 stars and up' },
];

const PAGE_SIZE = 12;

export default function CreatorDiscovery() {
  const [keyword, setKeyword] = useState('');
  const [niche, setNiche] = useState('');
  const [platform, setPlatform] = useState('');
  const [location, setLocation] = useState('');
  const [minFollowers, setMinFollowers] = useState('');
  const [maxFollowers, setMaxFollowers] = useState('');
  const [minEngagement, setMinEngagement] = useState('');
  const [maxEngagement, setMaxEngagement] = useState('');
  const [minRate, setMinRate] = useState('');
  const [maxRate, setMaxRate] = useState('');
  const [minRating, setMinRating] = useState('');
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [sort, setSort] = useState<Sort>('followers');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [page, setPage] = useState(1);

  const [results, setResults] = useState<CreatorProfile[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Any change to the search (not to the page) starts again from page 1.
  const searchKey = JSON.stringify([
    keyword, niche, platform, location, minFollowers, maxFollowers, minEngagement, maxEngagement,
    minRate, maxRate, minRating, verifiedOnly, sort,
  ]);
  const lastSearchKey = useRef(searchKey);

  useEffect(() => {
    if (lastSearchKey.current !== searchKey) {
      lastSearchKey.current = searchKey;
      if (page !== 1) {
        setPage(1); // this run is dropped; the page change runs the search once
        return;
      }
    }
    let cancelled = false;
    // A short wait while someone is typing, so each keystroke does not become a request.
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      searchCreators(
        {
          q: keyword || undefined,
          niche: niche || undefined,
          platform: platform || undefined,
          location: location || undefined,
          minFollowers: minFollowers ? Number(minFollowers) : undefined,
          maxFollowers: maxFollowers ? Number(maxFollowers) : undefined,
          minEngagement: minEngagement ? Number(minEngagement) : undefined,
          maxEngagement: maxEngagement ? Number(maxEngagement) : undefined,
          minRate: minRate ? Number(minRate) : undefined,
          maxRate: maxRate ? Number(maxRate) : undefined,
          minRating: minRating ? Number(minRating) : undefined,
          verifiedOnly,
          ordering: SORTS.find((s) => s.value === sort)?.ordering,
        },
        page,
        PAGE_SIZE,
      )
        .then((res) => {
          if (cancelled) return;
          setResults(res.items);
          setTotal(res.total);
        })
        .catch((err) => {
          if (cancelled) return;
          setError(err?.message ?? 'Could not load creators.');
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchKey, page]);

  const reset = () => {
    setKeyword(''); setNiche(''); setPlatform(''); setLocation('');
    setMinFollowers(''); setMaxFollowers(''); setMinEngagement(''); setMaxEngagement('');
    setMinRate(''); setMaxRate(''); setMinRating('');
    setVerifiedOnly(false);
  };

  const hasFilters = !!(
    keyword || niche || platform || location ||
    minFollowers || maxFollowers || minEngagement || maxEngagement ||
    minRate || maxRate || minRating || verifiedOnly
  );

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const firstShown = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastShown = Math.min(total, page * PAGE_SIZE);

  return (
    <div className="container-page py-6 sm:py-8 space-y-6">
      <PageHeader
        eyebrow="Marketplace"
        title="Find creators"
        description={
          loading
            ? 'Searching…'
            : `${total} creator${total === 1 ? '' : 's'}${
                hasFilters ? (total === 1 ? ' matches your filters' : ' match your filters') : ' in the marketplace'
              }.`
        }
      />

      <div className="card">
        <div className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center gap-3">
          <div className="relative flex-1 min-w-0">
            <Search className="w-4 h-4 text-ink-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none z-10" />
            <Input
              className="pl-10 h-11 w-full"
              placeholder="Search by name or username"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </div>
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <Select value={niche} onChange={(e) => setNiche(e.target.value)} className="w-40 h-11">
              <option value="">All niches</option>
              {NICHES.map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
            <Select value={platform} onChange={(e) => setPlatform(e.target.value)} className="w-40 h-11">
              <option value="">All platforms</option>
              {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
            <Button
              variant={showAdvanced ? 'primary' : 'secondary'}
              onClick={() => setShowAdvanced((v) => !v)}
              aria-expanded={showAdvanced}
              className="shrink-0 h-11"
            >
              <SlidersHorizontal className="w-4 h-4" /> More filters
            </Button>
          </div>
          <Button
            variant={showAdvanced ? 'primary' : 'secondary'}
            onClick={() => setShowAdvanced((v) => !v)}
            className="md:hidden w-full h-11"
          >
            <SlidersHorizontal className="w-4 h-4" /> Filters
          </Button>
        </div>

        {showAdvanced && (
          <div className="border-t border-ink-200 p-4 sm:p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 anim-fade-in bg-mist-50">
            <div className="md:hidden">
              <Field label="Niche">
                <Select value={niche} onChange={(e) => setNiche(e.target.value)}>
                  <option value="">All niches</option>
                  {NICHES.map((n) => <option key={n} value={n}>{n}</option>)}
                </Select>
              </Field>
            </div>
            <div className="md:hidden">
              <Field label="Platform">
                <Select value={platform} onChange={(e) => setPlatform(e.target.value)}>
                  <option value="">All platforms</option>
                  {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
                </Select>
              </Field>
            </div>
            <Field label="Min followers">
              <Input type="number" min={0} placeholder="10,000" value={minFollowers} onChange={(e) => setMinFollowers(e.target.value)} />
            </Field>
            <Field label="Max followers">
              <Input type="number" min={0} placeholder="100,000" value={maxFollowers} onChange={(e) => setMaxFollowers(e.target.value)} />
            </Field>
            <Field label="Min engagement (%)">
              <Input type="number" min={0} max={100} step="0.1" placeholder="3" value={minEngagement} onChange={(e) => setMinEngagement(e.target.value)} />
            </Field>
            <Field label="Max engagement (%)">
              <Input type="number" min={0} max={100} step="0.1" placeholder="10" value={maxEngagement} onChange={(e) => setMaxEngagement(e.target.value)} />
            </Field>
            <Field label="Location">
              <Input placeholder="City or country" value={location} onChange={(e) => setLocation(e.target.value)} />
            </Field>
            <Field label="Min rate (USD)">
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-500 text-sm">$</span>
                <Input type="number" min={0} className="pl-6" placeholder="200" value={minRate} onChange={(e) => setMinRate(e.target.value)} />
              </div>
            </Field>
            <Field label="Max rate (USD)">
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-500 text-sm">$</span>
                <Input type="number" min={0} className="pl-6" placeholder="2000" value={maxRate} onChange={(e) => setMaxRate(e.target.value)} />
              </div>
            </Field>
            <Field label="Rating">
              <Select value={minRating} onChange={(e) => setMinRating(e.target.value)}>
                {MIN_RATINGS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </Select>
            </Field>
            <label className="flex items-center gap-2 sm:col-span-2 lg:col-span-4 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={verifiedOnly}
                onChange={(e) => setVerifiedOnly(e.target.checked)}
                className="w-4 h-4 accent-ink-900"
              />
              Verified creators only
            </label>
          </div>
        )}

        <div className="px-4 sm:px-5 py-2.5 border-t border-ink-200 flex flex-wrap items-center justify-between gap-2 sm:gap-3 text-xs text-ink-500">
          <span>
            <span className="font-mono text-ink-900">{total}</span> creators
            {hasFilters && <span className="text-ink-400"> · filtered</span>}
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="hidden sm:inline">Sort by</span>
            <Select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="h-8 py-0 text-xs w-full sm:w-auto sm:min-w-[160px]">
              {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </Select>
            {hasFilters && (
              <Button variant="ghost" size="xs" onClick={reset}>
                <X className="w-3.5 h-3.5" /> Clear
              </Button>
            )}
          </div>
        </div>
      </div>

      {error ? (
        <div className="card p-8 text-center text-sm text-rose-700">{error}</div>
      ) : results.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<Users className="w-5 h-5" />}
            title={loading ? 'Searching…' : 'No creators match your filters'}
            description={loading ? 'Give it a moment.' : 'Try clearing filters or broadening your search.'}
            action={
              !loading ? (
                <Button variant="secondary" onClick={reset}>Clear filters</Button>
              ) : null
            }
          />
        </div>
      ) : (
        <>
          <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 stagger">
            {results.map((c) => (
              <li key={c.id}>
                <Link
                  to={`/brand/creators/${c.id}`}
                  className="card card-hover p-4 sm:p-5 group block h-full"
                >
                  <div className="flex items-start gap-3">
                    <ProfileTile name={c.fullName} seed={c.id} imageUrl={c.avatarUrl} height={48} className="w-12 rounded-full shrink-0 border border-ink-200 shadow-xs" />
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-ink-900 truncate flex items-center gap-1.5">
                        {c.fullName}
                      </div>
                      <div className="text-xs text-ink-500 mt-0.5 flex items-center gap-1.5 flex-wrap">
                        {c.primaryPlatform && <PlatformIcon platform={c.primaryPlatform} className="w-3 h-3" />}
                        <span>{c.niche || 'No niche yet'}</span>
                      </div>
                      <div className="mt-1.5">
                        <Rating value={c.ratingAvg} count={c.ratingCount} />
                      </div>
                    </div>
                    <VerifiedBadge verified={c.verified} />
                  </div>
                  <dl className="mt-4 grid grid-cols-2 gap-px bg-ink-200 border border-ink-200 rounded-md overflow-hidden">
                    <Stat label="Followers" value={fmtNumber(c.followers)} />
                    <Stat label="Engagement" value={c.engagementRate + '%'} />
                  </dl>
                  <div className="mt-3 flex items-center justify-end text-[11px] font-mono uppercase tracking-[0.12em] text-ink-500 group-hover:text-ink-900 transition-colors">
                    View profile
                    <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
                  </div>
                </Link>
              </li>
            ))}
          </ul>

          {pageCount > 1 && (
            <nav className="flex flex-wrap items-center justify-between gap-3 text-sm text-ink-600" aria-label="Pages">
              <span>
                Showing <span className="font-mono text-ink-900">{firstShown}–{lastShown}</span> of{' '}
                <span className="font-mono text-ink-900">{total}</span>
              </span>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>
                  <ArrowLeft className="w-3.5 h-3.5" /> Previous
                </Button>
                <span className="text-xs text-ink-500 font-mono">Page {page} of {pageCount}</span>
                <Button variant="secondary" size="sm" disabled={page >= pageCount || loading} onClick={() => setPage((p) => p + 1)}>
                  Next <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </nav>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-mist-50 py-2 px-2 text-center min-w-0 overflow-hidden">
      <div className="eyebrow !text-[10px] truncate">{label}</div>
      <div className="num-display text-sm mt-0.5 truncate">{value}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
    </div>
  );
}
