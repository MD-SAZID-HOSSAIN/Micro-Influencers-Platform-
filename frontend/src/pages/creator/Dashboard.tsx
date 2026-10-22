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
  SectionHeader, CampaignStatusBadge, EligibilityChip,
  ProfileTile, StatRow, ProposalStatusBadge, PageHeader,
} from '../../components/ui';
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
        eyebrow={new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'short' })}
        title={
          <>
            Welcome back, <span className="font-medium">{user?.fullName.split(' ')[0]}</span>
          </>
        }
        description={summary}
        action={
          <Link to="/creator/campaigns" className="btn btn-secondary btn-md self-start sm:self-auto">
            <Compass className="w-4 h-4" /> Browse campaigns
          </Link>
        }
      />

      <div className="space-y-8">
        <section aria-label="Your next step">
          <SectionHeader eyebrow="Next step" title="What to do next" />
          <div className="mt-5">
            {!data ? <div className="card p-5 text-sm text-ink-500">Loading…</div> : <AttentionList items={[next]} />}
          </div>
        </section>

        <StatRow
          items={[
            { label: 'Proposals sent', value: perf.proposalsSent, hint: 'all time' },
            { label: 'Waiting for reply', value: counts.pending + counts.shortlisted, hint: 'pending + shortlisted' },
            { label: 'Accepted', value: perf.accepted, hint: 'collaborations won' },
            { label: 'Success rate', value: perf.acceptanceRate !== null ? `${acceptancePct}%` : '—', hint: 'accepted of sent' },
          ]}
        />

        {accepted.length > 0 && (
          <section>
            <SectionHeader
              eyebrow="Accepted"
              title="Active collaborations"
              description="Campaigns where a brand accepted you."
              action={
                <Link to="/creator/applications" className="text-sm link-accent inline-flex items-center gap-1">
                  All proposals <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              }
            />
            <ul className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3 stagger">
              {accepted.slice(0, 4).map((p) => (
                <li key={p.id}>
                  <Link to={`/creator/applications/${p.id}`} className="card card-hover p-4 sm:p-5 group block h-full">
                    <div className="flex items-start gap-3">
                      <ProfileTile name={p.brandName} seed={p.brandId} height={48} className="w-12 rounded-md shrink-0" />
                      <div className="min-w-0 flex-1">
                        <div className="text-xs text-ink-500 truncate">{p.brandName}</div>
                        <div className="font-semibold text-ink-900 line-clamp-2 leading-snug">{p.campaignTitle}</div>
                        <div className="mt-2 text-xs text-ink-500">Rate {currency(p.proposedRate)}</div>
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
          <SectionHeader
            eyebrow="Proposals"
            title="My proposals"
            action={
              <Link to="/creator/applications" className="text-sm link-accent inline-flex items-center gap-1">
                View all <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          />
          {myProposals.length === 0 ? (
            <div className="card p-10 mt-5 text-center">
              <ListChecks className="w-8 h-8 text-ink-300 mx-auto mb-3" />
              <div className="text-sm font-semibold text-ink-900">No proposals yet</div>
              <div className="text-xs text-ink-500 mt-1">When you apply to a campaign, it shows up here with its status.</div>
              <Link to="/creator/campaigns" className="btn btn-primary btn-sm mt-4">
                Browse campaigns <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ) : (
            <div className="card mt-5 overflow-hidden">
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
                      <span className="font-mono font-semibold text-ink-900">{currency(p.proposedRate)}</span>
                    </div>
                  </Link>
                ))}
              </div>

              {/* Tablet/desktop table */}
              <div className="hidden sm:block overflow-x-auto">
                <table className="table-quiet min-w-[600px]">
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
                        <td className="text-ink-700 font-mono whitespace-nowrap">{currency(p.proposedRate)}</td>
                        <td className="text-right"><ProposalStatusBadge status={p.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

        <section>
          <SectionHeader
            eyebrow="New"
            title="Campaigns you might fit"
            action={
              <Link to="/creator/campaigns" className="text-sm link-accent inline-flex items-center gap-1">
                See all <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          />
          {available.length === 0 ? (
            <div className="card p-10 mt-5 text-center">
              <Megaphone className="w-8 h-8 text-ink-300 mx-auto mb-3" />
              <div className="text-sm font-semibold text-ink-900">No open campaigns right now</div>
              <div className="text-xs text-ink-500 mt-1">Check back soon. New campaigns appear as brands publish them.</div>
            </div>
          ) : (
            <ul className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-3 stagger">
              {available.slice(0, 5).map((c) => {
                // The server's answer, so this screen and the campaign page always agree.
                const eligible = c.eligible === true;
                return (
                  <li key={c.id}>
                    <Link to={`/creator/campaigns/${c.id}`} className="card card-hover p-4 sm:p-5 group block">
                      <div className="flex items-start gap-3">
                        <ProfileTile name={c.brandName} seed={c.brandId} height={48} className="w-12 rounded-md shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="text-xs text-ink-500 truncate">{c.brandName} · {c.category} · {c.requiredPlatform}</div>
                          <div className="mt-1 font-semibold text-ink-900 line-clamp-2 leading-snug">{c.title}</div>
                        </div>
                      </div>
                      <div className="mt-4 grid grid-cols-3 gap-px bg-ink-200 rounded-md overflow-hidden border border-ink-200">
                        <Cell label="Budget" value={currency(c.budgetPerCreator)} hint="/ creator" />
                        <Cell label="Deadline" value={fmtRelativeTime(c.applicationDeadline)} />
                        <Cell label="Need" value={`${c.creatorsNeeded}`} hint="creators" />
                      </div>
                      <div className="mt-4 flex items-center justify-between">
                        <EligibilityChip eligible={eligible} />
                        <CampaignStatusBadge status={c.status} />
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section>
          <SectionHeader eyebrow="Account" title="Your profile and YouTube" />
          <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
            <article className="card p-5 sm:p-6">
              <div className="eyebrow">Profile</div>
              <div className="mt-1.5 font-display text-xl text-ink-900 tracking-[-0.01em]">
                {completion === 100 ? 'Profile complete' : `${completion}% complete`}
              </div>
              <div className="text-xs text-ink-500 mt-1">
                {completion === 100
                  ? 'Brands see the full picture when you apply.'
                  : 'Brands can filter creators by these fields.'}
              </div>
              <div className="mt-4 h-1.5 bg-mist-100 rounded-sm overflow-hidden">
                <div
                  className="h-full bg-ink-900 transition-all duration-700 ease-out-quint"
                  style={{ width: completion + '%' }}
                />
              </div>
              {completion < 100 ? (
                <Link to="/creator/profile/edit" className="btn btn-secondary btn-sm mt-4">
                  Complete profile <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              ) : (
                <Link to="/creator/profile" className="btn btn-secondary btn-sm mt-4">
                  View profile <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              )}
            </article>

            <article className="card p-5 sm:p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="eyebrow">YouTube</div>
                  <div className="mt-1.5 font-display text-xl text-ink-900 tracking-[-0.01em]">
                    {yt ? (yt.handle || 'Connected') : 'Not connected'}
                  </div>
                  <div className="text-xs text-ink-500 mt-1">
                    {yt
                      ? `Last synced ${fmtRelativeTime(yt.lastSyncedAt)}`
                      : 'You need YouTube connected to apply to campaigns.'}
                  </div>
                </div>
                <Youtube className="w-5 h-5 text-rose-600" />
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {yt?.status === 'connected' && ytStatus?.belowMinimum && (
                  <span className="tag tag-amber">
                    <AlertTriangle className="w-3 h-3" /> Not verified · needs {ytStatus.minimumFollowers.toLocaleString()} subscribers
                  </span>
                )}
                {yt?.status === 'connected' && !ytStatus?.belowMinimum && (
                  <>
                    <span className="tag tag-brand"><CheckCircle2 className="w-3 h-3" /> Verified</span>
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
              <Link to="/creator/accounts" className="btn btn-secondary btn-sm mt-4">
                {yt ? 'Manage connection' : 'Connect YouTube'}
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </article>
          </div>
        </section>
      </div>
    </div>
  );
}

function Cell({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="bg-mist-50 py-2 px-1.5 sm:px-3 text-center min-w-0 overflow-hidden">
      <div className="eyebrow !text-[9px] truncate">{label}</div>
      <div className="num-display text-xs sm:text-sm mt-0.5 truncate">
        {value}
        {hint && <span className="text-[10px] text-ink-500 font-sans font-normal ml-0.5 sm:ml-1 hidden sm:inline">{hint}</span>}
      </div>
    </div>
  );
}
