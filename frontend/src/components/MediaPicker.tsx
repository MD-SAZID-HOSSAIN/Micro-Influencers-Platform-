import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Film, ImagePlus, X } from 'lucide-react';
import clsx from 'clsx';
import type { CampaignMedia } from '../types';
import { deleteCampaignMedia, uploadCampaignMedia } from '../api/endpoints';
import { isApiError } from '../api/client';
import { ACCEPT, MAX_PHOTOS, checkAdd, fileKind, formatSize } from '../lib/media';

/**
 * The photos or video of a campaign brief while it is being written.
 *
 * Nothing leaves the browser until `commit(campaignId)` runs (when the brand saves or publishes),
 * because the campaign has to exist before it can have media. Files removed from a saved draft are
 * deleted first, so swapping one photo for another always fits inside the limit.
 */
export function useMediaDraft(saved: CampaignMedia[] = []) {
  const [existing, setExisting] = useState<CampaignMedia[]>(saved);
  const [removed, setRemoved] = useState<string[]>([]);
  const [pending, setPending] = useState<File[]>([]);
  const [error, setError] = useState('');

  // Follow the saved list when it arrives or changes (for example after the campaign loads).
  const savedKey = saved.map((m) => m.id).join(',');
  useEffect(() => {
    setExisting(saved);
    setRemoved([]);
  }, [savedKey]);

  const visible = useMemo(() => existing.filter((m) => !removed.includes(m.id)), [existing, removed]);

  const add = useCallback(
    (files: File[]) => {
      const counted = [...visible.map((m) => m.kind), ...pending.map((f) => fileKind(f)!)];
      const { accepted, error: refusal } = checkAdd(counted, files);
      setError(refusal ?? '');
      if (accepted.length) setPending((p) => [...p, ...accepted]);
    },
    [visible, pending],
  );

  const removeExisting = useCallback((id: string) => {
    setError('');
    setRemoved((r) => [...r, id]);
  }, []);

  const removePending = useCallback((index: number) => {
    setError('');
    setPending((p) => p.filter((_, i) => i !== index));
  }, []);

  /** Apply the changes to a saved campaign. Throws on the first failure, keeping what is left to do. */
  const commit = useCallback(
    async (campaignId: string) => {
      for (const id of removed) {
        try {
          await deleteCampaignMedia(campaignId, id);
        } catch (err) {
          if (!(isApiError(err) && err.status === 404)) throw err; // already gone is fine
        }
        setExisting((prev) => prev.filter((m) => m.id !== id));
        setRemoved((r) => r.filter((x) => x !== id));
      }
      for (const file of pending) {
        const uploaded = await uploadCampaignMedia(campaignId, file);
        setExisting((prev) => [...prev, uploaded]);
        setPending((p) => p.filter((f) => f !== file));
      }
    },
    [removed, pending],
  );

  return {
    existing: visible,
    pending,
    error,
    add,
    removeExisting,
    removePending,
    commit,
    hasChanges: removed.length > 0 || pending.length > 0,
  };
}

export type MediaDraft = ReturnType<typeof useMediaDraft>;

export function MediaPicker({ draft, disabled = false }: { draft: MediaDraft; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const previews = useMemo(() => draft.pending.map((f) => URL.createObjectURL(f)), [draft.pending]);
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  const kinds = [...draft.existing.map((m) => m.kind), ...draft.pending.map((f) => fileKind(f))];
  const full = kinds.includes('video') || kinds.filter((k) => k === 'photo').length >= MAX_PHOTOS;

  return (
    <section className="card p-5 sm:p-6" aria-labelledby="media-heading">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="media-heading" className="display-sm">Photos or video</h2>
          <p className="mt-1 text-sm text-ink-500">
            Optional. Show creators the product or the mood: up to 2 photos (JPG, PNG or WebP, 5 MB each),
            or 1 video (MP4 or WebM, 50 MB).
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {draft.existing.map((m) => (
          <Tile
            key={m.id}
            kind={m.kind}
            src={m.url}
            caption={formatSize(m.size)}
            onRemove={() => draft.removeExisting(m.id)}
            disabled={disabled}
          />
        ))}
        {draft.pending.map((file, i) => (
          <Tile
            key={`${file.name}-${i}`}
            kind={fileKind(file) ?? 'photo'}
            src={previews[i]}
            caption={`${formatSize(file.size)} · uploads when you save`}
            onRemove={() => draft.removePending(i)}
            disabled={disabled}
          />
        ))}

        {!full && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (!disabled) draft.add(Array.from(e.dataTransfer.files));
            }}
            className={clsx(
              'aspect-video rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 text-sm font-semibold transition-colors',
              dragging
                ? 'border-brand-500 bg-brand-50 text-brand-700'
                : 'border-ink-300 text-ink-600 hover:border-brand-400 hover:bg-brand-50/50 hover:text-brand-700',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            <ImagePlus className="w-6 h-6" aria-hidden />
            Add a photo or video
            <span className="text-xs font-normal text-ink-500">or drop it here</span>
          </button>
        )}
      </div>

      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose photos or a video"
        onChange={(e) => {
          draft.add(Array.from(e.target.files ?? []));
          e.target.value = '';
        }}
      />

      {draft.error && (
        <p className="error mt-3" role="alert">
          {draft.error}
        </p>
      )}
    </section>
  );
}

function Tile({
  kind, src, caption, onRemove, disabled,
}: {
  kind: CampaignMedia['kind'];
  src: string;
  caption: string;
  onRemove: () => void;
  disabled: boolean;
}) {
  return (
    <figure className="relative aspect-video rounded-xl overflow-hidden border border-ink-200 bg-ink-100">
      {kind === 'video' ? (
        <video src={src} controls muted playsInline preload="metadata" className="w-full h-full object-cover bg-ink-900" />
      ) : (
        <img src={src} alt="Campaign photo" className="w-full h-full object-cover" />
      )}
      <figcaption className="absolute left-2 bottom-2 inline-flex items-center gap-1.5 rounded-md bg-ink-900/75 px-2 py-1 text-[11px] font-semibold text-white pointer-events-none">
        {kind === 'video' && <Film className="w-3 h-3" aria-hidden />}
        {caption}
      </figcaption>
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        aria-label={`Remove ${kind}`}
        className="absolute top-2 right-2 w-8 h-8 rounded-full bg-ink-900/75 text-white hover:bg-ink-900 flex items-center justify-center disabled:opacity-50"
      >
        <X className="w-4 h-4" />
      </button>
    </figure>
  );
}

/** What creators and brands see on a published or saved campaign. Renders nothing without media. */
export function MediaGallery({ media }: { media?: CampaignMedia[] }) {
  if (!media || media.length === 0) return null;
  const video = media.find((m) => m.kind === 'video');
  if (video) {
    return (
      <video
        src={video.url}
        controls
        preload="metadata"
        playsInline
        className="w-full max-h-[480px] rounded-2xl bg-ink-900"
      />
    );
  }
  return (
    <div className={clsx('grid gap-3', media.length > 1 && 'sm:grid-cols-2')}>
      {media.map((m) => (
        <img
          key={m.id}
          src={m.url}
          alt="Campaign photo"
          loading="lazy"
          className="w-full max-h-[420px] rounded-2xl object-cover bg-ink-100"
        />
      ))}
    </div>
  );
}
