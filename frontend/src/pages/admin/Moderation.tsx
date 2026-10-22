import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, Search, Star, Trash2, XCircle } from 'lucide-react';
import {
  closeAdminCampaign, deleteAdminReview, listAdminCampaigns, listAdminReviews,
  type AdminCampaignRow, type AdminPage, type AdminReviewRow,
} from '../../api/endpoints';
import { Button, CampaignStatusBadge, EmptyState, FormField, Input, PageHeader, Select, Textarea } from '../../components/ui';
import { Modal } from '../../components/Modal';
import { useToast } from '../../state/ToastContext';
import { isApiError } from '../../api/client';
import { fmtDate, fmtRelativeTime } from '../../lib/shared';
import type { CampaignStatus } from '../../types';

const PAGE_SIZE = 20;

type Tab = 'campaigns' | 'reviews';
const TABS: { key: Tab; label: string }[] = [
  { key: 'campaigns', label: 'Campaigns' },
  { key: 'reviews', label: 'Reviews' },
];

/** Closing a campaign or removing a review: find it, say why, and the action is saved in the audit log. */
export default function Moderation() {
  const [tab, setTab] = useState<Tab>('campaigns');
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Moderation"
        title="Campaigns and reviews"
        description="Close a campaign that breaks the rules, or remove a review that should not be public. Every action needs a reason and is saved in the audit log."
      />
      <div className="flex gap-1" role="tablist" aria-label="What to moderate">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={tab === t.key ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'campaigns' ? <CampaignsPanel /> : <ReviewsPanel />}
    </div>
  );
}

/** Loads one page of an admin list whenever the search or the page changes (after a short pause while typing). */
function usePagedList<T>(load: (page: number) => Promise<AdminPage<T>>, searchKey: string) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AdminPage<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [lastKey, setLastKey] = useState(searchKey);

  useEffect(() => {
    // A new search starts again from page 1.
    if (lastKey !== searchKey) {
      setLastKey(searchKey);
      if (page !== 1) {
        setPage(1);
        return;
      }
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      load(page)
        .then((res) => { if (!cancelled) setData(res); })
        .catch((err) => { if (!cancelled) setError(isApiError(err) ? err.message : 'Could not load the list.'); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchKey, page, tick]);

  return { page, setPage, data, loading, error, reload: () => setTick((n) => n + 1) };
}

function Pager({ page, total, loading, onPage }: { page: number; total: number; loading: boolean; onPage: (p: number) => void }) {
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (pageCount <= 1) return null;
  const first = (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(total, page * PAGE_SIZE);
  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 text-sm text-ink-600" aria-label="Pages">
      <span>
        Showing <span className="font-mono text-ink-900">{first}–{last}</span> of <span className="font-mono text-ink-900">{total}</span>
      </span>
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1 || loading} onClick={() => onPage(page - 1)}>
          <ArrowLeft className="w-3.5 h-3.5" /> Previous
        </Button>
        <span className="text-xs text-ink-500 font-mono">Page {page} of {pageCount}</span>
        <Button variant="secondary" size="sm" disabled={page >= pageCount || loading} onClick={() => onPage(page + 1)}>
          Next <ArrowRight className="w-3.5 h-3.5" />
        </Button>
      </div>
    </nav>
  );
}

/** The box that asks for a written reason before anything is closed or removed. */
function ReasonModal({
  open, title, intro, confirmLabel, danger, busy, onClose, onConfirm,
}: {
  open: boolean;
  title: string;
  intro: string;
  confirmLabel: string;
  danger?: boolean;
  busy: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  useEffect(() => { if (open) setReason(''); }, [open]);
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="md"
      footer={
        <>
          <button className="btn btn-secondary btn-md" onClick={onClose} disabled={busy}>Cancel</button>
          <button
            className={danger ? 'btn btn-danger btn-md' : 'btn btn-primary btn-md'}
            onClick={() => onConfirm(reason.trim())}
            disabled={!reason.trim() || busy}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-sm text-ink-600 mb-3">{intro}</p>
      <FormField label="Reason" required>
        <Textarea rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why are you taking this action?" />
      </FormField>
      <div className="text-xs text-ink-400 mt-1 text-right">{reason.length}/500</div>
    </Modal>
  );
}

// ----- Campaigns -------------------------------------------------------------

function CampaignsPanel() {
  const { push } = useToast();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<'' | CampaignStatus>('');
  const [target, setTarget] = useState<AdminCampaignRow | null>(null);
  const [busy, setBusy] = useState(false);
  const { page, setPage, data, loading, error, reload } = usePagedList(
    (p) => listAdminCampaigns({ q: q || undefined, status: status || undefined }, p, PAGE_SIZE),
    JSON.stringify([q, status]),
  );

  const close = async (reason: string) => {
    if (!target) return;
    setBusy(true);
    try {
      await closeAdminCampaign(target.id, reason);
      push(`"${target.title}" is closed.`, 'success');
      setTarget(null);
      reload();
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not close the campaign.', 'error');
    } finally {
      setBusy(false);
    }
  };

  const rows = data?.items ?? [];
  return (
    <div className="space-y-4">
      <div className="card p-4 sm:p-5 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-ink-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <Input className="pl-10 h-10" placeholder="Search by campaign title or brand" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value as '' | CampaignStatus)}
          aria-label="Status"
          className="sm:w-48 sm:shrink-0"
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="closed">Closed</option>
        </Select>
      </div>

      {loading && !data ? (
        <div className="card p-8 text-center text-sm text-ink-500">Loading campaigns…</div>
      ) : error ? (
        <div className="card p-8 text-center text-sm text-rose-700">{error}</div>
      ) : rows.length === 0 ? (
        <div className="card"><EmptyState title="No campaigns match" description="Try a different search or status." /></div>
      ) : (
        <ul className="space-y-3">
          {rows.map((c) => (
            <li key={c.id} className="card p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center gap-4">
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-ink-900 break-words">{c.title}</span>
                  <CampaignStatusBadge status={c.status} />
                </div>
                <div className="text-xs text-ink-500 flex flex-wrap gap-x-4 gap-y-1">
                  <span>by {c.brand.fullName} <span className="text-ink-400">@{c.brand.username}</span></span>
                  <span>{c.proposalCount} proposal{c.proposalCount === 1 ? '' : 's'}</span>
                  <span>{c.creatorsNeeded} creator{c.creatorsNeeded === 1 ? '' : 's'} needed</span>
                  <span>deadline {fmtDate(c.deadline)}</span>
                  <span>created {fmtRelativeTime(c.createdAt)}</span>
                </div>
              </div>
              <div className="shrink-0">
                {c.status === 'published' ? (
                  <Button size="sm" variant="secondary" onClick={() => setTarget(c)}>
                    <XCircle className="w-3.5 h-3.5" /> Close campaign
                  </Button>
                ) : c.status === 'closed' ? (
                  <span className="text-xs text-ink-500">Closed{c.closedAt ? ` ${fmtRelativeTime(c.closedAt)}` : ''}</span>
                ) : (
                  <span className="text-xs text-ink-500">Draft: not public, nothing to close</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <Pager page={page} total={data?.total ?? 0} loading={loading} onPage={setPage} />

      <ReasonModal
        open={!!target}
        title={target ? `Close “${target.title}”?` : ''}
        intro="Creators can no longer apply. The brand can still answer the proposals it already has. A closed campaign cannot be reopened."
        confirmLabel="Close campaign"
        busy={busy}
        onClose={() => setTarget(null)}
        onConfirm={close}
      />
    </div>
  );
}

// ----- Reviews ---------------------------------------------------------------

function ReviewsPanel() {
  const { push } = useToast();
  const [q, setQ] = useState('');
  const [rating, setRating] = useState('');
  const [target, setTarget] = useState<AdminReviewRow | null>(null);
  const [busy, setBusy] = useState(false);
  const { page, setPage, data, loading, error, reload } = usePagedList(
    (p) => listAdminReviews({ q: q || undefined, rating: rating ? Number(rating) : undefined }, p, PAGE_SIZE),
    JSON.stringify([q, rating]),
  );

  const remove = async (reason: string) => {
    if (!target) return;
    setBusy(true);
    try {
      await deleteAdminReview(target.id, reason);
      push('The review was removed and the creator’s rating was recalculated.', 'success');
      setTarget(null);
      reload();
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not remove the review.', 'error');
    } finally {
      setBusy(false);
    }
  };

  const rows = data?.items ?? [];
  return (
    <div className="space-y-4">
      <div className="card p-4 sm:p-5 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-ink-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <Input className="pl-10 h-10" placeholder="Search the review text, a brand, a creator or a campaign" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={rating} onChange={(e) => setRating(e.target.value)} aria-label="Rating" className="sm:w-48 sm:shrink-0">
          <option value="">Any rating</option>
          {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} star{n === 1 ? '' : 's'}</option>)}
        </Select>
      </div>

      {loading && !data ? (
        <div className="card p-8 text-center text-sm text-ink-500">Loading reviews…</div>
      ) : error ? (
        <div className="card p-8 text-center text-sm text-rose-700">{error}</div>
      ) : rows.length === 0 ? (
        <div className="card"><EmptyState title="No reviews match" description="Try a different search or rating." /></div>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.id} className="card p-4 sm:p-5 flex flex-col lg:flex-row lg:items-start gap-4">
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="inline-flex" aria-label={`${r.rating} out of 5 stars`}>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <Star key={n} className={n <= r.rating ? 'w-4 h-4 fill-brand-500 text-brand-500' : 'w-4 h-4 text-ink-200'} />
                    ))}
                  </span>
                  <span className="text-xs text-ink-500">{fmtRelativeTime(r.createdAt)}</span>
                </div>
                {r.text ? (
                  <p className="text-sm text-ink-800 leading-relaxed whitespace-pre-line break-words">{r.text}</p>
                ) : (
                  <p className="text-sm text-ink-400">No written review, only the stars.</p>
                )}
                <div className="text-xs text-ink-500">
                  {r.brand.fullName} <span className="text-ink-400">@{r.brand.username}</span> reviewed{' '}
                  {r.creator.fullName} <span className="text-ink-400">@{r.creator.username}</span> for “{r.campaign.title}”
                </div>
              </div>
              <div className="shrink-0">
                <Button size="sm" variant="secondary" onClick={() => setTarget(r)}>
                  <Trash2 className="w-3.5 h-3.5 text-rose-600" /> Remove review
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Pager page={page} total={data?.total ?? 0} loading={loading} onPage={setPage} />

      <ReasonModal
        open={!!target}
        title="Remove this review?"
        intro="The review disappears for everyone and the creator’s average rating is worked out again without it. This cannot be undone."
        confirmLabel="Remove review"
        danger
        busy={busy}
        onClose={() => setTarget(null)}
        onConfirm={remove}
      />
    </div>
  );
}
