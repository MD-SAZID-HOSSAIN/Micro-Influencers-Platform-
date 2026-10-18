import { ReactNode } from 'react';
import AuthVisual from './AuthVisual';
import { Wordmark } from './Logo';

type Variant = 'neutral' | 'creator' | 'brand';

export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
  side,
  variant = 'neutral',
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  side?: ReactNode;
  variant?: Variant;
}) {
  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-mist-50">
      <div className="flex-1 flex items-center justify-center py-10 sm:py-14 px-5 sm:px-6">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <Wordmark to="/" size="md" />
          </div>

          <h1 className="font-display text-ink-900 text-[clamp(1.75rem,3vw,2.25rem)] leading-[1.1] tracking-[-0.03em] font-semibold">
            {title}
          </h1>
          {subtitle && (
            <p className="text-sm sm:text-[15px] text-ink-500 mt-2.5 leading-relaxed">
              {subtitle}
            </p>
          )}

          <div className="mt-7">{children}</div>
          {footer && <div className="mt-6 text-sm text-ink-600">{footer}</div>}
        </div>
      </div>

      <div className="hidden lg:flex flex-1 items-stretch p-8 xl:p-12 bg-ink-800 overflow-hidden relative">
        <div className="w-full max-w-[560px] mx-auto flex">
          {side ?? <AuthVisual variant={variant} />}
        </div>
      </div>
    </div>
  );
}
