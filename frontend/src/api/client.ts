/**
 * Thin fetch wrapper around the CollabNest Django backend.
 *
 * The base URL is `VITE_API_URL` when set (production), otherwise `/api/v1` on the same origin,
 * which the Vite dev server proxies to Django (see vite.config.ts).
 *
 * - Reads the JWT from localStorage on every call and adds Authorization: Bearer …
 * - Normalises the backend's error envelope `{"error": {"code","message","details"}}` into a thrown `ApiError`.
 * - Sends cookies too (SameSite=Lax in dev), in case the backend ever moves to session auth.
 * - JSON-only, with a 12s timeout to avoid a hung UI.
 */

const DEFAULT_BASE_URL: string = import.meta.env.VITE_API_URL || '/api/v1';

/**
 * Creators/brands and admins sign in separately and must not overwrite each other, so each
 * keeps its own token. Calls under `admin/` use the admin session; everything else the user one.
 */
export type Session = 'user' | 'admin';

const STORAGE_KEYS = {
  baseUrl: 'microinf_api_base',
  token: { user: 'microinf_token', admin: 'microinf_admin_token' } as Record<Session, string>,
} as const;

export const getBaseUrl = (): string => {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.baseUrl);
    if (stored) return stored;
  } catch {}
  return DEFAULT_BASE_URL;
};

export const setBaseUrl = (url: string) => {
  try {
    localStorage.setItem(STORAGE_KEYS.baseUrl, url);
  } catch {}
};

/**
 * Uploaded pictures come back as paths like `/media/...`, which live on the API's server, not the
 * website's. This turns them into addresses the browser can open (full links pass through untouched).
 */
export const resolveAssetUrl = (url: string | null | undefined): string | undefined => {
  if (!url) return undefined;
  if (!url.startsWith('/')) return url;
  return new URL(url, new URL(getBaseUrl(), window.location.origin)).toString();
};

/** Every login is remembered between visits, until the person logs out. */
export const storageFor = (_session: Session): Storage => localStorage;

export const getToken = (session: Session = 'user'): string | null => {
  try {
    return storageFor(session).getItem(STORAGE_KEYS.token[session]);
  } catch {
    return null;
  }
};

export const setToken = (token: string | null, session: Session = 'user') => {
  try {
    if (token) storageFor(session).setItem(STORAGE_KEYS.token[session], token);
    else storageFor(session).removeItem(STORAGE_KEYS.token[session]);
  } catch {}
};

/**
 * Listeners told when an authenticated request comes back 401 (token expired or revoked), with
 * the session it belonged to. The auth providers register here so a dead session is cleared and
 * the route guards send the user to the login page, instead of the app staying "logged in"
 * while every call fails.
 */
const unauthorizedListeners = new Set<(session: Session) => void>();

export const onUnauthorized = (listener: (session: Session) => void): (() => void) => {
  unauthorizedListeners.add(listener);
  return () => {
    unauthorizedListeners.delete(listener);
  };
};

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  constructor(opts: {
    status: number;
    code: string;
    message: string;
    details?: unknown;
  }) {
    super(opts.message);
    this.name = 'ApiError';
    this.status = opts.status;
    this.code = opts.code;
    this.details = opts.details;
  }
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

type RequestOpts = {
  method?: Method;
  body?: unknown;
  /** Form data: pass an object that should be JSON-encoded, or a FormData instance. */
  formData?: FormData;
  /** Skip the Authorization header (e.g. for /auth/login). */
  anonymous?: boolean;
  /** Which login to use. Defaults to the admin session for `admin/…` paths, else the user one. */
  session?: Session;
  /** AbortController signal. */
  signal?: AbortSignal;
  /** How long to wait before giving up. Defaults to 12 seconds; uploads ask for longer. */
  timeoutMs?: number;
  /** Query string params, will be URL-encoded. */
  query?: Record<string, string | number | boolean | undefined | null>;
};

const buildUrl = (path: string, base: string, query?: RequestOpts['query']) => {
  const normalizedBase = base.endsWith('/') ? base : `${base}/`;
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  // The base may be relative ("/api/v1"), so resolve it against the page origin first.
  const url = new URL(cleanPath, new URL(normalizedBase, window.location.origin));
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null || v === '') continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
};

export async function request<T = unknown>(path: string, opts: RequestOpts = {}): Promise<T> {
  const base = getBaseUrl();
  const url = buildUrl(path, base, opts.query);
  const session: Session = opts.session ?? (path.replace(/^\//, '').startsWith('admin/') ? 'admin' : 'user');
  const token = getToken(session);

  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  let body: BodyInit | undefined;

  if (opts.formData) {
    body = opts.formData as unknown as BodyInit;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }

  if (!opts.anonymous && token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), opts.timeoutMs ?? 12_000);
  // The request always uses our controller's signal, so the timeout applies even when the
  // caller passes its own signal; the caller's abort is forwarded to the controller.
  const signal = controller.signal;
  const onCallerAbort = () => controller.abort();
  if (opts.signal?.aborted) controller.abort();
  else opts.signal?.addEventListener('abort', onCallerAbort);

  let res: Response;
  try {
    res = await fetch(url, {
      method: opts.method ?? (opts.body || opts.formData ? 'POST' : 'GET'),
      headers,
      body,
      credentials: 'same-origin',
      signal,
    });
  } catch (err) {
    window.clearTimeout(timeoutId);
    if ((err as DOMException)?.name === 'AbortError') {
      throw new ApiError({
        status: 0,
        code: 'aborted',
        message: 'Request was cancelled or timed out.',
      });
    }
    throw new ApiError({
      status: 0,
      code: 'network',
      message: 'Network error — could not reach the server. Is the backend running?',
      details: err,
    });
  } finally {
    window.clearTimeout(timeoutId);
    opts.signal?.removeEventListener('abort', onCallerAbort);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  // Try to parse JSON. Some 204s report no body, others return a payload; tolerate both.
  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { raw: text };
    }
  }

  if (!res.ok) {
    // A 401 on a request that carried a token means the session is gone. Anonymous calls
    // (login, register, password reset) also return 401 for bad input, so they are excluded.
    if (res.status === 401 && token && !opts.anonymous) {
      setToken(null, session);
      unauthorizedListeners.forEach((listener) => listener(session));
    }
    throw normaliseError(res, payload);
  }

  return payload as T;
}

function normaliseError(res: Response, payload: unknown): ApiError {
  // Backend envelope: { error: { code, message, details? } }
  if (
    payload &&
    typeof payload === 'object' &&
    'error' in (payload as Record<string, unknown>)
  ) {
    const env = (payload as { error: { code?: string; message?: string; details?: unknown } })
      .error;
    return new ApiError({
      status: res.status,
      code: env?.code ?? `http_${res.status}`,
      message: env?.message ?? res.statusText,
      details: env?.details,
    });
  }
  // DRF default {"detail": "..."} or {"field": ["..."]} validators
  if (payload && typeof payload === 'object') {
    const p = payload as Record<string, unknown>;
    if (typeof p.detail === 'string') {
      return new ApiError({ status: res.status, code: `http_${res.status}`, message: p.detail });
    }
    // Field errors — flatten the first message per field.
    const parts: string[] = [];
    for (const [k, v] of Object.entries(p)) {
      if (Array.isArray(v) && v.length) parts.push(`${k}: ${v[0]}`);
      else if (typeof v === 'string') parts.push(`${k}: ${v}`);
    }
    return new ApiError({
      status: res.status,
      code: `http_${res.status}`,
      message: parts.length ? parts.join(' · ') : res.statusText,
      details: payload,
    });
  }
  return new ApiError({
    status: res.status,
    code: `http_${res.status}`,
    message: res.statusText || 'Request failed',
  });
}

/** Shortcut to inspect if a thrown value is an ApiError. */
export const isApiError = (e: unknown): e is ApiError => e instanceof ApiError;
