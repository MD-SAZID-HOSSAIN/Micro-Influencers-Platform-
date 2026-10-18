import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Menu, X, ArrowRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Logo } from './Logo';
import clsx from 'clsx';

const PUBLIC_NAV = [
  { href: '/#how',      label: 'How it works' },
  { href: '/#creators', label: 'For creators' },
  { href: '/#brands',   label: 'For brands' },
] as const;

/** Sign-in and sign-up screens bring their own full-height layout, so they skip the site chrome. */
const FOCUSED_ROUTES =
  /^\/(login|register|forgot-password|verify-code|reset-password|verify-email)(\/|$)/;

export default function PublicLayout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 1024) setMenuOpen(false);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    if (menuOpen) {
      window.addEventListener('keydown', onKey);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', onKey);
      if (menuOpen) document.body.style.overflow = '';
    };
  }, [menuOpen]);

  useEffect(() => setMenuOpen(false), [pathname]);

  const closeMenu = () => setMenuOpen(false);

  if (FOCUSED_ROUTES.test(pathname)) {
    return (
      <main id="main">
        <Outlet />
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-mist-50 text-ink-700 flex flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50
                   focus:bg-ink-700 focus:text-white focus:px-3 focus:py-2 focus:rounded-md
                   focus:text-sm focus:font-semibold"
      >
        Skip to main content
      </a>

      <header
        className={clsx(
          'sticky top-0 z-40 transition-all duration-300 ease-out-quint',
          scrolled
            ? 'bg-mist-50/90 backdrop-blur-md border-b border-ink-200/80'
            : 'bg-mist-50 border-b border-transparent',
        )}
      >
        <div className="container-page h-16 flex items-center justify-between gap-3 sm:gap-6">
          <Logo onClick={closeMenu} size="md" />

          <nav aria-label="Primary" className="hidden lg:flex items-center gap-1 text-sm text-ink-700">
            {PUBLIC_NAV.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className="px-3.5 py-2 rounded-lg font-semibold text-ink-600 hover:text-ink-900 hover:bg-ink-100/70 transition-colors"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            <Link to="/login" className="btn btn-ghost btn-sm sm:btn-md hidden sm:inline-flex">
              Log in
            </Link>
            <button onClick={() => navigate('/register/role')} className="btn btn-primary btn-sm sm:btn-md">
              Get started
              <ArrowRight className="w-3.5 h-3.5 hidden sm:inline" />
            </button>

            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              aria-controls="primary-mobile-menu"
              className="lg:hidden ml-1 inline-flex items-center justify-center w-10 h-10
                         text-ink-700 hover:bg-ink-100/70 rounded-lg"
            >
              {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <div
          id="primary-mobile-menu"
          className={clsx(
            'lg:hidden overflow-hidden border-t border-ink-200 bg-mist-50',
            'transition-all duration-300 ease-out-quint',
            menuOpen ? 'max-h-[80vh] opacity-100' : 'max-h-0 opacity-0 pointer-events-none',
          )}
          aria-hidden={!menuOpen}
        >
          <nav className="container-page py-3 flex flex-col text-sm text-ink-700" aria-label="Primary mobile">
            {PUBLIC_NAV.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                onClick={closeMenu}
                className="py-3 border-b border-ink-200/60 font-semibold hover:text-ink-900 transition-colors"
              >
                {item.label}
              </Link>
            ))}
            <Link
              to="/login"
              onClick={closeMenu}
              className="py-3 font-semibold hover:text-ink-900 transition-colors"
            >
              Log in
            </Link>
          </nav>
        </div>
      </header>

      <main id="main" className="flex-1">
        <Outlet />
      </main>

      <footer className="bg-ink-800 text-ink-200">
        <div className="container-page py-14 sm:py-16">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
            <div className="lg:col-span-5">
              <Logo variant="invert" size="md" />
              <p className="mt-5 text-ink-300 max-w-sm leading-relaxed">
                Connect, create, grow. A marketplace where brands hire micro-influencers
                with audiences they can verify.
              </p>
            </div>

            <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-8 text-sm">
              <div>
                <h4 className="text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-400">Product</h4>
                <ul className="mt-4 space-y-2.5">
                  <li><Link to="/#how" className="hover:text-white transition-colors">How it works</Link></li>
                  <li><Link to="/#creators" className="hover:text-white transition-colors">For creators</Link></li>
                  <li><Link to="/#brands" className="hover:text-white transition-colors">For brands</Link></li>
                </ul>
              </div>
              <div>
                <h4 className="text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-400">Account</h4>
                <ul className="mt-4 space-y-2.5">
                  <li><Link to="/login" className="hover:text-white transition-colors">Log in</Link></li>
                  <li><Link to="/register/role" className="hover:text-white transition-colors">Create an account</Link></li>
                </ul>
              </div>
              <div>
                <h4 className="text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-400">Legal</h4>
                <ul className="mt-4 space-y-2.5">
                  <li><Link to="/terms" className="hover:text-white transition-colors">Terms</Link></li>
                  <li><Link to="/privacy" className="hover:text-white transition-colors">Privacy</Link></li>
                </ul>
              </div>
            </div>
          </div>

          <div className="mt-12 pt-6 border-t border-ink-600/60 text-xs text-ink-400">
            © 2026 CollabNest
          </div>
        </div>
      </footer>
    </div>
  );
}
