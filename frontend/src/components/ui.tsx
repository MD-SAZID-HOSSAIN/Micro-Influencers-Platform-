import { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes, InputHTMLAttributes, useEffect, useState } from 'react';
import clsx from 'clsx';
import {
  Inbox, AlertTriangle, Loader2,
  Youtube, Instagram, Facebook,
  CheckCircle2, Clock, Sparkles, X, ArrowUpRight, Bookmark, Plus,
} from 'lucide-react';
import type { CampaignStatus, ProposalStatus, Platform } from '../types';

// ---------- Button ----------
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'link' | 'accent' | 'outline';
  size?: 'xs' | 'sm' | 'md' | 'lg';
};
export function Button({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...rest
}: ButtonProps) {
  const v =
    variant === 'accent' ? 'btn-accent'
    : variant === 'outline' ? 'btn-secondary'
    : `btn-${variant}`;
  return (
    <button
      className={clsx('btn', v, `btn-${size}`, className)}
      {...rest}
    >
      {children}
    </button>
  );
}

// ---------- Inputs ----------
export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="label">{children}</label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return <input className={clsx('input', invalid && 'input-invalid', className)} {...rest} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return <textarea className={clsx('textarea', invalid && 'input-invalid', className)} {...rest} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  const { invalid, className, ...rest } = props;
  return <select className={clsx('input pr-8', invalid && 'input-invalid', className)} {...rest} />;
}

export function FormField({
  label, htmlFor, error, helper, children, optional, required,
}: {
  label: string;
  htmlFor?: string;
  error?: string;
  helper?: string;
  children: ReactNode;
  optional?: boolean;
  required?: boolean;
}) {
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between">
        <Label htmlFor={htmlFor}>
          {label}
          {required && <span className="text-brand-500 ml-0.5" aria-label="required">*</span>}
        </Label>
        {optional && <span className="text-[11px] text-ink-400 font-mono uppercase tracking-[0.14em]">Optional</span>}
      </div>
      {children}
      {error ? <div className="error">{error}</div> : helper ? <div className="helper">{helper}</div> : null}
    </div>
  );
}

// ---------- States ----------
export function EmptyState({
  icon, title, description, action, hint,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="text-center py-14 px-4 anim-fade-in">
      <div className="inline-flex items-center justify-center w-12 h-12 bg-mist-100 text-ink-500 mb-4 rounded-md">
        {icon ?? <Inbox className="w-5 h-5" />}
      </div>
      <h3 className="font-display text-lg text-ink-900 tracking-[-0.01em]">{title}</h3>
      {description && <p className="text-sm text-ink-500 mt-1.5 max-w-md mx-auto leading-relaxed">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
      {hint && <div className="mt-3 text-[11px] text-ink-400 font-mono uppercase tracking-[0.14em]">{hint}</div>}
    </div>
  );
}

export function ErrorState({
  title = 'Something went wrong',
  description = 'We couldn’t load this. Please try again.',
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="text-center py-12 px-4">
      <div className="inline-flex items-center justify-center w-12 h-12 bg-rose-50 text-rose-600 mb-3 rounded-md">
        <AlertTriangle className="w-5 h-5" />
      </div>
      <h3 className="font-display text-lg text-ink-900">{title}</h3>
      <p className="text-sm text-ink-500 mt-1.5 max-w-md mx-auto">{description}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} className="mt-4">Try again</Button>
      )}
    </div>
  );
}

export function LoadingSpinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-ink-500 text-sm">
      <Loader2 className="w-4 h-4 animate-spin" />
      {label ?? 'Loading…'}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('skeleton', className)} />;
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card p-4 flex gap-4">
          <Skeleton className="w-12 h-12 rounded-md shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- Status pills ----------
import type { CampaignStatus as CS, ProposalStatus as PS } from '../types';

const CAMPAIGN_STATUS: Record<CS, { label: string; cls: string; dot: string }> = {
  draft:     { label: 'Draft',     cls: 'tag-gray',    dot: 'bg-ink-300' },
  published: { label: 'Published', cls: 'tag-ember',   dot: 'bg-ember-500' },
  closed:    { label: 'Closed',    cls: 'tag-paper',   dot: 'bg-ink-500' },
};

const PROPOSAL_STATUS: Record<PS, { label: string; cls: string; dot: string }> = {
  pending:     { label: 'Pending',     cls: 'tag-amber',   dot: 'bg-amber-500' },
  shortlisted: { label: 'Shortlisted', cls: 'tag-sky',     dot: 'bg-sky-500' },
  accepted:    { label: 'Accepted',    cls: 'tag-green',   dot: 'bg-emerald-600' },
  rejected:    { label: 'Rejected',    cls: 'tag-rose',    dot: 'bg-rose-500' },
  withdrawn:   { label: 'Withdrawn',   cls: 'tag-gray',    dot: 'bg-ink-400' },
};

export function CampaignStatusBadge({ status }: { status: CS }) {
  const s = CAMPAIGN_STATUS[status];
  return (
    <span className={clsx('tag', s.cls)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', s.dot)} />
      {s.label}
    </span>
  );
}

export function ProposalStatusBadge({ status }: { status: PS }) {
  const s = PROPOSAL_STATUS[status];
  return (
    <span className={clsx('tag', s.cls)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', s.dot)} />
      {s.label}
    </span>
  );
}

export function EligibilityChip({ eligible, reason }: { eligible: boolean; reason?: string }) {
  if (eligible) {
    return (
      <span className="tag tag-green" title="You meet the campaign's eligibility">
        <CheckCircle2 className="w-3 h-3" /> Eligible
      </span>
    );
  }
  return (
    <span className="tag tag-amber" title={reason}>
      <Clock className="w-3 h-3" /> Check fit
    </span>
  );
}

export function VerifiedBadge({ verified }: { verified: boolean }) {
  if (verified) {
    return (
      <span className="tag tag-ember" title="Stats verified via YouTube">
        <CheckCircle2 className="w-3 h-3" /> Verified
      </span>
    );
  }
  return (
    <span className="tag tag-amber">
      <Clock className="w-3 h-3" /> Unverified
    </span>
  );
}

// ---------- Rating ----------
import { Star } from 'lucide-react';
export function Rating({
  value,
  count,
  size = 'sm',
}: { value: number | null | undefined; count?: number; size?: 'sm' | 'md' }) {
  const v = value ?? 0;
  const sizes = size === 'md' ? 'w-4 h-4' : 'w-3.5 h-3.5';
  if (v <= 0 || (count !== undefined && count === 0)) {
    return <span className="text-xs text-ink-400">No reviews yet</span>;
  }
  return (
    <span className="inline-flex items-center gap-1 text-sm text-ink-900" title={`${v.toFixed(1)} out of 5`}>
      <span className="inline-flex">
        {[1, 2, 3, 4, 5].map((n) => (
          <Star
            key={n}
            className={clsx(sizes, n <= Math.round(v) ? 'fill-brand-500 text-brand-500' : 'text-ink-200')}
          />
        ))}
      </span>
      <span className="font-mono font-semibold text-ink-900">{v.toFixed(1)}</span>
      {count !== undefined && <span className="text-xs text-ink-500">({count})</span>}
    </span>
  );
}

// ---------- Platform icons ----------
export function PlatformIcon({ platform, className }: { platform: Platform; className?: string }) {
  const cls = clsx('w-3.5 h-3.5', className);
  if (platform === 'YouTube') return <Youtube className={cls} />;
  if (platform === 'Instagram') return <Instagram className={cls} />;
  if (platform === 'Facebook') return <Facebook className={cls} />;
  // TikTok
  return (
    <svg viewBox="0 0 24 24" className={cls} aria-hidden>
      <path fill="currentColor" d="M16.6 1.82a5.6 5.6 0 0 0 4.39 4.4v3.05a8.65 8.65 0 0 1-4.39-1.27v6.7a6.21 6.21 0 1 1-5.34-6.13v3.2a3.08 3.08 0 1 0 2.15 2.94V1.82z" />
    </svg>
  );
}

// ---------- Avatar (initials with editorial monogram feel) ----------
/** "Amina Patel" -> "AP". Falls back to "?" for an empty name. */
export function initialsOf(name: string): string {
  const letters = name
    .split(' ')
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
  return letters || '?';
}

/**
 * Colour sets for generated pictures: a deep warm ink base and a terracotta accent. The same seed always picks the same set.
 */
const ART_PALETTE = [
  ['#1B1814', '#B8502B'],
  ['#13110E', '#DC8A66'],
  ['#2A2620', '#F4D6C2'],
  ['#0B0A08', '#CC6A42'],
  ['#3F3A2E', '#E9B294'],
];

/** A small stable number from some text: picks colours and shapes without storing anything. */
const hashSeed = (s: string) => Array.from(s).reduce((a, c) => a + c.charCodeAt(0), 0);

/**
 * A profile picture (photo or logo) in a tile of any size. When there is no picture, or it fails to
 * load, it shows the initials on a colour that stays the same for the same `seed`.
 */
export function ProfileTile({
  name, seed, imageUrl, height = 48, className,
}: {
  name: string;
  seed: string;
  imageUrl?: string;
  height?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [imageUrl]);
  if (imageUrl && !failed) {
    return (
      <img
        src={imageUrl}
        alt={name}
        loading="lazy"
        onError={() => setFailed(true)}
        className={clsx('object-cover bg-ink-100', className)}
        style={{ height }}
      />
    );
  }
  const [bg, accent] = ART_PALETTE[hashSeed(String(seed)) % ART_PALETTE.length];
  return (
    <div
      role="img"
      aria-label={name}
      className={clsx('flex items-center justify-center font-semibold text-paper-50 tracking-wide select-none overflow-hidden', className)}
      style={{ height, background: `linear-gradient(145deg, ${bg} 35%, ${accent})`, fontSize: Math.max(12, Math.round(height * 0.34)) }}
    >
      {initialsOf(name)}
    </div>
  );
}

export function Avatar({
  name, size = 'md', className, tone = 'ink', src,
}: {
  name: string;
  /** A profile picture. Shown instead of the initials when present. */
  src?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  tone?: 'ink' | 'ember' | 'paper';
}) {
  const initials = initialsOf(name);
  // A picture that fails to load (dead link, deleted file) falls back to the initials.
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  const sizeCls =
    size === 'xs' ? 'w-6 h-6 text-[10px]'
    : size === 'sm' ? 'w-8 h-8 text-xs'
    : size === 'lg' ? 'w-12 h-12 text-sm'
    : size === 'xl' ? 'w-16 h-16 text-base'
    : 'w-10 h-10 text-sm';
  const toneCls =
    tone === 'ember' ? 'bg-brand-500 text-mist-50'
    : tone === 'paper' ? 'bg-mist-200 text-ink-700'
    : 'bg-ink-900 text-mist-50';
  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        onError={() => setFailed(true)}
        className={clsx('rounded-full shrink-0 object-cover bg-ink-100 border border-ink-200/60 shadow-sm', sizeCls.split(' ').slice(0, 2).join(' '), className)}
      />
    );
  }
  return (
    <div
      aria-hidden
      className={clsx(
        'inline-flex items-center justify-center font-semibold rounded-full shrink-0 select-none shadow-sm',
        sizeCls, toneCls, className
      )}
    >
      {initials}
    </div>
  );
}

// ---------- Channel art (procedural SVG; replaces stock avatars) ----------
/**
 * ChannelArt — a deterministic, generated SVG used as cover art and for campaign tiles.
 * Uses the seed so it stays stable for the same item across pages. Editorial-feeling composition.
 * For a person's or brand's picture use ProfileTile, which shows the real image or the initials.
 */
export function ChannelArt({
  name, seed, height = 96, className, rounded = 'lg',
}: {
  name: string;
  seed: string;
  height?: number;
  className?: string;
  rounded?: 'sm' | 'md' | 'lg' | 'full';
}) {
  const r = rounded === 'full' ? 'rounded-full' : rounded === 'sm' ? 'rounded-sm' : rounded === 'md' ? 'rounded-md' : 'rounded-lg';
  const [bg, accent] = ART_PALETTE[hashSeed(seed) % ART_PALETTE.length];
  const id = `art-${String(seed).replace(/[^a-zA-Z0-9]/g, '')}-${height}`;
  const angle = (hashSeed(seed + 'a') % 24) - 12;
  const cx1 = 20 + (hashSeed(seed + 'b') % 30);
  const cy1 = 30 + (hashSeed(seed + 'c') % 20);
  const cx2 = 60 + (hashSeed(seed + 'd') % 30);
  const cy2 = 40 + (hashSeed(seed + 'e') % 30);
  return (
    <div
      className={clsx('relative overflow-hidden', r, className)}
      style={{ height, background: bg }}
      aria-label={`${name} cover`}
      role="img"
    >
      <svg viewBox="0 0 100 50" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 w-full h-full" aria-hidden>
        <defs>
          <linearGradient id={`${id}-g`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.9" />
            <stop offset="100%" stopColor={accent} stopOpacity="0.25" />
          </linearGradient>
        </defs>
        <g transform={`rotate(${angle} 50 25)`}>
          <circle cx={cx1} cy={cy1} r="20" fill={`url(#${id}-g)`} />
          <circle cx={cx2} cy={cy2} r="14" fill={accent} fillOpacity="0.4" />
          <path
            d={`M -10 ${40 + (hashSeed(seed + 'f') % 10)} Q 50 ${20 + (hashSeed(seed + 'g') % 15)} 110 ${45 + (hashSeed(seed + 'h') % 10)} L 110 60 L -10 60 Z`}
            fill={accent}
            fillOpacity="0.18"
          />
        </g>
      </svg>
    </div>
  );
}

// ---------- KPI (used in dashboards; restrained) ----------
export function KPI({
  label, value, hint, trend, tone = 'ink',
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  trend?: { dir: 'up' | 'down' | 'flat'; label: string };
  tone?: 'ink' | 'ember' | 'paper';
}) {
  const toneCls =
    tone === 'ember' ? 'text-brand-600'
    : tone === 'paper' ? 'text-mist-700'
    : 'text-ink-900';
  return (
    <div className="card p-5">
      <div className="eyebrow">{label}</div>
      <div className={clsx('num-display text-3xl mt-2', toneCls)}>{value}</div>
      {hint && <div className="text-[12px] text-ink-500 mt-1.5 leading-snug">{hint}</div>}
      {trend && (
        <div className="mt-2 text-[11px] font-mono uppercase tracking-[0.12em] text-ink-500 flex items-center gap-1.5">
          <span
            className={clsx(
              'inline-block w-0 h-0 border-y-[3px] border-y-transparent',
              trend.dir === 'up'   && 'border-l-[5px] border-l-emerald-600',
              trend.dir === 'down' && 'border-l-[5px] border-l-rose-500',
              trend.dir === 'flat' && 'border-l-[5px] border-l-ink-400',
            )}
            aria-hidden
          />
          {trend.label}
        </div>
      )}
    </div>
  );
}

// ---------- Section header (consistent across pages) ----------
export function SectionHeader({
  eyebrow, title, description, action, step,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  step?: string;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 border-b border-ink-200 pb-5">
      <div>
        {eyebrow && <div className="eyebrow">{step ? `${step} — ${eyebrow}` : eyebrow}</div>}
        <h2 className="display-sm mt-1.5">{title}</h2>
        {description && <p className="text-ink-500 text-[15px] mt-1.5 max-w-2xl leading-relaxed">{description}</p>}
      </div>
      {action}
    </div>
  );
}

// ---------- PageHeader (page-level) ----------
export function PageHeader({
  eyebrow, title, description, action,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="mb-6 sm:mb-8 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h1 className="display-md">{title}</h1>
        {description && (
          <p className="text-ink-500 text-[15px] mt-2 max-w-2xl leading-relaxed">{description}</p>
        )}
      </div>
      {action}
    </header>
  );
}

// ---------- StatRow (compact, used in profile/campaign headers) ----------
export function StatRow({ items }: { items: { label: string; value: ReactNode; hint?: ReactNode }[] }) {
  return (
    // The dividers are borders on the cells (not a coloured gap), so an unused slot in the last row stays blank.
    <dl className="grid grid-cols-2 sm:grid-cols-4 border border-ink-200 bg-paper-50 rounded-md overflow-hidden">
      {items.map((it) => (
        <div key={it.label} className="bg-paper-50 p-2.5 sm:p-4 min-w-0 -mr-px -mb-px border-r border-b border-ink-200">
          <dt className="eyebrow truncate">{it.label}</dt>
          <dd className="num-display text-lg sm:text-xl mt-1 sm:mt-1.5 truncate">{it.value}</dd>
          {it.hint && <div className="text-[10px] sm:text-[11px] text-ink-500 mt-0.5 truncate">{it.hint}</div>}
        </div>
      ))}
    </dl>
  );
}

// ---------- ActionListItem (used in dashboards, notifications, sidebars) ----------
export function ActionListItem({
  icon, title, hint, right, to, onClick, accent = 'ink',
}: {
  icon?: ReactNode;
  title: ReactNode;
  hint?: ReactNode;
  right?: ReactNode;
  to?: string;
  onClick?: () => void;
  accent?: 'ink' | 'ember' | 'sky' | 'amber' | 'rose';
}) {
  const accentCls =
    accent === 'ember' ? 'bg-brand-50 text-brand-700'
    : accent === 'sky' ? 'bg-sky-50 text-sky-700'
    : accent === 'amber' ? 'bg-amber-50 text-amber-700'
    : accent === 'rose' ? 'bg-rose-50 text-rose-600'
    : 'bg-ink-100 text-ink-700';
  const content = (
    <>
      {icon && (
        <div className={clsx('w-9 h-9 rounded-md flex items-center justify-center shrink-0', accentCls)}>
          {icon}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-ink-900 truncate">{title}</div>
        {hint && <div className="text-xs text-ink-500 truncate mt-0.5">{hint}</div>}
      </div>
      {right}
      {!right && <ArrowUpRight className="w-4 h-4 text-ink-300 group-hover:text-ink-700 transition-colors" />}
    </>
  );
  const cls = 'group flex items-center gap-3 p-3 -m-1 rounded-md hover:bg-mist-100 transition-colors anim-item-in';
  if (to) {
    return (
      <a href={to} className={cls}>
        {content}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} className={cls + ' w-full text-left'}>
      {content}
    </button>
  );
}

// ---------- A small icon button ----------
export function IconButton({
  children, label, className, ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return (
    <button
      aria-label={label}
      className={clsx(
        'inline-flex items-center justify-center w-10 h-10 rounded-md text-ink-700 hover:bg-ink-100/60 transition-colors',
        className
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

// ---------- Bookmark / Save (used on cards) ----------
export function SaveButton({ saved, onToggle, label }: { saved: boolean; onToggle?: () => void; label?: string }) {
  return (
    <button
      type="button"
      aria-pressed={saved}
      aria-label={label ?? (saved ? 'Saved' : 'Save')}
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggle?.(); }}
      className={clsx(
        'inline-flex items-center justify-center w-9 h-9 rounded-md border transition-colors',
        saved
          ? 'bg-ink-900 text-mist-50 border-ink-900'
          : 'bg-mist-50 text-ink-700 border-ink-200 hover:border-ink-400'
      )}
    >
      <Bookmark className={clsx('w-4 h-4', saved && 'fill-current')} />
    </button>
  );
}

// ---------- Plus (small additive chip; for adding fields) ----------
export function AddChip({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold border border-dashed border-ink-300 text-ink-700 hover:border-ink-700 hover:text-ink-900 rounded-md transition-colors"
    >
      <Plus className="w-3.5 h-3.5" />
      {children}
    </button>
  );
}

// ---------- Sparkles accent ----------
export function Spark({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={clsx('inline-flex items-center gap-1.5 text-brand-600', className)}>
      <Sparkles className="w-3.5 h-3.5" />
      {children}
    </span>
  );
}

// ---------- Close ----------
export { X };
