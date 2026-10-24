// Run: node --test tax-fairness/scripts/*.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { reconcile } from './reconcile-bill-status.mjs';

const NOW = '2026-10-22T00:00:00.000Z';
const good = (n, text = 'Passed First Reading.') => ({ type: 'HB', number: n, year: '2026', updates: [{ title: text, description: text, date: '2026-03-12T00:00:00.000Z', badge: 'x' }], isAlive: true });
const bad = (n, error = 'HTTP 403') => ({ type: 'HB', number: n, year: '2026', error });

test('everything fetched: the run is taken as it is', () => {
  const r = reconcile({ HB1: good('1') }, { HB1: good('1', 'Newer.'), HB2: good('2') }, NOW);
  assert.equal(r.ok, 2);
  assert.deepEqual(r.failed, []);
  assert.equal(r.abort, false);
  assert.equal(r.bills.HB1.updates[0].description, 'Newer.');
});

test('a bill that failed keeps its last good entry, flagged, instead of becoming an error', () => {
  const r = reconcile({ HB1: good('1'), HB2: good('2') }, { HB1: good('1'), HB2: bad('2') }, NOW);
  assert.equal(r.abort, false);
  assert.deepEqual(r.stale, ['HB2']);
  assert.equal(r.bills.HB2.error, undefined, 'the page must not see an error for it');
  assert.equal(r.bills.HB2.updates[0].description, 'Passed First Reading.');
  assert.equal(r.bills.HB2.staleError, 'HTTP 403');
  assert.equal(r.bills.HB2.staleSince, NOW);
});

test('staleSince is the first time it went stale, not every run, so the file does not churn', () => {
  const earlier = '2026-10-21T00:00:00.000Z';
  const prior = { ...good('2'), staleError: 'HTTP 403', staleSince: earlier };
  const r = reconcile({ HB2: prior, HB1: good('1') }, { HB1: good('1'), HB2: bad('2') }, NOW);
  assert.equal(r.bills.HB2.staleSince, earlier);
  assert.deepEqual(r.bills.HB2, prior);
});

test('a bill that fetches again is fresh again, with no stale flags left over', () => {
  const prior = { ...good('2'), staleError: 'HTTP 403', staleSince: NOW };
  const r = reconcile({ HB2: prior, HB1: good('1') }, { HB1: good('1'), HB2: good('2', 'Back.') }, NOW);
  assert.equal(r.bills.HB2.staleError, undefined);
  assert.equal(r.bills.HB2.staleSince, undefined);
  assert.equal(r.bills.HB2.updates[0].description, 'Back.');
});

test('a bill that never had data stays an error entry', () => {
  const r = reconcile({}, { HB1: good('1'), HB9: bad('9', 'HTTP 404') }, NOW);
  assert.equal(r.bills.HB9.error, 'HTTP 404');
  assert.deepEqual(r.stale, []);
  assert.deepEqual(r.failed, ['HB9 (HTTP 404)']);
});

test('every fetch failing aborts the run, so the file is left alone and the job fails', () => {
  const r = reconcile({ HB1: good('1'), HB2: good('2') }, { HB1: bad('1'), HB2: bad('2') }, NOW);
  assert.equal(r.abort, true);
  assert.equal(r.ok, 0);
  const none = reconcile({}, {}, NOW);
  assert.equal(none.abort, false, 'no bills at all is main()\'s own "discovered 0" case');
});

test('an entry with an empty updates list does not count as good data', () => {
  const r = reconcile({ HB2: { ...good('2'), updates: [] } }, { HB1: good('1'), HB2: bad('2') }, NOW);
  assert.equal(r.bills.HB2.error, 'HTTP 403');
});
