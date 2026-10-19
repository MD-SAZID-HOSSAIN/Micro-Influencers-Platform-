import { useRef, useState } from 'react';
import { Camera, Loader2, Trash2 } from 'lucide-react';
import clsx from 'clsx';
import { MAX_PHOTO_BYTES, fileKind, formatSize } from '../lib/media';
import { isApiError } from '../api/client';

/**
 * Upload, replace or remove a profile picture: a creator's photo or a brand's logo.
 * A change is saved as soon as the file is chosen (it does not wait for the "Save" button of the
 * form), because a picture is not part of the text fields the form tracks.
 */
export function ProfilePictureEditor({
  value,
  name,
  title,
  hint,
  shape,
  onUpload,
  onRemove,
}: {
  value?: string;
  name: string;
  title: string;
  hint: string;
  shape: 'circle' | 'rounded';
  onUpload: (file: File) => Promise<void>;
  onRemove: () => Promise<void>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<'upload' | 'remove' | null>(null);
  const [error, setError] = useState('');

  const initials = name
    .split(' ')
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const frame = shape === 'circle' ? 'rounded-full' : 'rounded-2xl';

  const run = async (kind: 'upload' | 'remove', action: () => Promise<void>) => {
    setBusy(kind);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(isApiError(err) ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(null);
    }
  };

  const choose = (file: File | undefined) => {
    if (!file) return;
    if (fileKind(file) !== 'photo') {
      setError('Use a JPG, PNG or WebP photo.');
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setError(`That photo is ${formatSize(file.size)}. The largest allowed is ${formatSize(MAX_PHOTO_BYTES)}.`);
      return;
    }
    void run('upload', () => onUpload(file));
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-5">
      <div
        className={clsx(
          'relative w-24 h-24 shrink-0 overflow-hidden border border-ink-200 bg-gradient-to-br from-nest-400 to-brand-400',
          frame,
        )}
      >
        {value ? (
          <img src={value} alt={`${name} profile picture`} className="w-full h-full object-cover" />
        ) : (
          <span className="absolute inset-0 flex items-center justify-center font-display text-2xl font-semibold text-white">
            {initials || '?'}
          </span>
        )}
        {busy && (
          <span className="absolute inset-0 flex items-center justify-center bg-ink-900/50">
            <Loader2 className="w-6 h-6 text-white animate-spin" aria-label="Working" />
          </span>
        )}
      </div>

      <div className="min-w-0">
        <div className="text-sm font-semibold text-ink-900">{title}</div>
        <p className="text-xs text-ink-500 mt-0.5">{hint} JPG, PNG or WebP, up to 5 MB.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={busy !== null}
            onClick={() => input.current?.click()}
          >
            <Camera className="w-4 h-4" />
            {value ? 'Replace' : 'Upload'}
          </button>
          {value && (
            <button
              type="button"
              className="btn btn-ghost btn-sm text-rose-600 hover:text-rose-700"
              disabled={busy !== null}
              onClick={() => void run('remove', onRemove)}
            >
              <Trash2 className="w-4 h-4" />
              Remove
            </button>
          )}
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>

      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        tabIndex={-1}
        aria-label={title}
        onChange={(e) => {
          choose(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
    </div>
  );
}
