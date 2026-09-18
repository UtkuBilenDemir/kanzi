import assert from 'assert';
// test the grouping logic for title variants sharing same candidate
function findOtherRows(rows, rowIndex, targetKey) {
  const row = rows[rowIndex];
  return rows.filter((r, idx) => idx !== rowIndex && (r.candidates||[]).some(c => (c.citation_key||c.key||String(c.item_id))===targetKey));
}
const rows = [
  {title:"gilbert-simondon-on-the-mode", candidates:[{citation_key:"chabot2013", key:"A"}, {citation_key:"simondon2017a"}]},
  {title:"On the Mode (Univocal)", candidates:[{citation_key:"chabot2013"}, {citation_key:"simondon2017a"}]},
  {title:"Other", candidates:[{citation_key:"foo"}]}
];
assert.equal(findOtherRows(rows, 0, "chabot2013").length, 1);
assert.equal(findOtherRows(rows, 0, "chabot2013")[0].title, "On the Mode (Univocal)");
console.log("manager logic ok");
