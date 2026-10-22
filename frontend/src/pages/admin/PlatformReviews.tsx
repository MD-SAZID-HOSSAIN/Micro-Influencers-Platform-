import { useEffect, useState } from 'react';
import { Check, ExternalLink, X } from 'lucide-react';
import {
  approveAdminBrandPlatform, approveAdminPlatformStats, listAdminBrandPlatforms, listAdminPlatformReviews,
  rejectAdminBrandPlatform, rejectAdminPlatformStats,
} from '../../api/endpoints';
import { Button, EmptyState, FormField, PageHeader, PlatformIcon, Textarea } from '../../components/ui';
import { Modal } from '../../components/Modal';
import { useToast } from '../../state/ToastContext';
import { isApiError } from '../../api/client';
import { fmtRelativeTime } from '../../lib/shared';
import type { Platform } from '../../types';

const TABS = [
  { key: 'pending', label: 'Waiting' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
] as const;
type Tab = (typeof TABS)[number]['key'];

const KINDS = [
  { key: 'creators', label: 'Creator numbers' },
  { key: 'brands', label: 'Brand links' },
] as const;
type Kind = (typeof KINDS)[number]['key'];

/** One row on this page, whether it is a creator's typed numbers or a brand's typed link. */
type Row = {
  id: number;
  who: { fullName: string; username: string };
  platform: Platform;
  link?: string;
  followers?: number;
  engagementRate?: number;
  status: Tab;
  note?: string;
  when: string;
};

const load = async (kind: Kind, status: Tab): Promise<Row[]> => {
  if (kind === 'creators') {
    return (await listAdminPlatformReviews(status)).map((r) => ({
      id: r.id,
      who: r.creator,
      platform: r.platform,
      link: r.handleUrl,
      followers: r.followers,
      engagementRate: r.engagementRate,
      status: r.reviewStatus,
      note: r.reviewNote,
      when: r.updatedAt,
    }));
  }
  return (await listAdminBrandPlatforms(status)).map((r) => ({
    id: r.id,
    who: r.brand,
    platform: r.platform,
    link: r.handleUrl,
    status: r.reviewStatus,
    note: r.reviewNote,
    when: r.connectedAt,
  }));
};

/** Instagram, TikTok and Facebook links and numbers that people typed. An admin checks the link, then approves or rejects. */
export default function PlatformReviews() {
  const { push } = useToast();
  const [kind, setKind] = useState<Kind>('creators');
  const [tab, setTab] = useState<Tab>('pending');
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<Row | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    load(kind, tab)
      .then((r) => { if (!cancelled) setRows(r); })
      .catch((err) => { if (!cancelled) setError(isApiError(err) ? err.message : 'Failed to load.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [kind, tab]);

  const approve = async (row: Row) => {
    setBusy(true);
    try {
      if (kind === 'creators') await approveAdminPlatformStats(row.id);
      else await approveAdminBrandPlatform(row.id);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      push(
        kind === 'creators'
          ? `${row.platform} approved for @${row.who.username}. It now shows on their profile.`
          : `${row.platform} approved for @${row.who.username}. The brand can now publish and accept.`,
        'success',
      );
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not approve.', 'error');
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!rejecting || !reason.trim()) return;
    setBusy(true);
    try {
      if (kind === 'creators') await rejectAdminPlatformStats(rejecting.id, reason.trim());
      else await rejectAdminBrandPlatform(rejecting.id, reason.trim());
      setRows((prev) => prev.filter((r) => r.id !== rejecting.id));
      push('Rejected. They see your reason.', 'info');
      setRejecting(null);
      setReason('');
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not reject.', 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Verification"
        title="Platform reviews"
        description="People type their Instagram, TikTok and Facebook links. Open the link and check it is the real page. For creators also check the followers match. Approved creator numbers show on their profile. An approved brand link lets the brand publish and accept. YouTube is checked by Google and does not appear here."
      />

      <div className="flex flex-wrap gap-x-6 gap-y-3">
        <div className="flex gap-1" role="tablist" aria-label="What to review">
          {KINDS.map((k) => (
            <button
              key={k.key}
              role="tab"
              aria-selected={kind === k.key}
              onClick={() => setKind(k.key)}
              className={kind === k.key ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'}
            >
              {k.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1" role="tablist" aria-label="Status">
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
      </div>

      {loading ? (
        <div className="card p-8 text-center text-sm text-ink-500">Loading…</div>
      ) : error ? (
        <div className="card p-8 text-center text-sm text-rose-700">{error}</div>
      ) : rows.length === 0 ? (
        <div className="card">
          <EmptyState
            title={tab === 'pending' ? 'Nothing is waiting' : 'Nothing here'}
            description={tab === 'pending' ? 'New links and numbers will show up here.' : 'No entries with this status.'}
          />
        </div>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.id} className="card p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center gap-4">
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-ink-900 inline-flex items-center gap-1.5">
                    <PlatformIcon platform={r.platform} /> {r.platform}
                  </span>
                  <span className="text-sm text-ink-600">
                    {r.who.fullName} <span className="text-ink-400">@{r.who.username}</span>
                  </span>
                  <span className="tag tag-paper text-[10px]">{kind === 'creators' ? 'Creator' : 'Brand'}</span>
                </div>
                <div className="text-sm text-ink-700 flex flex-wrap gap-x-4 gap-y-1">
                  {r.followers !== undefined && (
                    <span><strong className="text-ink-900">{r.followers.toLocaleString()}</strong> followers</span>
                  )}
                  {r.engagementRate !== undefined && (
                    <span><strong className="text-ink-900">{r.engagementRate}%</strong> engagement</span>
                  )}
                  <span className="text-xs text-ink-500">sent {fmtRelativeTime(r.when)}</span>
                </div>
                {r.link && (
                  <a href={r.link} target="_blank" rel="noreferrer noopener" className="link-accent inline-flex items-center gap-1 text-sm break-all">
                    {r.link} <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                  </a>
                )}
                {r.note && <div className="text-xs text-rose-700">Reason given: {r.note}</div>}
              </div>
              <div className="flex gap-2 shrink-0">
                {r.status !== 'approved' && (
                  <Button size="sm" onClick={() => void approve(r)} disabled={busy}>
                    <Check className="w-3.5 h-3.5" /> Approve
                  </Button>
                )}
                {r.status !== 'rejected' && (
                  <Button size="sm" variant="secondary" onClick={() => { setRejecting(r); setReason(''); }} disabled={busy}>
                    <X className="w-3.5 h-3.5" /> Reject
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={!!rejecting}
        onClose={() => { setRejecting(null); setReason(''); }}
        title={rejecting ? `Reject ${rejecting.platform} for @${rejecting.who.username}?` : ''}
        size="md"
        footer={
          <>
            <button className="btn btn-secondary btn-md" onClick={() => { setRejecting(null); setReason(''); }}>Cancel</button>
            <button className="btn btn-danger btn-md" onClick={() => void reject()} disabled={!reason.trim() || busy}>Reject</button>
          </>
        }
      >
        <p className="text-sm text-ink-600 mb-3">
          {kind === 'creators'
            ? 'The numbers stay hidden from brands. The creator sees your reason and can fix and send them again.'
            : 'The link does not count. The brand sees your reason and can add the correct link.'}
        </p>
        <FormField label="Reason" required>
          <Textarea rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="For example: this is not the brand's official page." />
        </FormField>
      </Modal>
    </div>
  );
}
