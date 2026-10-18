import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BadgeCheck,
  Check,
  Link2,
  Megaphone,
  Search,
  Users,
  Wallet,
  ListChecks,
} from 'lucide-react';
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
    <section className="relative overflow-hidden">
      <div className="container-page pt-12 sm:pt-16 lg:pt-20 pb-16 sm:pb-24">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          <div className="lg:col-span-6 min-w-0">
            <Reveal>
              <p className="eyebrow">Micro-influencers and the brands that hire them</p>
              <h1 className="display-xl mt-5">
                Find creators{' '}
                <span className="marker marker-soft">worth working with.</span>
              </h1>
            </Reveal>

            <Reveal delay={100}>
              <p className="mt-6 text-lg text-ink-500 leading-relaxed max-w-xl">
                CollabNest lists creators with audience stats taken from their YouTube
                channel, and brands with the budget stated up front. Post a brief, review
                proposals, and accept exactly as many creators as you need.
              </p>
            </Reveal>

            <Reveal delay={200}>
              <div className="mt-8 flex flex-col sm:flex-row gap-3">
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
              </div>
            </Reveal>

            <Reveal delay={300}>
              <ul className="mt-10 grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                {[
                  [BadgeCheck, 'Stats from the source', 'Audience size comes from YouTube, not screenshots.'],
                  [Wallet, 'Budget on every brief', 'Creators see the rate before they apply.'],
                  [ListChecks, 'A hard stop at your number', 'Acceptances end when the roster is full.'],
                ].map(([Icon, title, body]) => {
                  const I = Icon as typeof BadgeCheck;
                  return (
                    <li key={title as string} className="flex sm:block gap-3">
                      <I className="w-5 h-5 text-brand-500 shrink-0 sm:mb-2" aria-hidden />
                      <div>
                        <div className="font-semibold text-ink-900">{title as string}</div>
                        <div className="mt-0.5 text-ink-500 leading-snug">{body as string}</div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Reveal>
          </div>

          <div className="lg:col-span-6 min-w-0">
            <HeroArc />
          </div>
        </div>
      </div>
    </section>
  );
}

/**
 * The page's one signature: a brief on the left, a creator on the right, and the logo's arc
 * drawing itself between them with the bird landing on the creator. It is the product in a
 * single picture: a brief finding the right creator.
 */
function HeroArc() {
  return (
    <div className="relative mx-auto w-full max-w-[560px] h-[440px] sm:h-[480px]" aria-hidden>
      <svg
        viewBox="0 0 560 480"
        className="absolute inset-0 w-full h-full"
        fill="none"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="hero-arc" x1="40" y1="0" x2="160" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#06CAB5" />
            <stop offset="0.55" stopColor="#14B5E0" />
            <stop offset="1" stopColor="#0DA0FD" />
          </linearGradient>
        </defs>
        <path
          className="arc-path"
          pathLength={1}
          d="M74 300 C 34 190, 70 100, 156 92"
          stroke="url(#hero-arc)"
          strokeWidth="12"
          strokeLinecap="round"
        />
      </svg>

      {/* Creator card (top right) */}
      <div className="absolute right-0 top-[44px] w-[86%] sm:w-[74%] card shadow-pop p-5 anim-item-in" style={{ animationDelay: '.5s' }}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-11 h-11 rounded-full bg-gradient-to-br from-nest-400 to-brand-400 flex items-center justify-center text-white font-display font-semibold">
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
        <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
          <Fact label="Subscribers" value="52.4K" />
          <Fact label="Engagement" value="4.8%" />
          <Fact label="Per video" value="$600" />
        </dl>
        <div className="mt-3 text-[11px] text-ink-400">Sample profile</div>
      </div>

      {/* Brief card (bottom left) */}
      <div className="absolute left-0 bottom-0 w-[86%] sm:w-[78%] card shadow-pop p-5 anim-item-in" style={{ animationDelay: '.2s' }}>
        <div className="flex items-center gap-2 text-xs text-ink-500">
          <span className="tag tag-brand">Open brief</span>
          <span>YouTube · Skincare</span>
        </div>
        <div className="mt-3 font-display text-[19px] leading-snug font-semibold text-ink-900">
          Spring routine launch: one 8-minute review
        </div>
        <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
          <Fact label="Per creator" value="$400" />
          <Fact label="Roster" value="3 creators" />
          <Fact label="Apply by" value="14 Nov" />
        </dl>
        <div className="mt-3 text-[11px] text-ink-400">Sample brief</div>
      </div>

      {/* The bird perches where the arc meets the creator, above both cards. */}
      <svg
        viewBox="0 0 560 480"
        className="absolute inset-0 w-full h-full pointer-events-none"
        preserveAspectRatio="xMidYMid meet"
      >
        <g className="bird-land">
          <g transform="translate(118 44) scale(0.8) translate(-877 -251)">
            <path fill="#0DA0FD" fillRule="evenodd" d={BIRD} />
          </g>
        </g>
      </svg>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] text-ink-500">{label}</dt>
      <dd className="mt-0.5 font-display text-[17px] font-semibold text-ink-900 leading-none">{value}</dd>
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
              Set up a profile or post your first brief in a few minutes. It&apos;s free to join.
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
