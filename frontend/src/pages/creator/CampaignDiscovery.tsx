import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CampaignCard } from '../../components/CampaignCard';
import {
  EmptyState, Input, Select, Button, SectionHeader, PageHeader,
  FormField, Label, PlatformIcon, ProfileTile,
} from '../../components/ui';
import { NICHES, PLATFORMS, currency } from '../../lib/shared';
import {
  Search, X, SlidersHorizontal, Megaphone, Calendar, DollarSign, Sparkles, Compass, RefreshCw, ShieldCheck,
} from 'lucide-react';
import { useStore, loadCreatorCampaigns, loadCreatorProfile } from '../../state/Store';

type CampaignFilters = {
  q: string;
  niche: string;
  platform: string;
  minBudget: string;
  maxBudget: string;
  deadlineBefore: string;
};

const NO_FILTERS: CampaignFilters = { q: '', niche: '', platform: '', minBudget: '', maxBudget: '', deadlineBefore: '' };

export default function CampaignDiscovery() {
  const { campaigns, creator, loading, errors } = useStore();
  const [filters, setFilters] = useState<CampaignFilters>(NO_FILTERS);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await Promise.all([loadCreatorCampaigns(), loadCreatorProfile()]);
      } catch {
        if (cancelled) return;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refresh = () => {
    loadCreatorCampaigns({
      q: filters.q || undefined,
      niche: (filters.niche as any) || undefined,
      platform: (filters.platform as any) || undefined,
      minBudget: filters.minBudget ? Number(filters.minBudget) : undefined,
      maxBudget: filters.maxBudget ? Number(filters.maxBudget) : undefined,
      deadlineBefore: filters.deadlineBefore || undefined,
    });
  };

  useEffect(() => {
    const id = setTimeout(refresh, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.q, filters.niche, filters.platform, filters.minBudget, filters.maxBudget, filters.deadlineBefore]);

  const reset = () => setFilters(NO_FILTERS);

  const isFiltered = Boolean(
    filters.q || filters.niche || filters.platform || filters.minBudget || filters.maxBudget || filters.deadlineBefore,
  );
  const publishedCount = campaigns.filter((c) => c.status === 'published').length;
  // "Eligible" is the server's answer (the creator's stats for the campaign's own platform). It is a hint only.
  const sorted = useMemo(
    () =>
      [...campaigns]
        .filter((c) => c.status === 'published')
        .sort((a, b) => (b.eligible ? 1 : 0) - (a.eligible ? 1 : 0)),
    [campaigns],
  );

  return (
    <div className="container-page py-6 sm:py-8">
      <div className="space-y-6">
        <PageHeader
          eyebrow="Creator marketplace"
          title="Find work"
          description="Browse open brand briefs, filter by your platform and niche, and apply to sponsorships that fit your audience."
          action={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={refresh}
                disabled={loading.creatorCampaigns}
                className="hidden sm:inline-flex"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading.creatorCampaigns ? 'animate-spin' : ''}`} /> Refresh
              </Button>
              <Link to="/creator/dashboard" className="btn btn-secondary btn-sm">
                <Compass className="w-3.5 h-3.5" /> Dashboard
              </Link>
            </div>
          }
        />

        {/* How well the creator fits the open briefs */}
        <div className="card p-4 sm:p-5 bg-gradient-to-r from-paper-50 via-paper-100/50 to-ember-50/40">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5 min-w-0">
              <ProfileTile
                name={creator?.fullName || 'Your profile'}
                seed={creator?.id || 'me'}
                imageUrl={creator?.avatarUrl}
                height={48}
                className="w-12 rounded-xl shrink-0 shadow-sm"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-ink-900 text-sm">{creator?.fullName || 'Your profile'}</span>
                  {creator?.primaryPlatform && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-ink-700 bg-paper-200/80 px-2 py-0.5 rounded-full">
                      <PlatformIcon platform={creator.primaryPlatform} className="w-3 h-3" />
                      {creator.primaryPlatform}
                    </span>
                  )}
                  {creator?.verified && (
                    <span className="tag tag-green text-[10px]">
                      <ShieldCheck className="w-3 h-3" /> Verified
                    </span>
                  )}
                </div>
                <p className="text-xs text-ink-500 mt-0.5">
                  {(creator?.followers ?? 0).toLocaleString()} reach ·
                  <span className="text-emerald-700 font-semibold ml-1">
                    You match {sorted.filter((c) => c.eligible).length} of {sorted.length} open briefs
                  </span>
                </p>
              </div>
            </div>
            <Link
              to="/creator/profile/edit"
              className="btn btn-ghost btn-xs text-ink-600 hover:text-ink-900 self-start md:self-auto"
              title="Update your rates and platform handles"
            >
              Edit profile
            </Link>
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="p-4 sm:p-5 flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1 min-w-0">
              <Search className="w-4 h-4 text-ink-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <Input
                className="pl-10 h-11"
                placeholder="Search by title or description"
                value={filters.q}
                onChange={(e) => setFilters({ ...filters, q: e.target.value })}
              />
            </div>
            <div className="hidden sm:flex gap-2 shrink-0">
              <Button
                variant={showFilters ? 'primary' : 'secondary'}
                onClick={() => setShowFilters((v) => !v)}
                aria-expanded={showFilters}
              >
                <SlidersHorizontal className="w-4 h-4" />
                {showFilters ? 'Hide filters' : 'More filters'}
              </Button>
            </div>
            <Button
              variant="secondary"
              onClick={() => setShowFilters((v) => !v)}
              className="sm:hidden"
              aria-expanded={showFilters}
            >
              <SlidersHorizontal className="w-4 h-4" /> Filters
            </Button>
          </div>

          <div className="px-4 sm:px-5 pb-3 space-y-2.5">
            {/* Platform quick filters */}
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
              <button
                type="button"
                onClick={() => setFilters({ ...filters, platform: '' })}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border shrink-0 transition-colors ${
                  !filters.platform
                    ? 'bg-ink-900 text-paper-50 border-ink-900'
                    : 'bg-paper-50 text-ink-700 border-ink-200 hover:bg-paper-100'
                }`}
              >
                All platforms
              </button>
              {PLATFORMS.map((pl) => {
                const active = filters.platform === pl;
                return (
                  <button
                    key={pl}
                    type="button"
                    onClick={() => setFilters({ ...filters, platform: active ? '' : pl })}
                    aria-pressed={active}
                    className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border shrink-0 inline-flex items-center gap-1.5 transition-colors ${
                      active
                        ? 'bg-ink-900 text-paper-50 border-ink-900'
                        : 'bg-paper-50 text-ink-700 border-ink-200 hover:bg-paper-100'
                    }`}
                  >
                    <PlatformIcon platform={pl} className="w-3.5 h-3.5" />
                    {pl}
                  </button>
                );
              })}
            </div>

            {/* Niche quick filters */}
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
              <span className="text-[11px] font-semibold text-ink-400 uppercase tracking-wider shrink-0 mr-1">Niche</span>
              <button
                type="button"
                onClick={() => setFilters({ ...filters, niche: '' })}
                className={`px-2.5 py-1 rounded-full text-xs font-medium shrink-0 transition-colors ${
                  !filters.niche ? 'bg-ink-800 text-paper-50' : 'bg-paper-100 text-ink-600 hover:bg-paper-200'
                }`}
              >
                All
              </button>
              {NICHES.map((n) => {
                const active = filters.niche === n;
                return (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setFilters({ ...filters, niche: active ? '' : n })}
                    aria-pressed={active}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium shrink-0 transition-colors ${
                      active ? 'bg-ink-800 text-paper-50' : 'bg-paper-100 text-ink-600 hover:bg-paper-200'
                    }`}
                  >
                    {n}
                  </button>
                );
              })}
            </div>
          </div>

          {showFilters && (
            <div className="border-t border-ink-200 p-4 sm:p-5 bg-mist-100/50 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 anim-fade-in">
              <FormField label="Min budget per creator">
                <div className="relative">
                  <DollarSign className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <Input
                    type="number"
                    className="pl-9"
                    placeholder="500"
                    value={filters.minBudget}
                    onChange={(e) => setFilters({ ...filters, minBudget: e.target.value })}
                  />
                </div>
              </FormField>
              <FormField label="Max budget per creator">
                <div className="relative">
                  <DollarSign className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <Input
                    type="number"
                    className="pl-9"
                    placeholder="5000"
                    value={filters.maxBudget}
                    onChange={(e) => setFilters({ ...filters, maxBudget: e.target.value })}
                  />
                </div>
              </FormField>
              <FormField label="Apply by">
                <div className="relative">
                  <Calendar className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <Input
                    type="date"
                    className="pl-9"
                    value={filters.deadlineBefore}
                    onChange={(e) => setFilters({ ...filters, deadlineBefore: e.target.value })}
                  />
                </div>
              </FormField>
              <div className="flex items-end">
                <Button variant="ghost" onClick={reset}>
                  <X className="w-4 h-4" /> Clear all
                </Button>
              </div>
            </div>
          )}

          <div className="px-4 sm:px-5 py-2.5 border-t border-ink-200 flex items-center justify-between text-xs text-ink-500 gap-3">
            <span>
              <span className="font-mono text-ink-900 font-semibold">{sorted.length}</span>
              {' '}live brief{sorted.length === 1 ? '' : 's'}
              {isFiltered && <span className="text-ink-400"> · filtered</span>}
              {sorted[0]?.eligible && (
                <>
                  <span className="text-ink-300 mx-1.5">·</span>
                  <span className="inline-flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3 text-brand-500" />
                    Eligible first
                  </span>
                </>
              )}
            </span>
            {isFiltered ? (
              <button
                onClick={reset}
                className="inline-flex items-center gap-1 text-ink-500 hover:text-ink-900 transition-colors font-medium"
              >
                <X className="w-3 h-3" /> Reset
              </button>
            ) : (
              <span className="text-ink-400 font-mono">live · API</span>
            )}
          </div>
        </div>

        {loading.creatorCampaigns ? (
          <div className="card p-10 text-center text-sm text-ink-500">Loading briefs…</div>
        ) : errors.creatorCampaigns ? (
          <div className="card p-10 text-center text-sm text-rose-700">{errors.creatorCampaigns}</div>
        ) : sorted.length === 0 ? (
          <div className="card">
            <EmptyState
              icon={<Megaphone className="w-5 h-5" />}
              title="No live briefs match your filters"
              description="Try clearing filters or broadening your search. New briefs are added regularly."
              action={
                <Button variant="secondary" onClick={reset}>
                  <X className="w-4 h-4" /> Clear filters
                </Button>
              }
            />
          </div>
        ) : (
          <ul className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 stagger">
            {sorted.map((c) => {
              const eligible = c.eligible === true;
              const reason = eligible ? undefined : `Your ${c.requiredPlatform} stats do not match this brief. You can still apply.`;
              return (
                <li key={c.id}>
                  <CampaignCard
                    campaign={c}
                    to={`/creator/campaigns/${c.id}`}
                    eligibility={{ eligible, reason }}
                  />
                </li>
              );
            })}
          </ul>
        )}

        <div className="text-center pt-2 text-xs text-ink-400 font-mono">
          {currency(0)} placeholder · {sorted.length} of {publishedCount} live
        </div>
      </div>
    </div>
  );
}
