/**
 * Typed wrappers around the backend endpoints the UI needs.
 *
 * Each function maps the wire shape to the UI-facing types in src/types.ts and
 * src/state/Store.ts. Keep mappers in this file so screens never see raw API
 * field names.
 */

import { request, resolveAssetUrl } from './client';
import { NICHES, youtubeHandle } from '../lib/shared';
import type {
  AppNotification,
  BrandProfile,
  Campaign,
  CampaignMedia,
  CampaignStatus,
  ConnectedAccount,
  CreatorProfile,
  MyProposal,
  Niche,
  Platform,
  PortfolioLink,
  Proposal,
  ProposalStatus,
  Role,
  User,
} from '../types';

// ----- Auth -----------------------------------------------------------------

export type LoginInput = { identifier: string; password: string };
export type RegisterInput = {
  role: Role;
  fullName: string;
  email: string;
  username: string;
  password: string;
  mobileNumber: string;
};

type ApiUser = {
  id: number;
  full_name: string;
  email: string;
  username: string;
  role: Role;
  mobile_number: string;
  email_verified: boolean;
  platform_connected?: boolean | null;
  platform_status?: 'verified' | 'pending' | 'none' | null;
  email_notifications_enabled?: boolean;
  avatar_url?: string | null;
};

export const mapUser = (u: ApiUser): User => ({
  id: String(u.id),
  role: u.role,
  fullName: u.full_name,
  email: u.email,
  username: u.username,
  mobile: u.mobile_number || undefined,
  avatarUrl: resolveAssetUrl(u.avatar_url),
  emailVerified: u.email_verified,
  platformConnected: u.platform_connected,
  platformStatus: u.platform_status,
  emailNotificationsEnabled: u.email_notifications_enabled,
});

export async function login(input: LoginInput) {
  const data = await request<{ access: string; user: ApiUser }>('auth/login/', {
    method: 'POST',
    body: { identifier: input.identifier, password: input.password },
    anonymous: true,
  });
  return { access: data.access, user: mapUser(data.user) };
}

export async function register(input: RegisterInput) {
  const data = await request<ApiUser>('auth/register/', {
    method: 'POST',
    body: {
      role: input.role,
      full_name: input.fullName,
      email: input.email,
      username: input.username,
      password: input.password,
      mobile_number: input.mobileNumber,
    },
    anonymous: true,
  });
  return mapUser(data);
}

export async function logout(session?: 'user' | 'admin') {
  await request('auth/logout/', { method: 'POST', session });
}

export async function fetchMe(): Promise<User> {
  const data = await request<ApiUser>('auth/me/');
  return mapUser(data);
}

/** Same endpoint, but for the admin session (its token is kept apart from the user one). */
export async function fetchAdminMe(): Promise<User> {
  const data = await request<ApiUser>('auth/me/', { session: 'admin' });
  return mapUser(data);
}

export async function requestPasswordReset(email: string) {
  return request<{ detail: string }>('auth/password-reset/request/', {
    method: 'POST',
    body: { email },
    anonymous: true,
  });
}

export async function confirmPasswordReset(input: { email: string; code: string; newPassword: string }) {
  return request<{ detail: string }>('auth/password-reset/confirm/', {
    method: 'POST',
    body: { email: input.email, code: input.code, new_password: input.newPassword },
    anonymous: true,
  });
}

// ----- Niche / platform mapping --------------------------------------------

/** The backend's Niche choices (apps/core/choices.py), lowercase on the wire. */
export const NICHE_LABELS: Record<string, Niche> = {
  fitness: 'Fitness',
  tech: 'Tech',
  beauty: 'Beauty',
  food: 'Food',
  travel: 'Travel',
  other: 'Other',
};

export const NICHE_OPTIONS: Niche[] = [...NICHES];

/** Backend platforms already use the labels the UI shows. */
export const PLATFORM_LABELS: Record<string, Platform> = {
  youtube: 'YouTube',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  facebook: 'Facebook',
};

export const PLATFORM_OPTIONS: Platform[] = ['YouTube', 'Instagram', 'TikTok', 'Facebook'];

const labelToNiche = (label: string): Niche | undefined =>
  (Object.values(NICHE_LABELS) as string[]).includes(label) ? (label as Niche) : undefined;

export const nicheFromBackend = (v: string | null | undefined): Niche =>
  (v && NICHE_LABELS[v]) || 'Other';

export const platformFromBackend = (v: string | null | undefined): Platform =>
  (v && PLATFORM_LABELS[v]) || 'YouTube';

/** A creator's own choice: empty when they have not chosen yet (not "Other" / "YouTube"). */
export const nicheOrEmpty = (v: string | null | undefined): Niche | '' => (v && NICHE_LABELS[v]) || '';
export const platformOrEmpty = (v: string | null | undefined): Platform | '' => (v && PLATFORM_LABELS[v]) || '';

export const platformToBackend = (p: Platform): string => p.toLowerCase();

/** Backend uses one of the canonical Platform enum values. The UI select lets
 *  the user pick a label and we send the lowercase form back. */
export const nicheToBackend = (n: Niche): string => {
  for (const [k, v] of Object.entries(NICHE_LABELS)) {
    if (v === n) return k;
  }
  return 'other';
};

// ----- Creator profile (me) ------------------------------------------------

type ApiCreatorMe = {
  id: number;
  username: string;
  full_name: string;
  photo_url: string | null;
  bio: string;
  niche: string | null;
  primary_platform: string | null;
  city: string;
  country: string;
  rate_post: string | null;
  rate_story: string | null;
  rate_video: string | null;
  rating_avg: string | null;
  rating_count: number;
  completion_percent: number;
  /** The creator is Verified: a confirmed email AND YouTube with enough subscribers. Decided by the server. */
  is_verified?: boolean;
  stats: Array<{
    platform: string;
    handle_url: string | null;
    followers: number | null;
    engagement_rate: string | null;
    is_verified: boolean;
    review_status?: 'pending' | 'approved' | 'rejected';
    review_note?: string;
    is_outdated: boolean;
    last_synced_at: string | null;
  }>;
};

const numFrom = (v: string | null | undefined): number => {
  if (v === null || v === undefined || v === '') return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

export const mapCreatorMe = (p: ApiCreatorMe): CreatorProfile => {
  const yt = p.stats.find((s) => s.platform === 'youtube');
  // The headline numbers are the primary platform's (as in the creator directory); YouTube if there are none.
  // Typed Instagram/TikTok/Facebook numbers count here only once an admin approved them, as brands see them.
  const isPublic = (s: { platform: string; is_verified: boolean }) => s.platform === 'youtube' || s.is_verified;
  const primary = p.stats.find((s) => s.platform === p.primary_platform && isPublic(s)) ?? yt;
  const followers = primary?.followers ?? 0;
  const engagement = primary ? numFrom(primary.engagement_rate) : 0;
  return {
    id: String(p.id),
    fullName: p.full_name,
    avatarUrl: resolveAssetUrl(p.photo_url),
    coverUrl: undefined,
    bio: p.bio,
    niche: nicheOrEmpty(p.niche),
    primaryPlatform: platformOrEmpty(p.primary_platform),
    location: [p.city, p.country].filter(Boolean).join(', '),
    city: p.city,
    country: p.country,
    stats: p.stats.map((s) => ({
      platform: platformFromBackend(s.platform),
      handleUrl: s.handle_url ?? undefined,
      followers: s.followers ?? 0,
      engagementRate: numFrom(s.engagement_rate),
      isVerified: s.is_verified,
      reviewStatus: s.review_status ?? 'approved',
      reviewNote: s.review_note || undefined,
      lastSyncedAt: s.last_synced_at ?? undefined,
      isOutdated: s.is_outdated,
    })),
    ratePerPost: numFrom(p.rate_post),
    ratePerStory: numFrom(p.rate_story),
    ratePerVideo: numFrom(p.rate_video),
    followers,
    engagementRate: engagement,
    verified: !!p.is_verified,
    portfolio: [],
    // Best-effort: the verified flag is the YouTube verified status. The
    // dashboard reads it via the separate /social/youtube/ endpoint for the
    // more accurate "needs reconnect" / "expired" flags.
    connectedAccount: yt
      ? {
          id: 'yt',
          platform: 'YouTube',
          handle: youtubeHandle(yt.handle_url),
          url: yt.handle_url ?? undefined,
          verified: yt.is_verified,
          lastSyncedAt: yt.last_synced_at ?? new Date().toISOString(),
          status: 'connected',
        }
      : undefined,
    ratingAvg: p.rating_avg !== null ? numFrom(p.rating_avg) : null,
    ratingCount: p.rating_count ?? 0,
  };
};

export const fetchCreatorMe = async (): Promise<CreatorProfile> => {
  const data = await request<ApiCreatorMe>('creators/me/');
  return mapCreatorMe(data);
};

const imageForm = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return form;
};

/** Upload (replace) the creator's profile photo. Returns the updated profile. */
export const uploadCreatorPhoto = async (file: File): Promise<CreatorProfile> =>
  mapCreatorMe(
    await request<ApiCreatorMe>('creators/me/photo/', { method: 'PUT', formData: imageForm(file), timeoutMs: 60_000 }),
  );

export const deleteCreatorPhoto = async (): Promise<CreatorProfile> =>
  mapCreatorMe(await request<ApiCreatorMe>('creators/me/photo/', { method: 'DELETE' }));

/** A rate of 0 (or nothing) means "not set": send null so the server keeps it empty instead of storing $0. */
const rateToBackend = (n: number): string | null => (n > 0 ? String(n) : null);

export const updateCreatorMe = async (patch: Partial<{
  fullName: string;
  bio: string;
  /** '' means the creator has not chosen one: it is saved as empty. */
  niche: Niche | '';
  primaryPlatform: Platform | '';
  city: string;
  country: string;
  ratePerPost: number;
  ratePerStory: number;
  ratePerVideo: number;
}>): Promise<CreatorProfile> => {
  const body: Record<string, unknown> = {};
  if (patch.fullName !== undefined) body.full_name = patch.fullName;
  if (patch.bio !== undefined) body.bio = patch.bio;
  if (patch.niche !== undefined) body.niche = patch.niche === '' ? null : nicheToBackend(patch.niche);
  if (patch.primaryPlatform !== undefined) {
    body.primary_platform = patch.primaryPlatform === '' ? null : platformToBackend(patch.primaryPlatform);
  }
  if (patch.city !== undefined) body.city = patch.city;
  if (patch.country !== undefined) body.country = patch.country;
  if (patch.ratePerPost !== undefined) body.rate_post = rateToBackend(patch.ratePerPost);
  if (patch.ratePerStory !== undefined) body.rate_story = rateToBackend(patch.ratePerStory);
  if (patch.ratePerVideo !== undefined) body.rate_video = rateToBackend(patch.ratePerVideo);
  const data = await request<ApiCreatorMe>('creators/me/', { method: 'PATCH', body });
  return mapCreatorMe(data);
};

// ----- Portfolio ------------------------------------------------------------

export const fetchPortfolio = async (): Promise<PortfolioLink[]> => {
  const data = await request<Array<{ id: number; url: string; caption: string; source: string; created_at: string }>>(
    'creators/me/portfolio/',
  );
  return data.map((p) => ({ id: String(p.id), url: p.url, title: p.caption || undefined }));
};

export const addPortfolioItem = async (input: { url: string; caption?: string }): Promise<PortfolioLink> => {
  const data = await request<{ id: number; url: string; caption: string }>('creators/me/portfolio/', {
    method: 'POST',
    body: { url: input.url, caption: input.caption ?? '' },
  });
  return { id: String(data.id), url: data.url, title: data.caption || undefined };
};

export const deletePortfolioItem = async (id: string | number) => {
  await request(`creators/me/portfolio/${id}/`, { method: 'DELETE' });
};

// ----- Brand profile --------------------------------------------------------

type ApiBrandMe = {
  id: number;
  display_name: string;
  company_name: string;
  industry: string;
  website: string | null;
  logo_url: string | null;
  about: string;
};

export const mapBrandMe = (p: ApiBrandMe): BrandProfile => ({
  id: String(p.id),
  companyName: p.company_name || p.display_name,
  industry: p.industry,
  website: p.website ?? '',
  logoUrl: resolveAssetUrl(p.logo_url),
  coverUrl: undefined,
  about: p.about,
});

export const fetchBrandMe = async (): Promise<BrandProfile> => {
  const data = await request<ApiBrandMe>('brands/me/');
  return mapBrandMe(data);
};

/** Upload (replace) the brand's logo. Returns the updated company profile. */
export const uploadBrandLogo = async (file: File): Promise<BrandProfile> =>
  mapBrandMe(
    await request<ApiBrandMe>('brands/me/logo/', { method: 'PUT', formData: imageForm(file), timeoutMs: 60_000 }),
  );

export const deleteBrandLogo = async (): Promise<BrandProfile> =>
  mapBrandMe(await request<ApiBrandMe>('brands/me/logo/', { method: 'DELETE' }));

export const updateBrandMe = async (patch: Partial<{
  companyName: string;
  industry: string;
  website: string;
  about: string;
}>): Promise<BrandProfile> => {
  const body: Record<string, unknown> = {};
  if (patch.companyName !== undefined) body.company_name = patch.companyName;
  if (patch.industry !== undefined) body.industry = patch.industry;
  if (patch.website !== undefined) body.website = patch.website;
  if (patch.about !== undefined) body.about = patch.about;
  const data = await request<ApiBrandMe>('brands/me/', { method: 'PATCH', body });
  return mapBrandMe(data);
};

// ----- Creator directory ----------------------------------------------------

type ApiCreatorCard = {
  id: number;
  name: string;
  photo_url: string | null;
  niche: string | null;
  primary_platform: string | null;
  followers: number | null;
  engagement_rate: string | null;
  is_verified: boolean;
  rating_avg: string | null;
  rating_count: number;
};

export const mapCreatorCard = (c: ApiCreatorCard): CreatorProfile => ({
  id: String(c.id),
  fullName: c.name,
  avatarUrl: resolveAssetUrl(c.photo_url),
  coverUrl: undefined,
  bio: '',
  niche: nicheOrEmpty(c.niche),
  primaryPlatform: platformOrEmpty(c.primary_platform),
  location: '',
  ratePerPost: 0,
  ratePerStory: 0,
  ratePerVideo: 0,
  followers: c.followers ?? 0,
  engagementRate: c.engagement_rate ? numFrom(c.engagement_rate) : 0,
  verified: c.is_verified,
  portfolio: [],
  ratingAvg: c.rating_avg !== null && c.rating_avg !== undefined ? numFrom(c.rating_avg) : null,
  ratingCount: c.rating_count ?? 0,
});

export type SearchCreatorsParams = {
  q?: string;
  niche?: string;
  platform?: string;
  location?: string;
  minFollowers?: number;
  maxFollowers?: number;
  minEngagement?: number;
  maxEngagement?: number;
  minRate?: number;
  maxRate?: number;
  /** 0 to 5: only creators whose average rating is at least this. */
  minRating?: number;
  verifiedOnly?: boolean;
  /** One of: followers, -followers, engagement, -engagement, rate, -rate, rating, -rating. */
  ordering?: string;
};

// ----- Paged lists ----------------------------------------------------------

type ListQuery = Record<string, string | number | boolean | undefined | null>;

/** Backend page size ceiling (apps/core/pagination.py). */
const PAGE_SIZE = 50;
/** Stop after this many pages (500 items) so a runaway list cannot hammer the API. */
const MAX_PAGES = 10;

/**
 * Fetches every page of a list endpoint and returns the rows together with the extra
 * top-level fields of the first page (e.g. `unread_count`, `accepted_count`). The backend
 * returns `{count, next, previous, results}`, capped at 50 rows per page, so reading only the
 * first response would silently drop the rest. Endpoints that return a bare array are passed
 * through unchanged.
 */
async function fetchPages<T, Extra extends object = Record<string, never>>(
  path: string,
  query: ListQuery = {},
): Promise<{ items: T[]; extra: Extra }> {
  type Paged = { results: T[]; next?: string | null; count?: number; previous?: string | null } & Extra;
  let items: T[] = [];
  let extra = {} as Extra;
  for (let page = 1; page <= MAX_PAGES; page++) {
    const data = await request<T[] | Paged>(path, { query: { ...query, page, page_size: PAGE_SIZE } });
    if (Array.isArray(data)) return { items: data, extra };
    if (page === 1) {
      const { results: _r, next: _n, count: _c, previous: _p, ...rest } = data;
      extra = rest as unknown as Extra;
    }
    items = items.concat(data.results ?? []);
    if (!data.next) break;
  }
  return { items, extra };
}

/** One page of creator search results, with the total so the screen can offer Previous / Next. */
export type CreatorPage = { items: CreatorProfile[]; total: number; page: number; pageSize: number };

export const searchCreatorsPage = async (
  p: SearchCreatorsParams = {},
  page = 1,
  pageSize = 12,
): Promise<CreatorPage> => {
  const query: Record<string, string | number> = { page, page_size: pageSize };
  if (p.q) query.q = p.q;
  if (p.niche) query.niche = nicheToBackend(labelToNiche(p.niche) ?? ('Other' as Niche));
  if (p.platform) query.platform = platformToBackend(p.platform as Platform);
  if (p.location) query.location = p.location;
  if (p.minFollowers !== undefined) query.min_followers = p.minFollowers;
  if (p.maxFollowers !== undefined) query.max_followers = p.maxFollowers;
  if (p.minEngagement !== undefined) query.min_engagement = p.minEngagement;
  if (p.maxEngagement !== undefined) query.max_engagement = p.maxEngagement;
  if (p.minRate !== undefined) query.min_rate = p.minRate;
  if (p.maxRate !== undefined) query.max_rate = p.maxRate;
  if (p.minRating !== undefined) query.min_rating = p.minRating;
  if (p.verifiedOnly) query.verified_only = 'true';
  if (p.ordering) query.ordering = p.ordering;
  const data = await request<{ count: number; results: ApiCreatorCard[] }>('creators/', { query });
  return { items: data.results.map(mapCreatorCard), total: data.count, page, pageSize };
};

/** What a brand sees of a creator: the same fields as the creator's own profile, plus the portfolio items. */
type ApiCreatorDetail = ApiCreatorMe & {
  portfolio?: Array<{ id: number; url: string; caption: string }>;
};

export const fetchCreatorDetail = async (id: string | number): Promise<CreatorProfile> => {
  const data = await request<ApiCreatorDetail>(`creators/${id}/`);
  return {
    ...mapCreatorMe(data),
    // mapCreatorMe is built for the creator's own screen, where the portfolio is loaded separately.
    portfolio: (data.portfolio ?? []).map((p) => ({ id: String(p.id), url: p.url, title: p.caption || undefined })),
  };
};

// ----- Brand detail ---------------------------------------------------------

export const fetchBrandDetail = async (id: string | number): Promise<BrandProfile> => {
  const data = await request<ApiBrandMe>(`brands/${id}/`);
  return mapBrandMe(data);
};

// ----- Campaigns ------------------------------------------------------------

type ApiCampaign = {
  id: number;
  title: string;
  description: string;
  niche: string;
  platform: string;
  budget: string;
  deadline: string;
  deliverables: string;
  creators_needed: number;
  min_followers: number | null;
  allow_withdrawal?: boolean;
  status: CampaignStatus;
  published_at: string | null;
  closed_at: string | null;
  created_at: string;
  media?: ApiMedia[];
};

type ApiMedia = { id: number; kind: 'photo' | 'video'; url: string; size: number };

const mapMedia = (m: ApiMedia): CampaignMedia => ({
  id: String(m.id),
  kind: m.kind,
  url: m.url,
  size: m.size,
});

type ApiCampaignCard = {
  id: number;
  title: string;
  brand: { id: number; name: string; logo_url: string | null };
  niche: string;
  budget: string;
  platform: string;
  deadline: string;
  creators_needed: number;
  eligible: boolean;
};

type ApiCampaignDetail = ApiCampaignCard & {
  description: string;
  deliverables: string;
  min_followers: number | null;
  allow_withdrawal?: boolean;
  status: CampaignStatus;
  accepted_count: number;
  all_creators_selected: boolean;
  can_apply: boolean;
  apply_blocked_reason: string | null;
  media?: ApiMedia[];
};

export const mapCampaignCard = (c: ApiCampaignCard): Campaign => ({
  id: String(c.id),
  brandId: String(c.brand.id),
  brandName: c.brand.name,
  brandLogoUrl: resolveAssetUrl(c.brand.logo_url),
  title: c.title,
  description: '',
  category: nicheFromBackend(c.niche),
  requiredPlatform: platformFromBackend(c.platform),
  budgetPerCreator: numFrom(c.budget),
  applicationDeadline: c.deadline,
  deliverables: '',
  creatorsNeeded: c.creators_needed,
  minFollowers: undefined,
  eligible: c.eligible,
  // Creator-facing listings only ever contain published campaigns.
  status: 'published',
});

export const mapCampaignDetail = (c: ApiCampaignDetail): Campaign => ({
  ...mapCampaignCard(c),
  description: c.description,
  deliverables: c.deliverables,
  minFollowers: c.min_followers ?? undefined,
  allowWithdrawal: c.allow_withdrawal !== false,
  status: c.status,
  media: (c.media ?? []).map(mapMedia),
});

export const mapBrandCampaign = (c: ApiCampaign): Campaign => ({
  id: String(c.id),
  brandId: '',
  brandName: '',
  title: c.title,
  description: c.description,
  category: nicheFromBackend(c.niche),
  requiredPlatform: platformFromBackend(c.platform),
  budgetPerCreator: numFrom(c.budget),
  applicationDeadline: c.deadline,
  deliverables: c.deliverables,
  creatorsNeeded: c.creators_needed,
  minFollowers: c.min_followers ?? undefined,
  allowWithdrawal: c.allow_withdrawal !== false,
  status: c.status,
  createdAt: c.created_at,
  media: (c.media ?? []).map(mapMedia),
});

export type CampaignListParams = { status?: CampaignStatus };

export const listBrandCampaigns = async (p: CampaignListParams = {}): Promise<Campaign[]> => {
  const query: Record<string, string> = {};
  if (p.status) query.status = p.status;
  const { items } = await fetchPages<ApiCampaign>('brand/campaigns/', query);
  return items.map(mapBrandCampaign);
};

export const listCreatorCampaigns = async (filters: {
  q?: string;
  niche?: Niche;
  platform?: Platform;
  minBudget?: number;
  maxBudget?: number;
  deadlineBefore?: string;
} = {}): Promise<Campaign[]> => {
  const query: Record<string, string | number> = {};
  if (filters.q) query.q = filters.q; // the server reads "q"; any other name is silently ignored
  if (filters.niche) query.niche = nicheToBackend(filters.niche);
  if (filters.platform) query.platform = platformToBackend(filters.platform);
  if (filters.minBudget) query.min_budget = filters.minBudget;
  if (filters.maxBudget) query.max_budget = filters.maxBudget;
  if (filters.deadlineBefore) query.deadline_before = filters.deadlineBefore;
  const { items } = await fetchPages<ApiCampaignCard>('campaigns/', query);
  return items.map(mapCampaignCard);
};

export const fetchCreatorCampaign = async (id: string | number): Promise<{
  campaign: Campaign;
  acceptedCount: number;
  allSelected: boolean;
  /** Server's hint that the creator's stats fit the brief; it never blocks applying. */
  eligible: boolean;
  canApply: boolean;
  applyBlockedReason: string | null;
}> => {
  const data = await request<ApiCampaignDetail>(`campaigns/${id}/`);
  return {
    campaign: mapCampaignDetail(data),
    acceptedCount: data.accepted_count,
    allSelected: data.all_creators_selected,
    eligible: data.eligible,
    canApply: data.can_apply,
    applyBlockedReason: data.apply_blocked_reason,
  };
};

export const fetchBrandCampaign = async (id: string | number): Promise<Campaign> => {
  const data = await request<ApiCampaign>('brand/campaigns/' + id + '/');
  return mapBrandCampaign(data);
};

export type CreateCampaignInput = {
  title: string;
  description: string;
  niche: Niche;
  platform: Platform;
  budget: number;
  deadline: string; // ISO
  deliverables: string;
  creatorsNeeded: number;
  minFollowers?: number;
  allowWithdrawal?: boolean;
};

export const createCampaign = async (input: CreateCampaignInput): Promise<Campaign> => {
  const body: Record<string, unknown> = {
    title: input.title,
    description: input.description,
    niche: nicheToBackend(input.niche),
    platform: platformToBackend(input.platform),
    budget: input.budget,
    deadline: input.deadline,
    deliverables: input.deliverables,
    creators_needed: input.creatorsNeeded,
  };
  if (input.minFollowers !== undefined) body.min_followers = input.minFollowers;
  if (input.allowWithdrawal !== undefined) body.allow_withdrawal = input.allowWithdrawal;
  const data = await request<ApiCampaign>('brand/campaigns/', { method: 'POST', body });
  return mapBrandCampaign(data);
};

export const updateCampaign = async (
  id: string | number,
  patch: Partial<CreateCampaignInput>,
): Promise<Campaign> => {
  const body: Record<string, unknown> = {};
  if (patch.title !== undefined) body.title = patch.title;
  if (patch.description !== undefined) body.description = patch.description;
  if (patch.niche !== undefined) body.niche = nicheToBackend(patch.niche);
  if (patch.platform !== undefined) body.platform = platformToBackend(patch.platform);
  if (patch.budget !== undefined) body.budget = patch.budget;
  if (patch.deadline !== undefined) body.deadline = patch.deadline;
  if (patch.deliverables !== undefined) body.deliverables = patch.deliverables;
  if (patch.creatorsNeeded !== undefined) body.creators_needed = patch.creatorsNeeded;
  if (patch.minFollowers !== undefined) body.min_followers = patch.minFollowers;
  if (patch.allowWithdrawal !== undefined) body.allow_withdrawal = patch.allowWithdrawal;
  const data = await request<ApiCampaign>('brand/campaigns/' + id + '/', { method: 'PATCH', body });
  return mapBrandCampaign(data);
};

export const deleteCampaign = async (id: string | number) => {
  await request('brand/campaigns/' + id + '/', { method: 'DELETE' });
};

/** Attach a photo or video to a draft campaign (2 photos, or 1 video). Uploads get a longer timeout. */
export const uploadCampaignMedia = async (campaignId: string | number, file: File): Promise<CampaignMedia> => {
  const form = new FormData();
  form.append('file', file);
  const data = await request<ApiMedia>('brand/campaigns/' + campaignId + '/media/', {
    method: 'POST',
    formData: form,
    timeoutMs: 120_000,
  });
  return mapMedia(data);
};

export const deleteCampaignMedia = async (campaignId: string | number, mediaId: string | number) => {
  await request('brand/campaigns/' + campaignId + '/media/' + mediaId + '/', { method: 'DELETE' });
};

export const publishCampaign = async (id: string | number): Promise<Campaign> => {
  const data = await request<ApiCampaign>('brand/campaigns/' + id + '/publish/', { method: 'POST' });
  return mapBrandCampaign(data);
};

export const closeCampaign = async (id: string | number): Promise<Campaign> => {
  const data = await request<ApiCampaign>('brand/campaigns/' + id + '/close/', { method: 'POST' });
  return mapBrandCampaign(data);
};

// ----- Proposals ------------------------------------------------------------

type ApiProposal = {
  id: number;
  campaign_id: number;
  status: ProposalStatus;
  proposed_rate: string;
  cover_message: string;
  portfolio_links: string[];
  experience_note: string;
  withdrawal_reason: string | null;
  completed_at: string | null;
  created_at: string;
};

type ApiBrandProposal = {
  id: number;
  creator: {
    id: number;
    name: string;
    niche: string | null;
    platform: string | null;
    followers: number | null;
    engagement_rate: string | null;
    is_verified: boolean;
    rating_avg: string | null;
    rating_count: number;
  };
  proposed_rate: string;
  cover_message: string;
  portfolio_links: string[];
  experience_note: string;
  status: ProposalStatus;
  withdrawal_reason: string | null;
  profile_url: string;
  completed_at: string | null;
  review?: { id: number; rating: number; text: string; created_at: string } | null;
  created_at: string;
};

type ApiMyProposal = {
  id: number;
  status: ProposalStatus;
  proposed_rate: string;
  created_at: string;
  completed_at: string | null;
  withdrawal_reason: string | null;
  campaign: {
    id: number;
    title: string;
    status: CampaignStatus;
    allow_withdrawal?: boolean;
    brand: { id: number; name: string };
  };
};

const proposalPortfolioFrom = (links: string[]): PortfolioLink[] =>
  links.map((url, i) => ({ id: 'p' + i, url, title: undefined }));

const proposalPortfolioTo = (links: PortfolioLink[]): string[] =>
  links.map((l) => l.url).filter(Boolean);

export const mapMyProposal = (p: ApiMyProposal): MyProposal => ({
  id: String(p.id),
  campaignId: String(p.campaign.id),
  creatorId: '',
  creatorName: '',
  creatorNiche: 'Other',
  creatorPlatform: 'YouTube',
  creatorFollowers: 0,
  creatorEngagement: 0,
  coverMessage: '',
  proposedRate: numFrom(p.proposed_rate),
  portfolio: [],
  relevantExperience: '',
  status: p.status,
  submittedAt: p.created_at,
  withdrawReason: p.withdrawal_reason ?? undefined,
  completedAt: p.completed_at ?? undefined,
  campaignTitle: p.campaign.title,
  brandName: p.campaign.brand.name,
  brandId: String(p.campaign.brand.id),
  campaignStatus: p.campaign.status,
  allowWithdrawal: p.campaign.allow_withdrawal !== false,
});

export const mapBrandProposal = (p: ApiBrandProposal): Proposal => ({
  id: String(p.id),
  campaignId: '',
  creatorId: String(p.creator.id),
  creatorName: p.creator.name,
  creatorNiche: nicheFromBackend(p.creator.niche),
  creatorPlatform: platformFromBackend(p.creator.platform),
  creatorFollowers: p.creator.followers ?? 0,
  creatorEngagement: p.creator.engagement_rate ? numFrom(p.creator.engagement_rate) : 0,
  creatorRatingAvg: p.creator.rating_avg !== null && p.creator.rating_avg !== undefined ? numFrom(p.creator.rating_avg) : null,
  creatorRatingCount: p.creator.rating_count ?? 0,
  review: p.review ? { id: p.review.id, rating: p.review.rating, text: p.review.text } : null,
  coverMessage: p.cover_message,
  proposedRate: numFrom(p.proposed_rate),
  portfolio: proposalPortfolioFrom(p.portfolio_links ?? []),
  relevantExperience: p.experience_note ?? '',
  status: p.status,
  submittedAt: p.created_at,
  withdrawReason: p.withdrawal_reason ?? undefined,
  completedAt: p.completed_at ?? undefined,
});

export const listMyProposals = async (filter?: { status?: ProposalStatus }): Promise<MyProposal[]> => {
  const query: Record<string, string> = {};
  if (filter?.status) query.status = filter.status;
  const { items } = await fetchPages<ApiMyProposal>('creators/me/proposals/', query);
  return items.map(mapMyProposal);
};

export const listBrandCampaignProposals = async (
  campaignId: string | number,
  filter?: { status?: ProposalStatus },
): Promise<{ results: Proposal[]; acceptedCount: number; creatorsNeeded: number }> => {
  const query: Record<string, string> = {};
  if (filter?.status) query.status = filter.status;
  const { items, extra } = await fetchPages<
    ApiBrandProposal,
    { accepted_count: number; creators_needed: number }
  >('brand/campaigns/' + campaignId + '/proposals/', query);
  return {
    // The server does not repeat the campaign on each proposal, but the caller asked for this campaign's list,
    // so every proposal belongs to it. Without this the id was blank and later requests for it got a 404.
    results: items.map((p) => ({ ...mapBrandProposal(p), campaignId: String(campaignId) })),
    acceptedCount: extra.accepted_count,
    creatorsNeeded: extra.creators_needed,
  };
};

export const submitProposal = async (input: {
  campaignId: string | number;
  coverMessage: string;
  portfolioLinks: PortfolioLink[];
  experienceNote: string;
}): Promise<Proposal> => {
  const data = await request<ApiProposal>('campaigns/' + input.campaignId + '/proposals/', {
    method: 'POST',
    body: {
      cover_message: input.coverMessage,
      portfolio_links: proposalPortfolioTo(input.portfolioLinks),
      experience_note: input.experienceNote,
    },
  });
  return mapMyProposal({
    id: data.id,
    status: data.status,
    proposed_rate: data.proposed_rate,
    created_at: data.created_at,
    completed_at: data.completed_at,
    withdrawal_reason: data.withdrawal_reason,
    campaign: { id: data.campaign_id, title: '', status: 'published', brand: { id: 0, name: '' } },
  });
};

export const withdrawProposal = async (id: string | number, reason?: string): Promise<void> => {
  await request('creators/me/proposals/' + id + '/withdraw/', {
    method: 'POST',
    body: { reason: reason ?? '' },
  });
};

export const shortlistProposal = async (id: string | number) =>
  request<{ id: number; status: ProposalStatus; accepted_count: number; creators_needed: number }>(
    'brand/proposals/' + id + '/shortlist/',
    { method: 'POST' },
  );

export const acceptProposal = async (id: string | number) =>
  request<{ id: number; status: ProposalStatus; accepted_count: number; creators_needed: number }>(
    'brand/proposals/' + id + '/accept/',
    { method: 'POST' },
  );

export const rejectProposal = async (id: string | number) =>
  request<{ id: number; status: ProposalStatus; accepted_count: number; creators_needed: number }>(
    'brand/proposals/' + id + '/reject/',
    { method: 'POST' },
  );

// ----- Notifications --------------------------------------------------------

type ApiNotification = {
  id: number;
  kind: string;
  message: string;
  payload: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string;
};

const NOTIF_KIND_TO_UI: Record<string, AppNotification['type']> = {
  proposal_shortlisted: 'proposal_shortlisted',
  proposal_accepted: 'proposal_accepted',
  proposal_rejected: 'proposal_rejected',
  proposal_received: 'proposal_received',
  proposal_withdrawn: 'proposal_withdrawn',
  account_reconnect: 'account_reconnect',
  slot_opened: 'slot_opened',
  campaign_closed: 'campaign_closed',
  // The backend's name for a campaign closed by its deadline.
  campaign_auto_closed: 'campaign_closed',
};

/**
 * The backend reports "a creator withdrew an accepted proposal" as `proposal_withdrawn` with a
 * `slot_opened` flag in the payload. Show that as its own kind so it gets the "Slot opened" title.
 */
const effectiveKind = (kind: string, payload: Record<string, unknown> | null): string =>
  kind === 'proposal_withdrawn' && payload?.slot_opened === true ? 'slot_opened' : kind;

const kindToTitle = (kind: string): string => {
  const map: Record<string, string> = {
    proposal_shortlisted: 'You were shortlisted',
    proposal_accepted: 'Proposal accepted',
    proposal_rejected: 'Proposal rejected',
    proposal_received: 'New proposal received',
    proposal_withdrawn: 'A creator withdrew',
    account_reconnect: 'Reconnect your account',
    slot_opened: 'Slot opened',
    campaign_closed: 'Campaign closed',
    campaign_auto_closed: 'Campaign closed',
  };
  return map[kind] ?? 'Update';
};

/**
 * Where a notification leads. Brand notifications carry a `campaign_id` (and a `proposal_id`, which
 * is NOT a campaign), so they must link by the campaign; creator notifications link by the proposal.
 */
const kindToLink = (kind: string, payload: Record<string, unknown> | null): string | undefined => {
  const campaignId = payload?.campaign_id;
  const proposalId = payload?.proposal_id;
  if (kind === 'proposal_received' || kind === 'proposal_withdrawn' || kind === 'slot_opened') {
    return campaignId ? `/brand/campaigns/${campaignId}/proposals` : '/brand/campaigns';
  }
  if (kind === 'campaign_closed' || kind === 'campaign_auto_closed') {
    return campaignId ? `/brand/campaigns/${campaignId}` : '/brand/campaigns';
  }
  if (kind === 'proposal_shortlisted' || kind === 'proposal_accepted' || kind === 'proposal_rejected') {
    return proposalId ? `/creator/applications/${proposalId}` : '/creator/applications';
  }
  if (kind === 'account_reconnect') return '/creator/accounts';
  return undefined;
};

export const mapNotification = (n: ApiNotification): AppNotification => {
  const kind = effectiveKind(n.kind, n.payload);
  return {
    id: String(n.id),
    type: NOTIF_KIND_TO_UI[kind] ?? 'proposal_received',
    title: kindToTitle(kind),
    description: n.message,
    createdAt: n.created_at,
    read: n.is_read,
    link: kindToLink(kind, n.payload),
  };
};

export const listNotifications = async (): Promise<{
  results: AppNotification[];
  unreadCount: number;
}> => {
  const { items, extra } = await fetchPages<ApiNotification, { unread_count: number }>('notifications/');
  return {
    results: items.map(mapNotification),
    unreadCount: extra.unread_count,
  };
};

export const markNotificationRead = async (id: string | number) => {
  const data = await request<ApiNotification>('notifications/' + id + '/read/', { method: 'POST' });
  return mapNotification(data);
};

export const markAllNotificationsRead = async (): Promise<number> => {
  const data = await request<{ marked_read: number }>('notifications/read-all/', { method: 'POST' });
  return data.marked_read;
};

// ----- YouTube connection ---------------------------------------------------

export type YouTubeStatus = {
  connected: boolean;
  status: ConnectedAccount['status'] | null;
  needsReconnect: boolean;
  connectedAt: string | null;
  lastSyncedAt: string | null;
  /** Why the last sync could not verify the channel, e.g. 'subscribers_hidden' or 'no_channel'. */
  lastError: string | null;
  /** Subscribers at the last sync, the number needed to be Verified, and whether the channel is under it. */
  followers: number | null;
  minimumFollowers: number;
  belowMinimum: boolean;
};

export const fetchYouTubeStatus = async (): Promise<YouTubeStatus> => {
  const data = await request<{
    connected: boolean;
    status: string | null;
    needs_reconnect: boolean;
    connected_at: string | null;
    last_synced_at: string | null;
    last_error?: string | null;
    followers?: number | null;
    minimum_followers?: number;
    below_minimum?: boolean;
  }>('social/youtube/');
  return {
    connected: data.connected,
    status: (data.status as ConnectedAccount['status']) ?? null,
    needsReconnect: data.needs_reconnect,
    connectedAt: data.connected_at,
    lastSyncedAt: data.last_synced_at,
    lastError: data.last_error ?? null,
    followers: data.followers ?? null,
    minimumFollowers: data.minimum_followers ?? 1000,
    belowMinimum: data.below_minimum ?? false,
  };
};

/**
 * Instagram, TikTok and Facebook cannot be connected automatically, so a creator types their numbers.
 * They are always saved as Unverified. The link is optional.
 */
export type ManualStatsInput = { handleUrl: string; followers: number; engagementRate: number };

export const saveManualStats = async (platform: Platform, input: ManualStatsInput): Promise<void> => {
  await request(`creators/me/stats/${platformToBackend(platform)}/`, {
    method: 'PUT',
    body: {
      handle_url: input.handleUrl.trim() || null,
      followers: input.followers,
      engagement_rate: String(input.engagementRate),
    },
  });
};

export const removeManualStats = async (platform: Platform): Promise<void> => {
  await request(`creators/me/stats/${platformToBackend(platform)}/`, { method: 'DELETE' });
};

export const startYouTubeConnect = async (): Promise<string> => {
  const data = await request<{ authorization_url: string }>('social/youtube/connect/');
  return data.authorization_url;
};

export const refreshYouTube = async () => {
  await request('social/youtube/refresh/', { method: 'POST' });
};

/** Last step of the connect flow: send back the `code` and `state` the callback redirect carried. */
export const completeYouTubeConnect = async (input: { code: string; state: string }) => {
  await request('social/youtube/complete/', {
    method: 'POST',
    body: { code: input.code, state: input.state },
  });
};

export const disconnectYouTube = async () => {
  await request('social/youtube/', { method: 'DELETE' });
};

// ----- Email verification + Notification Settings (FR-24) ------------------

export const verifyEmail = async (code: string) => {
  const data = await request<ApiUser>('auth/email/verify/', {
    method: 'POST',
    body: { code },
  });
  return mapUser(data);
};

export const resendVerificationEmail = async (): Promise<{ detail: string }> => {
  return request<{ detail: string }>('auth/email/resend/', { method: 'POST' });
};

export type NotificationSettings = {
  emailEnabled: boolean;
  emailVerified: boolean;
};

export const fetchNotificationSettings = async (): Promise<NotificationSettings> => {
  const data = await request<{ email_enabled: boolean; email_verified: boolean }>(
    'settings/notifications/',
  );
  return { emailEnabled: data.email_enabled, emailVerified: data.email_verified };
};

export const updateNotificationSettings = async (
  patch: { emailEnabled?: boolean },
): Promise<NotificationSettings> => {
  const body: Record<string, unknown> = {};
  if (patch.emailEnabled !== undefined) body.email_enabled = patch.emailEnabled;
  const data = await request<{ email_enabled: boolean; email_verified: boolean }>(
    'settings/notifications/',
    { method: 'PATCH', body },
  );
  return { emailEnabled: data.email_enabled, emailVerified: data.email_verified };
};

// ----- Dashboards (FR-17, FR-18) -------------------------------------------

export type CreatorDashboardData = {
  profileCompletion: number;
  youtube: {
    connected: boolean;
    status: ConnectedAccount['status'] | null;
    needsReconnect: boolean;
    lastSyncedAt: string | null;
    isOutdated: boolean;
    followers: number | null;
    minimumFollowers: number;
    belowMinimum: boolean;
  };
  availableCampaigns: Campaign[];
  /** Counts over every proposal (the `applications` list below is only the newest few). */
  pendingCount: number;
  shortlistedCount: number;
  applications: MyProposal[];
  acceptedCampaigns: MyProposal[];
  performance: { proposalsSent: number; accepted: number; acceptanceRate: number | null };
};

type ApiCreatorDashboard = {
  profile_completion: number;
  youtube: {
    connected: boolean;
    status: string | null;
    needs_reconnect: boolean;
    last_synced_at: string | null;
    is_outdated: boolean;
    followers?: number | null;
    minimum_followers?: number;
    below_minimum?: boolean;
  };
  available_campaigns: ApiCampaignCard[];
  pending_count?: number;
  shortlisted_count?: number;
  applications: ApiMyProposal[];
  accepted_campaigns: ApiMyProposal[];
  performance: { proposals_sent: number; accepted: number; acceptance_rate: number | null };
};

export const fetchCreatorDashboard = async (): Promise<CreatorDashboardData> => {
  const data = await request<ApiCreatorDashboard>('creators/me/dashboard/');
  return {
    profileCompletion: data.profile_completion,
    youtube: {
      connected: data.youtube.connected,
      status: (data.youtube.status as ConnectedAccount['status']) ?? null,
      needsReconnect: data.youtube.needs_reconnect,
      lastSyncedAt: data.youtube.last_synced_at,
      isOutdated: data.youtube.is_outdated,
      followers: data.youtube.followers ?? null,
      minimumFollowers: data.youtube.minimum_followers ?? 1000,
      belowMinimum: data.youtube.below_minimum ?? false,
    },
    availableCampaigns: data.available_campaigns.map(mapCampaignCard),
    pendingCount: data.pending_count ?? data.applications.filter((p) => p.status === 'pending').length,
    shortlistedCount: data.shortlisted_count ?? data.applications.filter((p) => p.status === 'shortlisted').length,
    applications: data.applications.map(mapMyProposal),
    acceptedCampaigns: data.accepted_campaigns.map(mapMyProposal),
    performance: {
      proposalsSent: data.performance.proposals_sent,
      accepted: data.performance.accepted,
      acceptanceRate: data.performance.acceptance_rate,
    },
  };
};

export type BrandDashboardData = {
  totalCampaigns: number;
  activeCampaigns: number;
  totalProposals: number;
  pendingCount: number;
  shortlistedCount: number;
  acceptedCount: number;
  /** Over every campaign, not just the listed ones. */
  draftCount: number;
  firstDraftId: number | null;
  busiestCampaign: { id: number; title: string; pendingCount: number } | null;
  campaigns: Array<{
    id: number;
    title: string;
    status: CampaignStatus;
    proposalsUrl: string;
    proposalCount: number;
    pendingCount: number;
    acceptedCount: number;
    creatorsNeeded: number;
  }>;
};

type ApiBrandDashboard = {
  total_campaigns: number;
  active_campaigns: number;
  total_proposals: number;
  pending_count?: number;
  shortlisted_count: number;
  accepted_count: number;
  draft_count?: number;
  first_draft_id?: number | null;
  busiest_campaign?: { id: number; title: string; pending_count: number } | null;
  campaigns: Array<{
    id: number;
    title: string;
    status: CampaignStatus;
    proposals_url: string;
    proposal_count: number;
    pending_count?: number;
    accepted_count: number;
    creators_needed: number;
  }>;
};

export const fetchBrandDashboard = async (): Promise<BrandDashboardData> => {
  const data = await request<ApiBrandDashboard>('brands/me/dashboard/');
  return {
    totalCampaigns: data.total_campaigns,
    activeCampaigns: data.active_campaigns,
    totalProposals: data.total_proposals,
    pendingCount: data.pending_count ?? 0,
    shortlistedCount: data.shortlisted_count,
    acceptedCount: data.accepted_count,
    draftCount: data.draft_count ?? data.campaigns.filter((c) => c.status === 'draft').length,
    firstDraftId: data.first_draft_id ?? data.campaigns.find((c) => c.status === 'draft')?.id ?? null,
    busiestCampaign: data.busiest_campaign
      ? { id: data.busiest_campaign.id, title: data.busiest_campaign.title, pendingCount: data.busiest_campaign.pending_count }
      : null,
    campaigns: data.campaigns.map((c) => ({
      id: c.id,
      title: c.title,
      status: c.status,
      proposalsUrl: c.proposals_url,
      proposalCount: c.proposal_count,
      pendingCount: c.pending_count ?? 0,
      acceptedCount: c.accepted_count,
      creatorsNeeded: c.creators_needed,
    })),
  };
};

// ----- Brand connected platforms ---------------------------------------------

export type BrandSocialPlatform = 'instagram' | 'tiktok' | 'facebook';

export type BrandSocialAccount = {
  platform: BrandSocialPlatform;
  handleUrl: string;
  /** A typed link an admin approved. */
  isVerified: boolean;
  /** A typed link waits for an admin ("pending"), then is "approved" or "rejected". */
  reviewStatus: 'pending' | 'approved' | 'rejected';
  reviewNote?: string;
  connectedAt: string;
};

type ApiBrandSocial = {
  platform: BrandSocialPlatform;
  handle_url: string;
  is_verified: boolean;
  review_status?: 'pending' | 'approved' | 'rejected';
  review_note?: string;
  connected_at: string;
};

const mapBrandSocial = (a: ApiBrandSocial): BrandSocialAccount => ({
  platform: a.platform,
  handleUrl: a.handle_url,
  isVerified: a.is_verified,
  reviewStatus: a.review_status ?? 'approved',
  reviewNote: a.review_note || undefined,
  connectedAt: a.connected_at,
});

export const fetchBrandSocial = async (): Promise<BrandSocialAccount[]> =>
  (await request<ApiBrandSocial[]>('brands/me/social/')).map(mapBrandSocial);

/** Save the link typed for Instagram, TikTok or Facebook. An admin checks it. YouTube does not verify a brand. */
export const saveBrandSocialLink = async (platform: BrandSocialPlatform, handleUrl: string): Promise<BrandSocialAccount> =>
  mapBrandSocial(
    await request<ApiBrandSocial>(`brands/me/social/${platform}/`, { method: 'PUT', body: { handle_url: handleUrl } }),
  );

export const removeBrandSocial = async (platform: BrandSocialPlatform): Promise<void> => {
  await request(`brands/me/social/${platform}/`, { method: 'DELETE' });
};

// ----- Campaign analytics (FR-23) ------------------------------------------

export type CampaignMetrics = {
  views: number;
  funnel: { received: number; shortlisted: number; accepted: number; rejected: number; withdrawn: number };
  acceptedVsNeeded: { accepted: number; needed: number };
  budgetPerCreator: number;
  acceptanceRate: number | null;
};

export const fetchCampaignAnalytics = async (id: number | string): Promise<CampaignMetrics> => {
  const data = await request<{
    views: number;
    funnel: { received: number; shortlisted: number; accepted: number; rejected: number; withdrawn: number };
    accepted_vs_needed: { accepted: number; needed: number };
    budget_per_creator: string;
    acceptance_rate: number | null;
  }>('brand/campaigns/' + id + '/analytics/');
  return {
    views: data.views,
    funnel: data.funnel,
    acceptedVsNeeded: data.accepted_vs_needed,
    budgetPerCreator: numFrom(data.budget_per_creator),
    acceptanceRate: data.acceptance_rate,
  };
};

/** A number from the platform, or "not_available" when it does not give it (or has not been fetched yet). */
export type Metric = number | 'not_available';

/** How one delivered post is doing. The numbers come from the last daily refresh, never from a live call. */
export type ContentPerformanceRow = {
  deliverableId: number;
  proposalId: number;
  creator: { id: number; name: string };
  platform: Platform;
  postUrl: string;
  views: Metric;
  likes: Metric;
  comments: Metric;
  /** (likes + comments) / views, as a percentage. */
  engagementRate: Metric;
  syncedAt: string | null;
};

export const fetchContentPerformance = async (id: number | string): Promise<ContentPerformanceRow[]> => {
  const data = await request<Array<{
    deliverable_id: number;
    proposal_id: number;
    creator: { id: number; name: string };
    platform: string;
    post_url: string;
    views: Metric;
    likes: Metric;
    comments: Metric;
    engagement_rate: string | 'not_available';
    synced_at: string | null;
  }>>('brand/campaigns/' + id + '/analytics/content/');
  return data.map((r) => ({
    deliverableId: r.deliverable_id,
    proposalId: r.proposal_id,
    creator: r.creator,
    platform: platformFromBackend(r.platform),
    postUrl: r.post_url,
    views: r.views,
    likes: r.likes,
    comments: r.comments,
    engagementRate: r.engagement_rate === 'not_available' ? 'not_available' : numFrom(r.engagement_rate),
    syncedAt: r.synced_at,
  }));
};

// ----- Deliverables + completion (FR-20) -----------------------------------

export type Deliverable = {
  id: number;
  postUrl: string;
  platform: Platform;
  note: string;
  createdAt: string;
  updatedAt: string;
};

export type CampaignDeliverableRow = {
  proposalId: number;
  creator: { id: number; name: string };
  completedAt: string | null;
  deliverables: Deliverable[];
};

const mapDeliverable = (d: { id: number; post_url: string; platform: string; note: string; created_at: string; updated_at: string }): Deliverable => ({
  id: d.id,
  postUrl: d.post_url,
  platform: platformFromBackend(d.platform),
  note: d.note,
  createdAt: d.created_at,
  updatedAt: d.updated_at,
});

export const listMyDeliverables = async (proposalId: number | string): Promise<Deliverable[]> => {
  const data = await request<Array<{ id: number; post_url: string; platform: string; note: string; created_at: string; updated_at: string }>>(
    'creators/me/proposals/' + proposalId + '/deliverables/',
  );
  return data.map(mapDeliverable);
};

export const addDeliverable = async (
  proposalId: number | string,
  input: { postUrl: string; platform: Platform; note?: string },
): Promise<Deliverable> => {
  const data = await request<{ id: number; post_url: string; platform: string; note: string; created_at: string; updated_at: string }>(
    'creators/me/proposals/' + proposalId + '/deliverables/',
    { method: 'POST', body: { post_url: input.postUrl, platform: platformToBackend(input.platform), note: input.note ?? '' } },
  );
  return mapDeliverable(data);
};

export const updateDeliverable = async (
  proposalId: number | string,
  deliverableId: number | string,
  patch: { postUrl?: string; platform?: Platform; note?: string },
): Promise<Deliverable> => {
  const body: Record<string, unknown> = {};
  if (patch.postUrl !== undefined) body.post_url = patch.postUrl;
  if (patch.platform !== undefined) body.platform = platformToBackend(patch.platform);
  if (patch.note !== undefined) body.note = patch.note;
  const data = await request<{ id: number; post_url: string; platform: string; note: string; created_at: string; updated_at: string }>(
    'creators/me/proposals/' + proposalId + '/deliverables/' + deliverableId + '/',
    { method: 'PATCH', body },
  );
  return mapDeliverable(data);
};

export const deleteDeliverable = async (proposalId: number | string, deliverableId: number | string) => {
  await request('creators/me/proposals/' + proposalId + '/deliverables/' + deliverableId + '/', { method: 'DELETE' });
};

export const completeProposal = async (proposalId: number | string): Promise<{ id: number; status: ProposalStatus; completedAt: string | null }> => {
  const data = await request<{ id: number; status: ProposalStatus; completed_at: string | null }>('brand/proposals/' + proposalId + '/complete/', { method: 'POST' });
  return { id: data.id, status: data.status, completedAt: data.completed_at };
};

export const listCampaignDeliverables = async (campaignId: number | string): Promise<CampaignDeliverableRow[]> => {
  const data = await request<Array<{
    proposal_id: number;
    creator: { id: number; name: string };
    completed_at: string | null;
    deliverables: Array<{ id: number; post_url: string; platform: string; note: string; created_at: string; updated_at: string }>;
  }>>('brand/campaigns/' + campaignId + '/deliverables/');
  return data.map((row) => ({
    proposalId: row.proposal_id,
    creator: row.creator,
    completedAt: row.completed_at,
    deliverables: row.deliverables.map(mapDeliverable),
  }));
};

// ----- Reviews (FR-21) ------------------------------------------------------

export type Review = {
  id: number;
  rating: number;
  text: string;
  brand: { id: number; name: string };
  campaign: { id: number; title: string };
  createdAt: string;
};

export const createReview = async (
  proposalId: number | string,
  input: { rating: number; text?: string },
): Promise<Review> => {
  const data = await request<{ id: number; rating: number; text: string; brand: { id: number; name: string }; campaign: { id: number; title: string }; created_at: string }>(
    'brand/proposals/' + proposalId + '/review/',
    { method: 'POST', body: { rating: input.rating, text: input.text ?? '' } },
  );
  return {
    id: data.id,
    rating: data.rating,
    text: data.text,
    brand: data.brand,
    campaign: data.campaign,
    createdAt: data.created_at,
  };
};

export const listCreatorReviews = async (userId: number | string): Promise<Review[]> => {
  const { items } = await fetchPages<{ id: number; rating: number; text: string; brand: { id: number; name: string }; campaign: { id: number; title: string }; created_at: string }>(
    'creators/' + userId + '/reviews/',
  );
  return items.map((r) => ({
    id: r.id,
    rating: r.rating,
    text: r.text,
    brand: r.brand,
    campaign: r.campaign,
    createdAt: r.created_at,
  }));
};

// ----- Admin panel (FR-22) -------------------------------------------------

export type AdminUser = {
  id: number;
  fullName: string;
  email: string;
  username: string;
  role: Role;
  status: 'active' | 'suspended';
  emailVerified: boolean;
  dateJoined: string;
};

export type AdminAction = {
  id: number;
  admin: { id: number; username: string };
  action: string;
  targetType: string;
  targetId: number;
  targetLabel: string;
  reason: string;
  createdAt: string;
};

export type AdminOverview = {
  users: { total: number; suspended: number; byRole: Record<string, number> };
  signups: Array<{ date: string; count: number }>;
  campaignsByStatus: Record<string, number>;
  totalProposals: number;
};

export const adminLogin = async (input: { identifier: string; password: string }): Promise<{ access: string; user: User }> => {
  const data = await request<{ access: string; user: ApiUser }>('admin/auth/login/', {
    method: 'POST',
    body: { identifier: input.identifier, password: input.password },
    anonymous: true,
  });
  return { access: data.access, user: mapUser(data.user) };
};

export type AdminPlatformReview = {
  id: number;
  creator: { id: number; username: string; fullName: string };
  platform: Platform;
  handleUrl?: string;
  followers: number;
  engagementRate: number;
  reviewStatus: 'pending' | 'approved' | 'rejected';
  reviewNote?: string;
  updatedAt: string;
};

type ApiPlatformReview = {
  id: number;
  creator: { id: number; username: string; full_name: string };
  platform: string;
  handle_url: string | null;
  followers: number;
  engagement_rate: string;
  review_status: 'pending' | 'approved' | 'rejected';
  review_note: string;
  updated_at: string;
};

const mapPlatformReview = (r: ApiPlatformReview): AdminPlatformReview => ({
  id: r.id,
  creator: { id: r.creator.id, username: r.creator.username, fullName: r.creator.full_name },
  platform: platformFromBackend(r.platform),
  handleUrl: r.handle_url ?? undefined,
  followers: r.followers,
  engagementRate: numFrom(r.engagement_rate),
  reviewStatus: r.review_status,
  reviewNote: r.review_note || undefined,
  updatedAt: r.updated_at,
});

/** Instagram, TikTok and Facebook numbers typed by creators. */
export const listAdminPlatformReviews = async (status: 'pending' | 'approved' | 'rejected' = 'pending'): Promise<AdminPlatformReview[]> => {
  const { items } = await fetchPages<ApiPlatformReview>('admin/platform-stats/', { status });
  return items.map(mapPlatformReview);
};

export const approveAdminPlatformStats = async (id: number): Promise<AdminPlatformReview> =>
  mapPlatformReview(await request<ApiPlatformReview>(`admin/platform-stats/${id}/approve/`, { method: 'POST', body: {} }));

export const rejectAdminPlatformStats = async (id: number, reason: string): Promise<AdminPlatformReview> =>
  mapPlatformReview(await request<ApiPlatformReview>(`admin/platform-stats/${id}/reject/`, { method: 'POST', body: { reason } }));

export type AdminBrandPlatformReview = {
  id: number;
  brand: { id: number; username: string; fullName: string };
  platform: Platform;
  handleUrl: string;
  reviewStatus: 'pending' | 'approved' | 'rejected';
  reviewNote?: string;
  connectedAt: string;
};

type ApiBrandPlatformReview = {
  id: number;
  brand: { id: number; username: string; full_name: string };
  platform: string;
  handle_url: string;
  review_status: 'pending' | 'approved' | 'rejected';
  review_note: string;
  connected_at: string;
};

const mapBrandPlatformReview = (r: ApiBrandPlatformReview): AdminBrandPlatformReview => ({
  id: r.id,
  brand: { id: r.brand.id, username: r.brand.username, fullName: r.brand.full_name },
  platform: platformFromBackend(r.platform),
  handleUrl: r.handle_url,
  reviewStatus: r.review_status,
  reviewNote: r.review_note || undefined,
  connectedAt: r.connected_at,
});

/** Instagram, TikTok and Facebook links that brands typed. */
export const listAdminBrandPlatforms = async (status: 'pending' | 'approved' | 'rejected' = 'pending'): Promise<AdminBrandPlatformReview[]> => {
  const { items } = await fetchPages<ApiBrandPlatformReview>('admin/brand-platforms/', { status });
  return items.map(mapBrandPlatformReview);
};

export const approveAdminBrandPlatform = async (id: number): Promise<AdminBrandPlatformReview> =>
  mapBrandPlatformReview(await request<ApiBrandPlatformReview>(`admin/brand-platforms/${id}/approve/`, { method: 'POST', body: {} }));

export const rejectAdminBrandPlatform = async (id: number, reason: string): Promise<AdminBrandPlatformReview> =>
  mapBrandPlatformReview(await request<ApiBrandPlatformReview>(`admin/brand-platforms/${id}/reject/`, { method: 'POST', body: { reason } }));

export const listAdminUsers = async (params: { q?: string; role?: Role; status?: 'active' | 'suspended' } = {}): Promise<AdminUser[]> => {
  const query: Record<string, string> = {};
  if (params.q) query.q = params.q;
  if (params.role) query.role = params.role;
  if (params.status) query.status = params.status;
  const { items } = await fetchPages<{
    id: number; full_name: string; email: string; username: string; role: Role;
    status: 'active' | 'suspended'; email_verified: boolean; date_joined: string;
  }>('admin/users/', query);
  return items.map((u) => ({
    id: u.id,
    fullName: u.full_name,
    email: u.email,
    username: u.username,
    role: u.role,
    status: u.status,
    emailVerified: u.email_verified,
    dateJoined: u.date_joined,
  }));
};

export const suspendAdminUser = async (userId: number | string, reason: string): Promise<AdminUser> => {
  const data = await request<{
    id: number; full_name: string; email: string; username: string; role: Role;
    status: 'active' | 'suspended'; email_verified: boolean; date_joined: string;
  }>('admin/users/' + userId + '/suspend/', { method: 'POST', body: { reason } });
  return {
    id: data.id, fullName: data.full_name, email: data.email, username: data.username,
    role: data.role, status: data.status, emailVerified: data.email_verified, dateJoined: data.date_joined,
  };
};

export const reactivateAdminUser = async (userId: number | string, reason: string): Promise<AdminUser> => {
  const data = await request<{
    id: number; full_name: string; email: string; username: string; role: Role;
    status: 'active' | 'suspended'; email_verified: boolean; date_joined: string;
  }>('admin/users/' + userId + '/reactivate/', { method: 'POST', body: { reason } });
  return {
    id: data.id, fullName: data.full_name, email: data.email, username: data.username,
    role: data.role, status: data.status, emailVerified: data.email_verified, dateJoined: data.date_joined,
  };
};

export const deleteAdminUser = async (userId: number | string, reason: string) => {
  await request('admin/users/' + userId + '/', { method: 'DELETE', body: { reason } });
};

/** One page of an admin list, with the total so the screen can offer Previous / Next. */
export type AdminPage<T> = { items: T[]; total: number; page: number; pageSize: number };

type AdminPerson = { id: number; username: string; fullName: string };
const mapAdminPerson = (p: { id: number; username: string; full_name: string }): AdminPerson => ({
  id: p.id,
  username: p.username,
  fullName: p.full_name,
});

export type AdminCampaignRow = {
  id: number;
  title: string;
  status: CampaignStatus;
  brand: AdminPerson;
  deadline: string;
  creatorsNeeded: number;
  /** Every proposal received, withdrawn ones included. */
  proposalCount: number;
  createdAt: string;
  closedAt: string | null;
};

export const listAdminCampaigns = async (
  params: { q?: string; status?: CampaignStatus } = {},
  page = 1,
  pageSize = 20,
): Promise<AdminPage<AdminCampaignRow>> => {
  const query: Record<string, string | number> = { page, page_size: pageSize };
  if (params.q) query.q = params.q;
  if (params.status) query.status = params.status;
  const data = await request<{
    count: number;
    results: Array<{
      id: number;
      title: string;
      status: CampaignStatus;
      brand: { id: number; username: string; full_name: string };
      deadline: string;
      creators_needed: number;
      proposal_count: number;
      created_at: string;
      closed_at: string | null;
    }>;
  }>('admin/campaigns/', { query });
  return {
    items: data.results.map((c) => ({
      id: c.id,
      title: c.title,
      status: c.status,
      brand: mapAdminPerson(c.brand),
      deadline: c.deadline,
      creatorsNeeded: c.creators_needed,
      proposalCount: c.proposal_count,
      createdAt: c.created_at,
      closedAt: c.closed_at,
    })),
    total: data.count,
    page,
    pageSize,
  };
};

export type AdminReviewRow = {
  id: number;
  rating: number;
  text: string;
  brand: AdminPerson;
  creator: AdminPerson;
  campaign: { id: number; title: string };
  createdAt: string;
};

export const listAdminReviews = async (
  params: { q?: string; rating?: number } = {},
  page = 1,
  pageSize = 20,
): Promise<AdminPage<AdminReviewRow>> => {
  const query: Record<string, string | number> = { page, page_size: pageSize };
  if (params.q) query.q = params.q;
  if (params.rating) query.rating = params.rating;
  const data = await request<{
    count: number;
    results: Array<{
      id: number;
      rating: number;
      text: string;
      brand: { id: number; username: string; full_name: string };
      creator: { id: number; username: string; full_name: string };
      campaign: { id: number; title: string };
      created_at: string;
    }>;
  }>('admin/reviews/', { query });
  return {
    items: data.results.map((r) => ({
      id: r.id,
      rating: r.rating,
      text: r.text,
      brand: mapAdminPerson(r.brand),
      creator: mapAdminPerson(r.creator),
      campaign: r.campaign,
      createdAt: r.created_at,
    })),
    total: data.count,
    page,
    pageSize,
  };
};

export const closeAdminCampaign = async (campaignId: number | string, reason: string) => {
  return request<{ id: number; title: string; status: CampaignStatus; closed_at: string | null }>(
    'admin/campaigns/' + campaignId + '/close/',
    { method: 'POST', body: { reason } },
  );
};

export const deleteAdminReview = async (reviewId: number | string, reason: string) => {
  await request('admin/reviews/' + reviewId + '/', { method: 'DELETE', body: { reason } });
};

export const listAdminActions = async (): Promise<AdminAction[]> => {
  const { items } = await fetchPages<{
    id: number;
    admin: { id: number; username: string };
    action: string;
    target_type: string;
    target_id: number;
    target_label: string;
    reason: string;
    created_at: string;
  }>('admin/actions/');
  return items.map((a) => ({
    id: a.id,
    admin: a.admin,
    action: a.action,
    targetType: a.target_type,
    targetId: a.target_id,
    targetLabel: a.target_label,
    reason: a.reason,
    createdAt: a.created_at,
  }));
};

export const fetchAdminOverview = async (): Promise<AdminOverview> => {
  const data = await request<{
    users: { total: number; suspended: number; by_role: Record<string, number> };
    signups: Array<{ date: string; count: number }>;
    campaigns_by_status: Record<string, number>;
    total_proposals: number;
  }>('admin/overview/');
  return {
    users: { total: data.users.total, suspended: data.users.suspended, byRole: data.users.by_role },
    signups: data.signups,
    campaignsByStatus: data.campaigns_by_status,
    totalProposals: data.total_proposals,
  };
};
