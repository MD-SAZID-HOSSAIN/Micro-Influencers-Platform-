import { useState } from 'react';
import { ExternalLink, Pencil, Trash2 } from 'lucide-react';
import { Button, FormField, Input, PlatformIcon, SectionHeader } from '../../components/ui';
import { ConfirmDialog } from '../../components/Modal';
import { useToast } from '../../state/ToastContext';
import { isApiError } from '../../api/client';
import { removeManualStats, saveManualStats } from '../../api/endpoints';
import { fmtRelativeTime } from '../../lib/shared';
import type { Platform, PlatformStatEntry } from '../../types';

const PLATFORMS = ['Instagram', 'TikTok', 'Facebook'] as const;
type ManualPlatform = (typeof PLATFORMS)[number];

const LINK_EXAMPLES: Record<ManualPlatform, string> = {
  Instagram: 'https://instagram.com/yourname',
  TikTok: 'https://www.tiktok.com/@yourname',
  Facebook: 'https://facebook.com/yourpage',
};

const STATUS_TAG = {
  pending: { label: 'Waiting for admin', tone: 'tag-amber' },
  approved: { label: 'Verified', tone: 'tag-green' },
  rejected: { label: 'Rejected', tone: 'tag-rose' },
} as const;

type Draft = { link: string; followers: string; engagement: string };
type Errors = Partial<Record<'followers' | 'engagement' | 'link' | 'general', string>>;

const draftFrom = (entry?: PlatformStatEntry): Draft => ({
  link: entry?.handleUrl ?? '',
  followers: entry ? String(entry.followers) : '',
  engagement: entry ? String(entry.engagementRate) : '',
});

/** Instagram, TikTok and Facebook cannot be connected automatically, so the creator types the numbers. */
export default function ManualPlatformStats({
  stats,
  onChanged,
}: {
  stats: PlatformStatEntry[];
  /** Called after a save or remove, so the page can reload the profile. */
  onChanged: () => Promise<unknown>;
}) {
  const { push } = useToast();
  const [editing, setEditing] = useState<ManualPlatform | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [errors, setErrors] = useState<Record<string, Errors>>({});
  const [working, setWorking] = useState<ManualPlatform | null>(null);
  const [removing, setRemoving] = useState<ManualPlatform | null>(null);

  const entryOf = (p: Platform) => stats.find((s) => s.platform === p);
  const draftOf = (p: ManualPlatform): Draft => drafts[p] ?? draftFrom(entryOf(p));
  const setDraft = (p: ManualPlatform, patch: Partial<Draft>) =>
    setDrafts((d) => ({ ...d, [p]: { ...draftOf(p), ...patch } }));

  const save = async (p: ManualPlatform) => {
    const draft = draftOf(p);
    const problems: Errors = {};
    const followers = Number(draft.followers);
    const engagement = Number(draft.engagement);
    if (draft.followers.trim() === '' || !Number.isInteger(followers) || followers < 0 || followers > 2_000_000_000) {
      problems.followers = 'Enter your followers as a whole number, for example 12500.';
    }
    if (draft.link.trim() === '') {
      problems.link = `Enter the link to your ${p} page so the admin can check it.`;
    }
    if (draft.engagement.trim() === '' || Number.isNaN(engagement) || engagement < 0 || engagement > 100) {
      problems.engagement = 'Enter a percentage from 0 to 100, for example 4.5.';
    }
    setErrors((e) => ({ ...e, [p]: problems }));
    if (Object.keys(problems).length) return;

    setWorking(p);
    try {
      await saveManualStats(p, { handleUrl: draft.link, followers, engagementRate: engagement });
      await onChanged();
      setEditing(null);
      setDrafts((d) => {
        const { [p]: _gone, ...rest } = d;
        return rest;
      });
      push(`${p} saved. An admin will check it. It shows on your profile once approved.`, 'success');
    } catch (err) {
      const details = isApiError(err) ? (err.details as Record<string, string[]> | null) : null;
      setErrors((e) => ({
        ...e,
        [p]: {
          link: details?.handle_url?.[0],
          followers: details?.followers?.[0],
          engagement: details?.engagement_rate?.[0],
          general: details ? undefined : isApiError(err) ? err.message : 'Could not save. Try again.',
        },
      }));
    } finally {
      setWorking(null);
    }
  };

  const remove = async (p: ManualPlatform) => {
    try {
      await removeManualStats(p);
      await onChanged();
      push(`${p} removed.`, 'info');
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not remove it.', 'error');
    }
  };

  return (
    <section className="card p-5 sm:p-6">
      <SectionHeader
        eyebrow="Type your numbers"
        title="Instagram, TikTok and Facebook"
        description="These cannot be connected automatically, so type your followers, engagement rate and profile link. An admin checks the link. Once approved, the numbers show on your profile as Verified. Until then only you can see them. You still need a connected YouTube channel to apply to campaigns."
      />
      <div className="mt-5 grid grid-cols-1 gap-3">
        {PLATFORMS.map((p) => {
          const entry = entryOf(p);
          const open = editing === p || !entry;
          const draft = draftOf(p);
          const err = errors[p] ?? {};
          const busy = working === p;
          return (
            <div key={p} className="p-4 border border-ink-200 rounded-md">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-ink-900 text-sm inline-flex items-center gap-1.5">
                  <PlatformIcon platform={p} />
                  {p}
                </span>
                <span className={'tag shrink-0 ' + (entry ? STATUS_TAG[entry.reviewStatus].tone : '')}>
                  {entry ? STATUS_TAG[entry.reviewStatus].label : 'Not added'}
                </span>
              </div>

              {entry && editing !== p && (
                <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-3">
                  <div className="text-sm text-ink-700 flex flex-wrap items-center gap-x-4 gap-y-1">
                    <span><strong className="text-ink-900">{entry.followers.toLocaleString()}</strong> followers</span>
                    <span><strong className="text-ink-900">{entry.engagementRate}%</strong> engagement</span>
                    {entry.lastSyncedAt && <span className="text-xs text-ink-500">updated {fmtRelativeTime(entry.lastSyncedAt)}</span>}
                    {entry.reviewStatus === 'rejected' && entry.reviewNote && (
                      <span className="w-full text-xs text-rose-700">Admin said: “{entry.reviewNote}” Change the details and save to send it again.</span>
                    )}
                    {entry.reviewStatus === 'pending' && (
                      <span className="w-full text-xs text-ink-500">Waiting for an admin. Brands cannot see this yet.</span>
                    )}
                    {entry.handleUrl && (
                      <a href={entry.handleUrl} target="_blank" rel="noreferrer noopener" className="link-accent inline-flex items-center gap-1 break-all">
                        {entry.handleUrl} <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                      </a>
                    )}
                  </div>
                  <div className="flex gap-2 sm:ml-auto">
                    <Button variant="secondary" size="sm" onClick={() => { setDrafts((d) => ({ ...d, [p]: draftFrom(entry) })); setErrors((e) => ({ ...e, [p]: {} })); setEditing(p); }}>
                      <Pencil className="w-3.5 h-3.5" /> Edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setRemoving(p)}>
                      <Trash2 className="w-4 h-4 text-rose-600" /> Remove
                    </Button>
                  </div>
                </div>
              )}

              {open && (
                <form
                  className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void save(p);
                  }}
                  noValidate
                >
                  <FormField label="Followers" htmlFor={`${p}-followers`} error={err.followers} required>
                    <Input
                      id={`${p}-followers`}
                      type="number"
                      min={0}
                      inputMode="numeric"
                      value={draft.followers}
                      onChange={(e) => setDraft(p, { followers: e.target.value })}
                      placeholder="e.g. 12500"
                      invalid={!!err.followers}
                    />
                  </FormField>
                  <FormField label="Engagement rate (%)" htmlFor={`${p}-engagement`} error={err.engagement} required>
                    <Input
                      id={`${p}-engagement`}
                      type="number"
                      min={0}
                      max={100}
                      step="0.01"
                      inputMode="decimal"
                      value={draft.engagement}
                      onChange={(e) => setDraft(p, { engagement: e.target.value })}
                      placeholder="e.g. 4.5"
                      invalid={!!err.engagement}
                    />
                  </FormField>
                  <div className="sm:col-span-2">
                    <FormField label="Profile link" htmlFor={`${p}-link`} error={err.link} required>
                      <Input
                        id={`${p}-link`}
                        value={draft.link}
                        onChange={(e) => setDraft(p, { link: e.target.value })}
                        placeholder={LINK_EXAMPLES[p]}
                        inputMode="url"
                        autoCapitalize="none"
                        autoCorrect="off"
                        invalid={!!err.link}
                      />
                    </FormField>
                  </div>
                  {err.general && <div className="error sm:col-span-2" role="alert">{err.general}</div>}
                  <div className="sm:col-span-2 flex flex-wrap gap-2">
                    <Button type="submit" disabled={busy}>{busy ? 'Saving…' : entry ? 'Save changes' : `Add ${p}`}</Button>
                    {entry && (
                      <Button type="button" variant="ghost" onClick={() => setEditing(null)} disabled={busy}>Cancel</Button>
                    )}
                  </div>
                </form>
              )}
            </div>
          );
        })}
      </div>

      <ConfirmDialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        onConfirm={() => {
          if (removing) void remove(removing);
        }}
        title={`Remove ${removing ?? 'this platform'}?`}
        description="Your numbers for this platform are deleted. You can add them again at any time, but they will need an admin to check them again."
        confirmLabel="Remove"
        destructive
      />
    </section>
  );
}
