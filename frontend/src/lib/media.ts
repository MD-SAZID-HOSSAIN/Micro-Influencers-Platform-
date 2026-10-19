import type { CampaignMedia } from '../types';

/**
 * Rules for photos and videos on a campaign brief. They mirror the backend (apps/campaigns/media.py),
 * which is the real gatekeeper: up to 2 photos, or exactly 1 video, never both.
 */

export const MAX_PHOTOS = 2;
export const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
export const MAX_VIDEO_BYTES = 50 * 1024 * 1024;

export const ACCEPT = 'image/jpeg,image/png,image/webp,video/mp4,video/webm';

type Kind = CampaignMedia['kind'];

const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const VIDEO_TYPES = ['video/mp4', 'video/webm'];

/** Photo or video, from the browser's MIME type (falling back to the extension). Null if unsupported. */
export function fileKind(file: File): Kind | null {
  if (PHOTO_TYPES.includes(file.type)) return 'photo';
  if (VIDEO_TYPES.includes(file.type)) return 'video';
  if (!file.type) {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext && ['jpg', 'jpeg', 'png', 'webp'].includes(ext)) return 'photo';
    if (ext && ['mp4', 'webm'].includes(ext)) return 'video';
  }
  return null;
}

export const formatSize = (bytes: number): string =>
  bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

/**
 * Which of `incoming` can be added next to what is already attached, and why the first refusal
 * happened. `current` is every photo and video already counted (saved, or chosen but not uploaded).
 */
export function checkAdd(current: Kind[], incoming: File[]): { accepted: File[]; error?: string } {
  const kinds = [...current];
  const accepted: File[] = [];
  let error: string | undefined;
  for (const file of incoming) {
    const kind = fileKind(file);
    if (!kind) {
      error ??= `${file.name}: use a JPG, PNG or WebP photo, or an MP4 or WebM video.`;
      continue;
    }
    const limit = kind === 'video' ? MAX_VIDEO_BYTES : MAX_PHOTO_BYTES;
    if (file.size > limit) {
      error ??= `${file.name} is too large. A ${kind} can be at most ${formatSize(limit)}.`;
      continue;
    }
    if (kind === 'video' && kinds.length > 0) {
      error ??= kinds.includes('video')
        ? 'A campaign can have only 1 video.'
        : 'A video can’t be added next to photos. Remove the photos first.';
      continue;
    }
    if (kind === 'photo' && kinds.includes('video')) {
      error ??= 'A campaign with a video can’t also have photos. Remove the video first.';
      continue;
    }
    if (kind === 'photo' && kinds.filter((k) => k === 'photo').length >= MAX_PHOTOS) {
      error ??= 'A campaign can have up to 2 photos.';
      continue;
    }
    kinds.push(kind);
    accepted.push(file);
  }
  return { accepted, error };
}
