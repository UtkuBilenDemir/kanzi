const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const bootstrapContext = {};
vm.runInNewContext(fs.readFileSync('plugin/bootstrap.js', 'utf8'), bootstrapContext);
const plugin = bootstrapContext.Kanzi;
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
assert.equal(plugin.countClippingsForTitle({ clippings: [
  { title: 'Shared title' },
  { title: 'Shared title' },
  { title: 'Different title' },
] }, 'Shared title'), 2);

manager.data = {
  clippings: { clippings: [
    { id: 'h1', title: 'Shared title', kind: 'highlight', text: 'first' },
    { id: 'n1', title: 'Shared title', kind: 'note', text: 'note' },
    { id: 'h2', title: 'Shared title', kind: 'highlight', text: 'second' },
  ] },
  matches: { matches: [{
    clipping_title: 'Shared title',
    clipping_count: 3,
    status: 'matched',
    candidates: [],
  }] },
  generatedOverrides: { overrides: [] },
  positionedPlan: { items: [{
    clipping: { id: 'h2', title: 'Shared title', kind: 'highlight', text: 'second' },
    status: 'pdf-text-not-found',
    problems: ['not found'],
  }] },
  finalPlan: { all_annotations: [] },
  persistentOverrides: { overrides: [] },
};
const conflictRows = manager.conflictRows();
assert.equal(conflictRows.length, 1);
assert.equal(conflictRows[0].count, 3);
assert.equal(conflictRows[0].clippings.length, 3);
assert.equal(conflictRows[0].highlights, 2);
assert.equal(conflictRows[0].notes, 1);

manager.sortState.conflicts = { column: 'count', direction: 'desc' };
const sortedRows = manager.sortRows(
  [{ title: 'small', count: 2 }, { title: 'large', count: 20 }, { title: 'middle', count: 10 }],
  'conflicts',
  { count: row => row.count }
);
assert.deepEqual(Array.from(sortedRows, row => row.title), ['large', 'middle', 'small']);
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

async function testPythonPathRecovery() {
  bootstrapContext.Services = { appinfo: { OS: 'Darwin' } };
  bootstrapContext.IOUtils = {
    exists: async path => path === '/opt/homebrew/opt/python@3.13/bin/python3.13',
  };
  assert.equal(
    await plugin.resolvePythonPath('/opt/homebrew/bin/python3'),
    '/opt/homebrew/opt/python@3.13/bin/python3.13'
  );
  bootstrapContext.IOUtils.exists = async path => path === '/custom/python3';
  assert.equal(await plugin.resolvePythonPath('/custom/python3'), '/custom/python3');

  bootstrapContext.Services.appinfo.OS = 'WINNT';
  const windowsEnvironment = {
    LOCALAPPDATA: 'C:\\Users\\test\\AppData\\Local',
    ProgramFiles: 'C:\\Program Files',
    'ProgramFiles(x86)': 'C:\\Program Files (x86)',
    USERPROFILE: 'C:\\Users\\test',
    SystemDrive: 'C:',
    PATH: 'C:\\Tools\\Python;C:\\Windows\\System32',
  };
  plugin.getEnvironmentVariable = name => windowsEnvironment[name] || '';
  const expected = 'C:\\Users\\test\\AppData\\Local\\Programs\\Python\\Python313\\python.exe';
  bootstrapContext.IOUtils.exists = async path => path === expected;
  assert.equal(await plugin.resolvePythonPath('python'), expected);
  assert.ok(plugin.getWindowsPythonCandidates('python').includes('C:\\Tools\\Python\\python.exe'));
}

async function testMaintenanceSweep() {
  const annotation = (id, text, end, comment = '') => ({
    id,
    parentItemID: 10,
    annotationText: text,
    annotationComment: comment,
    annotationTags: [{ name: 'kindle-import' }],
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
  const manual = annotation(6, 'A progressive highlight long enough to compare', 994, '[r] manual note');
  manual.annotationTags = [];
  const results = { updatedComments: 0, removedDuplicates: 0 };

  await plugin.maintainImportedAnnotations([short, middle, longest, separate, emptyComment, manual], false, results);

  assert.equal(results.removedDuplicates, 2);
  assert.deepEqual(Array.from(results.maintenanceDeletedIds), []);
  assert.equal(short.erased, 1);
  assert.equal(middle.erased, 1);
  assert.equal(longest.erased, 0);
  assert.equal(separate.erased, 0);
  assert.equal(emptyComment.saved, 0);
  assert.equal(manual.erased, 0);
  assert.equal(manual.saved, 0);
  assert.equal(longest.annotationComment, 'useful note');
  assert.equal(results.updatedComments, 1);
}

async function testMaintenanceRequiresApproval() {
  const annotation = (id, comment) => ({
    id,
    parentItemID: 10,
    annotationText: `Distinct annotation ${id}`,
    annotationComment: comment,
    annotationPosition: JSON.stringify({ pageIndex: id, rects: [[1, 2, 3, 4]] }),
    annotationTags: [{ name: 'kindle-import' }],
    saved: 0,
    saveTx: async function () { this.saved += 1; },
  });
  const approved = annotation(21, '[r] duplicate note\n\nduplicate note');
  const declined = annotation(22, '[r] leave this as written');
  const results = { updatedComments: 0, removedDuplicates: 0 };
  await plugin.maintainImportedAnnotations(
    [approved, declined],
    false,
    results,
    ['maintenance:comment:21']
  );
  assert.equal(approved.annotationComment, 'duplicate note');
  assert.equal(approved.saved, 1);
  assert.equal(declined.annotationComment, '[r] leave this as written');
  assert.equal(declined.saved, 0);
}

async function testReviewModelCoversEveryMutationCategory() {
  const originalZotero = bootstrapContext.Zotero;
  const originalCollect = plugin.collectImportedAnnotations;
  let attachmentAnnotations = [];
  const attachment = { id: 11, getAnnotations: () => attachmentAnnotations };
  const items = {
    1: { id: 1, key: 'SOURCE', libraryID: 1 },
    2: { id: 2, key: 'SAME', libraryID: 1 },
    3: { id: 3, key: 'CROSS', libraryID: 2 },
    11: attachment,
  };
  bootstrapContext.Zotero = { Items: { get: id => items[id] || null } };
  const imported = {
    id: 31,
    parentItemID: 11,
    annotationText: 'Imported text',
    annotationComment: '[r] note\n\nnote',
    annotationPosition: JSON.stringify({ pageIndex: 1, rects: [[1, 2, 3, 4]] }),
    annotationTags: [{ name: 'kindle-import' }],
  };
  const entry = {
    clipping_id: 'new',
    clipping_title: 'Source book',
    attachment_item_id: 11,
    parent_item_id: 1,
    parent_title: 'Source item',
    citation_key: 'source2020',
    library_id: 1,
    annotation: { text: 'New highlight', pageLabel: '4', color: '#ffd400', comment: '' },
    related_items: [
      { item_id: 2, key: 'SAME', title: 'Same library', citation_key: 'same2020', library_id: 1, link: 'zotero://select/library/items/SAME' },
      { item_id: 3, key: 'CROSS', title: 'Other library', citation_key: 'cross2020', library_id: 2, link: 'zotero://select/groups/2/items/CROSS' },
    ],
  };
  try {
    const historicalEntry = {
      ...entry,
      clipping_id: 'history',
      ambiguous_citekeys: ['duplicate2020'],
      annotation: { ...entry.annotation, text: 'Historical highlight' },
    };
    const historicalAnnotation = {
      annotationComment: '',
      annotationTags: [{ name: 'kindle-import' }, { name: 'kindle-id:history' }],
    };
    attachmentAnnotations = [historicalAnnotation];
    plugin.collectImportedAnnotations = async () => [imported];
    const review = await plugin.buildReviewModel({
      annotations: [entry],
      all_annotations: [entry, historicalEntry],
      deletion_candidates: [
        { clipping_id: 'old', replacement_clipping_id: 'new', reason: 'source-revision', blocked: false },
        { clipping_id: 'blocked', replacement_clipping_id: 'missing', reason: 'source-revision', blocked: true },
      ],
    }, null);
    assert.equal(review.annotations.length, 1);
    assert.equal(review.maintenance.length, 1);
    assert.equal(review.deletions.length, 2);
    assert.equal(review.relations.length, 1);
    assert.equal(review.commentLinks.length, 2);
    assert.equal(review.warnings.length, 1);
    assert.equal(review.deletions.filter(operation => operation.blocked).length, 1);
    assert.ok(review.commentLinks[0].action.includes('unavailable across libraries'));
    assert.equal(
      review.commentLinks.find(operation => operation.clipping_id === 'new').depends_on_clipping_id,
      'new'
    );
    assert.ok(review.annotations[0].destination.label.includes('Source item'));
  } finally {
    bootstrapContext.Zotero = originalZotero;
    plugin.collectImportedAnnotations = originalCollect;
  }
}

async function testUnchangedPlanProducesNoOperations() {
  const originalZotero = bootstrapContext.Zotero;
  const originalCollect = plugin.collectImportedAnnotations;
  const position = { pageIndex: 1, rects: [[1, 2, 3, 4]] };
  const existing = {
    annotationText: 'Already present',
    annotationPosition: JSON.stringify(position),
    annotationComment: 'note',
    annotationColor: '#ffd400',
    annotationSortIndex: '0001',
    annotationTags: [{ name: 'kindle-import' }, { name: 'kindle-id:same' }],
  };
  bootstrapContext.Zotero = {
    Items: { get: id => id === 11 ? { id: 11, getAnnotations: () => [existing] } : null },
  };
  plugin.collectImportedAnnotations = async () => [];
  try {
    const review = await plugin.buildReviewModel({
      annotations: [{
        clipping_id: 'same',
        attachment_item_id: 11,
        annotation: {
          text: 'Already present',
          position,
          comment: 'note',
          color: '#ffd400',
          sortIndex: '0001',
          tags: [{ name: 'kindle-import' }, { name: 'kindle-id:same' }],
        },
      }],
      all_annotations: [],
      deletion_candidates: [],
    });
    assert.equal(review.operation_count, 0);
    assert.deepEqual(Array.from(review.annotations), []);
  } finally {
    bootstrapContext.Zotero = originalZotero;
    plugin.collectImportedAnnotations = originalCollect;
  }
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

async function testSuccessfulReplacementCreatesBeforeDeletingOldAnnotation() {
  const originalZotero = bootstrapContext.Zotero;
  const originalCollect = plugin.collectImportedAnnotations;
  const originalMaintain = plugin.maintainImportedAnnotations;
  const old = {
    parentItemID: 11,
    annotationText: 'A progressive highlight long enough to compare',
    annotationPosition: JSON.stringify({
      type: 'FragmentSelector',
      value: 'epubcfi(/6/12!/4/2/8,/1:10,/1:60)',
    }),
    annotationComment: '',
    annotationTags: [{ name: 'kindle-import' }, { name: 'kindle-id:old' }],
    erased: 0,
    eraseTx: async function () { this.erased += 1; },
  };
  const attachment = { id: 11, getAnnotations: () => [old] };
  let created = 0;
  bootstrapContext.Zotero = {
    Items: { get: id => id === 11 ? attachment : null },
    DataObjectUtilities: { generateKey: () => 'NEWKEY01' },
    Annotations: { saveFromJSON: async () => { created += 1; } },
    logError: () => {},
  };
  plugin.collectImportedAnnotations = async () => [old];
  plugin.maintainImportedAnnotations = async () => {};
  try {
    const results = await plugin.writeAnnotations({
      format: 'kindle-zotero-importer.zotero-writer-plan.v1',
      annotations: [{
        clipping_id: 'new',
        attachment_item_id: 11,
        annotation: {
          text: 'A progressive highlight long enough to compare and then extend',
          position: {
            type: 'FragmentSelector',
            value: 'epubcfi(/6/12!/4/2/8,/1:10,/1:90)',
          },
          comment: '',
          tags: [{ name: 'kindle-import' }, { name: 'kindle-id:new' }],
        },
      }],
      all_annotations: [],
      deletions: ['old'],
      deletion_candidates: [{ clipping_id: 'old', replacement_clipping_id: 'new' }],
    }, false);
    assert.equal(created, 1);
    assert.equal(old.erased, 1);
    assert.deepEqual(Array.from(results.successfulClippingIds), ['new']);
    assert.deepEqual(Array.from(results.successfulDeletionIds), ['old']);
  } finally {
    bootstrapContext.Zotero = originalZotero;
    plugin.collectImportedAnnotations = originalCollect;
    plugin.maintainImportedAnnotations = originalMaintain;
  }
}

async function testCitekeyRelationsAreBidirectionalAndAdditive() {
  const originalZotero = bootstrapContext.Zotero;
  const originalCollect = plugin.collectImportedAnnotations;
  const originalMaintain = plugin.maintainImportedAnnotations;
  const item = (id, key) => ({
    id,
    key,
    related: new Set(),
    saved: 0,
    addRelatedItem(other) {
      if (this.related.has(other.key)) return false;
      this.related.add(other.key);
      return true;
    },
    async save(options) {
      assert.equal(options.skipDateModifiedUpdate, true);
      this.saved += 1;
    },
  });
  const source = item(1, 'SOURCE01');
  const target = item(2, 'TARGET02');
  bootstrapContext.Zotero = {
    Items: { get: id => id === 1 ? source : id === 2 ? target : id === 11 ? attachment : null },
    DB: { executeTransaction: async callback => callback() },
    logError: () => {},
  };
  const entries = [
    {
      clipping_id: 'history-1',
      parent_item_id: 1,
      attachment_item_id: 11,
      related_items: [{ item_id: 2, key: 'TARGET02', citation_key: 'target2020', link: 'zotero://select/library/items/TARGET02' }],
    },
    {
      parent_item_id: 1,
      related_items: [{ item_id: 2, key: 'TARGET02', citation_key: 'target2020', link: 'zotero://select/library/items/TARGET02' }],
    },
  ];
  const existingAnnotation = {
    annotationComment: 'an old note',
    annotationTags: [{ name: 'kindle-id:history-1' }],
    saved: 0,
    saveTx: async function () { this.saved += 1; },
  };
  const attachment = { getAnnotations: () => [existingAnnotation] };
  const results = {
    relationsAdded: 0,
    relationsSkipped: 0,
    relationsPlanned: 0,
    relationFailures: [],
  };
  try {
    plugin.collectImportedAnnotations = async () => [];
    plugin.maintainImportedAnnotations = async () => {};
    const writerResults = await plugin.writeAnnotations({
      format: 'kindle-zotero-importer.zotero-writer-plan.v1',
      annotations: [],
      all_annotations: entries,
      deletions: [],
    }, false);
    assert.deepEqual(Array.from(source.related), ['TARGET02']);
    assert.deepEqual(Array.from(target.related), ['SOURCE01']);
    assert.equal(source.saved, 1);
    assert.equal(target.saved, 1);
    assert.equal(writerResults.relationsAdded, 1);
    assert.equal(writerResults.relationFailures.length, 0);
    assert.equal(writerResults.commentLinksAdded, 1);
    assert.ok(existingAnnotation.annotationComment.includes(
      'Related: @target2020 zotero://select/library/items/TARGET02'
    ));
    assert.equal(existingAnnotation.saved, 1);

    await plugin.addRelatedItemRelations(entries, false, results);
    assert.equal(source.saved, 1);
    assert.equal(target.saved, 1);
    assert.equal(results.relationsSkipped, 1);
  } finally {
    bootstrapContext.Zotero = originalZotero;
    plugin.collectImportedAnnotations = originalCollect;
    plugin.maintainImportedAnnotations = originalMaintain;
  }
}

async function testCrossLibraryRelationUsesCommentLinkOnly() {
  const originalZotero = bootstrapContext.Zotero;
  const originalCollect = plugin.collectImportedAnnotations;
  const originalMaintain = plugin.maintainImportedAnnotations;
  const source = {
    id: 1,
    key: 'SOURCE01',
    libraryID: 1,
    saved: 0,
    addRelatedItem: () => { throw new Error('must not add a cross-library relation'); },
    save: async function () { this.saved += 1; },
  };
  const target = {
    id: 2,
    key: 'TARGET02',
    libraryID: 2,
    saved: 0,
    addRelatedItem: () => { throw new Error('must not add a cross-library relation'); },
    save: async function () { this.saved += 1; },
  };
  const existingAnnotation = {
    annotationComment: '',
    annotationTags: [{ name: 'kindle-import' }, { name: 'kindle-id:history-cross' }],
    saved: 0,
    saveTx: async function () { this.saved += 1; },
  };
  const attachment = { id: 11, getAnnotations: () => [existingAnnotation] };
  bootstrapContext.Zotero = {
    Items: { get: id => id === 1 ? source : id === 2 ? target : id === 11 ? attachment : null },
    DB: { executeTransaction: async callback => callback() },
    logError: () => {},
  };
  plugin.collectImportedAnnotations = async () => [existingAnnotation];
  plugin.maintainImportedAnnotations = async () => {};
  try {
    const results = await plugin.writeAnnotations({
      format: 'kindle-zotero-importer.zotero-writer-plan.v1',
      annotations: [],
      all_annotations: [{
        clipping_id: 'history-cross',
        parent_item_id: 1,
        attachment_item_id: 11,
        related_items: [{ item_id: 2, key: 'TARGET02', citation_key: 'target2020', link: 'zotero://select/groups/2/items/TARGET02' }],
      }],
      deletions: [],
    }, false);
    assert.equal(results.relationsAdded, 0);
    assert.equal(results.relationsUnavailable, 1);
    assert.equal(source.saved, 0);
    assert.equal(target.saved, 0);
    assert.equal(results.commentLinksAdded, 1);
    assert.ok(existingAnnotation.annotationComment.includes('zotero://select/groups/2/items/TARGET02'));
  } finally {
    bootstrapContext.Zotero = originalZotero;
    plugin.collectImportedAnnotations = originalCollect;
    plugin.maintainImportedAnnotations = originalMaintain;
  }
}

function testPendingReviewGrouping() {
  const groups = manager.groupPendingAnnotations([
    { clipping_id: 'a1', clipping_title: 'Dune (Frank Herbert)', citation_key: 'herbert2020', annotation: { text: 'spice', pageLabel: '12', color: '#ffd400' } },
    { clipping_id: 'a2', clipping_title: 'Dune (Frank Herbert)', citation_key: 'herbert2020', annotation: { text: 'worm', pageLabel: '', color: '#ff6666' } },
    { clipping_id: 'b1', clipping_title: 'Unknown Book', citation_key: '', annotation: { text: 'mystery', pageLabel: '', color: '#ffd400' } },
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].items.length, 2);
  assert.equal(groups[0].citationKey, 'herbert2020');
  assert.equal(groups[1].items.length, 1);
  assert.deepEqual(manager.groupPendingAnnotations([]), []);
}

function testFilterPlanForSelection() {
  const plan = {
    annotations: [{ clipping_id: 'keep' }, { clipping_id: 'skip' }],
    all_annotations: [{ clipping_id: 'old' }, { clipping_id: 'keep' }, { clipping_id: 'skip' }],
  };
  const previous = { deferred_clipping_ids: ['older'] };
  const filtered = plugin.filterPlanForSelection(plan, ['keep', 'skip'], ['keep'], previous);
  assert.deepEqual(Array.from(filtered.annotations, a => a.clipping_id), ['keep']);
  assert.deepEqual(Array.from(filtered.all_annotations, a => a.clipping_id), ['old', 'keep']);
  assert.deepEqual(Array.from(filtered.deferred_clipping_ids), ['older', 'skip']);
  // Original plan is not mutated.
  assert.equal(plan.annotations.length, 2);
  const all = plugin.filterPlanForSelection(plan, ['keep', 'skip'], ['keep', 'skip'], previous);
  assert.equal(all.annotations.length, 2);
  assert.equal(all.all_annotations.length, 3);
  assert.deepEqual(Array.from(all.deferred_clipping_ids), ['older']);

  const priorAnnotation = { clipping_id: 'skip', annotation: { text: 'existing' } };
  const preserved = plugin.filterPlanForSelection(
    plan,
    ['keep', 'skip'],
    ['keep'],
    { all_annotations: [priorAnnotation] }
  );
  assert.equal(preserved.all_annotations.find(a => a.clipping_id === 'skip'), priorAnnotation);

  const deferred = plugin.deferPendingPlan(
    { all_annotations: [{ clipping_id: 'old' }], deferred_clipping_ids: ['earlier'] },
    plan,
    ['keep', 'skip']
  );
  assert.deepEqual(Array.from(deferred.deferred_clipping_ids), ['earlier', 'keep', 'skip']);
  assert.deepEqual(Array.from(deferred.all_annotations, a => a.clipping_id), ['old']);
  const deferredDeletion = plugin.deferPendingPlan(
    { all_annotations: [{ clipping_id: 'old' }] },
    { deletion_candidates: [{ clipping_id: 'old', replacement_clipping_id: 'new' }] },
    ['new']
  );
  assert.equal(deferredDeletion.pending_deletion_candidates[0].replacement_clipping_id, 'new');

  const replacementPlan = {
    annotations: [{ clipping_id: 'new' }],
    all_annotations: [{ clipping_id: 'new' }],
    deletions: ['old'],
    deletion_candidates: [{ clipping_id: 'old', replacement_clipping_id: 'new', blocked: false }],
  };
  const withoutReplacement = plugin.filterPlanForSelection(
    replacementPlan,
    ['new'],
    [],
    { all_annotations: [{ clipping_id: 'old' }] }
  );
  assert.deepEqual(Array.from(withoutReplacement.deletion_candidates), []);
  assert.deepEqual(Array.from(withoutReplacement.deletions), []);
  assert.equal(withoutReplacement.pending_deletion_candidates.length, 1);
  const withReplacement = plugin.filterPlanForSelection(
    replacementPlan,
    ['new'],
    ['new'],
    { all_annotations: [{ clipping_id: 'old' }] }
  );
  assert.equal(withReplacement.deletion_candidates.length, 1);

  const relationPlan = {
    annotations: [{ clipping_id: 'new' }],
    all_annotations: [{
      clipping_id: 'new',
      parent_item_id: 1,
      related_items: [{ item_id: 2 }],
    }],
    deletion_candidates: [],
  };
  const relationOnly = plugin.filterPlanForSelection(
    relationPlan,
    ['new'],
    [],
    { all_annotations: [] },
    [],
    ['relation:1:2']
  );
  assert.deepEqual(Array.from(relationOnly.annotations), []);
  assert.equal(relationOnly.all_annotations.length, 1);

  const linkedEntry = {
    clipping_id: 'linked',
    annotation: { comment: 'Kindle note\n\nRelated: @target zotero://select/library/items/TARGET' },
    related_items: [{ citation_key: 'target', link: 'zotero://select/library/items/TARGET' }],
  };
  const withoutLink = plugin.filterPlanForSelection(
    { annotations: [linkedEntry], all_annotations: [linkedEntry], deletion_candidates: [] },
    ['linked'],
    ['linked'],
    null,
    [],
    ['annotation:linked']
  );
  assert.equal(withoutLink.annotations[0].annotation.comment, 'Kindle note');
  const withLink = plugin.filterPlanForSelection(
    { annotations: [linkedEntry], all_annotations: [linkedEntry], deletion_candidates: [] },
    ['linked'],
    ['linked'],
    null,
    [],
    ['annotation:linked', 'comment-link:linked']
  );
  assert.ok(withLink.annotations[0].annotation.comment.includes('Related: @target'));
}

function testTitleCountsAreAuthoritative() {
  manager.data = {
    clippings: { clippings: [
      { id: 'h1', title: 'Shared title', kind: 'highlight', text: 'first' },
      { id: 'h2', title: 'Shared title', kind: 'highlight', text: 'second' },
      { id: 'h3', title: 'Shared title', kind: 'highlight', text: 'third' },
    ] },
    matches: { matches: [{
      clipping_title: 'Shared title',
      clipping_count: 99,
      status: 'ambiguous',
      candidates: [{ citation_key: 'shared2020', key: '', item_id: 1, title: 'Shared', score: 0.9 }],
    }] },
    generatedOverrides: { overrides: [{
      clipping_title: 'Shared title',
      review: { status: 'review', clipping_count: 1 },
      candidates: [],
    }] },
    positionedPlan: { items: [{
      clipping: { id: 'h1', title: 'Shared title', kind: 'highlight', text: 'first' },
      status: 'pdf-text-not-found',
      problems: ['not found'],
    }] },
    finalPlan: { all_annotations: [] },
    persistentOverrides: { overrides: [] },
  };
  const rows = manager.conflictRows();
  assert.equal(rows.length, 1);
  // Source has 3 clippings; misleading match (99) and override (1) counts must not win.
  assert.equal(rows[0].count, 3);
  assert.equal(rows[0].clippings.length, 3);
  // Only 1 of 3 has position problems.
  assert.deepEqual(manager.conflictAffected(rows[0]), { failed: 1, total: 3 });

  // Without clippings.json, fall back to conflict counts.
  manager.data = {
    clippings: null,
    matches: { matches: [{
      clipping_title: 'Lonely title',
      clipping_count: 5,
      status: 'ambiguous',
      candidates: [],
    }] },
    generatedOverrides: { overrides: [] },
    positionedPlan: { items: [] },
    finalPlan: { all_annotations: [] },
    persistentOverrides: { overrides: [] },
  };
  const fallback = manager.conflictRows();
  assert.equal(fallback.length, 1);
  assert.equal(fallback[0].count, 5);
}

function testMappedTargetAndDiscardedClips() {
  manager.data = {
    clippings: { clippings: [
      { id: 'h1', title: 'Mapped title', kind: 'highlight', text: 'first' },
      { id: 'n1', title: 'Mapped title', kind: 'note', text: 'standalone note' },
    ] },
    matches: { matches: [{
      clipping_title: 'Mapped title',
      clipping_count: 2,
      status: 'matched',
      candidates: [{ citation_key: 'mapped2020', key: '', item_id: 7, title: 'Mapped', score: 1 }],
    }] },
    generatedOverrides: { overrides: [] },
    positionedPlan: { items: [
      { clipping: { id: 'h1', title: 'Mapped title', kind: 'highlight', text: 'first' }, status: 'pdf-text-not-found', problems: ['pdf-text-not-found'] },
      { clipping: { id: 'n1', title: 'Mapped title', kind: 'note', text: 'standalone note' }, status: 'pdf-position-skipped-non-highlight', problems: ['pdf-position-skipped-non-highlight'] },
    ] },
    finalPlan: { all_annotations: [], discarded_clipping_ids: [] },
    persistentOverrides: { overrides: [{ clipping_title: 'Mapped title', resolution: { citation_key: 'mapped2020' } }] },
  };
  let rows = manager.conflictRows();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].mappedTarget, 'mapped2020');
  assert.deepEqual(manager.conflictAffected(rows[0]), { failed: 2, total: 2 });

  manager.data.finalPlan.discarded_clipping_ids = ['n1'];
  rows = manager.conflictRows();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].count, 1);
  assert.deepEqual(manager.conflictAffected(rows[0]), { failed: 1, total: 1 });
}

async function testDiscardClipPersists() {
  const originalZotero = bootstrapContext.Zotero;
  let written = null;
  const plan = { discarded_clipping_ids: [], deferred_clipping_ids: ['x1'] };
  bootstrapContext.Zotero = {
    File: {
      getContentsAsync: async () => JSON.stringify(plan),
      putContentsAsync: async (_path, text) => { written = JSON.parse(text); },
    },
  };
  const originalArtifactPath = plugin.artifactPath;
  plugin.artifactPath = rel => `/proj/${rel}`;
  try {
    await plugin.discardClip('x1');
    assert.deepEqual(written.discarded_clipping_ids, ['x1']);
    assert.deepEqual(written.deferred_clipping_ids, []);
  } finally {
    plugin.artifactPath = originalArtifactPath;
    bootstrapContext.Zotero = originalZotero;
  }
}

function testTitleOverviewAndSorting() {
  manager.data = {
    clippings: { clippings: [
      { id: 'a1', title: 'Alpha', kind: 'highlight', text: 'one' },
      { id: 'a2', title: 'Alpha', kind: 'highlight', text: 'two' },
      { id: 'b1', title: 'Beta', kind: 'highlight', text: 'three' },
    ] },
    matches: { matches: [
      { clipping_title: 'Alpha', clipping_count: 2, status: 'matched', candidates: [{ citation_key: 'alpha2020' }] },
      { clipping_title: 'Beta', clipping_count: 1, status: 'unmatched', candidates: [] },
    ] },
    generatedOverrides: { overrides: [] },
    positionedPlan: { items: [] },
    finalPlan: {
      all_annotations: [{ clipping_id: 'a1', clipping_title: 'Alpha' }],
      deferred_clipping_ids: ['b1'],
    },
    persistentOverrides: { overrides: [] },
  };
  const overview = manager.titleOverviewRows();
  assert.equal(overview.length, 2);
  const alpha = overview.find(r => r.title === 'Alpha');
  const beta = overview.find(r => r.title === 'Beta');
  assert.equal(alpha.integrated, 1);
  assert.equal(beta.pending, 1);
  assert.equal(beta.status, 'pending review');

  manager.sortState.titles = { column: 'title', direction: 'desc' };
  const sorted = manager.sortRows(overview, 'titles', { title: row => row.title });
  assert.deepEqual(Array.from(sorted, row => row.title), ['Beta', 'Alpha']);
}

async function testSaveOverrideUsesSourceCount() {
  const originalRead = plugin.readJsonArtifact;
  const originalArtifactPath = plugin.artifactPath;
  const originalZotero = bootstrapContext.Zotero;
  let written = null;
  plugin.artifactPath = rel => `/proj/${rel}`;
  plugin.readJsonArtifact = async rel => rel === 'clippings.json'
    ? { clippings: [{ title: 'Shared title' }, { title: 'Shared title' }, { title: 'Shared title' }] }
    : null;
  bootstrapContext.Zotero = {
    File: {
      getContentsAsync: async () => JSON.stringify({ format: 'kindle-zotero-importer.match-overrides.v1', overrides: [] }),
      putContentsAsync: async (_path, text) => { written = JSON.parse(text); },
    },
  };
  try {
    const entry = await plugin.saveOverride({
      clipping_title: 'Shared title',
      clipping_count: 1,
      resolution: { citation_key: 'shared2020' },
      review: { status: 'pdf-text-not-found', clipping_count: 1 },
    });
    assert.equal(entry.review.clipping_count, 3);
    assert.equal(written.overrides[0].review.clipping_count, 3);
  } finally {
    plugin.readJsonArtifact = originalRead;
    plugin.artifactPath = originalArtifactPath;
    bootstrapContext.Zotero = originalZotero;
  }
}

testTitleCountsAreAuthoritative();
testTitleOverviewAndSorting();
testMappedTargetAndDiscardedClips();
testPendingReviewGrouping();
testFilterPlanForSelection();

testRuntimeExtraction()
  .then(testPythonPathRecovery)
  .then(testSaveOverrideUsesSourceCount)
  .then(testDiscardClipPersists)
  .then(testMaintenanceSweep)
  .then(testMaintenanceRequiresApproval)
  .then(testReviewModelCoversEveryMutationCategory)
  .then(testUnchangedPlanProducesNoOperations)
  .then(testWriterReconciliation)
  .then(testDeletionFailureIsRetried)
  .then(testMaintenanceDeletionIsNotRepeated)
  .then(testSameClippingDuplicateKeepsLogicalHistoryAndDeletesSurvivor)
  .then(testEnumerationFailurePersistsAllDeletions)
  .then(testReplacementFailurePreservesOldAnnotationAndDeletionRetry)
  .then(testSuccessfulReplacementCreatesBeforeDeletingOldAnnotation)
  .then(testCitekeyRelationsAreBidirectionalAndAdditive)
  .then(testCrossLibraryRelationUsesCommentLinkOnly)
  .then(() => {
  console.log('manager and annotation logic ok');
}).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
