import { Youtube, AlertTriangle, RefreshCw, Unplug, CheckCircle2, Lock, ArrowUpRight, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useStore, connectYouTube, disconnectYouTube, updateConnectedAccount, loadCreatorProfile } from '../../state/Store';
import { ConfirmDialog } from '../../components/Modal';
import { useToast } from '../../state/ToastContext';
import { fmtRelativeTime } from '../../lib/shared';
import { Button, PageHeader, SectionHeader, PlatformIcon, StatRow } from '../../components/ui';
import { isApiError } from '../../api/client';
import { completeYouTubeConnect } from '../../api/endpoints';
import { useLocation } from 'react-router-dom';

/** Codes already sent to the backend this session (each Google code works once). */
const handledCodes = new Set<string>();

const YOUTUBE_FAILURES: Record<string, string> = {
  access_denied: 'You declined access on Google.',
  invalid_state: 'That sign-in link expired or was started from another account. Try connecting again.',
  exchange_failed: 'Google did not accept the sign-in. Try connecting again.',
  no_refresh_token:
    'Google did not grant lasting access. Remove CollabNest under your Google account permissions, then connect again.',
};

const youTubeFailure = (code: string | null | undefined) =>
  `YouTube was not connected. ${(code && YOUTUBE_FAILURES[code]) || 'Something went wrong. Try again.'}`;

export default function ConnectedAccounts() {
  const { connectedAccounts, creator } = useStore();
  const { push } = useToast();
  const yt = connectedAccounts.find((a) => a.platform === 'YouTube');
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [working, setWorking] = useState(false);
  const location = useLocation();

  useEffect(() => {
    loadCreatorProfile().catch(() => undefined);

    // After Google's consent screen the backend redirects back here with
    //   ?youtube=confirm&code=…&state=…   or   ?youtube=error&reason=…
    // The code is single-use, so it is stripped from the address bar first, and
    // `handledCodes` stops React StrictMode's second effect run from sending it twice.
    const params = new URLSearchParams(location.search);
    const ytParam = params.get('youtube');
    if (!ytParam) return;
    const code = params.get('code');
    const state = params.get('state');
    const reason = params.get('reason');

    const url = new URL(window.location.href);
    ['youtube', 'code', 'state', 'reason'].forEach((k) => url.searchParams.delete(k));
    window.history.replaceState({}, '', url.toString());

    if (ytParam === 'error') {
      push(youTubeFailure(reason), 'error');
      return;
    }
    if (ytParam === 'confirm' && code && state && !handledCodes.has(code)) {
      handledCodes.add(code);
      setWorking(true);
      completeYouTubeConnect({ code, state })
        .then(() => loadCreatorProfile())
        .then(() => push('YouTube connected. Your stats are now verified.', 'success'))
        .catch((err) => push(youTubeFailure(isApiError(err) ? err.code : null), 'error'))
        .finally(() => setWorking(false));
    }
  }, [location.search]);

  const onConnect = async () => {
    setWorking(true);
    try {
      await connectYouTube();
      // connectYouTube navigates away (Google consent). The function only
      // returns if the navigation somehow failed; in that case, just re-load.
      await loadCreatorProfile();
    } catch (err) {
      push(isApiError(err) ? err.message : 'Could not start YouTube connect.', 'error');
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="container-page py-6 sm:py-8">
      <div className="space-y-8">
        <PageHeader
          eyebrow="Account"
          title="Connected accounts"
          description="Connect YouTube to verify your stats. Other platforms are manual entry only in this version."
        />

        {/* YouTube — primary */}
        <article className="card overflow-hidden">
          <div className="p-4 sm:p-6 flex flex-col sm:flex-row sm:items-start gap-4">
            <div className="flex items-start gap-3 sm:gap-4 flex-1 min-w-0">
              <div className="w-12 h-12 rounded-md bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
                <Youtube className="w-6 h-6" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-semibold text-ink-900">YouTube</h3>
                  <span className="tag tag-brand">
                    <Sparkles className="w-3 h-3" /> Core integration
                  </span>
                </div>
                <p className="text-xs text-ink-500 mt-1">Official OAuth · verified stats</p>
              </div>
            </div>
            {!yt && (
              <Button onClick={onConnect} disabled={working} className="w-full sm:w-auto shrink-0">
                {working ? 'Opening Google…' : 'Connect YouTube'}
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Button>
            )}
          </div>

          {yt && (
            <>
              {yt.status === 'expired' && (
                <div className="bg-amber-50 border-y border-amber-200 px-5 py-3 flex items-center gap-2 text-sm text-amber-800">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  Your YouTube connection expired. Reconnect to keep your stats verified.
                </div>
              )}

              <div className="p-5 sm:p-6 border-t border-ink-200">
                <StatRow
                  items={[
                    { label: 'Account', value: '@' + (yt.handle || 'channel') },
                    { label: 'Status', value: yt.verified ? 'Verified' : 'Unverified' },
                    { label: 'Last synced', value: fmtRelativeTime(yt.lastSyncedAt) },
                    { label: 'Followers', value: (creator?.followers ?? 0).toLocaleString() },
                  ]}
                />
              </div>

              <div className="border-t border-ink-200 p-5 sm:p-6 flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={async () => {
                    try {
                      await updateConnectedAccount(yt.id, { lastSyncedAt: new Date().toISOString() });
                      await loadCreatorProfile();
                      push('Stats refreshed', 'success');
                    } catch (err) {
                      push(isApiError(err) ? err.message : 'Could not refresh stats.', 'error');
                    }
                  }}
                >
                  <RefreshCw className="w-4 h-4" /> Refresh
                </Button>
                {yt.status === 'expired' && (
                  <Button onClick={onConnect} disabled={working}>
                    <CheckCircle2 className="w-4 h-4" /> Reconnect
                  </Button>
                )}
                <Button variant="ghost" onClick={() => setConfirmDisconnect(true)} disabled={working}>
                  <Unplug className="w-4 h-4 text-rose-600" /> Disconnect
                </Button>
              </div>
            </>
          )}
        </article>

        {/* Other platforms — manual */}
        <section className="card p-5 sm:p-6">
          <SectionHeader
            eyebrow="Manual entry"
            title="Other platforms"
            description="OAuth for these platforms isn’t supported in this version. Enter stats on your profile (marked as Unverified)."
          />
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(['Instagram', 'TikTok', 'Facebook'] as const).map((p) => (
              <div key={p} className="p-4 border border-dashed border-ink-200 rounded-md">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-ink-900 text-sm inline-flex items-center gap-1.5 truncate">
                    <PlatformIcon platform={p as any} />
                    {p}
                  </span>
                  <span className="tag tag-amber shrink-0">
                    <Lock className="w-3 h-3" /> Manual
                  </span>
                </div>
                <p className="text-xs text-ink-500 mt-2 leading-relaxed">
                  OAuth not supported in this version. Enter stats manually on your profile.
                </p>
              </div>
            ))}
          </div>
        </section>

        <ConfirmDialog
          open={confirmDisconnect}
          onClose={() => setConfirmDisconnect(false)}
          onConfirm={async () => {
            try {
              await disconnectYouTube();
              push('YouTube disconnected', 'info');
            } catch (err) {
              push(isApiError(err) ? err.message : 'Could not disconnect YouTube.', 'error');
            }
          }}
          title="Disconnect YouTube?"
          description="Your stats will stay on your profile but will be marked Unverified. You can reconnect any time."
          confirmLabel="Disconnect"
          destructive
        />
      </div>
    </div>
  );
}
