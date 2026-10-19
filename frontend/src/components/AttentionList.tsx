import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export type AttentionItem = {
  key: string;
  tone: 'brand' | 'amber' | 'rose';
  icon: ReactNode;
  title: string;
  text?: string;
  to: string;
  cta: string;
  /** Router state passed to the link (for example to ask the verify page to send a code). */
  state?: unknown;
};

const TONE: Record<AttentionItem['tone'], string> = {
  brand: 'bg-brand-50 text-brand-700',
  amber: 'bg-amber-50 text-amber-700',
  rose: 'bg-rose-50 text-rose-600',
};

/** A short list of things the user should do next. The most important item is the first one. */
export default function AttentionList({ items }: { items: AttentionItem[] }) {
  return (
    <ul className="card divide-y divide-ink-200/60">
      {items.map((it, i) => (
        <li key={it.key}>
          <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <span className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 ${TONE[it.tone]}`}>
                {it.icon}
              </span>
              <div className="min-w-0">
                <div className="text-sm sm:text-base font-semibold text-ink-900 leading-snug">{it.title}</div>
                {it.text && <div className="text-xs sm:text-sm text-ink-500 mt-0.5">{it.text}</div>}
              </div>
            </div>
            <Link
              to={it.to}
              state={it.state}
              className={`btn btn-md shrink-0 self-start sm:self-auto ${i === 0 ? 'btn-primary' : 'btn-secondary'}`}
            >
              {it.cta} <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}
