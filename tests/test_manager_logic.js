const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const bootstrapContext = {};
vm.runInNewContext(fs.readFileSync('plugin/bootstrap.js', 'utf8'), bootstrapContext);
const plugin = bootstrapContext.KindleZoteroImporter;
const maintainImportedAnnotations = plugin.maintainImportedAnnotations;

assert.equal(
  plugin.mergeComments('[r] this is a red note\n\nthis is a red note', ''),
  'this is a red note'
);
assert.equal(plugin.mergeComments('[o]', ''), '');
assert.equal(plugin.mergeComments('[citation] keep this', ''), '[citation] keep this');
assert.equal(
  plugin.commentForExistingAnnotation(
    { annotationComment: 'old note', annotationTags: [{ name: 'kindle-import' }] },
    'replacement note',
    'old note'
  ),
  'replacement note'
);
assert.equal(
  plugin.commentForExistingAnnotation(
    { annotationComment: 'old note\n\nmanual addition', annotationTags: [{ name: 'kindle-import' }] },
    'replacement note',
    'old note'
  ),
  'manual addition\n\nreplacement note'
);
assert.equal(
  plugin.commentForExistingAnnotation(
    { annotationComment: 'old first\n\nold second\n\nmanual addition', annotationTags: [{ name: 'kindle-import' }] },
    'new note',
    'old first\n\nold second'
  ),
  'manual addition\n\nnew note'
);
assert.equal(
  plugin.commentForExistingAnnotation(
    { annotationComment: 'manual note', annotationTags: [] },
    'imported note'
  ),
  'manual note\n\nimported note'
);

const base = {
  annotationText: 'forged its might, should be enough to discredit',
  annotationPosition: JSON.stringify({
    type: 'FragmentSelector',
    value: 'epubcfi(/6/12!/4/2/8,/1:1142,/1:1255)',
  }),
};
const extended = {
  annotationText: 'forged its might, should be enough to discredit, even in the eyes of philosophers',
  annotationPosition: JSON.stringify({
    type: 'FragmentSelector',
    value: 'epubcfi(/6/12!/4/2/8,/1:1142,/1:1300)',
  }),
};
assert.equal(plugin.areImportedDuplicates(base, extended), true);
assert.equal(
  plugin.areImportedDuplicates(base, {
    ...base,
    annotationPosition: JSON.stringify({
      type: 'FragmentSelector',
      value: 'epubcfi(/6/12!/4/2/8,/1:2000,/1:2050)',
    }),
  }),
  false
);
assert.equal(
  plugin.areImportedDuplicates(base, {
    ...base,
    annotationText: 'OCR-corrected text at the identical annotation position',
  }),
  true
);
assert.equal(
  plugin.areImportedDuplicates(
    {
      annotationText: 'A multiline PDF selection long enough to compare',
      annotationPosition: JSON.stringify({ pageIndex: 2, rects: [[10, 20, 100, 30]] }),
    },
    {
      annotationText: 'A multiline PDF selection long enough to compare with an extended ending',
      annotationPosition: JSON.stringify({ pageIndex: 2, rects: [[10, 20, 100, 30], [10, 40, 120, 50]] }),
    }
  ),
  true
);

const managerHtml = fs.readFileSync('plugin/manager.html', 'utf8');
const scripts = [...managerHtml.matchAll(/<script>([\s\S]*?)<\/script>/g)];
const managerContext = { TextEncoder };
vm.runInNewContext(scripts[0][1], managerContext);
const manager = managerContext.KindleManager;
manager.integratedPage = 1;
manager.integratedPageSize = 50;
const page = manager.paginate(Array.from({ length: 121 }, (_, index) => index), 'integratedPage', 'integratedPageSize');
assert.equal(page.totalPages, 3);
assert.deepEqual(Array.from(page.rows), Array.from({ length: 50 }, (_, index) => index + 50));

manager.mappingsPage = 99;
manager.mappingsPageSize = 50;
const finalPage = manager.paginate(Array.from({ length: 51 }, (_, index) => index), 'mappingsPage', 'mappingsPageSize');
assert.equal(manager.mappingsPage, 1);
assert.deepEqual(Array.from(finalPage.rows), [50]);

const collectorBatches = manager.collectorBatches('installation', Array.from(
  { length: 450 },
  (_, index) => ({ clipping_id_hash: String(index), text: 'x'.repeat(2000) })
));
assert.equal(collectorBatches.length, 3);
assert.ok(collectorBatches.every(batch => batch.length <= 200));
assert.ok(collectorBatches.every(batch => new TextEncoder().encode(
  JSON.stringify({ anonId: 'installation', data: batch })
).length <= 1500000));
assert.throws(
  () => manager.collectorBatches('installation', [{ text: 'x'.repeat(1500000) }]),
  /exceeds the collector request limit/
);

async function testRuntimeExtraction() {
  const writes = [];
  bootstrapContext.PathUtils = {
    profileDir: '/profile',
    join: (...parts) => parts.join('/').replaceAll('//', '/'),
    parent: path => path.slice(0, path.lastIndexOf('/')),
  };
  bootstrapContext.IOUtils = {
    makeDirectory: async () => {},
  };
  bootstrapContext.Zotero = {
    File: { putContentsAsync: async (path, text) => writes.push([path, text]) },
  };
  bootstrapContext.fetch = async url => ({ ok: true, text: async () => url });
  plugin.rootURI = 'jar:file:///kanzi.xpi!/';
  await plugin.ensureRuntime();
  assert.equal(plugin.runtimeProjectDir, '/profile/kanzi-runtime');
  assert.equal(writes.length, 13);
  assert.ok(writes.some(([path]) => path.endsWith('/src/kindle_zotero_importer/cli.py')));
}

async function testMaintenanceSweep() {
  const annotation = (id, text, end, comment = '') => ({
    id,
    parentItemID: 10,
    annotationText: text,
    annotationComment: comment,
    annotationPosition: JSON.stringify({
      type: 'FragmentSelector',
      value: `epubcfi(/6/12!/4/2/8,/1:795,/1:${end})`,
    }),
    saved: 0,
    erased: 0,
    saveTx: async function () { this.saved += 1; },
    eraseTx: async function () { this.erased += 1; },
  });
  const short = annotation(1, 'A progressive highlight long enough to compare', 994);
  const middle = annotation(2, 'A progressive highlight long enough to compare and then extended', 1093);
  const longest = annotation(
    3,
    'A progressive highlight long enough to compare and then extended to its final form',
    1141,
    '[r] useful note\n\nuseful note'
  );
  const separate = annotation(4, 'A progressive highlight long enough to compare', 2050);
  separate.annotationPosition = JSON.stringify({
    type: 'FragmentSelector',
    value: 'epubcfi(/6/12!/4/2/8,/1:2000,/1:2050)',
  });
  const emptyComment = annotation(5, 'A separate highlight with a null comment', 3050, null);
  emptyComment.annotationPosition = JSON.stringify({
    type: 'FragmentSelector',
    value: 'epubcfi(/6/12!/4/2/8,/1:3000,/1:3050)',
  });
  const results = { updatedComments: 0, removedDuplicates: 0 };

  await plugin.maintainImportedAnnotations([short, middle, longest, separate, emptyComment], false, results);

  assert.equal(results.removedDuplicates, 2);
  assert.deepEqual(Array.from(results.maintenanceDeletedIds), []);
  assert.equal(short.erased, 1);
  assert.equal(middle.erased, 1);
  assert.equal(longest.erased, 0);
  assert.equal(separate.erased, 0);
  assert.equal(emptyComment.saved, 0);
  assert.equal(longest.annotationComment, 'useful note');
  assert.equal(results.updatedComments, 1);
}

async function testWriterReconciliation() {
  let written = null;
  bootstrapContext.Zotero = {
    File: { putContentsAsync: async (_path, text) => { written = JSON.parse(text); } },
  };
  const plan = {
    annotations: [{ clipping_id: 'ok' }, { clipping_id: 'failed' }],
    all_annotations: [{ clipping_id: 'old' }, { clipping_id: 'ok' }, { clipping_id: 'failed' }],
  };
  await plugin.reconcileWriterState('/plan.json', plan, {
    failed: [{ clipping_id: 'failed' }, { clipping_id: 'maintenance' }],
    failedDeletionIds: ['delete-me'],
    maintenanceDeletedIds: ['old'],
  });
  assert.deepEqual(Array.from(written.write_failed_ids), ['failed']);
  assert.deepEqual(Array.from(written.annotations, entry => entry.clipping_id), ['ok']);
  assert.deepEqual(Array.from(written.all_annotations, entry => entry.clipping_id), ['ok']);
  assert.equal(written.annotation_count, 1);
  assert.deepEqual(Array.from(written.delete_failed_ids), ['delete-me']);
}

async function testDeletionFailureIsRetried() {
  bootstrapContext.Zotero = { logError: () => {} };
  const annotation = {
    annotationTags: [{ name: 'kindle-id:delete-me' }],
    eraseTx: async () => { throw new Error('locked'); },
  };
  plugin.collectImportedAnnotations = async () => [annotation];
  plugin.maintainImportedAnnotations = async () => {};
  const results = await plugin.writeAnnotations({
    format: 'kindle-zotero-importer.zotero-writer-plan.v1',
    annotations: [],
    deletions: ['delete-me'],
  }, false);
  assert.deepEqual(Array.from(results.failedDeletionIds), ['delete-me']);
  assert.equal(results.failed.length, 1);
}

async function testMaintenanceDeletionIsNotRepeated() {
  bootstrapContext.Zotero = { logError: () => {} };
  const annotation = {
    annotationTags: [{ name: 'kindle-id:already-deleted' }],
    eraseTx: async () => { throw new Error('must not be called again'); },
  };
  plugin.collectImportedAnnotations = async () => [annotation];
  plugin.maintainImportedAnnotations = async (_annotations, _dryRun, results) => {
    results.maintenanceDeletedIds.push('already-deleted');
  };
  const results = await plugin.writeAnnotations({
    format: 'kindle-zotero-importer.zotero-writer-plan.v1',
    annotations: [],
    deletions: ['already-deleted'],
  }, false);
  assert.deepEqual(Array.from(results.failedDeletionIds), []);
  assert.equal(results.failed.length, 0);
}

async function testSameClippingDuplicateKeepsLogicalHistoryAndDeletesSurvivor() {
  bootstrapContext.Zotero = { logError: () => {} };
  const active = {
    parentItemID: 10,
    annotationText: 'The longer OCR-corrected duplicate annotation text',
    annotationComment: '',
    annotationPosition: JSON.stringify({ pageIndex: 1, rects: [[1, 2, 3, 4]] }),
    annotationTags: [{ name: 'kindle-import' }, { name: 'kindle-id:same' }],
    erased: 0,
    eraseTx: async function () { this.erased += 1; },
  };
  const duplicate = {
    ...active,
    annotationText: 'The duplicate annotation text',
    annotationTags: [{ name: 'kindle-import' }, { name: 'kindle-id:same' }],
    erased: 0,
    eraseTx: async function () { this.erased += 1; },
  };
  let collection = 0;
  plugin.collectImportedAnnotations = async () => (++collection === 1 ? [active, duplicate] : [active]);
  plugin.maintainImportedAnnotations = maintainImportedAnnotations;
  const results = await plugin.writeAnnotations({
    format: 'kindle-zotero-importer.zotero-writer-plan.v1',
    annotations: [],
    deletions: ['same'],
  }, false);
  assert.deepEqual(Array.from(results.maintenanceDeletedIds), []);
  assert.equal(duplicate.erased, 1);
  assert.equal(active.erased, 1);
  assert.equal(results.deletedForIncremental, 1);
  assert.equal(results.failed.length, 0);
}

async function testEnumerationFailurePersistsAllDeletions() {
  bootstrapContext.Zotero = { logError: () => {} };
  plugin.collectImportedAnnotations = async () => { throw new Error('enumeration failed'); };
  const results = await plugin.writeAnnotations({
    format: 'kindle-zotero-importer.zotero-writer-plan.v1',
    annotations: [],
    deletions: ['retry-deletion'],
  }, false);
  assert.deepEqual(Array.from(results.failedDeletionIds), ['retry-deletion']);
  assert.equal(results.failed[0].clipping_id, 'maintenance');
}

async function testReplacementFailurePreservesOldAnnotationAndDeletionRetry() {
  const old = {
    annotationTags: [{ name: 'kindle-id:replacement' }],
    erased: 0,
    eraseTx: async function () { this.erased += 1; },
  };
  bootstrapContext.Zotero = {
    logError: () => {},
    Items: { get: () => null },
  };
  plugin.collectImportedAnnotations = async () => [old];
  plugin.maintainImportedAnnotations = async () => {};
  const results = await plugin.writeAnnotations({
    format: 'kindle-zotero-importer.zotero-writer-plan.v1',
    annotations: [{ clipping_id: 'replacement', attachment_item_id: 99, annotation: {} }],
    deletions: ['replacement'],
  }, false);
  assert.equal(old.erased, 0);
  assert.deepEqual(Array.from(results.failedDeletionIds), ['replacement']);
  assert.equal(results.failed[0].clipping_id, 'replacement');
}

testRuntimeExtraction()
  .then(testMaintenanceSweep)
  .then(testWriterReconciliation)
  .then(testDeletionFailureIsRetried)
  .then(testMaintenanceDeletionIsNotRepeated)
  .then(testSameClippingDuplicateKeepsLogicalHistoryAndDeletesSurvivor)
  .then(testEnumerationFailurePersistsAllDeletions)
  .then(testReplacementFailurePreservesOldAnnotationAndDeletionRetry)
  .then(() => {
  console.log('manager and annotation logic ok');
}).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
