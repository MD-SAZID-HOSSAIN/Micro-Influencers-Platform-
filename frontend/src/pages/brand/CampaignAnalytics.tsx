import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Megaphone, Users, Eye, Inbox, TrendingUp, Wallet, CheckCircle2, Clock, X, Check, Minus } from 'lucide-react';
import { useStore, loadBrandCampaigns } from '../../state/Store';
import { useAsyncLoader } from '../../state/useEffectAsync';
import {
  fetchCampaignAnalytics, fetchContentPerformance, type CampaignMetrics, type ContentPerformanceRow, type Metric,
} from '../../api/endpoints';
import { fmtRelativeTime } from '../../lib/shared';
import { ExternalLink } from 'lucide-react';
import { PageHeader, SectionHeader, StatRow, ChannelArt, CampaignStatusBadge } from '../../components/ui';
import { currency } from '../../lib/shared';
import { useEffect } from 'react';

const FunnelBar = ({ value, max, label, tone, hint }: { value: number; max: number; label: string; tone: string; hint?: string }) => {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <div className="font-semibold text-ink-900">{label}</div>
        <div className="text-ink-500">
          <span className="font-mono font-semibold text-ink-900">{value}</span>
          {hint && <span className="text-xs text-ink-500 ml-2">{hint}</span>}
        </div>
      </div>
      <div className="mt-2 h-2 bg-mist-100 rounded-sm overflow-hidden">
        <div className={clsx('h-full transition-all duration-500', tone)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
};

import clsx from 'clsx';

export default function CampaignAnalytics() {
  const { id } = useParams();
  const { campaigns } = useStore();
  const campaign = campaigns.find((c) => c.id === id);

  useEffect(() => {
    if (!campaign) loadBrandCampaigns().catch(() => undefined);
  }, [campaign?.id]);

  const { data: m, loading, error } = useAsyncLoader<CampaignMetrics>(
    () => fetchCampaignAnalytics(id!),
    [id],
  );
  // The posts table loads on its own, so a slow or failed one never hides the numbers above it.
  const content = useAsyncLoader<ContentPerformanceRow[]>(() => fetchContentPerformance(id!), [id]);

  if (loading || (!m && !error)) {
    return <div className="container-page py-8"><div className="card p-8 text-center text-sm text-ink-500">Loading analytics…</div></div>;
  }
  if (error || !m) {
    return (
      <div className="container-page py-6 sm:py-8">
        <div className="card p-10 text-center text-sm text-rose-700">{error ?? 'Could not load analytics.'}</div>
      </div>
    );
  }

  const received = m.funnel.received;
  const acceptancePct = m.acceptanceRate !== null ? Math.round(m.acceptanceRate * 100) : 0;
  const fill = m.acceptedVsNeeded.needed > 0
    ? Math.round((m.acceptedVsNeeded.accepted / m.acceptedVsNeeded.needed) * 100)
    : 0;

  return (
    <div className="container-page py-6 sm:py-8 space-y-6 max-w-4xl">
      <Link to={campaign ? `/brand/campaigns/${campaign.id}` : '/brand/campaigns'} className="text-sm text-ink-600 hover:text-ink-900 inline-flex items-center gap-1">
        <ArrowLeft className="w-4 h-4" /> Back to campaign
      </Link>

      <PageHeader
        eyebrow="Analytics"
        title={campaign?.title ?? 'Campaign analytics'}
        description="How this campaign has performed so far. Updated as new proposals come in."
        action={campaign && <CampaignStatusBadge status={campaign.status} />}
      />

      {campaign && (
        <div className="card p-4 sm:p-5 flex items-center gap-3">
          <ChannelArt name={campaign.title} seed={campaign.id} height={48} className="w-12 rounded-md shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="font-semibold text-ink-900 truncate">{campaign.title}</div>
            <div className="text-xs text-ink-500">{campaign.category} · {campaign.requiredPlatform} · {currency(m.budgetPerCreator)} per creator</div>
          </div>
        </div>
      )}

      <StatRow
        items={[
          // Every time a creator opens the campaign page counts, so the same creator can add more than one.
          { label: 'Page views', value: m.views, hint: 'times it was opened' },
          { label: 'Proposals', value: m.funnel.received, hint: 'total received' },
          { label: 'Accepted', value: m.funnel.accepted, hint: `of ${m.acceptedVsNeeded.needed}` },
          { label: 'Acceptance', value: m.acceptanceRate !== null ? `${acceptancePct}%` : '—', hint: 'from sent' },
        ]}
      />

      <section className="card p-5 sm:p-6">
        <SectionHeader eyebrow="Funnel" title="Proposals" />
        <div className="mt-5 space-y-4">
          <FunnelBar value={m.funnel.received}     max={Math.max(received, 1)} label="Received"   tone="bg-ink-900" />
          <FunnelBar value={m.funnel.shortlisted}  max={Math.max(received, 1)} label="Shortlisted" tone="bg-sky-500" />
          <FunnelBar value={m.funnel.accepted}     max={Math.max(received, 1)} label="Accepted"   tone="bg-emerald-600" />
          <FunnelBar value={m.funnel.rejected}     max={Math.max(received, 1)} label="Rejected"   tone="bg-rose-500" />
          <FunnelBar value={m.funnel.withdrawn}    max={Math.max(received, 1)} label="Withdrawn"  tone="bg-ink-400" />
        </div>
      </section>

      <section className="card p-5 sm:p-6">
        <SectionHeader eyebrow="Budget" title="Roster fill" />
        <div className="mt-5">
          <div className="flex items-center justify-between text-sm">
            <div className="font-semibold text-ink-900">Accepted vs. Needed</div>
            <div className="text-ink-500">
              <span className="font-mono font-semibold text-ink-900">{m.acceptedVsNeeded.accepted}</span> of {m.acceptedVsNeeded.needed}
            </div>
          </div>
          <div className="mt-2 h-2 bg-mist-100 rounded-sm overflow-hidden">
            <div className="h-full bg-ink-900 transition-all duration-500" style={{ width: `${fill}%` }} />
          </div>
        </div>
        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="rounded-md border border-ink-200 p-4">
            <div className="eyebrow">Budget per creator</div>
            <div className="font-display text-xl text-ink-900 mt-1">{currency(m.budgetPerCreator)}</div>
          </div>
          <div className="rounded-md border border-ink-200 p-4">
            <div className="eyebrow">Total if every spot is filled</div>
            <div className="font-display text-xl text-ink-900 mt-1">
              {currency(m.budgetPerCreator * m.acceptedVsNeeded.needed)}
            </div>
            <div className="text-xs text-ink-500 mt-0.5">The rate is fixed. Creators cannot negotiate it.</div>
          </div>
        </div>
      </section>

      <section className="card p-5 sm:p-6">
        <SectionHeader
          eyebrow="Content"
          title="How the delivered posts are doing"
          description="Views, likes and comments of each post the accepted creators delivered. YouTube posts are refreshed once a day. Other platforms do not share these numbers, so they show “Not available”."
        />
        <div className="mt-5">
          {content.loading ? (
            <div className="text-sm text-ink-500">Loading posts…</div>
          ) : content.error ? (
            <div className="text-sm text-rose-700">{content.error}</div>
          ) : !content.data || content.data.length === 0 ? (
            <div className="border border-dashed border-ink-200 rounded-md p-6 text-center text-sm text-ink-500">
              No posts yet. They appear here once an accepted creator adds a link to their published content.
            </div>
          ) : (
            <div className="overflow-x-auto -mx-1 px-1">
              <table className="table-quiet min-w-[640px] w-full">
                <thead>
                  <tr>
                    <th>Post</th>
                    <th className="text-right">Views</th>
                    <th className="text-right">Likes</th>
                    <th className="text-right">Comments</th>
                    <th className="text-right">Engagement</th>
                    <th className="text-right">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {content.data.map((r) => (
                    <tr key={r.deliverableId}>
                      <td className="max-w-[260px]">
                        <div className="font-semibold text-ink-900 truncate">{r.creator.name}</div>
                        <a
                          href={r.postUrl}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="text-xs link-accent inline-flex items-center gap-1 max-w-full"
                        >
                          <span className="truncate">{r.platform} · {r.postUrl.replace(/^https?:\/\/(www\.)?/, '')}</span>
                          <ExternalLink className="w-3 h-3 shrink-0" />
                        </a>
                      </td>
                      <td className="text-right font-mono"><MetricValue value={r.views} /></td>
                      <td className="text-right font-mono"><MetricValue value={r.likes} /></td>
                      <td className="text-right font-mono"><MetricValue value={r.comments} /></td>
                      <td className="text-right font-mono"><MetricValue value={r.engagementRate} suffix="%" /></td>
                      <td className="text-right text-xs text-ink-500 whitespace-nowrap">
                        {r.syncedAt ? fmtRelativeTime(r.syncedAt) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

/** A number, or a quiet "Not available" when the platform does not give it. */
function MetricValue({ value, suffix = '' }: { value: Metric; suffix?: string }) {
  if (value === 'not_available') return <span className="text-xs text-ink-400 font-sans">Not available</span>;
  return <>{value.toLocaleString()}{suffix}</>;
}
