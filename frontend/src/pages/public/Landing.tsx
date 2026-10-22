import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  Check,
  ChevronRight,
  LineChart,
  Megaphone,
  Play,
  Users,
} from 'lucide-react';
import clsx from 'clsx';
import { useAuth } from '../../state/AuthContext';
import { useReveal } from '../../hooks/useReveal';
import { NICHES, currency } from '../../lib/shared';
import { Avatar, ChannelArt, PlatformIcon, CampaignStatusBadge } from '../../components/ui';
import type { Platform } from '../../types';

/* ─────────────────────────── Data ─────────────────────────── */

/** What the scrolling strip shows: the niches and platforms creators and brands pick from on CollabNest. */
const STRIP = [...NICHES, 'YouTube', 'Instagram', 'TikTok', 'Facebook'];

/** The rules of the marketplace, in the words the product uses. */
const GROUND_RULES = [
  ['Creators are verified on YouTube', 'A confirmed email and a channel with at least 1,000 subscribers, connected with Google sign-in.'],
  ['Brands are checked too', 'A confirmed email and one platform an admin has approved, or a YouTube channel.'],
  ['One fixed price', 'The brand sets the budget per creator. There is no bidding and no haggling.'],
  ['Typed numbers wait for an admin', 'Instagram, TikTok and Facebook numbers stay hidden until they are approved.'],
] as const;

/**
 * The Marketplace section shows what a profile and a brief look like. These are made-up examples, labelled "Sample"
 * on the page: the real directories are only open to signed-in brands and creators.
 */
const SAMPLE_CREATORS: {
  id: string; name: string; platform: Platform; niche: string; location: string; engagement: number; subscribers: string;
}[] = [
  { id: 'sample-creator-1', name: 'Amara Okafor', platform: 'YouTube', niche: 'Beauty', location: 'Lagos, Nigeria', engagement: 4.8, subscribers: '52.4K' },
  { id: 'sample-creator-2', name: 'Daniel Reyes', platform: 'YouTube', niche: 'Tech', location: 'Manila, Philippines', engagement: 6.1, subscribers: '31.9K' },
  { id: 'sample-creator-3', name: 'Priya Nair', platform: 'YouTube', niche: 'Food', location: 'Kochi, India', engagement: 5.3, subscribers: '78.2K' },
];

const SAMPLE_BRIEFS: {
  id: string; brand: string; title: string; category: string; platform: Platform; due: string; budget: number; needed: number;
}[] = [
  { id: 'sample-brief-1', brand: 'Sample Skincare Co', title: 'Spring routine launch: one 8-minute review', category: 'Beauty', platform: 'YouTube', due: '14 Nov', budget: 400, needed: 3 },
  { id: 'sample-brief-2', brand: 'Sample Gadgets', title: 'Unboxing and first-week impressions', category: 'Tech', platform: 'YouTube', due: '21 Nov', budget: 650, needed: 2 },
  { id: 'sample-brief-3', brand: 'Sample Pantry', title: 'Three-ingredient weeknight recipe video', category: 'Food', platform: 'YouTube', due: '2 Dec', budget: 300, needed: 4 },
];

/* ─────────────────────────── Page ─────────────────────────── */

export default function Landing() {
  const { user } = useAuth();
  const dashboardLink = user
    ? user.role === 'creator' ? '/creator/dashboard' : '/brand/dashboard'
    : null;

  return (
    <div className="bg-paper-50 text-ink-700">
      <Hero dashboardLink={dashboardLink} />
      <Strip />
      <Manifesto />
      <MarketplaceSection />
      <HowItWorks />
      <Roles />
      <FinalCTA dashboardLink={dashboardLink} />
    </div>
  );
}

/* ════════════════════════════════════════════════════════
   HERO: type-led, no blobs or floating cards.
   ════════════════════════════════════════════════════════ */

function Hero({ dashboardLink }: { dashboardLink: string | null }) {
  const navigate = useNavigate();
  return (
    <section className="relative bg-paper-50 overflow-hidden">
      <div className="absolute inset-0 bg-grid-faint pointer-events-none" aria-hidden />

      <div className="container-page relative pt-10 sm:pt-16 pb-14 sm:pb-20">
        <div className="flex items-center justify-between text-xs text-ink-500">
          <div className="eyebrow flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-ember-500" />
            <span>For micro-influencers and brands</span>
          </div>
          <div className="hidden sm:flex items-center gap-5">
            <span className="font-mono text-ink-400">Connect, create, grow</span>
            <span className="font-mono text-ink-400">/ 2026</span>
          </div>
        </div>

        <div className="mt-10 sm:mt-14 grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16 items-end">
          <div className="lg:col-span-8 min-w-0">
            <Reveal>
              <h1 className="display-xl">
                <span>A marketplace for</span>
                <span className="block">
                  <span className="marker">
                    <span className="italic font-medium">micro</span>
                  </span>
                  <span>-influencers</span>
                  <span className="text-ink-400"> &amp;</span>
                </span>
                <span className="block">the brands that hire them.</span>
              </h1>
            </Reveal>

            <Reveal delay={100}>
              <p className="mt-6 sm:mt-8 text-base sm:text-lg text-ink-500 leading-relaxed max-w-xl">
                On CollabNest, creators connect YouTube so brands see real audience numbers.
                Brands post a brief with the budget up front, and every proposal moves through
                one clear status. No bidding wars, no digging through DMs.
              </p>
            </Reveal>

            <Reveal delay={200}>
              <div className="mt-7 sm:mt-9 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                {dashboardLink ? (
                  <Link to={dashboardLink} className="btn btn-primary btn-lg w-full sm:w-auto">
                    Open my dashboard
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                ) : (
                  <>
                    <button onClick={() => navigate('/register/brand')} className="btn btn-primary btn-lg w-full sm:w-auto">
                      <Megaphone className="w-4 h-4" />
                      I&apos;m a brand
                    </button>
                    <button onClick={() => navigate('/register/creator')} className="btn btn-secondary btn-lg w-full sm:w-auto">
                      <Users className="w-4 h-4" />
                      I&apos;m a creator
                    </button>
                  </>
                )}
                <Link to="/#how" className="btn btn-ghost btn-lg w-full sm:w-auto text-ink-600 hover:text-ink-900">
                  <Play className="w-3.5 h-3.5 fill-current" />
                  See how it works
                </Link>
              </div>
            </Reveal>
          </div>

          <div className="lg:col-span-4 min-w-0">
            <Reveal delay={300}>
              <div className="card p-5 sm:p-6">
                <div className="flex items-center justify-between">
                  <span className="eyebrow">Ground rules</span>
                  <span className="tag tag-ember">
                    <BadgeCheck className="w-3.5 h-3.5" /> Verified
                  </span>
                </div>
                <ul className="mt-5 space-y-4">
                  {GROUND_RULES.map(([title, body]) => (
                    <li key={title} className="flex gap-3">
                      <span className="mt-1.5 inline-block w-1.5 h-1.5 rounded-full bg-ember-500 shrink-0" />
                      <div>
                        <div className="text-sm font-semibold text-ink-900">{title}</div>
                        <div className="mt-0.5 text-[13px] text-ink-500 leading-relaxed">{body}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          </div>
        </div>

        <Reveal delay={300}>
          <div className="mt-10 sm:mt-20 grid grid-cols-2 sm:grid-cols-4 gap-y-6 sm:gap-y-8 gap-x-4 sm:gap-x-6 border-t border-ink-200 pt-6 sm:pt-8">
            <Fact value="1,000+" label="YouTube subscribers to apply" hint="Checked through Google sign-in" />
            <Fact value="Fixed" label="Budget per creator" hint="Shown before anyone applies" />
            <Fact value="Admin" label="Approves other platforms" hint="Instagram, TikTok and Facebook" />
            <Fact value="1" label="Status for both sides" hint="Pending to accepted, in one place" />
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function Fact({ value, label, hint }: { value: string; label: string; hint: string }) {
  return (
    <div className="min-w-0">
      <div className="num-display text-[clamp(1.75rem,3.4vw,2.75rem)]">{value}</div>
      <div className="mt-2 text-sm font-semibold text-ink-900">{label}</div>
      <div className="mt-0.5 text-xs text-ink-500">{hint}</div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════
   STRIP: the scrolling band under the hero.
   ════════════════════════════════════════════════════════ */

const SWATCHES = [
  'bg-ember-100 text-ember-700',
  'bg-sky-100 text-sky-700',
  'bg-amber-100 text-amber-700',
  'bg-rose-100 text-rose-700',
  'bg-emerald-100 text-emerald-700',
  'bg-violet-100 text-violet-700',
];

function Strip() {
  return (
    <section
      aria-label="Niches and platforms on CollabNest"
      className="border-y border-ink-200 bg-paper-100/60 py-6 overflow-hidden"
    >
      <div className="container-page mb-3 flex items-center justify-between text-ink-500">
        <span className="eyebrow flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-ember-500 animate-blink" />
          Niches and platforms on CollabNest
        </span>
        <span className="hidden sm:block eyebrow text-ink-400">Hover to pause</span>
      </div>

      {/* The mask fades the edges; the track holds the list twice so the loop has no gap. */}
      <div className="marquee-mask marquee-pause-on-hover" aria-hidden>
        <div className="marquee-track gap-8 pr-8" style={{ animationDuration: '36s' }}>
          {[...STRIP, ...STRIP].map((name, i) => (
            <div
              key={`${name}-${i}`}
              className="inline-flex items-center gap-2.5 h-10 pl-1.5 pr-4 bg-paper-50 border border-ink-200/80 rounded-md
                         text-ink-700 hover:text-ink-900 hover:border-ink-300 transition-colors shrink-0"
            >
              <span
                className={clsx(
                  'w-7 h-7 rounded-sm flex items-center justify-center font-display font-semibold text-[14px] leading-none',
                  SWATCHES[(name.charCodeAt(0) + i) % SWATCHES.length],
                )}
              >
                {name[0]}
              </span>
              <span className="font-display text-[15px] font-medium tracking-[-0.015em] whitespace-nowrap">{name}</span>
              <span className="font-mono text-[10px] text-ink-400 ml-1 hidden md:inline">
                0{(i % STRIP.length) + 1}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ════════════════════════════════════════════════════════
   MANIFESTO
   ════════════════════════════════════════════════════════ */

function Manifesto() {
  return (
    <section className="container-page py-20 sm:py-28">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16">
        <div className="lg:col-span-4">
          <Reveal>
            <span className="eyebrow">/ 01 — The problem</span>
            <h2 className="display-md mt-4">
              Influencer marketing<br />
              stopped making sense.
            </h2>
          </Reveal>
        </div>
        <div className="lg:col-span-7 lg:col-start-6">
          <Reveal delay={100}>
            <p className="text-ink-700 text-lg sm:text-xl leading-relaxed">
              Big platforms reward big creators. Brands pay inflated rates for audiences they
              can&apos;t verify. Smaller creators, the ones with real, loyal followings, get buried in DMs.
            </p>
            <p className="mt-4 text-ink-500 text-base sm:text-lg leading-relaxed">
              CollabNest flips the model: verified stats, transparent briefs and a single status
              flow that both sides can see.
            </p>
          </Reveal>

          <Reveal delay={200}>
            <ul className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-5 text-sm">
              {[
                ['Verified YouTube stats', 'Subscribers and engagement come straight from the channel, not from screenshots.'],
                ['Briefs with budgets', 'Every campaign lists its deliverables, deadline and per-creator budget up front.'],
                ['One status flow', 'Shortlist, accept, reject. Both sides see the same status at all times.'],
                ['A full roster stops', 'Accepting stops at the number of creators the brand asked for.'],
              ].map(([title, body]) => (
                <li key={title} className="flex gap-3">
                  <span className="mt-1.5 inline-block w-1.5 h-1.5 rounded-full bg-ember-500 shrink-0" />
                  <div>
                    <div className="font-semibold text-ink-900">{title}</div>
                    <div className="mt-1 text-ink-500 leading-relaxed">{body}</div>
                  </div>
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ════════════════════════════════════════════════════════
   MARKETPLACE: what a profile and a brief look like.
   ════════════════════════════════════════════════════════ */

function MarketplaceSection() {
  return (
    <section id="marketplace" className="bg-paper-100/60 border-y border-ink-200 py-20 sm:py-28">
      <div className="container-page">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16 items-end mb-12">
          <div className="lg:col-span-7">
            <Reveal>
              <span className="eyebrow">/ 02 — Marketplace</span>
              <h2 className="display-lg mt-3">
                A look at <span className="marker marker-soft">both sides</span> of the board.
              </h2>
            </Reveal>
          </div>
          <Reveal delay={100} className="lg:col-span-5">
            <p className="text-ink-500 text-lg leading-relaxed">
              Brands browse creators by their real numbers. Creators browse open briefs with the budget
              shown up front. The examples below are samples. Sign up to see the live marketplace.
            </p>
          </Reveal>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          {/* Creators */}
          <Reveal>
            <div className="flex items-end justify-between mb-4">
              <h3 className="display-sm">From the creator directory</h3>
              <Link to="/register/brand" className="text-sm link-accent inline-flex items-center gap-1">
                Join as a brand <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
            <ul className="space-y-3 stagger">
              {SAMPLE_CREATORS.map((c) => (
                <li key={c.id}>
                  <Link to="/register/brand" className="card card-hover p-4 flex items-center gap-4 group">
                    <ChannelArt name={c.name} seed={c.id} height={56} className="w-14 rounded-md" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="font-semibold text-ink-900 truncate">{c.name}</div>
                        <BadgeCheck className="w-3.5 h-3.5 text-ember-500 shrink-0" />
                        <span className="tag tag-paper !py-0.5 !text-[9px] shrink-0">Sample</span>
                      </div>
                      <div className="mt-0.5 text-xs text-ink-500 flex items-center gap-1.5 min-w-0">
                        <span className="shrink-0"><PlatformIcon platform={c.platform} /></span>
                        <span className="truncate">{c.niche}</span>
                        <span className="text-ink-300 shrink-0">·</span>
                        <span className="truncate">{c.location}</span>
                      </div>
                    </div>
                    <div className="hidden sm:block text-right shrink-0">
                      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">Engagement</div>
                      <div className="num-display text-lg text-ink-900">{c.engagement}%</div>
                      <div className="text-[11px] text-ink-500">{c.subscribers} subscribers</div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Reveal>

          {/* Briefs */}
          <Reveal delay={100}>
            <div className="flex items-end justify-between mb-4">
              <h3 className="display-sm">From open briefs</h3>
              <Link to="/register/creator" className="text-sm link-accent inline-flex items-center gap-1">
                Join as a creator <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
            <ul className="space-y-3 stagger">
              {SAMPLE_BRIEFS.map((b) => (
                <li key={b.id}>
                  <Link to="/register/creator" className="card card-hover p-4 group block">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-xs text-ink-500 flex items-center gap-1.5 mb-1">
                          <Avatar name={b.brand} size="xs" tone="ink" />
                          <span className="truncate">{b.brand}</span>
                          <span className="tag tag-paper !py-0.5 !text-[9px] shrink-0">Sample</span>
                        </div>
                        <div className="font-semibold text-ink-900 leading-snug line-clamp-2">{b.title}</div>
                        <div className="mt-1 text-xs text-ink-500">
                          {b.category} · {b.platform} · due {b.due}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">Per creator</div>
                        <div className="num-display text-lg text-ink-900">{currency(b.budget)}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-[11px] text-ink-500">
                      <CampaignStatusBadge status="published" />
                      <span>{b.needed} creators needed</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ════════════════════════════════════════════════════════
   HOW IT WORKS
   ════════════════════════════════════════════════════════ */

function HowItWorks() {
  return (
    <section id="how" className="bg-ink-900 text-ink-200 py-20 sm:py-28 relative overflow-hidden scroll-mt-16">
      <div
        className="absolute inset-0 opacity-[0.06] pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)',
          backgroundSize: '64px 64px',
        }}
        aria-hidden
      />

      <div className="container-page relative">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 border-b border-ink-700/70 pb-8">
          <Reveal>
            <span className="eyebrow text-ink-300">/ 03 — How it works</span>
            <h2 className="display-lg mt-3 text-paper-50 max-w-xl">
              Three steps. <span className="text-ink-300">Both sides.</span>
            </h2>
          </Reveal>
          <Reveal delay={100}>
            <p className="text-ink-200 max-w-sm text-base sm:text-lg">
              From a connected channel to a booked creator, the flow is the same for everyone.
            </p>
          </Reveal>
        </div>

        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-px bg-ink-700/70 border border-ink-700/70 stagger">
          <Step
            n="01"
            side="Creator"
            icon={<BadgeCheck className="w-4 h-4" />}
            title="Connect and get verified."
            body="Sign in with Google to connect your YouTube channel. Your subscriber count and engagement come from the channel itself."
            meta="Takes a minute"
          />
          <Step
            n="02"
            side="Brand"
            icon={<Megaphone className="w-4 h-4" />}
            title="Post a brief with a budget."
            body="Set the deliverables, the deadline, the budget per creator and how many creators you need. Then publish."
            meta="Takes a few minutes"
          />
          <Step
            n="03"
            side="Both"
            icon={<LineChart className="w-4 h-4" />}
            title="Move proposals through one status."
            body="Brands shortlist, accept or reject. Creators see the decision as soon as it is made."
            meta="Ongoing"
          />
        </div>
      </div>
    </section>
  );
}

function Step({
  n, side, icon, title, body, meta,
}: {
  n: string; side: string;
  icon: JSX.Element; title: string; body: string; meta: string;
}) {
  return (
    <article className="bg-ink-900 p-7 sm:p-9 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] tracking-[0.2em] text-ink-300">STEP {n}</span>
        <span className="tag tag-outline !text-ink-200 !border-ink-500 flex items-center gap-1.5">
          {icon} {side}
        </span>
      </div>
      <h3 className="mt-10 font-display text-2xl sm:text-3xl text-paper-50 leading-[1.1] tracking-[-0.02em]">{title}</h3>
      <p className="mt-4 text-ink-200 leading-relaxed text-[15px]">{body}</p>
      <div className="mt-auto pt-8 flex items-center gap-2 text-xs text-ink-300">
        <span className="w-1.5 h-1.5 rounded-full bg-ember-400" />
        <span className="font-mono uppercase tracking-[0.14em]">{meta}</span>
      </div>
    </article>
  );
}

/* ════════════════════════════════════════════════════════
   ROLES
   ════════════════════════════════════════════════════════ */

function Roles() {
  const navigate = useNavigate();
  return (
    <section className="container-page py-20 sm:py-28">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16 items-end mb-12 sm:mb-16">
        <div className="lg:col-span-7">
          <Reveal>
            <span className="eyebrow">/ 04 — Pick a side</span>
            <h2 className="display-lg mt-3">
              Two roles, <span className="text-ink-400">one</span> clean flow.
            </h2>
          </Reveal>
        </div>
        <Reveal delay={100} className="lg:col-span-5">
          <p className="text-ink-500 text-lg leading-relaxed">
            Sign up as a creator or a brand. Either way you see the same proposal status as the
            other side.
          </p>
        </Reveal>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Reveal>
          <RoleCard
            id="creators"
            tone="creator"
            tag="For creators"
            title="Build a profile brands actually want to work with."
            body="Stand out with verified stats, a rate card and a portfolio of past work."
            points={[
              'Verified YouTube connection',
              'Rates for posts, stories and videos',
              'Portfolio links brands can open',
              'Every application tracked to a decision',
            ]}
            cta="Join as a creator"
            onClick={() => navigate('/register/creator')}
          />
        </Reveal>
        <Reveal delay={100}>
          <RoleCard
            id="brands"
            tone="brand"
            tag="For brands"
            title="Find the right creators and run real campaigns."
            body="Search creators by the numbers, post briefs in minutes and manage every proposal in one place."
            points={[
              'Search by niche, platform, reach and engagement',
              'See which numbers are verified',
              'Post briefs with a budget and a roster size',
              'Mark work complete and leave a review',
            ]}
            cta="Join as a brand"
            onClick={() => navigate('/register/brand')}
          />
        </Reveal>
      </div>
    </section>
  );
}

function RoleCard({
  id, tone, tag, title, body, points, cta, onClick,
}: {
  id: string;
  tone: 'creator' | 'brand';
  tag: string; title: string; body: string;
  points: string[]; cta: string; onClick: () => void;
}) {
  const isCreator = tone === 'creator';
  return (
    <article
      id={id}
      className={`relative overflow-hidden rounded-[20px] border p-7 sm:p-10
        ${isCreator ? 'bg-ink-900 text-paper-50 border-ink-900' : 'bg-paper-50 text-ink-900 border-ink-200'}`}
    >
      <div
        className={`absolute top-0 right-0 w-32 h-32 -mr-12 -mt-12 rounded-full ${isCreator ? 'bg-ember-500/15' : 'bg-ember-500/10'}`}
        aria-hidden
      />

      <div className="relative flex items-center justify-between">
        <span className={`eyebrow ${isCreator ? 'text-ink-300' : 'text-ink-500'}`}>{tag}</span>
        <ArrowUpRight className={`w-4 h-4 ${isCreator ? 'text-ink-300' : 'text-ink-500'}`} />
      </div>

      <h3
        className={`relative mt-6 font-display tracking-[-0.02em] leading-[1.05] text-[clamp(1.5rem,2.6vw,2rem)]
        ${isCreator ? 'text-paper-50' : 'text-ink-900'}`}
      >
        {title}
      </h3>
      <p className={`relative mt-3 text-[15px] leading-relaxed max-w-md ${isCreator ? 'text-ink-200' : 'text-ink-500'}`}>
        {body}
      </p>

      <ul className="relative mt-7 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
        {points.map((p) => (
          <li key={p} className="flex items-start gap-2.5">
            <span
              className={`mt-0.5 inline-flex items-center justify-center w-4 h-4 shrink-0
              ${isCreator ? 'bg-ember-500 text-paper-50' : 'bg-ink-900 text-paper-50'}`}
              style={{ borderRadius: 3 }}
            >
              <Check className="w-3 h-3" />
            </span>
            <span className={isCreator ? 'text-paper-200' : 'text-ink-700'}>{p}</span>
          </li>
        ))}
      </ul>

      <div className="relative mt-9">
        <button
          onClick={onClick}
          className={`btn btn-md ${isCreator ? 'bg-paper-50 text-ink-900 hover:bg-paper-100' : 'btn-primary'}`}
        >
          {cta}
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </article>
  );
}

/* ════════════════════════════════════════════════════════
   FINAL CALL TO ACTION
   ════════════════════════════════════════════════════════ */

function FinalCTA({ dashboardLink }: { dashboardLink: string | null }) {
  return (
    <section className="container-page pb-20 sm:pb-28">
      <Reveal>
        <div className="relative overflow-hidden bg-ink-900 text-paper-50 rounded-[24px] px-6 sm:px-10 lg:px-14 py-12 sm:py-16">
          <div
            className="absolute inset-0 opacity-[0.05] pointer-events-none"
            style={{
              backgroundImage:
                'linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)',
              backgroundSize: '48px 48px',
            }}
            aria-hidden
          />
          <div className="absolute -right-24 -top-24 w-80 h-80 rounded-full bg-ember-500/30 blur-3xl" aria-hidden />

          <div className="relative grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            <div className="lg:col-span-7">
              <span className="eyebrow text-ink-300">/ 05 — Get started</span>
              <h2 className="display-lg mt-3 text-paper-50">
                Connect. Create.<br />
                <span className="text-ember-300 italic font-medium">Grow.</span>
              </h2>
              <p className="mt-5 text-ink-200 text-lg max-w-md leading-relaxed">
                Set up a profile or post your first brief in a few minutes.
              </p>
            </div>

            <div className="lg:col-span-5 flex flex-col sm:flex-row lg:flex-col gap-3">
              {dashboardLink ? (
                <Link to={dashboardLink} className="btn btn-accent btn-lg w-full">
                  Open my dashboard
                  <ArrowRight className="w-4 h-4" />
                </Link>
              ) : (
                <>
                  <Link to="/register/role" className="btn btn-accent btn-lg w-full">
                    Create an account
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                  <Link
                    to="/login"
                    className="btn btn-lg w-full bg-transparent text-paper-50 border border-ink-500 hover:bg-ink-800"
                  >
                    I already have an account
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

/* ─────────────────────── Reveal wrapper ─────────────────────── */

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
