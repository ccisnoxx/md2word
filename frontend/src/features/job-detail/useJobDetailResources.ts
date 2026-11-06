import { computed } from "vue";
import { formatDateTime, getJobSourceFilename } from "@/utils/format";
import { documentJobRequestSnapshotForDisplay } from "@/utils/documentJobConfig";
import { readRecord, readString, readResourceSnapshot, versionLabel } from "./jobDetailFormat";
import type { JobDetailData } from "./useJobDetailData";

export function useJobDetailResources(
  data: Pick<JobDetailData, "job">
) {
  const { job } = data;

  const requestSnapshotPreview = computed(() => JSON.stringify(
    job.value ? documentJobRequestSnapshotForDisplay(job.value.request_snapshot, job.value.mode) : {},
    null,
    2,
  ));

  const sourceFilename = computed(() => (job.value ? getJobSourceFilename(job.value) : "-"));
  const translationQaReviewText = computed(() => {
    if (!job.value || job.value.translation_qa_status === "unreviewed") {
      return "尚未复核";
    }
    return `${job.value.translation_qa_reviewed_by || "-"} · ${formatDateTime(job.value.translation_qa_reviewed_at)}`;
  });

  const resourceSnapshot = computed(() => readResourceSnapshot(job.value?.request_snapshot.resources));
  const boundTemplate = computed(() => resourceSnapshot.value?.template || null);
  const boundTermRuleSet = computed(() => resourceSnapshot.value?.term_rule_set || null);
  const boundTranslationTermSet = computed(() => resourceSnapshot.value?.translation_term_set || null);
  const boundTranslationProfile = computed(() => resourceSnapshot.value?.translation_profile || null);
  const boundTemplateLabel = computed(() => {
    const bound = boundTemplate.value;
    return bound ? `${bound.resource_id}@${bound.version}` : job.value?.template_version_id || "-";
  });

  const boundTermRuleSetLabel = computed(() => {
    const bound = boundTermRuleSet.value;
    if (!bound) {
      const assets = readRecord(job.value?.request_snapshot.term_assets);
      return versionLabel(readString(assets?.term_rule_set_id), readString(assets?.term_rule_set_version));
    }
    return `${bound.resource_id}@${bound.version}`;
  });

  const boundTranslationTermSetLabel = computed(() => {
    const bound = boundTranslationTermSet.value;
    if (!bound) {
      const assets = readRecord(job.value?.request_snapshot.term_assets);
      const setId = readString(assets?.translation_term_set_id);
      const version = readString(assets?.translation_term_version) || job.value?.term_version_id || null;
      return versionLabel(setId, version);
    }
    return `${bound.set_id}@${bound.version}`;
  });

  const boundTranslationProfileLabel = computed(() => {
    const bound = boundTranslationProfile.value;
    if (!bound) {
      const profile = readRecord(job.value?.request_snapshot.translation_profile);
      return versionLabel(
        readString(profile?.translation_profile_id),
        readString(profile?.translation_profile_version),
      );
    }
    return `${bound.resource_id}@${bound.version}`;
  });

  const termRuleProposalVersionLabel = computed(() =>
    versionLabel(termRuleProposalSetId.value, termRuleProposalVersion.value),
  );

  const translationTermProposalVersionLabel = computed(() =>
    versionLabel(translationTermProposalSetId.value, translationTermProposalVersion.value),
  );

  const termRuleProposalSetId = computed(() => {
    const bound = boundTermRuleSet.value;
    if (bound) {
      return bound.resource_id;
    }
    const assets = readRecord(job.value?.request_snapshot.term_assets);
    return readString(assets?.term_rule_set_id);
  });

  const termRuleProposalVersion = computed(() => {
    const bound = boundTermRuleSet.value;
    if (bound) {
      return bound.version;
    }
    const assets = readRecord(job.value?.request_snapshot.term_assets);
    return readString(assets?.term_rule_set_version);
  });

  const translationTermProposalSetId = computed(() => {
    const bound = boundTranslationTermSet.value;
    if (bound) {
      return bound.set_id;
    }
    const assets = readRecord(job.value?.request_snapshot.term_assets);
    return readString(assets?.translation_term_set_id);
  });

  const translationTermProposalVersion = computed(() => {
    const bound = boundTranslationTermSet.value;
    if (bound) {
      return bound.version;
    }
    const assets = readRecord(job.value?.request_snapshot.term_assets);
    return readString(assets?.translation_term_version) || job.value?.term_version_id || null;
  });

  return {
    requestSnapshotPreview,
    sourceFilename,
    translationQaReviewText,
    boundTemplateLabel,
    boundTermRuleSetLabel,
    boundTranslationTermSetLabel,
    boundTranslationProfileLabel,
    termRuleProposalVersionLabel,
    translationTermProposalVersionLabel,
    termRuleProposalSetId,
    termRuleProposalVersion,
    translationTermProposalSetId,
    translationTermProposalVersion,
  };
}

export type JobDetailResources = ReturnType<typeof useJobDetailResources>;
