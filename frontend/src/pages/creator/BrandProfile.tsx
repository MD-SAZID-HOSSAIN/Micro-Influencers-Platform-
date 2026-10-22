import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Building2 } from 'lucide-react';
import { useAsyncLoader } from '../../state/useEffectAsync';
import { fetchBrandDetail } from '../../api/endpoints';
import { ChannelArt, ProfileTile, SectionHeader } from '../../components/ui';

/** A brand's company page, as a logged-in creator sees it (opened from a campaign or a proposal). */
export default function CreatorBrandProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: brand, loading, error } = useAsyncLoader(() => fetchBrandDetail(id!), [id]);

  if (loading) {
    return <div className="container-page py-8"><div className="card p-8 text-center text-sm text-ink-500">Loading…</div></div>;
  }
  if (error || !brand) {
    return (
      <div className="container-page py-6 sm:py-8">
        <div className="card p-10 text-center">
          <Building2 className="w-7 h-7 text-ink-300 mx-auto mb-2" />
          <div className="text-sm font-semibold text-ink-900">Brand not found</div>
          <div className="text-xs text-ink-500 mt-1">{error ?? 'This company page is not available.'}</div>
          <Link to="/creator/campaigns" className="text-sm link-accent inline-flex items-center gap-1 mt-3">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to campaigns
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-6 sm:py-8 space-y-6 max-w-3xl">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="text-sm text-ink-600 hover:text-ink-900 inline-flex items-center gap-1"
      >
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      <div className="card overflow-hidden">
        <ChannelArt name={brand.companyName} seed={brand.id} height={120} className="rounded-none w-full" />
        <div className="p-5 sm:p-6 flex items-start gap-4">
          <ProfileTile
            name={brand.companyName}
            seed={brand.id}
            imageUrl={brand.logoUrl}
            height={96}
            className="w-20 sm:w-24 !h-20 sm:!h-24 rounded-2xl ring-4 ring-white shadow-md shrink-0 -mt-12 sm:-mt-14 relative z-10"
          />
          <div className="min-w-0 flex-1 pt-0.5">
            <h1 className="font-display text-2xl sm:text-3xl text-ink-900 leading-tight tracking-[-0.02em] break-words">
              {brand.companyName}
            </h1>
            {brand.industry && <div className="text-sm text-ink-500 mt-1.5">{brand.industry}</div>}
            {brand.website && (
              <a
                href={brand.website}
                target="_blank"
                rel="noreferrer noopener"
                className="mt-2 text-sm text-brand-600 hover:text-brand-700 inline-flex items-center gap-1 font-semibold break-all"
              >
                <ExternalLink className="w-3.5 h-3.5 shrink-0" /> {brand.website}
              </a>
            )}
          </div>
        </div>
      </div>

      <section className="card p-5 sm:p-6">
        <SectionHeader eyebrow="About" title="What we do" />
        <p className="mt-4 text-ink-700 leading-relaxed text-[15px] whitespace-pre-line break-words">
          {brand.about || <span className="text-ink-400">This brand has not written anything about itself yet.</span>}
        </p>
      </section>
    </div>
  );
}
