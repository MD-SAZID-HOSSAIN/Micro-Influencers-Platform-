import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BadgeCheck,
  Check,
  Link2,
  Megaphone,
  Search,
  Star,
  Users,
  ListChecks,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../state/AuthContext';
import { useReveal } from '../../hooks/useReveal';
import { ArcMark } from '../../components/ArcMark';
import { BIRD } from '../../components/Logo';

/* ─────────────────────────── Page ─────────────────────────── */

export default function Landing() {
  const { user } = useAuth();
  const dashboardLink = user
    ? user.role === 'creator' ? '/creator/dashboard' : '/brand/dashboard'
    : null;

  return (
    <div className="bg-mist-50 text-ink-700">
      <Hero dashboardLink={dashboardLink} />
      <HowItWorks />
      <Roles />
      <ClosingCTA dashboardLink={dashboardLink} />
    </div>
  );
}

/* ─────────────────────────── Hero ─────────────────────────── */

function Hero({ dashboardLink }: { dashboardLink: string | null }) {
  const navigate = useNavigate();
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-mist-50 via-mist-50 to-mist-100">
      {/* The one decoration: a soft pool of the logo blue behind the visual. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -right-40 w-[760px] h-[760px] rounded-full bg-brand-100/70 blur-3xl"
      />

      <div className="container-page relative py-14 sm:py-20 lg:py-0 lg:min-h-[calc(100vh-64px)] lg:flex lg:items-center">
        <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-14 lg:gap-6 items-center">
          <div className="lg:col-span-6 min-w-0">
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-ink-200 bg-mist-50/80 px-3.5 py-1.5 text-[13px] font-semibold text-ink-600 shadow-card">
                <span className="w-1.5 h-1.5 rounded-full bg-nest-400" aria-hidden />
                For micro-influencers and brands
              </span>
              <h1 className="mt-6 font-display font-semibold text-ink-900 text-[clamp(2.5rem,4.7vw,4.25rem)] leading-[1.02] tracking-[-0.04em] [text-wrap:balance]">
                Find creators{' '}
                <span className="sm:block bg-gradient-to-r from-nest-600 to-brand-500 bg-clip-text text-transparent">
                  worth working with.
                </span>
              </h1>
            </Reveal>

            <Reveal delay={100}>
              <p className="mt-6 text-[18px] sm:text-[19px] text-ink-500 leading-relaxed max-w-[34rem]">
                Creators show audience stats pulled straight from YouTube. Brands post a
                brief with the budget up front, review proposals, and accept exactly as many
                creators as they need.
              </p>
            </Reveal>

            <Reveal delay={200}>
              <div className="mt-9 flex flex-col sm:flex-row sm:items-center gap-3">
                {dashboardLink ? (
                  <Link to={dashboardLink} className="btn btn-primary btn-lg">
                    Open my dashboard
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                ) : (
                  <>
                    <button onClick={() => navigate('/register/brand')} className="btn btn-primary btn-lg">
                      <Megaphone className="w-4 h-4" />
                      I&apos;m a brand
                    </button>
                    <button onClick={() => navigate('/register/creator')} className="btn btn-secondary btn-lg">
                      <Users className="w-4 h-4" />
                      I&apos;m a creator
                    </button>
                  </>
                )}
                <Link
                  to="/#how"
                  className="btn btn-ghost btn-lg text-ink-600 hover:text-ink-900 sm:ml-1"
                >
                  See how it works
                </Link>
              </div>
            </Reveal>

            <Reveal delay={300}>
              <ul className="mt-10 pt-8 border-t border-ink-200/80 flex flex-col gap-3 text-[15px] font-semibold text-ink-700">
                {[
                  'Stats come from YouTube, not screenshots',
                  'Every brief shows its budget before you apply',
                  'Acceptances stop when the roster is full',
                ].map((line) => (
                  <li key={line} className="flex items-center gap-3">
                    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-nest-50 text-nest-600 shrink-0">
                      <Check className="w-3 h-3" strokeWidth={3} />
                    </span>
                    {line}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>

          <div className="lg:col-span-6 min-w-0">
            <HeroVisual />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────── Hero visual ─────────────────────────
 * The page's one signature: a brief on the left, a creator on the right, and the logo's arc
 * drawing itself between them with the bird landing on the creator. It is the product in a
 * single picture: a brief finding the right creator.
 *
 * Wide screens get a fixed 600x520 composition that scales to fit its column, so the arc
 * always meets the cards. Phones get the two cards stacked with a short arc between them.
 */

const STAGE_W = 600;
const STAGE_H = 520;

function useFitScale(designWidth: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setScale(Math.min(1, el.clientWidth / designWidth));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, [designWidth]);
  return { ref, scale };
}

function HeroVisual() {
  const { ref, scale } = useFitScale(STAGE_W);
  return (
    <div aria-hidden>
      {/* sm and up */}
      <div
        ref={ref}
        className="hidden sm:block w-full max-w-[600px] mx-auto lg:mr-0"
        style={{ height: STAGE_H * scale }}
      >
        <div
          className="relative"
          style={{ width: STAGE_W, height: STAGE_H, transform: `scale(${scale})`, transformOrigin: 'top left' }}
        >
          <div className="absolute inset-x-0 inset-y-3 rounded-[32px] border border-ink-200/70 bg-gradient-to-br from-brand-50 via-mist-50 to-nest-50 shadow-card" />

          <svg viewBox={`0 0 ${STAGE_W} ${STAGE_H}`} className="absolute inset-0 w-full h-full" fill="none">
            <defs>
              <linearGradient id="hero-arc" x1="60" y1="0" x2="200" y2="0" gradientUnits="userSpaceOnUse">
                <stop offset="0" stopColor="#06CAB5" />
                <stop offset="0.55" stopColor="#14B5E0" />
                <stop offset="1" stopColor="#0DA0FD" />
              </linearGradient>
            </defs>
            <path
              className="arc-path"
              pathLength={1}
              d="M84 318 C 36 206, 76 118, 196 108"
              stroke="url(#hero-arc)"
              strokeWidth="14"
              strokeLinecap="round"
            />
            <path
              className="arc-path"
              pathLength={1}
              style={{ animationDelay: '.45s' }}
              d="M84 318 C 36 206, 76 118, 196 108"
              transform="translate(-20 14)"
              stroke="url(#hero-arc)"
              strokeOpacity="0.22"
              strokeWidth="5"
              strokeLinecap="round"
            />
          </svg>

          <CreatorCard className="absolute right-6 top-[52px] w-[360px] anim-item-in" delay=".5s" />
          <BriefCard className="absolute left-6 bottom-9 w-[372px] anim-item-in" delay=".2s" />
          <StatusChip className="absolute right-4 bottom-[118px] anim-item-in" delay=".95s" />

          <svg viewBox={`0 0 ${STAGE_W} ${STAGE_H}`} className="absolute inset-0 w-full h-full pointer-events-none">
            <g className="bird-land">
              <g transform="translate(156 60) scale(0.9) translate(-877 -251)">
                <path fill="#0DA0FD" fillRule="evenodd" d={BIRD} />
              </g>
            </g>
          </svg>
        </div>
      </div>

      {/* phones */}
      <div className="sm:hidden flex flex-col items-stretch gap-0">
        <BriefCard className="anim-item-in" delay=".1s" />
        <svg viewBox="0 0 40 56" className="w-10 h-14 ml-8 -my-1" fill="none">
          <defs>
            <linearGradient id="hero-arc-m" x1="0" y1="56" x2="0" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor="#06CAB5" />
              <stop offset="1" stopColor="#0DA0FD" />
            </linearGradient>
          </defs>
          <path d="M20 54 C 20 34, 20 20, 20 4" stroke="url(#hero-arc-m)" strokeWidth="6" strokeLinecap="round" />
        </svg>
        <CreatorCard className="anim-item-in" delay=".3s" />
      </div>
    </div>
  );
}

function CreatorCard({ className = '', delay }: { className?: string; delay?: string }) {
  return (
    <div className={`card shadow-pop p-5 ${className}`} style={delay ? { animationDelay: delay } : undefined}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-nest-400 to-brand-400 flex items-center justify-center text-white font-display font-semibold">
            AO
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-ink-900 truncate">Amara Okafor</div>
            <div className="text-xs text-ink-500 truncate">Skincare · Lagos</div>
          </div>
        </div>
        <span className="tag tag-green shrink-0">
          <BadgeCheck className="w-3.5 h-3.5" /> Verified
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-3">
        <Fact label="Subscribers" value="52.4K" />
        <Fact label="Engagement" value="4.8%" />
        <Fact label="Per video" value="$600" />
      </dl>
      <div className="mt-3 flex items-center justify-between text-[11px] text-ink-400">
        <span>Sample profile</span>
        <span className="inline-flex items-center gap-1 text-ink-500">
          <Star className="w-3 h-3 fill-amber-400 text-amber-400" /> 4.9 · 12 reviews
        </span>
      </div>
    </div>
  );
}

function BriefCard({ className = '', delay }: { className?: string; delay?: string }) {
  return (
    <div className={`card shadow-pop p-5 ${className}`} style={delay ? { animationDelay: delay } : undefined}>
      <div className="flex items-center gap-2 text-xs text-ink-500">
        <span className="tag tag-brand">Open brief</span>
        <span>YouTube · Skincare</span>
      </div>
      <div className="mt-3 font-display text-[19px] leading-snug font-semibold text-ink-900">
        Spring routine launch: one 8-minute review
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-3">
        <Fact label="Per creator" value="$400" />
        <Fact label="Apply by" value="14 Nov" />
        <Fact label="Proposals" value="18" />
      </dl>
      <div className="mt-4">
        <div className="flex items-center justify-between text-[11px] text-ink-500">
          <span>Roster</span>
          <span className="font-semibold text-ink-700">2 of 3 accepted</span>
        </div>
        <div className="mt-1.5 grid grid-cols-3 gap-1.5">
          <span className="h-1.5 rounded-full bg-brand-500" />
          <span className="h-1.5 rounded-full bg-brand-500" />
          <span className="h-1.5 rounded-full bg-ink-200" />
        </div>
      </div>
      <div className="mt-3 text-[11px] text-ink-400">Sample brief</div>
    </div>
  );
}

function StatusChip({ className = '', delay }: { className?: string; delay?: string }) {
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full bg-ink-800 text-white pl-2.5 pr-3.5 py-2 text-[13px] font-semibold shadow-pop ${className}`}
      style={delay ? { animationDelay: delay } : undefined}
    >
      <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-nest-400 text-ink-900">
        <Check className="w-3 h-3" strokeWidth={3} />
      </span>
      Proposal accepted
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] text-ink-500">{label}</dt>
      <dd className="mt-0.5 font-display text-[18px] font-semibold text-ink-900 leading-none">{value}</dd>
    </div>
  );
}

/* ───────────────────────── How it works ───────────────────────── */

function HowItWorks() {
  const steps = [
    {
      icon: <Link2 className="w-5 h-5" />,
      title: 'Creators connect YouTube',
      body: 'Subscriber count and engagement come straight from the channel. Instagram, TikTok and Facebook can be added by hand and are marked unverified.',
    },
    {
      icon: <Megaphone className="w-5 h-5" />,
      title: 'Brands post a brief',
      body: 'Set the deliverables, the budget per creator, the application deadline and how many creators you need.',
    },
    {
      icon: <ListChecks className="w-5 h-5" />,
      title: 'Proposals get decided',
      body: 'Creators apply with a rate and a note. Brands shortlist, accept or reject, and both sides see the same status.',
    },
  ];
  return (
    <section id="how" className="bg-mist-100 border-y border-ink-200/70 py-20 sm:py-24">
      <div className="container-page">
        <Reveal>
          <p className="eyebrow">How it works</p>
          <h2 className="display-lg mt-3 max-w-2xl">From brief to booked creator in three steps.</h2>
        </Reveal>

        <ol className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-5">
          {steps.map((s, i) => (
            <li key={s.title}>
              <Reveal delay={((i + 1) * 100) as 100 | 200 | 300}>
                <div className="card p-6 h-full">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-brand-50 text-brand-600">
                      {s.icon}
                    </span>
                    <span className="font-display text-3xl font-semibold text-ink-200" aria-hidden>
                      {i + 1}
                    </span>
                  </div>
                  <h3 className="display-sm mt-5">{s.title}</h3>
                  <p className="mt-2 text-[15px] text-ink-500 leading-relaxed">{s.body}</p>
                </div>
              </Reveal>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ─────────────────────────── Roles ─────────────────────────── */

function Roles() {
  const navigate = useNavigate();
  return (
    <section className="py-20 sm:py-24">
      <div className="container-page">
        <Reveal>
          <p className="eyebrow">Two sides, one marketplace</p>
          <h2 className="display-lg mt-3 max-w-2xl">Built for the people on both ends of a campaign.</h2>
        </Reveal>

        <div className="mt-12 grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Reveal>
            <RoleCard
              id="creators"
              icon={<Users className="w-5 h-5" />}
              tag="For creators"
              title="Show brands what your audience is worth."
              points={[
                'A profile with verified YouTube reach and engagement',
                'A rate card for posts, stories and videos',
                'Portfolio links brands can open',
                'Every application tracked, from pending to decision',
              ]}
              cta="Join as a creator"
              onClick={() => navigate('/register/creator')}
            />
          </Reveal>
          <Reveal delay={100}>
            <RoleCard
              id="brands"
              dark
              icon={<Search className="w-5 h-5" />}
              tag="For brands"
              title="Hire with the facts in front of you."
              points={[
                'Search creators by niche, platform, reach and engagement',
                'See at a glance which numbers are verified',
                'Post briefs with a budget, deadline and roster size',
                'Mark work complete and leave a review',
              ]}
              cta="Join as a brand"
              onClick={() => navigate('/register/brand')}
            />
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function RoleCard({
  id, icon, tag, title, points, cta, onClick, dark = false,
}: {
  id: string;
  icon: JSX.Element;
  tag: string;
  title: string;
  points: string[];
  cta: string;
  onClick: () => void;
  dark?: boolean;
}) {
  return (
    <article
      id={id}
      className={
        dark
          ? 'h-full rounded-2xl bg-ink-800 text-white p-7 sm:p-9 flex flex-col'
          : 'h-full rounded-2xl bg-mist-50 border border-ink-200 shadow-card p-7 sm:p-9 flex flex-col'
      }
    >
      <div className={`flex items-center gap-2.5 text-[13px] font-semibold ${dark ? 'text-nest-400' : 'text-brand-600'}`}>
        {icon}
        {tag}
      </div>
      <h3 className={`mt-5 font-display text-[clamp(1.5rem,2.4vw,1.875rem)] leading-[1.12] tracking-[-0.025em] font-semibold ${dark ? 'text-white' : 'text-ink-900'}`}>
        {title}
      </h3>
      <ul className="mt-6 space-y-3 text-[15px]">
        {points.map((p) => (
          <li key={p} className="flex items-start gap-3">
            <span
              className={`mt-0.5 inline-flex items-center justify-center w-5 h-5 rounded-full shrink-0 ${
                dark ? 'bg-nest-400/15 text-nest-400' : 'bg-brand-50 text-brand-600'
              }`}
            >
              <Check className="w-3 h-3" />
            </span>
            <span className={dark ? 'text-ink-100' : 'text-ink-600'}>{p}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-8">
        <button onClick={onClick} className={`btn btn-md ${dark ? 'bg-white text-ink-800 hover:bg-ink-50' : 'btn-primary'}`}>
          {cta}
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </article>
  );
}

/* ───────────────────────── Closing call to action ───────────────────────── */

function ClosingCTA({ dashboardLink }: { dashboardLink: string | null }) {
  return (
    <section className="container-page pb-20 sm:pb-24">
      <Reveal>
        <div className="relative overflow-hidden rounded-3xl bg-ink-800 px-6 sm:px-12 py-14 sm:py-16">
          <ArcMark className="absolute -right-24 -top-16 w-[90%] sm:w-[70%] max-w-none opacity-80" />
          <div className="relative max-w-xl">
            <h2 className="display-lg text-white">Connect. Create. Grow.</h2>
            <p className="mt-4 text-lg text-ink-200 leading-relaxed">
              Set up a profile or post your first brief in a few minutes.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row gap-3">
              {dashboardLink ? (
                <Link to={dashboardLink} className="btn btn-lg bg-white text-ink-800 hover:bg-ink-50">
                  Open my dashboard <ArrowRight className="w-4 h-4" />
                </Link>
              ) : (
                <>
                  <Link to="/register/role" className="btn btn-lg bg-white text-ink-800 hover:bg-ink-50">
                    Create an account <ArrowRight className="w-4 h-4" />
                  </Link>
                  <Link to="/login" className="btn btn-lg text-white border border-ink-500 hover:bg-ink-700">
                    Log in
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

/* ───────────────────────── Reveal wrapper ───────────────────────── */

function Reveal({
  children, className, delay,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: 100 | 200 | 300 | 400 | 500;
}) {
  const { ref, visible } = useReveal<HTMLDivElement>({ rootMargin: '0px 0px -8% 0px' });
  return (
    <div
      ref={ref}
      className={`reveal min-w-0 ${visible ? 'is-visible' : ''} ${className ?? ''}`}
      data-delay={delay}
    >
      {children}
    </div>
  );
}
