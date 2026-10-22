import { Link, useNavigate, useParams } from 'react-router-dom';
import { useStore, addProposal, loadMyProposals } from '../../state/Store';
import { useAsyncLoader } from '../../state/useEffectAsync';
import { fetchCreatorCampaign } from '../../api/endpoints';
import {
  Button, CampaignStatusBadge, EligibilityChip, ChannelArt, ProfileTile, PlatformIcon,
  SectionHeader, StatRow, PageHeader,
} from '../../components/ui';
import { currency, fmtDate } from '../../lib/shared';
import { ArrowLeft, ArrowRight, CheckCircle2, AlertTriangle, Megaphone, X } from 'lucide-react';
import { useState } from 'react';
import { Modal } from '../../components/Modal';
import { FormField, Textarea, Input } from '../../components/ui';
import { useToast } from '../../state/ToastContext';
import { isApiError } from '../../api/client';
import { MediaGallery } from '../../components/MediaPicker';

type Detail = Awaited<ReturnType<typeof fetchCreatorCampaign>>;

export default function CampaignDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();
  const { creator, proposals } = useStore();
  const { data, loading, error, refresh } = useAsyncLoader<Detail>(
    () => fetchCreatorCampaign(id!),
    [id],
  );
  const [applyOpen, setApplyOpen] = useState(false);
  const [applying, setApplying] = useState(false);

  if (loading) {
    return <div className="container-page py-8"><div className="card p-8 text-center text-sm text-ink-500">Loading…</div></div>;
  }
  if (error || !data) {
    return (
      <div className="container-page py-6 sm:py-8">
        <div className="card p-10 text-center">
          <Megaphone className="w-7 h-7 text-ink-300 mx-auto mb-2" />
          <div className="text-sm font-semibold text-ink-900">Couldn’t load this brief</div>
          <div className="text-xs text-ink-500 mt-1">{error ?? 'Try again from the list.'}</div>
          <Link to="/creator/campaigns" className="text-sm link-accent inline-flex items-center gap-1 mt-3">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to briefs
          </Link>
        </div>
      </div>
    );
  }

  const { campaign, acceptedCount, allSelected, canApply, applyBlockedReason, eligible } = data;
  const myProposalForCampaign = proposals.find(
    (p) => p.campaignId === campaign.id,
  );

  // `eligible` comes from the server, which looks at the creator's stats for the campaign's own
  // platform (verified or entered by hand). It is a hint only: it never stops anyone applying.
  const requirement = campaign.minFollowers
    ? `${campaign.requiredPlatform} with ${campaign.minFollowers.toLocaleString()}+ followers`
    : campaign.requiredPlatform;

  const hasActive = myProposalForCampaign &&
    (myProposalForCampaign.status === 'pending' ||
      myProposalForCampaign.status === 'shortlisted' ||
      myProposalForCampaign.status === 'accepted');
  const wasRejected = myProposalForCampaign?.status === 'rejected';

  // The server decides whether Apply is allowed and, if not, why (as a short code). Show that as a sentence.
  // The checks run in the PRD's order: a live proposal, then a rejected one, then a closed campaign.
  const BLOCKED: Record<string, { label: string; reason: string }> = {
    active_proposal: {
      label: 'You already applied',
      reason: 'You have a live proposal for this campaign. You can follow it under My proposals.',
    },
    proposal_rejected: {
      label: 'Proposal not selected',
      reason: 'The brand rejected your proposal, so you cannot apply to this campaign again.',
    },
    campaign_closed: {
      label: 'Campaign closed',
      reason: 'This campaign is no longer accepting applications.',
    },
  };
  const blockedCode =
    applyBlockedReason ??
    (hasActive ? 'active_proposal' : wasRejected ? 'proposal_rejected' : campaign.status === 'closed' ? 'campaign_closed' : null);

  let buttonState: { label: string; disabled: boolean; reason?: string };
  if (!canApply) {
    const why = BLOCKED[blockedCode ?? ''] ?? {
      label: 'Cannot apply',
      reason: 'You cannot apply to this campaign right now.',
    };
    buttonState = { ...why, disabled: true };
  } else {
    // A full campaign does not stop anyone applying: a place opens up again if an accepted creator withdraws.
    buttonState = {
      label: 'Apply now',
      disabled: false,
      reason: allSelected
        ? 'All creators are selected right now. You can still apply in case a place opens up.'
        : undefined,
    };
  }

  return (
    <div className="container-page py-6 sm:py-8 space-y-6">
      <Link to="/creator/campaigns" className="text-sm text-ink-600 hover:text-ink-900 inline-flex items-center gap-1">
        <ArrowLeft className="w-4 h-4" /> Back to briefs
      </Link>

      <header className="card overflow-hidden">
        <ChannelArt name={campaign.brandName} seed={campaign.brandId} height={96} className="rounded-none" />
        <div className="p-4 sm:p-6">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
            <div className="flex flex-col sm:flex-row sm:items-start gap-3 min-w-0">
              {/* Only the logo overlaps the cover image. `relative z-10` keeps it above the image; the text stays below it. */}
              <ProfileTile name={campaign.brandName} seed={campaign.brandId} imageUrl={campaign.brandLogoUrl} height={56} className="w-12 sm:w-14 rounded-md ring-4 ring-mist-50 shrink-0 -mt-10 sm:-mt-12 relative z-10" />
              <div className="min-w-0">
                <h1 className="font-display text-xl sm:text-2xl md:text-3xl text-ink-900 leading-[1.15] tracking-[-0.02em] break-words">
                  {campaign.title}
                </h1>
              </div>
            </div>
            <div className="self-start sm:self-auto shrink-0">
              <CampaignStatusBadge status={campaign.status} />
            </div>
          </div>
          {/* Below the banner on purpose: the line used to sit under the cover image, where nobody could see it. */}
          <div className="text-sm text-ink-500 mt-4">
            Posted by{' '}
            <Link to={`/creator/brands/${campaign.brandId}`} className="link-accent font-semibold">
              {campaign.brandName}
            </Link>{' '}
            · {campaign.category}
          </div>
          <p className="text-[15px] text-ink-700 mt-3 leading-relaxed whitespace-pre-line break-words">{campaign.description}</p>
        </div>
      </header>

      <MediaGallery media={campaign.media} />

      <StatRow
        items={[
          { label: 'Budget', value: currency(campaign.budgetPerCreator), hint: 'per creator' },
          { label: 'Deadline', value: fmtDate(campaign.applicationDeadline) },
          { label: 'Creators', value: String(campaign.creatorsNeeded), hint: 'needed' },
          { label: 'Min followers', value: campaign.minFollowers?.toLocaleString() ?? '—' },
          { label: 'Withdrawing', value: campaign.allowWithdrawal === false ? 'Not allowed' : 'Allowed', hint: 'after you apply' },
        ]}
      />

      <section className="card p-5 sm:p-6">
        <SectionHeader eyebrow="Brief" title="Details" />
        <dl className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-5 text-sm">
          <Row label="Required platform">
            <span className="inline-flex items-center gap-1.5">
              <PlatformIcon platform={campaign.requiredPlatform} />
              {campaign.requiredPlatform}
            </span>
          </Row>
          <Row label="Category">{campaign.category}</Row>
          <Row label="Deliverables"><span className="font-sans font-normal text-ink-700">{campaign.deliverables || '—'}</span></Row>
        </dl>
      </section>

      <section className="card p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="eyebrow mb-1.5">Eligibility</div>
          <div className="text-sm font-semibold text-ink-900">
            {eligible ? 'Your profile fits this brief.' : 'Your profile may not fit this brief.'}
          </div>
          <div className="text-xs text-ink-500 mt-1">
            {eligible
              ? `Looking for: ${requirement}.`
              : `Looking for: ${requirement}. This is a guide only, you can still apply.`}
          </div>
        </div>
        <EligibilityChip eligible={eligible} reason={`Looking for ${requirement}`} />
      </section>

      {allSelected && (
        <div className="card p-4 flex items-center gap-3 border-emerald-200 bg-emerald-50 text-sm text-emerald-800">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          Brand has selected all creators for this campaign.
        </div>
      )}
      {campaign.status === 'closed' && !allSelected && (
        <div className="card p-4 flex items-center gap-3 border-amber-200 bg-amber-50 text-sm text-amber-800">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          This campaign has been closed to new proposals.
        </div>
      )}

      <div className="card p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink-900">Ready to apply?</div>
          {buttonState.reason && <div className="text-xs text-ink-500 mt-0.5">{buttonState.reason}</div>}
        </div>
        <Button
          disabled={buttonState.disabled || applying}
          onClick={() => setApplyOpen(true)}
          size="lg"
        >
          {buttonState.label}
          {!buttonState.disabled && <ArrowRight className="w-4 h-4" />}
        </Button>
      </div>

      {applyOpen && (
        <ApplyModal
          onClose={() => setApplyOpen(false)}
          onSubmitted={async (newId) => {
            setApplyOpen(false);
            push('Proposal submitted!', 'success');
            await loadMyProposals();
            refresh();
            navigate(`/creator/applications/${newId}`);
          }}
          campaignId={campaign.id}
          budget={campaign.budgetPerCreator}
          allowWithdrawal={campaign.allowWithdrawal !== false}
          applying={applying}
          setApplying={setApplying}
        />
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="eyebrow">{label}</dt>
      <dd className="mt-1.5 text-ink-700 font-semibold">{children}</dd>
    </div>
  );
}

function ApplyModal({
  onClose, onSubmitted, campaignId, budget, allowWithdrawal, applying, setApplying,
}: {
  onClose: () => void;
  onSubmitted: (proposalId: string) => void;
  campaignId: string;
  /** The brand's fixed rate for each creator. The creator cannot change it. */
  budget: number;
  /** False when the brand does not let creators withdraw after applying. */
  allowWithdrawal: boolean;
  applying: boolean;
  setApplying: (b: boolean) => void;
}) {
  const { creator } = useStore();
  const [cover, setCover] = useState('');
  const [experience, setExperience] = useState('');
  const [links, setLinks] = useState((creator?.portfolio ?? []).slice(0, 3).map((p) => ({ ...p })));
  const [error, setError] = useState('');

  const valid = cover.length >= 30;

  const submit = async () => {
    if (!valid) {
      setError('Your cover message must be at least 30 characters.');
      return;
    }
    setApplying(true);
    setError('');
    try {
      const p = await addProposal(campaignId, {
        coverMessage: cover,
        portfolio: links.filter((l) => l.url).slice(0, 3),
        relevantExperience: experience,
      });
      onSubmitted(p.id);
    } catch (err) {
      const msg = isApiError(err) ? err.message : 'Could not submit your proposal.';
      setError(msg);
    } finally {
      setApplying(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Submit a proposal"
      size="lg"
      footer={
        <>
          <button className="btn btn-secondary btn-md" onClick={onClose} disabled={applying}>Cancel</button>
          <button className="btn btn-primary btn-md" disabled={!valid || applying} onClick={submit}>
            {applying ? 'Submitting…' : 'Submit proposal'}
          </button>
        </>
      }
    >
      <FormField label="Cover message" helper={`${cover.length}/3000 · at least 30 characters`}>
        <Textarea rows={5} maxLength={3000} value={cover} onChange={(e) => setCover(e.target.value)} placeholder="Tell the brand why you’re a fit…" />
      </FormField>
      <div className="rounded-md border border-ink-200 bg-mist-100/60 p-3 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="font-semibold text-ink-900">Fixed rate</span>
          <span className="font-mono font-semibold text-ink-900">{currency(budget)}</span>
        </div>
        <p className="text-xs text-ink-500 mt-1">
          The brand set this rate for every creator. It cannot be negotiated or changed, so there is nothing to type here.
        </p>
      </div>
      {!allowWithdrawal && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <strong>You cannot withdraw.</strong> This brand does not allow creators to take a proposal back once it is
          sent. Only apply if you can do the work.
        </div>
      )}
      <FormField label="Relevant experience" helper="Optional, up to 2000 chars">
        <Input value={experience} onChange={(e) => setExperience(e.target.value)} maxLength={2000} placeholder="e.g. 3 beverage collabs in 2024" />
      </FormField>
      <FormField label="Portfolio links" helper="Up to 3 · pre-filled from your profile">
        {links.map((l, i) => (
          <div key={l.id} className="flex gap-2 mb-2">
            <Input
              placeholder="https://…"
              className="flex-1 min-w-0"
              value={l.url}
              onChange={(e) => {
                const next = [...links];
                next[i] = { ...next[i], url: e.target.value };
                setLinks(next);
              }}
            />
            <button
              type="button"
              className="text-ink-500 hover:text-rose-600 transition-colors px-2"
              onClick={() => setLinks(links.filter((_, idx) => idx !== i))}
              aria-label="Remove link"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
        {links.length === 0 && (
          <div className="text-xs text-ink-500">No portfolio links yet — add some to your profile first.</div>
        )}
      </FormField>
      {error && <div className="error">{error}</div>}
    </Modal>
  );
}
