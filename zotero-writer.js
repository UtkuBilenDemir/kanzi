// Run in Zotero via Tools > Developer > Run JavaScript.
// Set PLAN_PATH to the generated import-plan.final.json path.
// Keep DRY_RUN=true until the preview output looks correct.

const PLAN_PATH = "/home/user/Library/Mobile Documents/iCloud~md~obsidian/Documents/rhizome/06_projects/UTI/kindle-zotero-importer/import-plan.final.json";
const DRY_RUN = false;

const text = await Zotero.File.getContentsAsync(PLAN_PATH);
const plan = JSON.parse(text);

if (plan.format !== "kindle-zotero-importer.zotero-writer-plan.v1") {
  throw new Error(`Unsupported plan format: ${plan.format}`);
}

const results = {
  dryRun: DRY_RUN,
  total: plan.annotations.length,
  created: 0,
  skippedExisting: 0,
  updatedComments: 0,
  removedDuplicates: 0,
  failed: [],
  preview: [],
};

const existingByAttachment = new Map();

function normalizePosition(position) {
  if (!position) {
    return "";
  }
  if (typeof position === "string") {
    try {
      return JSON.stringify(JSON.parse(position));
    } catch (_error) {
      return position;
    }
  }
  return JSON.stringify(position);
}

function annotationFingerprint(annotation) {
  return `${annotation.text || ""}\u0000${normalizePosition(annotation.position)}`;
}

function existingAnnotationFingerprint(annotation) {
  return `${annotation.annotationText || ""}\u0000${normalizePosition(annotation.annotationPosition)}`;
}

async function getExistingAnnotations(attachment) {
  if (!existingByAttachment.has(attachment.id)) {
    const annotations = attachment.getAnnotations ? attachment.getAnnotations() : [];
    const byFingerprint = new Map();

    for (const annotation of annotations) {
      const fingerprint = existingAnnotationFingerprint(annotation);
      const kept = byFingerprint.get(fingerprint);
      if (!kept) {
        byFingerprint.set(fingerprint, annotation);
        continue;
      }

      const keptHasComment = Boolean(kept.annotationComment);
      const currentHasComment = Boolean(annotation.annotationComment);
      const duplicate = keptHasComment || !currentHasComment ? annotation : kept;
      const replacement = duplicate === annotation ? kept : annotation;

      byFingerprint.set(fingerprint, replacement);
      if (!DRY_RUN) {
        await duplicate.eraseTx();
      }
      results.removedDuplicates += 1;
    }

    existingByAttachment.set(attachment.id, byFingerprint);
  }
  return existingByAttachment.get(attachment.id);
}

function mergeComments(existingComment, newComment) {
  const seen = new Set();
  const merged = [];
  for (const comment of [existingComment, newComment]) {
    for (const part of String(comment || "").split(/\n\s*\n/)) {
      const cleaned = part.trim();
      if (!cleaned || seen.has(cleaned)) {
        continue;
      }
      seen.add(cleaned);
      merged.push(cleaned);
    }
  }
  return merged.join("\n\n");
}

for (const entry of plan.annotations) {
  try {
    const attachment = Zotero.Items.get(entry.attachment_item_id);
    if (!attachment) {
      throw new Error(`Attachment not found: ${entry.attachment_item_id}`);
    }

    const annotation = {
      key: Zotero.DataObjectUtilities.generateKey(),
      ...entry.annotation,
    };
    if (!annotation.sortIndex) {
      delete annotation.sortIndex;
    }

    const existingAnnotations = await getExistingAnnotations(attachment);
    const fingerprint = annotationFingerprint(annotation);
    const existingAnnotation = existingAnnotations.get(fingerprint);
    if (existingAnnotation) {
      const mergedComment = mergeComments(existingAnnotation.annotationComment, annotation.comment);
      if (mergedComment && existingAnnotation.saveTx && existingAnnotation.annotationComment !== mergedComment) {
        existingAnnotation.annotationComment = mergedComment;
        if (!DRY_RUN) {
          await existingAnnotation.saveTx();
        }
        results.updatedComments += 1;
      }
      results.skippedExisting += 1;
      continue;
    }

    if (DRY_RUN) {
      results.preview.push({
        clipping_id: entry.clipping_id,
        attachment_item_id: entry.attachment_item_id,
        type: annotation.type,
        text: annotation.text.slice(0, 120),
        pageLabel: annotation.pageLabel,
        sortIndex: annotation.sortIndex,
        position: annotation.position,
      });
      continue;
    }

    await Zotero.Annotations.saveFromJSON(attachment, annotation);
    existingAnnotations.set(fingerprint, {
      annotationComment: annotation.comment || "",
      annotationPosition: annotation.position,
      annotationText: annotation.text || "",
    });
    results.created += 1;
  } catch (error) {
    results.failed.push({
      clipping_id: entry.clipping_id,
      attachment_item_id: entry.attachment_item_id,
      message: String(error),
    });
  }
}

return JSON.stringify(results, null, 2);
