import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowUpRight, CheckCircle2, Circle, ExternalLink, Trash2 } from 'lucide-react';
import { Button, FormField, Input, PageHeader, PlatformIcon, SectionHeader } from '../../components/ui';
import { ConfirmDialog } from '../../components/Modal';
import { useAuth } from '../../state/AuthContext';
import { useToast } from '../../state/ToastContext';
import { isApiError } from '../../api/client';
import {
  completeBrandYouTubeConnect, fetchBrandSocial, removeBrandSocial, saveBrandSocialLink, startBrandYouTubeConnect,
  type BrandSocialAccount, type BrandSocialPlatform,
} from '../../api/endpoints';
import type { Platform } from '../../types';

/** Codes already sent to the backend this session (each Google code works once). */
const handledCodes = new Set<string>();

const PLATFORMS: { key: BrandSocialPlatform; label: Platform; example?: string }[] = [
  { key: 'youtube', label: 'YouTube' },
  { key: 'instagram', label: 'Instagram', example: 'https://instagram.com/yourbrand' },
  { key: 'tiktok', label: 'TikTok', example: 'https://www.tiktok.com/@yourbrand' },
  { key: 'facebook', label: 'Facebook', example: 'https://facebook.com/yourbrand' },
];

const GOOGLE_FAILURES: Record<string, string> = {
  access_denied: 'You declined access on Google.',
  invalid_state: 'That sign-in link expired or was started from another account. Try connecting again.',
  exchange_failed: 'Google did not accept the sign-in. Try connecting again.',
  no_channel: 'That Google account has no YouTube channel. Sign in with an account that has one, or connect another platform.',
};

const googleFailure = (code: string | null | undefined) =>
  `YouTube was not connected. ${(code && GOOGLE_FAILURES[code]) || 'Something went wrong. Try again.'}`;

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
  const location = useLocation();
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

    // After Google's consent screen the backend redirects here with
    //   ?youtube=confirm&code=…&state=…   or   ?youtube=error&reason=…
    // The code is single-use: it is removed from the address bar first, and `handledCodes` stops React
    // StrictMode's second effect run from sending it twice.
    const params = new URLSearchParams(location.search);
    const flag = params.get('youtube');
    if (!flag) return;
    const code = params.get('code');
    const state = params.get('state');
    const reason = params.get('reason');
    const url = new URL(window.location.href);
    ['youtube', 'code', 'state', 'reason'].forEach((k) => url.searchParams.delete(k));
    window.history.replaceState({}, '', url.toString());

    if (flag === 'error') {
      push(googleFailure(reason), 'error');
      return;
    }
    if (flag === 'confirm' && code && state && !handledCodes.has(code)) {
      handledCodes.add(code);
      setWorking('youtube');
      completeBrandYouTubeConnect({ code, state })
        .then((list) => {
          setAccounts(list);
          return refreshUser();
        })
        .then(() => push('YouTube connected. Your brand is now verified.', 'success'))
        .catch((err) => push(googleFailure(isApiError(err) ? err.code : null), 'error'))
        .finally(() => setWorking(null));
    }
  }, [location.search]);

  const connectYouTube = async () => {
    setWorking('youtube');
    try {
      const url = await startBrandYouTubeConnect();
      if (!url) {
        push('Google sign-in is not set up on this server yet.', 'error');
        return;
      }
      window.location.assign(url);
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not start YouTube sign-in.', 'error');
    } finally {
      setWorking(null);
    }
  };

  const saveLink = async (platform: BrandSocialPlatform) => {
    setErrors((e) => ({ ...e, [platform]: '' }));
    setWorking(platform);
    try {
      await saveBrandSocialLink(platform, (links[platform] ?? '').trim());
      setLinks((l) => ({ ...l, [platform]: '' }));
      await Promise.all([reload(), refreshUser()]);
      push('Platform connected.', 'success');
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

  const connectedCount = accounts?.length ?? 0;
  const emailDone = user?.emailVerified !== false;
  const fullyVerified = emailDone && connectedCount > 0;

  return (
    <div className="container-page py-6 sm:py-8">
      <div className="space-y-8 max-w-3xl mx-auto">
        <PageHeader
          eyebrow="Account"
          title="Connected accounts"
          description="Connect any one of YouTube, Instagram, TikTok or Facebook to finish verifying your brand."
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
            <Step done={connectedCount > 0} title="Connect one platform">
              {connectedCount > 0
                ? `${connectedCount} connected. One is enough; add more if you like.`
                : 'Connect YouTube, Instagram, TikTok or Facebook below.'}
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
                      <h3 className="text-sm font-semibold text-ink-900">{label}</h3>
                      <p className="text-xs text-ink-500 mt-0.5">
                        {key === 'youtube' ? 'Google sign-in · proves you own the channel' : 'Link you type · not checked by us'}
                      </p>
                    </div>
                  </div>
                  {account && (
                    <span className={account.isVerified ? 'tag tag-brand shrink-0' : 'tag tag-amber shrink-0'}>
                      <CheckCircle2 className="w-3 h-3" /> {account.isVerified ? 'Verified' : 'Added'}
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
                ) : key === 'youtube' ? (
                  <Button onClick={connectYouTube} disabled={busy} className="mt-4 w-full sm:w-auto">
                    {busy ? 'Opening Google…' : 'Connect YouTube'} <ArrowUpRight className="w-3.5 h-3.5" />
                  </Button>
                ) : (
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
            connectedCount <= 1
              ? 'This is your only connected platform. Without one you cannot publish campaigns or accept proposals until you connect another.'
              : 'You can connect it again at any time.'
          }
          confirmLabel="Remove"
          destructive
        />
      </div>
    </div>
  );
}
