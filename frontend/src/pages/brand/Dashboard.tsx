import { Link } from 'react-router-dom';
import { Plus, ArrowRight, Users, Megaphone, ChevronRight, Mail, Inbox, Star, FilePen, CheckCircle2, Link2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useStore, loadBrandProfile, loadBrandCampaigns } from '../../state/Store';
import { fetchBrandDashboard, type BrandDashboardData } from '../../api/endpoints';
import { useAuth } from '../../state/AuthContext';
import {
  CampaignStatusBadge, PageHeader, ChannelArt, StatRow, EmptyState, SectionHeader,
} from '../../components/ui';
import AttentionList, { type AttentionItem } from '../../components/AttentionList';
import { isApiError } from '../../api/client';

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export default function BrandDashboard() {
  const { user } = useAuth();
  const { brand } = useStore();
  const [data, setData] = useState<BrandDashboardData | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadBrandProfile();
        const [dash] = await Promise.all([
          fetchBrandDashboard(),
          loadBrandCampaigns(),
        ]);
        if (!cancelled) setData(dash);
      } catch (err) {
        if (!cancelled) {
          setBootError(isApiError(err) ? err.message : 'Could not load the dashboard.');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (bootError) {
    return (
      <div className="container-page py-8">
        <div className="card p-6 text-sm text-rose-700">{bootError}</div>
      </div>
    );
  }

  const campaigns = data?.campaigns ?? [];
  const totalProposals = data?.totalProposals ?? 0;
  const pending = data?.pendingCount ?? 0;
  const shortlisted = data?.shortlistedCount ?? 0;
  const accepted = data?.acceptedCount ?? 0;
  const activeCampaigns = data?.activeCampaigns ?? 0;
  const totalCampaigns = data?.totalCampaigns ?? 0;
  // These come from the API over every campaign, so they do not depend on which rows are listed below.
  const draftCount = data?.draftCount ?? 0;
  const firstDraftId = data?.firstDraftId ?? null;
  const busiest = data?.busiestCampaign ?? null;
  const emailUnverified = user?.emailVerified === false;

  // Most important first. A brand with an unverified email cannot publish or accept, so that comes first.
  const attention: AttentionItem[] = [];
  if (emailUnverified) {
    attention.push({
      key: 'verify',
      tone: 'amber',
      icon: <Mail className="w-5 h-5" />,
      title: 'Verify your email to publish and accept',
      text: 'Until your email is verified you can save drafts, but you cannot publish campaigns or accept proposals.',
      to: '/verify-email',
      state: { email: user?.email, sendCode: true },
      cta: 'Verify email',
    });
  }
  if (user?.platformConnected === false && !emailUnverified) {
    attention.push({
      key: 'platform',
      tone: 'amber',
      icon: <Link2 className="w-5 h-5" />,
      title: user.platformStatus === 'pending' ? 'An admin is checking your link' : 'Connect a platform to publish and accept',
      text: user.platformStatus === 'pending'
        ? 'You can publish campaigns and accept proposals once an admin approves your Instagram, TikTok or Facebook link.'
        : 'Add your official Instagram, TikTok or Facebook link for an admin to approve.',
      to: '/brand/accounts',
      cta: user.platformStatus === 'pending' ? 'See status' : 'Connect account',
    });
  }
  if (pending > 0 && busiest) {
    attention.push({
      key: 'pending',
      tone: 'brand',
      icon: <Inbox className="w-5 h-5" />,
      title: `${plural(pending, 'new proposal')} waiting for your decision`,
      text: `Most are on “${busiest.title}” (${busiest.pendingCount}). Shortlist, accept or reject each one.`,
      to: `/brand/campaigns/${busiest.id}/proposals`,
      cta: 'Review proposals',
    });
  }
  if (shortlisted > 0) {
    attention.push({
      key: 'shortlisted',
      tone: 'brand',
      icon: <Star className="w-5 h-5" />,
      title: `${plural(shortlisted, 'creator')} shortlisted`,
      text: 'These are your strongest candidates. Accept the ones you want to work with.',
      to: '/brand/campaigns',
      cta: 'Open campaigns',
    });
  }
  if (draftCount > 0 && firstDraftId !== null) {
    attention.push({
      key: 'drafts',
      tone: 'amber',
      icon: <FilePen className="w-5 h-5" />,
      title: `${plural(draftCount, 'draft')} not published yet`,
      text: 'Creators cannot see a campaign until you publish it.',
      to: `/brand/campaigns/${firstDraftId}`,
      cta: 'Finish and publish',
    });
  }

  const summary =
    totalProposals > 0
      ? `${plural(totalProposals, 'proposal')} received across ${plural(totalCampaigns, 'campaign')}. ${accepted} accepted so far.`
      : activeCampaigns > 0
        ? `${plural(activeCampaigns, 'campaign')} live. Proposals will appear here when creators apply.`
        : 'Create your first campaign to start receiving proposals from creators.';

  return (
    <div className="container-page py-6 sm:py-8">
      <PageHeader
        eyebrow={`Dashboard · ${new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'short' })}`}
        title={brand?.companyName || user?.fullName || 'Your dashboard'}
        description={summary}
        action={
          <Link to="/brand/campaigns/create" className="btn btn-primary btn-md self-start sm:self-auto">
            <Plus className="w-4 h-4" /> New campaign <ArrowRight className="w-4 h-4" />
          </Link>
        }
      />

      <div className="space-y-8">
        <StatRow
          size="lg"
          items={[
            { label: 'Live campaigns', value: activeCampaigns, hint: `${totalCampaigns} in total` },
            { label: 'New proposals', value: pending, hint: 'waiting for you', attention: pending > 0 },
            { label: 'Shortlisted', value: shortlisted, hint: 'ready to accept' },
            { label: 'Accepted', value: accepted, hint: 'creators hired' },
          ]}
        />

        <section aria-label="What needs your attention">
          <SectionHeader eyebrow="To do" title="What needs your attention" />
          <div className="mt-5">
            {!data ? (
              <div className="card p-5 text-sm text-ink-500">Loading…</div>
            ) : attention.length > 0 ? (
              <AttentionList items={attention} />
            ) : (
              <div className="card p-5 sm:p-6 flex items-center gap-3">
                <span className="w-10 h-10 rounded-md bg-brand-50 text-brand-700 flex items-center justify-center shrink-0">
                  <CheckCircle2 className="w-5 h-5" />
                </span>
                <div>
                  <div className="text-sm sm:text-base font-semibold text-ink-900">You’re all caught up</div>
                  <div className="text-xs sm:text-sm text-ink-500 mt-0.5">
                    No proposals are waiting. Browse creators to invite more interest in your campaigns.
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        <section>
          <SectionHeader
            eyebrow="Campaigns"
            title="Your campaigns"
            description="Open a campaign to review its proposals, publish it or close it."
            action={
              <Link to="/brand/campaigns" className="text-sm link-accent inline-flex items-center gap-1">
                All campaigns <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          />
          {campaigns.length === 0 ? (
            <div className="card mt-5">
              <EmptyState
                icon={<Megaphone className="w-5 h-5" />}
                title="No campaigns yet"
                description="Create your first campaign to start receiving proposals."
                action={
                  <Link to="/brand/campaigns/create" className="btn btn-primary btn-md">
                    <Plus className="w-4 h-4" /> New campaign
                  </Link>
                }
              />
            </div>
          ) : (
            <ul className="mt-5 card divide-y divide-ink-200/60 stagger">
              {campaigns.slice(0, 8).map((c) => {
                const fill = c.creatorsNeeded > 0 ? Math.min(100, Math.round((c.acceptedCount / c.creatorsNeeded) * 100)) : 0;
                const isDraft = c.status === 'draft';
                return (
                  <li key={c.id}>
                    <Link
                      to={isDraft ? `/brand/campaigns/${c.id}` : `/brand/campaigns/${c.id}/proposals`}
                      className="block p-4 sm:p-5 hover:bg-mist-100/60 transition-colors group"
                    >
                      <div className="flex items-center gap-3 sm:gap-4">
                        <ChannelArt name={c.title} seed={String(c.id)} height={48} className="w-12 rounded-md shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <CampaignStatusBadge status={c.status} />
                            {c.pendingCount > 0 && (
                              <span className="tag tag-amber">{c.pendingCount} new</span>
                            )}
                          </div>
                          <div className="mt-1 font-semibold text-ink-900 line-clamp-1 leading-snug">{c.title}</div>
                          {isDraft ? (
                            <div className="mt-1 text-xs text-ink-500">Draft. Open it to finish and publish.</div>
                          ) : (
                            <>
                              <div className="mt-1.5 h-1.5 bg-mist-100 rounded-sm overflow-hidden max-w-xs">
                                <div
                                  className="h-full bg-ink-900 transition-all duration-500 ease-out-quint"
                                  style={{ width: fill + '%' }}
                                />
                              </div>
                              <div className="mt-1 text-xs text-ink-500">
                                {c.acceptedCount} of {c.creatorsNeeded} creators accepted
                                <span className="sm:hidden"> · {plural(c.proposalCount, 'proposal')}</span>
                              </div>
                            </>
                          )}
                        </div>
                        {!isDraft && (
                          <div className="hidden sm:flex flex-col items-end shrink-0">
                            <div className="text-sm font-mono font-semibold text-ink-900 inline-flex items-center gap-1">
                              <Users className="w-3.5 h-3.5 text-ink-500" />
                              {plural(c.proposalCount, 'proposal')}
                            </div>
                          </div>
                        )}
                        <ChevronRight className="w-4 h-4 text-ink-300 group-hover:text-brand-600 group-hover:translate-x-0.5 transition-all shrink-0" />
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
