import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CampaignForm, CampaignFormValues, validateCampaign } from './CampaignForm';
import {
  addCampaign,
  updateCampaign,
  setCampaignStatus,
  loadBrandCampaigns,
  useStore,
  loadBrandProfile,
} from '../../state/Store';
import { Button, PageHeader } from '../../components/ui';
import { MediaPicker, useMediaDraft } from '../../components/MediaPicker';
import { useToast } from '../../state/ToastContext';
import { useEffect } from 'react';
import { isApiError } from '../../api/client';

const blank: CampaignFormValues = {
  title: '',
  description: '',
  category: 'Other',
  requiredPlatform: 'YouTube',
  budgetPerCreator: 500,
  applicationDeadline: new Date(Date.now() + 14 * 86400000).toISOString(),
  deliverables: '',
  creatorsNeeded: 1,
  minFollowers: undefined,
  allowWithdrawal: true,
};

export default function CreateCampaign() {
  const navigate = useNavigate();
  const { push } = useToast();
  const { brand } = useStore();
  const [values, setValues] = useState<CampaignFormValues>(blank);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  // Set once the brief has been saved as a draft. If publishing then fails, pressing the button
  // again updates and publishes this draft instead of creating a second copy.
  const [draftId, setDraftId] = useState<string | null>(null);
  const media = useMediaDraft();

  useEffect(() => {
    loadBrandProfile().catch(() => undefined);
  }, []);

  const handle = async (action: 'draft' | 'publish') => {
    const errs = validateCampaign(values);
    setErrors(errs);
    if (Object.keys(errs).length) {
      push('Please fix the highlighted fields', 'error');
      return;
    }
    setSubmitting(true);
    try {
      let id = draftId;
      if (id) {
        await updateCampaign(id, values);
      } else {
        id = (await addCampaign(values)).id;
        setDraftId(id);
      }
      // Photos and videos go up once the campaign exists. A failure here keeps the draft and the
      // files still waiting, so pressing the button again only retries what is missing.
      try {
        await media.commit(id);
      } catch (err) {
        const reason = isApiError(err) ? err.message : 'Something went wrong.';
        push(`Saved as a draft, but the photo or video did not upload: ${reason} Press the button again to retry.`, 'error');
        return;
      }
      if (action === 'publish') {
        try {
          await setCampaignStatus(id, 'published');
        } catch (err) {
          const reason = isApiError(err) ? err.message : 'Something went wrong.';
          push(`Saved as a draft, but not published: ${reason} Fix it and press Publish again.`, 'error');
          return;
        }
        push('Campaign published', 'success');
      } else {
        push('Draft saved', 'success');
      }
      await loadBrandCampaigns();
      navigate(`/brand/campaigns/${id}`);
    } catch (err) {
      const msg = isApiError(err) ? err.message : 'Could not create campaign.';
      push(msg, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container-page py-6 sm:py-8 space-y-6 max-w-3xl">
      <PageHeader
        eyebrow="New"
        title="Create a campaign"
        description="Save as a draft to keep editing, or publish to start receiving proposals."
      />
      <CampaignForm values={values} onChange={setValues} errors={errors} />
      <MediaPicker draft={media} disabled={submitting} />
      <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
        <Button variant="ghost" onClick={() => navigate('/brand/campaigns')} className="w-full sm:w-auto" disabled={submitting}>
          Cancel
        </Button>
        <Button variant="secondary" onClick={() => handle('draft')} className="w-full sm:w-auto" disabled={submitting}>
          {submitting ? 'Saving…' : 'Save draft'}
        </Button>
        <Button onClick={() => handle('publish')} className="w-full sm:w-auto" disabled={submitting}>
          {submitting ? 'Publishing…' : 'Publish'}
        </Button>
      </div>
    </div>
  );
}
