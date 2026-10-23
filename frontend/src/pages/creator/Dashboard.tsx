import { Link } from 'react-router-dom';
import {
  ArrowRight, Megaphone, Youtube, AlertTriangle, CheckCircle2, Compass,
  ListChecks, ArrowUpRight, UserRound, Star,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  useStore, loadCreatorProfile, loadMyProposals, loadCreatorCampaigns,
} from '../../state/Store';
import { fetchCreatorDashboard, type CreatorDashboardData } from '../../api/endpoints';
import { fmtNumber, fmtRelativeTime, currency } from '../../lib/shared';
import { useAuth } from '../../state/AuthContext';
import {
  ProfileTile, StatRow, ProposalStatusBadge, PageHeader,
} from '../../components/ui';
import { CampaignCard } from '../../components/CampaignCard';
import AttentionList, { type AttentionItem } from '../../components/AttentionList';
import type { CreatorProfile, MyProposal } from '../../types';

function calcLocalCompletion(c: CreatorProfile | null): number {
  if (!c) return 0;
  const checks = [
    !!c.fullName,
    !!c.location,
    !!c.niche,
    c.bio.length >= 40,
    c.followers > 0,
    c.engagementRate > 0,
    c.portfolio.length >= 2,
    c.ratePerPost > 0,
  ];
  return Math.round((checks.filter(Boolean).length / checks.length) * 100);
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export default function CreatorDashboard() {
  const { user } = useAuth();
  const { creator, proposals, connectedAccounts } = useStore();
  const [data, setData] = useState<CreatorDashboardData | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [dash] = await Promise.all([
          fetchCreatorDashboard(),
          loadCreatorProfile().catch(() => undefined),
          loadMyProposals(),
          loadCreatorCampaigns(),
        ]);
        if (!cancelled) setData(dash);
      } catch (err) {
        if (!cancelled) {
          const msg = (err as Error).message || 'Could not load the dashboard.';
          setBootError(msg);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const yt = connectedAccounts.find((a) => a.platform === 'YouTube');
  const completion = data?.profileCompletion ?? calcLocalCompletion(creator);
  const ytStatus = data?.youtube;
  const ytConnected = ytStatus?.connected ?? !!yt;
  const ytNeedsReconnect = !!ytStatus?.needsReconnect || yt?.status === 'expired';
  const available = data?.availableCampaigns ?? [];
  const myProposals = (data?.applications ?? (proposals as MyProposal[])) as MyProposal[];
  const accepted = data?.acceptedCampaigns ?? [];
  const perf = data?.performance ?? { proposalsSent: 0, accepted: 0, acceptanceRate: null };

  // Exact counts from the API over every proposal. The lists above only hold the newest few.
  const counts = {
    pending: data?.pendingCount ?? myProposals.filter((p) => p.status === 'pending').length,
    shortlisted: data?.shortlistedCount ?? myProposals.filter((p) => p.status === 'shortlisted').length,
    accepted: data ? perf.accepted : accepted.length,
  };

  const acceptancePct = perf.acceptanceRate !== null ? Math.round(perf.acceptanceRate * 100) : 0;
  const summary =
    counts.shortlisted > 0
      ? `You are shortlisted on ${plural(counts.shortlisted, 'campaign')} and have ${counts.pending} waiting for a reply.`
      : counts.pending > 0
        ? `${plural(counts.pending, 'proposal')} waiting for a brand to reply.`
        : counts.accepted > 0
          ? `You have ${plural(counts.accepted, 'active collaboration')}.`
          : 'Browse campaigns and send your first proposal.';

  // One clear next step, most important first. Applying needs a connected YouTube channel.
  let next: AttentionItem;
  if (!ytConnected) {
    next = {
      key: 'youtube',
      tone: 'amber',
      icon: <Youtube className="w-5 h-5" />,
      title: 'Connect YouTube to start applying',
      text: 'Only creators with a connected YouTube channel can apply to campaigns. It takes one step and also verifies your stats for brands.',
      to: '/creator/accounts',
      cta: 'Connect YouTube',
    };
  } else if (ytNeedsReconnect) {
    next = {
      key: 'reconnect',
      tone: 'amber',
      icon: <AlertTriangle className="w-5 h-5" />,
      title: 'Reconnect YouTube',
      text: 'Your YouTube connection expired, so your stats are no longer updating. Reconnect to keep them current.',
      to: '/creator/accounts',
      cta: 'Reconnect',
    };
  } else if (ytStatus?.belowMinimum) {
    next = {
      key: 'too-small',
      tone: 'amber',
      icon: <Youtube className="w-5 h-5" />,
      title: 'Your channel is not big enough to apply yet',
      text: `Your YouTube channel has ${(ytStatus.followers ?? 0).toLocaleString()} subscribers. You need at least ${ytStatus.minimumFollowers.toLocaleString()} to be Verified and apply to campaigns. We check again every day.`,
      to: '/creator/accounts',
      cta: 'See details',
    };
  } else if (completion < 100) {
    next = {
      key: 'profile',
      tone: 'brand',
      icon: <UserRound className="w-5 h-5" />,
      title: `Finish your profile (${completion}% done)`,
      text: 'Brands look at your profile before they accept you. A complete one gets more replies.',
      to: '/creator/profile/edit',
      cta: 'Complete profile',
    };
  } else if (counts.shortlisted > 0) {
    next = {
      key: 'shortlisted',
      tone: 'brand',
      icon: <Star className="w-5 h-5" />,
      title: `You are shortlisted on ${plural(counts.shortlisted, 'campaign')}`,
      text: 'A brand picked you as a strong candidate. Check the details of your proposals.',
      to: '/creator/applications',
      cta: 'View my proposals',
    };
  } else {
    next = {
      key: 'browse',
      tone: 'brand',
      icon: <Compass className="w-5 h-5" />,
      title: 'Find your next campaign',
      text: available.length > 0 ? `${plural(available.length, 'campaign')} open for applications right now.` : 'New campaigns appear here as brands publish them.',
      to: '/creator/campaigns',
      cta: 'Browse campaigns',
    };
  }

  if (bootError) {
    return (
      <div className="container-page py-8">
        <div className="card p-6 text-sm text-rose-700">{bootError}</div>
      </div>
    );
  }

  return (
    <div className="container-page py-6 sm:py-8">
      <PageHeader
        eyebrow={new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}
        title={
          <>
            Welcome back, <span className="italic font-medium">{user?.fullName.split(' ')[0]}.</span>
          </>
        }
        description={summary}
        action={
          <Link to="/creator/campaigns" className="btn btn-primary btn-md self-start sm:self-auto">
            <Compass className="w-4 h-4" /> Find work <ArrowRight className="w-4 h-4" />
          </Link>
        }
      />

      <div className="space-y-6">
        {/* The one thing to do next */}
        <section aria-label="Your next step">
          {!data ? <div className="card p-5 text-sm text-ink-500">Loading…</div> : <AttentionList items={[next]} />}
        </section>

        <StatRow
          size="lg"
          items={[
            { label: 'Proposals sent', value: perf.proposalsSent, hint: 'all time' },
            { label: 'Acceptance rate', value: perf.acceptanceRate !== null ? `${acceptancePct}%` : '—', hint: 'of proposals sent' },
            { label: 'In flight', value: counts.pending + counts.shortlisted, hint: 'pending or shortlisted' },
            { label: 'Accepted', value: perf.accepted, hint: 'collaborations won' },
          ]}
        />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-8 space-y-8 min-w-0">
            <section>
              <BlockHeader
                title="Briefs you might be a fit for"
                to="/creator/campaigns"
                linkLabel="See all briefs"
              />
              {available.length === 0 ? (
                <div className="card p-10 mt-4 text-center">
                  <Megaphone className="w-8 h-8 text-ink-300 mx-auto mb-3" />
                  <div className="text-sm font-semibold text-ink-900">No open campaigns right now</div>
                  <div className="text-xs text-ink-500 mt-1">Check back soon. New campaigns appear as brands publish them.</div>
                </div>
              ) : (
                <ul className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 stagger">
                  {available.slice(0, 4).map((c) => {
                    // The server's answer, so this screen and the campaign page always agree.
                    const eligible = c.eligible === true;
                    return (
                      <li key={c.id}>
                        <CampaignCard
                          campaign={c}
                          to={`/creator/campaigns/${c.id}`}
                          eligibility={{ eligible }}
                        />
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            {accepted.length > 0 && (
              <section>
                <BlockHeader title="Active collaborations" to="/creator/applications" linkLabel="All proposals" />
                <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4 stagger">
                  {accepted.slice(0, 4).map((p) => (
                    <li key={p.id}>
                      <Link to={`/creator/applications/${p.id}`} className="card card-hover p-4 sm:p-5 group block h-full">
                        <div className="flex items-start gap-3">
                          <ProfileTile name={p.brandName} seed={p.brandId} height={44} className="w-11 rounded-lg shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="text-xs text-ink-500 truncate">{p.brandName}</div>
                            <div className="font-semibold text-ink-900 line-clamp-2 leading-snug">{p.campaignTitle}</div>
                            <div className="mt-2 text-xs text-ink-500">Your rate <span className="font-semibold text-ink-900 num-display">{currency(p.proposedRate)}</span></div>
                          </div>
                          <ProposalStatusBadge status={p.status} />
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section>
              <BlockHeader title="My proposals" to="/creator/applications" linkLabel="View all" />
              {myProposals.length === 0 ? (
                <div className="card p-10 mt-4 text-center">
                  <ListChecks className="w-8 h-8 text-ink-300 mx-auto mb-3" />
                  <div className="text-sm font-semibold text-ink-900">No proposals yet</div>
                  <div className="text-xs text-ink-500 mt-1">When you apply to a campaign, it shows up here with its status.</div>
                  <Link to="/creator/campaigns" className="btn btn-primary btn-sm mt-4">
                    Browse campaigns <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              ) : (
                <div className="card mt-4 overflow-hidden">
                  {/* Mobile card view */}
                  <div className="sm:hidden divide-y divide-ink-200/60">
                    {myProposals.slice(0, 6).map((p) => (
                      <Link
                        key={p.id}
                        to={`/creator/applications/${p.id}`}
                        className="p-4 block hover:bg-mist-100/60 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="font-semibold text-ink-900 line-clamp-1">{p.campaignTitle}</div>
                            <div className="text-xs text-ink-500 mt-0.5">{p.brandName}</div>
                          </div>
                          <ProposalStatusBadge status={p.status} />
                        </div>
                        <div className="mt-2.5 flex items-center justify-between text-xs">
                          <span className="text-ink-500">{fmtRelativeTime(p.submittedAt)}</span>
                          <span className="num-display text-ink-900">{currency(p.proposedRate)}</span>
                        </div>
                      </Link>
                    ))}
                  </div>

                  {/* Tablet/desktop table */}
                  <div className="hidden sm:block overflow-x-auto">
                    <table className="table-quiet min-w-[560px]">
                      <thead>
                        <tr>
                          <th>Campaign</th>
                          <th>Sent</th>
                          <th>Rate</th>
                          <th className="text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {myProposals.slice(0, 6).map((p) => (
                          <tr key={p.id}>
                            <td>
                              <Link
                                to={`/creator/applications/${p.id}`}
                                className="font-semibold text-ink-900 hover:text-brand-600 transition-colors line-clamp-1"
                              >
                                {p.campaignTitle}
                              </Link>
                              <div className="text-xs text-ink-500">{p.brandName}</div>
                            </td>
                            <td className="text-ink-500 whitespace-nowrap">{fmtRelativeTime(p.submittedAt)}</td>
                            <td className="text-ink-900 num-display whitespace-nowrap">{currency(p.proposedRate)}</td>
                            <td className="text-right"><ProposalStatusBadge status={p.status} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </section>
          </div>

          <aside className="lg:col-span-4 space-y-5 lg:sticky lg:top-24">
            <article className="card p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="eyebrow">Profile</div>
                <span className="num-display text-sm text-ink-900">{completion}%</span>
              </div>
              <div className="mt-1.5 text-[15px] font-semibold text-ink-900">
                {completion === 100 ? 'Profile complete' : 'Finish your profile'}
              </div>
              <div className="text-sm text-ink-500 mt-0.5">
                {completion === 100
                  ? 'Brands see the full picture when you apply.'
                  : 'Brands can filter creators by these fields.'}
              </div>
              <div
                className="mt-4 h-2 bg-paper-200 rounded-full overflow-hidden"
                role="progressbar"
                aria-valuenow={completion}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Profile completion"
              >
                <div
                  className="h-full bg-brand-500 rounded-full transition-all duration-700 ease-out-quint"
                  style={{ width: completion + '%' }}
                />
              </div>
              {completion < 100 ? (
                <Link to="/creator/profile/edit" className="btn btn-secondary btn-sm mt-4 w-full">
                  Complete profile <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              ) : (
                <Link to="/creator/profile" className="btn btn-secondary btn-sm mt-4 w-full">
                  View profile <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              )}
            </article>

            <article className="card p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="eyebrow">YouTube</div>
                  <div className="mt-1.5 text-[15px] font-semibold text-ink-900 truncate">
                    {yt ? (yt.handle || 'Connected') : 'Not connected'}
                  </div>
                  <div className="text-sm text-ink-500 mt-0.5">
                    {yt
                      ? `Last synced ${fmtRelativeTime(yt.lastSyncedAt)}`
                      : 'You need YouTube connected to apply to campaigns.'}
                  </div>
                </div>
                <span className="w-9 h-9 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
                  <Youtube className="w-[18px] h-[18px]" />
                </span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {yt?.status === 'connected' && ytStatus?.belowMinimum && (
                  <span className="tag tag-amber">
                    <AlertTriangle className="w-3 h-3" /> Not verified · needs {ytStatus.minimumFollowers.toLocaleString()} subscribers
                  </span>
                )}
                {yt?.status === 'connected' && !ytStatus?.belowMinimum && (
                  <>
                    <span className="tag tag-green"><CheckCircle2 className="w-3 h-3" /> Verified</span>
                    <span className="text-xs text-ink-500">
                      {fmtNumber(creator?.followers ?? 0)} followers · {creator?.engagementRate ?? 0}% engagement
                    </span>
                  </>
                )}
                {yt?.status === 'expired' && (
                  <span className="tag tag-amber">
                    <AlertTriangle className="w-3 h-3" /> Reconnect needed
                  </span>
                )}
                {ytStatus?.isOutdated && (
                  <span className="tag tag-amber"><AlertTriangle className="w-3 h-3" /> Stats outdated</span>
                )}
                {!yt && <span className="tag tag-amber">Not connected</span>}
              </div>
              <Link to="/creator/accounts" className="btn btn-secondary btn-sm mt-4 w-full">
                {yt ? 'Manage connection' : 'Connect YouTube'}
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </article>

            <nav aria-label="Shortcuts" className="card divide-y divide-ink-200/60 overflow-hidden">
              {[
                { to: '/creator/campaigns', icon: <Compass className="w-4 h-4" />, title: 'Browse new briefs', hint: `${available.length} live`, tint: 'bg-brand-50 text-brand-700' },
                { to: '/creator/applications', icon: <ListChecks className="w-4 h-4" />, title: 'Check proposal status', hint: `${counts.pending} pending`, tint: 'bg-amber-50 text-amber-700' },
                { to: '/creator/accounts', icon: <Youtube className="w-4 h-4" />, title: 'Verify your stats', hint: yt ? 'Connected' : 'Not connected', tint: 'bg-rose-50 text-rose-600' },
              ].map((a) => (
                <Link key={a.to} to={a.to} className="p-3.5 flex items-center gap-3 group hover:bg-paper-100/70 transition-colors">
                  <span className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${a.tint}`}>{a.icon}</span>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-ink-900 truncate">{a.title}</div>
                    <div className="text-xs text-ink-500 mt-0.5">{a.hint}</div>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-ink-300 group-hover:text-brand-600 transition-colors shrink-0" />
                </Link>
              ))}
            </nav>
          </aside>
        </div>
      </div>
    </div>
  );
}

function BlockHeader({ title, to, linkLabel }: { title: string; to: string; linkLabel: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <h2 className="font-display text-xl text-ink-900 tracking-[-0.015em]">{title}</h2>
      <Link to={to} className="text-sm link-accent inline-flex items-center gap-1 shrink-0">
        {linkLabel} <ArrowRight className="w-3.5 h-3.5" />
      </Link>
    </div>
  );
}
