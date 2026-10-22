import { useId } from 'react';

/**
 * The CollabNest arc: the swoop from the logo's "N", drawn once as a gradient stroke.
 * Used as the single decorative device on navy surfaces (auth panel, closing call to action).
 */
export function ArcMark({ className }: { className?: string }) {
  const gid = `arc-${useId().replace(/:/g, '')}`;
  return (
    <svg viewBox="0 0 700 420" fill="none" aria-hidden focusable="false" className={className}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#DC8A66" />
          <stop offset="0.55" stopColor="#CC6A42" />
          <stop offset="1" stopColor="#B8502B" />
        </linearGradient>
      </defs>
      <path
        className="arc-path"
        pathLength={1}
        d="M12 404 C 150 130, 380 26, 690 92"
        stroke={`url(#${gid})`}
        strokeWidth="26"
        strokeLinecap="round"
        opacity="0.9"
      />
      <path
        className="arc-path"
        pathLength={1}
        style={{ animationDelay: '0.55s' }}
        d="M12 404 C 150 130, 380 26, 690 92"
        transform="translate(0 46)"
        stroke="#ffffff"
        strokeOpacity="0.1"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
