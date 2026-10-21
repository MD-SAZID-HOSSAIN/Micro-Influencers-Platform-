import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, RefreshCw, ArrowLeft, CheckCircle2 } from 'lucide-react';
import AuthShell from '../../components/AuthShell';
import { Button } from '../../components/ui';
import { useAuth } from '../../state/AuthContext';
import { useToast } from '../../state/ToastContext';
import { verifyEmail, resendVerificationEmail } from '../../api/endpoints';
import { useLocation } from 'react-router-dom';
import { ApiError, isApiError } from '../../api/client';

export default function VerifyEmail() {
  const { user, ready } = useAuth();
  const navigate = useNavigate();
  const { push } = useToast();
  const location = useLocation();
  const email = (location.state as { email?: string })?.email ?? user?.email ?? '';
  // Coming from the "Verify your email" banner: no code was just sent (unlike right after registering).
  const sendOnOpen = (location.state as { sendCode?: boolean } | null)?.sendCode === true;
  const sentOnOpen = useRef(false);
  const [digits, setDigits] = useState(['', '', '', '', '', '']);
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const [error, setError] = useState('');
  const [cooldown, setCooldown] = useState(60);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && !user) {
      navigate('/login', { replace: true });
    }
  }, [ready, user]);

  useEffect(() => {
    if (!sendOnOpen || !ready || !user || sentOnOpen.current) return;
    sentOnOpen.current = true;
    // The flag lives in the browser's history entry, so it would survive a reload or going back to this
    // page and send another email each time. Drop it from this entry now that the request is made.
    navigate(location.pathname, { replace: true, state: { email } });
    resendVerificationEmail()
      .then(() => push('A verification code was sent.', 'info'))
      .catch((err) => {
        if (isApiError(err) && err.code === 'already_verified') push('Your email is already verified.', 'info');
        // A code was sent less than a minute ago (cooldown): the one already in the inbox still works.
        else if (!(isApiError(err) && (err.code === 'resend_cooldown' || err.status === 429))) {
          push(isApiError(err) ? err.message : 'Could not send the code.', 'error');
        }
      });
  }, [sendOnOpen, ready, user]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const setDigit = (i: number, v: string) => {
    if (!/^\d?$/.test(v)) return;
    const next = [...digits];
    next[i] = v;
    setDigits(next);
    if (v && i < 5) refs.current[i + 1]?.focus();
  };

  const onPaste = (startIndex: number, e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!pasted.length) return;
    e.preventDefault();
    const next = [...digits];
    for (let i = 0; i < pasted.length; i++) {
      const idx = startIndex + i;
      if (idx < 6) next[idx] = pasted[i];
    }
    setDigits(next);
    refs.current[Math.min(startIndex + pasted.length, 5)]?.focus();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const code = digits.join('');
    if (code.length < 6) {
      setError('Please enter the full 6-digit code.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await verifyEmail(code);
      push('Email verified — thanks!', 'success');
      // Refresh the user object so the UI knows email_verified=true.
      const { fetchMe } = await import('../../api/endpoints');
      const me = await fetchMe();
      // Update the auth context user — for simplicity, force a reload to pick up new state.
      window.location.assign(me.role === 'creator' ? '/creator/dashboard' : '/brand/dashboard');
    } catch (err) {
      const msg = isApiError(err) ? err.message : 'Could not verify your email.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const resend = async () => {
    if (cooldown > 0) return;
    setError('');
    try {
      await resendVerificationEmail();
      setCooldown(60);
      push('A new code was sent.', 'info');
    } catch (err) {
      if (isApiError(err) && (err.code === 'resend_cooldown' || err.status === 429)) {
        setCooldown(60);
        push('Please wait a minute before asking for another code.', 'error');
      } else if (isApiError(err) && err.code === 'already_verified') {
        push('Your email is already verified.', 'info');
      } else {
        push(isApiError(err) ? err.message : 'Could not resend the code.', 'error');
      }
    }
  };

  return (
    <AuthShell
      title="Verify your email"
      subtitle={
        <span>
          We sent a 6-digit code to <strong>{email || 'your email'}</strong>. Enter it below to finish setting up your account.
        </span>
      }
      footer={
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="text-brand-600 hover:text-brand-700 font-semibold inline-flex items-center gap-1 cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>
      }
    >
      <form onSubmit={submit} noValidate>
        <div className="flex justify-between gap-1.5 sm:gap-2 mb-4" role="group" aria-label="6-digit verification code">
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => (refs.current[i] = el)}
              value={d}
              onChange={(e) => setDigit(i, e.target.value)}
              onPaste={(e) => onPaste(i, e)}
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete={i === 0 ? 'one-time-code' : 'off'}
              maxLength={1}
              aria-label={`Digit ${i + 1} of 6`}
              aria-invalid={!!error}
              className="flex-1 min-w-0 max-w-[48px] h-11 sm:h-14 text-center text-lg sm:text-2xl font-semibold border border-ink-200 rounded-md focus:border-ink-900 focus:ring-0 outline-none transition-colors"
            />
          ))}
        </div>
        {error && <div className="error mb-3" role="alert">{error}</div>}
        <Button size="lg" className="w-full" disabled={submitting}>
          {submitting ? 'Verifying…' : 'Verify email'}
        </Button>
        <div className="text-sm text-ink-600 mt-4 text-center">
          Didn't get a code?{' '}
          {cooldown > 0 ? (
            <span className="text-ink-400">Resend in {cooldown}s</span>
          ) : (
            <button
              type="button"
              onClick={resend}
              className="text-brand-600 hover:text-brand-700 font-semibold inline-flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Resend code
            </button>
          )}
        </div>
        <div className="mt-6 p-3 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-900 leading-relaxed">
          <strong>Cannot find the email?</strong> Look in your <strong>Spam</strong> or <strong>Junk</strong> folder (and
          Promotions). If it is there, open it and press <strong>Not spam</strong> so the next ones arrive in your inbox.
          The code can take a minute to arrive.
        </div>
        <div className="mt-3 p-3 bg-mist-100 rounded-md text-xs text-ink-500 leading-relaxed">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 inline-block mr-1" />
          You can log in and look around without verifying. Brands need a verified email to publish campaigns and accept
          proposals, and creators need one to apply. You can verify later from your account.
        </div>
      </form>
    </AuthShell>
  );
}
