import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Circle, ExternalLink, Trash2 } from 'lucide-react';
import { Button, FormField, Input, PageHeader, PlatformIcon, SectionHeader } from '../../components/ui';
import { ConfirmDialog } from '../../components/Modal';
import { useAuth } from '../../state/AuthContext';
import { useToast } from '../../state/ToastContext';
import { isApiError } from '../../api/client';
import {
  fetchBrandSocial, removeBrandSocial, saveBrandSocialLink,
  type BrandSocialAccount, type BrandSocialPlatform,
} from '../../api/endpoints';
import type { Platform } from '../../types';

const PLATFORMS: { key: BrandSocialPlatform; label: Platform; example?: string }[] = [
  { key: 'instagram', label: 'Instagram', example: 'https://instagram.com/yourbrand' },
  { key: 'tiktok', label: 'TikTok', example: 'https://www.tiktok.com/@yourbrand' },
  { key: 'facebook', label: 'Facebook', example: 'https://facebook.com/yourbrand' },
];

const STATUS_TAG = {
  pending: { label: 'Waiting for admin', tone: 'tag-amber' },
  approved: { label: 'Verified', tone: 'tag-green' },
  rejected: { label: 'Rejected', tone: 'tag-rose' },
} as const;

function Step({ done, title, children }: { done: boolean; title: string; children?: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      {done ? (
        <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
      ) : (
        <Circle className="w-5 h-5 text-ink-300 shrink-0 mt-0.5" />
      )}
      <div className="min-w-0">
        <div className="text-sm font-semibold text-ink-900">{title}</div>
        {children && <div className="text-xs text-ink-500 mt-0.5">{children}</div>}
      </div>
    </li>
  );
}

export default function BrandConnectedAccounts() {
  const { user, refreshUser } = useAuth();
  const { push } = useToast();
  const [accounts, setAccounts] = useState<BrandSocialAccount[] | null>(null);
  const [links, setLinks] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [working, setWorking] = useState<string | null>(null);
  const [removing, setRemoving] = useState<BrandSocialPlatform | null>(null);

  const reload = async () => {
    try {
      setAccounts(await fetchBrandSocial());
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not load your connected accounts.', 'error');
      setAccounts((a) => a ?? []);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const saveLink = async (platform: BrandSocialPlatform) => {
    setErrors((e) => ({ ...e, [platform]: '' }));
    setWorking(platform);
    try {
      await saveBrandSocialLink(platform, (links[platform] ?? '').trim());
      setLinks((l) => ({ ...l, [platform]: '' }));
      await Promise.all([reload(), refreshUser()]);
      push('Link saved. An admin will check it. You can publish once it is approved.', 'success');
    } catch (err) {
      const detail = isApiError(err) ? (err.details as { handle_url?: string[] } | null)?.handle_url?.[0] : undefined;
      setErrors((e) => ({ ...e, [platform]: detail ?? (isApiError(err) ? err.message : 'Could not save that link.') }));
    } finally {
      setWorking(null);
    }
  };

  const remove = async (platform: BrandSocialPlatform) => {
    try {
      await removeBrandSocial(platform);
      await Promise.all([reload(), refreshUser()]);
      push('Platform removed.', 'info');
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not remove it.', 'error');
    }
  };

  const verifiedCount = accounts?.filter((a) => a.isVerified).length ?? 0;
  const pendingCount = accounts?.filter((a) => a.reviewStatus === 'pending').length ?? 0;
  const emailDone = user?.emailVerified !== false;
  const fullyVerified = emailDone && verifiedCount > 0;

  return (
    <div className="container-page py-6 sm:py-8">
      <div className="space-y-8 max-w-3xl mx-auto">
        <PageHeader
          eyebrow="Account"
          title="Connected accounts"
          description="Add your official Instagram, TikTok or Facebook link. An admin checks the link before it counts."
        />

        <section className="card p-5 sm:p-6">
          <SectionHeader eyebrow="Verification" title={fullyVerified ? 'Your brand is verified' : 'Two steps to verify your brand'} />
          <ul className="mt-5 space-y-4">
            <Step done={emailDone} title="Confirm your email">
              {emailDone ? (
                'Done.'
              ) : (
                <>
                  Enter the 6-digit code we sent you.{' '}
                  <Link to="/verify-email" state={{ email: user?.email, sendCode: true }} className="link-accent font-semibold">
                    Verify email
                  </Link>
                </>
              )}
            </Step>
            <Step done={verifiedCount > 0} title="One verified platform">
              {verifiedCount > 0
                ? `${verifiedCount} verified. One is enough; add more if you like.`
                : pendingCount > 0
                  ? 'Your link is waiting for an admin to check it.'
                  : 'Add your official Instagram, TikTok or Facebook link below. An admin approves the link.'}
            </Step>
          </ul>
          <p className="text-xs text-ink-500 mt-5">
            {fullyVerified
              ? 'You can publish campaigns and accept proposals.'
              : 'Until both steps are done you can save drafts, browse creators, shortlist and reject, but not publish campaigns or accept proposals.'}
          </p>
        </section>

        <section className="space-y-4">
          {PLATFORMS.map(({ key, label, example }) => {
            const account = accounts?.find((a) => a.platform === key);
            const busy = working === key;
            return (
              <article key={key} className="card p-4 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="w-10 h-10 rounded-md bg-mist-100 text-ink-700 flex items-center justify-center shrink-0">
                      <PlatformIcon platform={label} className="w-5 h-5" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold text-ink-900">{label}</h3>
                      <p className="text-xs text-ink-500 mt-0.5">Official page link · an admin checks it</p>
                    </div>
                  </div>
                  {account && (
                    <span className={'tag shrink-0 ' + STATUS_TAG[account.reviewStatus].tone}>
                      <CheckCircle2 className="w-3 h-3" /> {STATUS_TAG[account.reviewStatus].label}
                    </span>
                  )}
                </div>

                {account ? (
                  <div className="mt-4 flex flex-col sm:flex-row sm:items-center gap-3">
                    <a
                      href={account.handleUrl}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-sm link-accent inline-flex items-center gap-1 min-w-0 break-all"
                    >
                      {account.handleUrl} <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                    </a>
                    <Button variant="ghost" size="sm" className="sm:ml-auto self-start" onClick={() => setRemoving(key)}>
                      <Trash2 className="w-4 h-4 text-rose-600" /> Remove
                    </Button>
                  </div>
                ) : null}
                {account?.reviewStatus === 'pending' && (
                  <p className="mt-2 text-xs text-ink-500">Waiting for an admin. It does not count until it is approved.</p>
                )}
                {account?.reviewStatus === 'rejected' && (
                  <p className="mt-2 text-xs text-rose-700">
                    Admin said: “{account.reviewNote}” Remove it and add the correct link.
                  </p>
                )}
                {!account && (
                  <form
                    className="mt-4 flex flex-col sm:flex-row sm:items-start gap-3"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void saveLink(key);
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <FormField label={`${label} link`} htmlFor={`link-${key}`} error={errors[key]}>
                        <Input
                          id={`link-${key}`}
                          value={links[key] ?? ''}
                          onChange={(e) => setLinks((l) => ({ ...l, [key]: e.target.value }))}
                          placeholder={example}
                          inputMode="url"
                          autoCapitalize="none"
                          autoCorrect="off"
                          invalid={!!errors[key]}
                        />
                      </FormField>
                    </div>
                    <Button type="submit" disabled={busy || !(links[key] ?? '').trim()} className="sm:mt-[1.65rem] w-full sm:w-auto">
                      {busy ? 'Saving…' : `Connect ${label}`}
                    </Button>
                  </form>
                )}
              </article>
            );
          })}
        </section>

        <ConfirmDialog
          open={removing !== null}
          onClose={() => setRemoving(null)}
          onConfirm={() => {
            if (removing) void remove(removing);
          }}
          title="Remove this platform?"
          description={
            verifiedCount <= 1
              ? 'Without a verified platform you cannot publish campaigns or accept proposals until you connect another.'
              : 'You can connect it again at any time.'
          }
          confirmLabel="Remove"
          destructive
        />
      </div>
    </div>
  );
}
