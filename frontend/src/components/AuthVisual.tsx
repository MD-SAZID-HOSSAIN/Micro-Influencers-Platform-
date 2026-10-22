import { BadgeCheck, Megaphone, Users, Check } from 'lucide-react';
import { Wordmark } from './Logo';
import { ArcMark } from './ArcMark';

type Variant = 'neutral' | 'creator' | 'brand';

const COPY: Record<
  Variant,
  { icon: JSX.Element; kicker: string; title: string; body: string; points: string[] }
> = {
  creator: {
    icon: <BadgeCheck className="w-4 h-4" />,
    kicker: 'For creators',
    title: 'Let your numbers do the talking.',
    body: 'Connect your YouTube channel and brands see audience stats pulled from the source, next to your rates and portfolio.',
    points: ['Verified YouTube reach', 'Rate card and portfolio in one profile', 'Every application tracked to a decision'],
  },
  brand: {
    icon: <Megaphone className="w-4 h-4" />,
    kicker: 'For brands',
    title: 'Post a brief. Pick your creators.',
    body: 'Describe the campaign once, set the budget and how many creators you need, then review proposals in one place.',
    points: ['Search creators by niche, reach and engagement', 'Selection stops at the number you set', 'Deliverables and reviews after the work'],
  },
  neutral: {
    icon: <Users className="w-4 h-4" />,
    kicker: 'CollabNest',
    title: 'Connect. Create. Grow.',
    body: 'A marketplace where brands find micro-influencers they can trust, and creators find paid work that fits their audience.',
    points: ['Verified audience stats', 'Briefs with budgets up front', 'One clear proposal status for both sides'],
  },
};

/** Dark panel shown beside the auth forms: the logo's arc, a role-specific message, three facts. */
export default function AuthVisual({ variant = 'neutral' }: { variant?: Variant }) {
  const c = COPY[variant];
  return (
    <div className="relative w-full flex flex-col justify-between min-h-[520px] text-white">
      <ArcMark className="absolute -right-16 -top-10 w-[130%] max-w-none opacity-90" />

      <div className="relative">
        <Wordmark to="/" size="md" variant="invert" />
      </div>

      <div className="relative mt-24">
        <span className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.12em] text-ember-300">
          {c.icon}
          {c.kicker}
        </span>
        <h2 className="mt-4 font-display text-[clamp(1.75rem,2.8vw,2.5rem)] leading-[1.08] tracking-[-0.03em] font-semibold text-white">
          {c.title}
        </h2>
        <p className="mt-4 text-[15px] leading-relaxed text-ink-200 max-w-md">{c.body}</p>

        <ul className="mt-7 space-y-3">
          {c.points.map((p) => (
            <li key={p} className="flex items-center gap-3 text-[14px] text-ink-100">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-ember-400/20 text-ember-300">
                <Check className="w-3 h-3" />
              </span>
              {p}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
