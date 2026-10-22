import { useId } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';

/**
 * CollabNest brand assets, drawn inline from collabnest-logo.svg so the navy parts can
 * follow `currentColor` (navy on light surfaces, white on dark ones) and the gradients stay
 * unique per instance.
 *
 *   <Wordmark />  mark + "ollabnest" lettering, links home
 *   <Mark />      the C/o infinity loop only, for tight spots (drawer header, avatars)
 *
 * Variants: `default` for light surfaces, `invert` for navy panels and the footer.
 */

type Size = 'sm' | 'md' | 'lg';
type Variant = 'default' | 'invert';

const HEIGHT: Record<Size, number> = { sm: 26, md: 32, lg: 42 };
const MARK_BOX: Record<Size, number> = { sm: 26, md: 32, lg: 42 };

export function Wordmark({
  to = '/',
  onClick,
  size = 'md',
  variant = 'default',
  ariaLabel = 'CollabNest home',
  className,
}: {
  to?: string;
  onClick?: () => void;
  size?: Size;
  variant?: Variant;
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      aria-label={ariaLabel}
      className={clsx('inline-flex items-center rounded-md select-none', className)}
    >
      <LogoArt height={HEIGHT[size]} variant={variant} />
    </Link>
  );
}

/** The loop mark on its own. */
export function Mark({ size = 'md', variant = 'default' }: { size?: Size; variant?: Variant }) {
  return <LogoArt height={MARK_BOX[size]} variant={variant} markOnly />;
}

function LogoArt({
  height,
  variant,
  markOnly = false,
}: {
  height: number;
  variant: Variant;
  markOnly?: boolean;
}) {
  const uid = useId().replace(/:/g, '');
  const swoosh = `sw-${uid}`;
  const arc = `ar-${uid}`;
  const bird = `bd-${uid}`;
  // Source art lives in a 1115x369 canvas; crop to the artwork we need.
  const viewBox = markOnly ? '182 275 275 185' : '184 245 1056 214';
  const width = markOnly ? (height * 275) / 185 : (height * 1056) / 214;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={viewBox}
      width={width}
      height={height}
      aria-hidden
      focusable="false"
      // The logo keeps its own navy (#212F41) whatever the page palette is.
      style={{ color: variant === 'invert' ? '#FFFFFF' : '#212F41' }}
    >
      <defs>
        <linearGradient id={swoosh} gradientUnits="userSpaceOnUse" x1="290" y1="0" x2="425" y2="0">
          <stop offset="0" stopColor="#d9906c" />
          <stop offset="0.2" stopColor="#d2835f" />
          <stop offset="0.45" stopColor="#ca734f" />
          <stop offset="0.6" stopColor="#c56a45" />
          <stop offset="0.78" stopColor="#bf5e3a" />
          <stop offset="1" stopColor="#b8502b" />
        </linearGradient>
        <linearGradient id={arc} gradientUnits="userSpaceOnUse" x1="557" y1="0" x2="800" y2="0">
          <stop offset="0" stopColor="#e9b294" />
          <stop offset="0.247" stopColor="#dd997a" />
          <stop offset="0.494" stopColor="#d0815f" />
          <stop offset="0.741" stopColor="#c46845" />
          <stop offset="0.988" stopColor="#b8502b" />
        </linearGradient>
        <linearGradient id={bird} gradientUnits="userSpaceOnUse" x1="880" y1="292" x2="932" y2="258">
          <stop offset="0" stopColor="#d0815f" />
          <stop offset="0.5" stopColor="#c46845" />
          <stop offset="1" stopColor="#b8502b" />
        </linearGradient>
      </defs>

      <path fill="currentColor" d={O_NAVY} />
      <path fill={`url(#${swoosh})`} d={SWOOSH} />

      {!markOnly && (
        <>
          <path fill="currentColor" fillRule="evenodd" d={L1} />
          <path fill="currentColor" fillRule="evenodd" d={L2} />
          <path fill="currentColor" fillRule="evenodd" d={A} />
          <path fill="currentColor" fillRule="evenodd" d={B} />
          <path fill="#b8502b" d={N_STEM} />
          <path fill={`url(#${arc})`} d={N_ARC} />
          <path fill={`url(#${bird})`} fillRule="evenodd" d={BIRD} />
          <path fill="currentColor" fillRule="evenodd" d={E} />
          <path fill="currentColor" fillRule="evenodd" d={S} />
          <path fill="currentColor" fillRule="evenodd" d={T} />
        </>
      )}
    </svg>
  );
}

/* Default to Logo so the public API stays the same for existing imports. */
export const Logo = Wordmark;
export const LogoMark = Mark;

/* Path data, copied unchanged from collabnest-logo.svg (only the gradient colours were changed, from cyan and blue to e9b294 to b8502b). */
const O_NAVY =
  'M346.1 418.6L365.6 394.2C365.8 394.7 366.2 395.2 366.5 395.7C367.1 396.9 366.9 398.9 367.1 400.2C368.2 407 372.1 413 377 417.6C391 430.7 414.5 424.4 421.6 407.2C426.5 395.4 425.3 380.9 417 370.9C414.5 367.9 411.1 366 408.1 363.8C410 362.8 412.1 362.4 414 361.5C419.7 358.9 428.1 353.7 430.7 348C438.5 352.7 443.9 361.7 447.3 370C458.4 396.8 447.8 432 420.1 443.9C397.6 453.6 368.6 449.4 352.7 429.6C350 426.3 347.2 422.7 346.1 418.6Z';
const SWOOSH =
  'M325.5 326L306.3 345C302 341.3 298.2 337 293.7 333.4C283.5 325 266 323.1 253.6 326.6C211.8 338.4 209.2 400 244.9 417.7C250.5 420.5 254.6 421.3 260.6 422.3C265.5 423.1 270.1 422.6 275 422C313.6 417.3 330.6 365.4 361.6 346.3C377 336.9 395 334.2 412.5 338.7C418 340.2 427 343.3 430.2 348.1C430.1 348.6 430.3 349.1 430 349.6C428 354.1 412.5 363.5 407.5 363.5C404.5 363.5 399.7 360.3 391.3 361.6C379.8 363.3 371.4 371 363.5 378.9C359.7 382.6 356.4 387 353.2 391.1C340.9 406.7 329.2 423.5 313 435.3C300 444.8 283.7 450 267.6 450C254.1 450 240.1 447.4 228.3 440.5C217.4 434.2 208.1 425.6 201.7 414.7C185.4 387 187.4 349.3 208.3 324.4C237.7 289.4 298.7 288.1 325.5 326Z';
const L1 = 'M467.7 446.8L467.7 296.2L494.5 296.2L494.5 446.8L467.7 446.8Z';
const L2 = 'M514.7 446.8L514.7 296.2L541.5 296.2L541.5 446.8L514.7 446.8Z';
const A =
  'M640.8 350.3L640.8 338.7L666.8 338.7L666.8 446.8L641 446.8L641 435C640.4 435.4 639.7 435.5 639.1 435.8C638.1 436.4 636.8 438.1 635.9 439C630.1 444.2 622.1 447.9 614.4 448.7C551.5 455.3 536.6 363.3 589.4 340.3C596.4 337.2 604.4 336.5 612 336.8C620.8 337.1 628.9 340.7 635.7 346.2C636.7 346.9 639 350.1 640 350.3C640.3 350.3 640.5 350.2 640.8 350.3ZM613.4 424.6C631 424.3 640.8 408.1 640.7 391.9C640.7 378.4 632.3 365.3 619.1 361.6C616.8 361 614.1 360.6 611.7 360.9C608.8 361.2 606.1 361.2 603.3 362.2C590.3 366.8 584.2 380.3 584.3 393.3C584.3 410.2 595.6 425 613.4 424.6Z';
const B =
  'M712.3 434.7L712.3 446.8L686.7 446.8L686.7 296.2L713.3 296.2L713.3 349.8C715.4 348.9 712.7 350.9 714.4 349.7C717.6 347.5 719.4 344.4 723.6 342.1C731.7 337.6 740.4 336.3 749.6 336.8C754.3 337 758.8 338.4 763.2 339.9C803.9 354.1 809.2 426.5 764.1 445.3C757.9 447.9 750.4 449.6 743.6 449C734.2 448.1 725.9 445.5 718.4 439.4C716.9 438.3 715.5 436.2 713.9 435.4C713.4 435.1 712.8 435 712.3 434.7ZM742.7 424.4C746.4 423.9 750 423.5 753.3 421.7C763.7 416 770 402.9 768.8 391.3C768.4 387.4 768.1 383.6 766.7 380C762.5 368.8 751.9 359.4 739.3 360.9C737.8 361.1 736.3 361 734.9 361.4C719.1 365 713 379.5 713 394.3C713 409.8 726 426.4 742.7 424.4Z';
const N_STEM = 'M811.5 446.8V339.4C822 346.8 833 358.5 839.9 369.5V446.8Z';
const N_ARC =
  'M905.2 446.7C899.9 439.1 894.4 431.6 889 424C879.5 410.6 870.4 396.8 861 383.3C848.5 365.4 837.2 346.5 820.9 331.8C788.1 302 750.1 284.8 705.7 282.7C688.3 281.9 670.6 282.6 653.5 286.1C630.7 290.9 609.3 299.4 588.6 310.1C581.6 313.8 574.6 318 568.2 322.7C566.9 323.6 560.2 329 559.2 329.1C558.6 329.2 557.9 329 557.3 329.2L557.3 301.3C594 276.3 639.7 261 683.9 258.8C696.7 258.1 709.5 259 722.3 260C732.6 260.8 742.6 263.7 752.7 265.9C763.2 268.2 774 272 783.8 276.5C802 284.8 818.5 295.6 833.7 308.6C851.9 324.1 866.1 343.5 879.7 363C884.6 369.9 888.7 377.4 893.7 384.3C894.5 385.4 897.9 391.5 898.6 391.9C899.3 392.2 900.1 392.3 900.7 392.8L900.7 306.3C905.1 305.2 909.8 304.6 914.1 302.9C917.2 301.7 920.4 300.4 923.1 298.5C924 297.9 925.8 296.2 926.9 296.1C927.6 296.1 928.3 296.3 929 296.2L929 446.7L905.2 446.7Z';
/** The bird that perches on the "N". Exported so the landing hero can reuse the same glyph. */
export const BIRD =
  'M877.7 293.2C877.8 292.6 877.4 292.3 877.8 291.8C879.3 289.7 883.8 285.7 886.4 282.1C892.2 274 894.7 266.7 899.5 259C904.5 251 914.3 245.6 923.3 251.2C927.6 253.9 929.5 258.5 931.6 259.8C933.9 261.3 937.1 261.6 939.4 262.8C937.5 265 934.3 266.2 932.6 268.6C931.3 270.3 930.8 273.1 929.9 275C926.7 282.5 919.5 288.9 912 291.7C903.6 294.8 885.8 296.9 877.7 293.2ZM918.1 267.6C919.1 266.9 920.1 266.7 920.2 265.1C920.2 263.6 919.2 263.2 918.2 262.4C917.1 262.8 916 262.8 915.5 264.2C914.6 266.3 916.7 267.1 918.1 267.6Z';
const E =
  'M1050.4 402.2L972.7 402.2C976.1 421 996.1 429.6 1013.3 423.8C1017.4 422.4 1021.4 420.4 1024.7 417.6C1026.3 416.3 1027.5 414.8 1029.3 413.8L1044.4 429.5C1041.4 434.6 1036.6 438.4 1031.5 441.4C1009.9 454.3 980.1 450.6 961.7 434C945.7 419.6 941.9 395.3 947.2 375.3C957.1 338.5 1003.5 324.4 1032.6 348.5C1048.1 361.4 1052.4 383.2 1050.4 402.2ZM1024 383.5C1024 382.9 1024.2 382.2 1024.2 381.6C1024.3 380.3 1023.5 379 1023.1 377.8C1020.7 369.5 1013.8 361.7 1005.2 359.9C993 357.5 982.1 361.6 975.8 372.6C974.4 375.1 972.4 378.5 972.2 381.4C972.2 382.1 972.3 382.8 972.2 383.5L1004.1 383.5L1024 383.5Z';
const S =
  'M1059.2 433.1L1070.3 413.2C1080.1 419.4 1087 424.6 1099 426C1101.2 426.3 1103.3 426.6 1105.5 426.5C1111.5 426.1 1119.2 424.1 1119.5 416.7C1119.6 414.7 1119 412.7 1117.7 411.1C1113.6 406.1 1105.4 405.3 1099.5 403.7C1084 399.8 1066.2 395.5 1062.3 377.4C1061.2 372.4 1061.5 366.5 1062.8 361.6C1071.4 330.8 1120.8 330.7 1141 349L1130.4 368.1C1127.6 367 1124.9 364.9 1122.2 363.4C1115.8 359.8 1105 357.7 1097.9 359.3C1089.8 361.1 1083.8 368.5 1089.5 374.6C1093.6 378.9 1101.1 379.8 1106.5 381.3C1121.5 385.4 1141.5 389.4 1144.9 407.7C1153.7 454.7 1088.1 458.9 1059.2 433.1Z';
const T =
  'M1164.5 360.5L1149.2 360.5L1149.2 338.7L1165 338.7L1165 311L1191.5 311L1191.5 338.7L1217.8 338.7L1217.8 360.5L1191.9 360.5C1190.6 371.1 1191.5 391.8 1191.5 403.5C1191.5 409.7 1191 417.1 1195.3 422.2C1200.8 428.5 1210.1 424.4 1216.2 421.5L1223.9 441.4C1218.1 446.4 1210.4 448.3 1202.9 448.8C1198.3 449 1193.5 449.1 1189 447.8C1174.1 443.3 1167.1 432.8 1165.1 417.8C1164.4 413.3 1165 408.4 1165 403.8C1165 392.9 1165.9 370 1164.5 360.5Z';
