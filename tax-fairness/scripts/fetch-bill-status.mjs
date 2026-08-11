#!/usr/bin/env node
// Fetches bill status RSS from the Hawaii Legislature and writes tax-fairness/data/bill-status.json.
// Bill numbers are NOT hardcoded here — they're discovered from data-tracker-id/data-hb/data-sb/
// data-year/data-issue-area attributes in the tracked HTML pages (see TRACKED_PAGES below).
// See tax-fairness/README.md for how to add a bill or point this at a different legislature.

import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..');

const TRACKED_PAGES = [
  'tax-fairness/wealth_taxes_squarespace.html',
];

const OUTPUT_PATH = path.join(REPO_ROOT, 'tax-fairness/data/bill-status.json');
const RSS_BASE_URL = 'https://www.capitol.hawaii.gov/sessions/session'; // {year}/rss/{TYPE}{NUMBER}.xml
const FETCH_TIMEOUT_MS = 15000;

function discoverTrackers(html) {
  const trackers = [];
  const blockRe = /<div\s+class="tfc-bill-tracker[^"]*"\s+([^>]*)>/g;
  let match;
  while ((match = blockRe.exec(html))) {
    const attrs = match[1];
    const get = (name) => {
      const m = attrs.match(new RegExp(`data-${name}="([^"]*)"`));
      return m ? m[1] : '';
    };
    const trackerId = get('tracker-id');
    if (!trackerId) continue;
    trackers.push({
      trackerId,
      issueArea: get('issue-area') || trackerId,
      year: get('year') || '2026',
      hbNumbers: get('hb').split(',').map((s) => s.trim()).filter(Boolean),
      sbNumbers: get('sb').split(',').map((s) => s.trim()).filter(Boolean),
    });
  }
  return trackers;
}

// Some cards have a client-side "policy options" toggle (see switchCapGainsPolicy /
// switchMillionairesTaxPolicy in wealth_taxes_squarespace.html) that swaps a tracker's
// data-hb/data-sb to an alternate bill when the user picks a different option. Those
// alternate bill numbers live in small JS config objects, not in a data-tracker-id block,
// so they need their own discovery pass or their status never gets fetched.
function discoverPolicyToggleBills(html, defaultYear) {
  const bills = [];
  const configRe = /hbNumbers:\s*'([^']*)'[\s\S]{0,40}?sbNumbers:\s*'([^']*)'/g;
  let match;
  while ((match = configRe.exec(html))) {
    const [, hb, sb] = match;
    if (hb) bills.push({ type: 'HB', number: hb, year: defaultYear });
    if (sb) bills.push({ type: 'SB', number: sb, year: defaultYear });
  }
  return bills;
}

async function loadTrackers() {
  const all = [];
  const extraBills = [];
  for (const relPath of TRACKED_PAGES) {
    const html = await readFile(path.join(REPO_ROOT, relPath), 'utf8');
    all.push(...discoverTrackers(html));
    extraBills.push(...discoverPolicyToggleBills(html, '2026'));
  }
  return { trackers: all, extraBills };
}

function uniqueBills(trackers, extraBills) {
  const seen = new Map();
  for (const t of trackers) {
    for (const number of t.hbNumbers) addBill(seen, 'HB', number, t.year);
    for (const number of t.sbNumbers) addBill(seen, 'SB', number, t.year);
  }
  for (const b of extraBills) addBill(seen, b.type, b.number, b.year);
  return [...seen.values()];
}

function addBill(map, type, number, year) {
  const key = `${type}${number}_${year}`;
  if (!map.has(key)) map.set(key, { type, number, year });
}

async function fetchWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

// Minimal RSS <item><title>/<pubDate> extraction — avoids adding an XML-parsing dependency.
function parseRssItems(xmlText) {
  const items = [];
  const itemRe = /<item>([\s\S]*?)<\/item>/g;
  let m;
  while ((m = itemRe.exec(xmlText))) {
    const block = m[1];
    const title = extractTag(block, 'title');
    const pubDate = extractTag(block, 'pubDate');
    if (!title || !pubDate) continue;
    items.push({ title: decodeEntities(title), pubDate });
  }
  return items;
}

function extractTag(block, tag) {
  const m = block.match(new RegExp(`<${tag}>([\\s\\S]*?)<\\/${tag}>`));
  if (!m) return '';
  return m[1].replace(/^<!\[CDATA\[/, '').replace(/\]\]>$/, '').trim();
}

function decodeEntities(str) {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"');
}

function getStatusBadge(description) {
  const desc = description.toLowerCase();
  if (desc.includes('signed by governor') || desc.includes('became law')) return { text: 'Enacted', class: 'enacted' };
  if (desc.includes('passed third reading') && desc.includes('transmitted')) return { text: 'Passed Chamber', class: 'passed' };
  if (desc.includes('passed third reading')) return { text: 'Passed', class: 'passed' };
  if (desc.includes('passed second reading')) return { text: 'Second Reading', class: 'progress' };
  if (desc.includes('passed first reading')) return { text: 'First Reading', class: 'progress' };
  if (desc.includes('carried over')) return { text: 'Carried Over', class: 'deferred' };
  if (desc.includes('deferred')) return { text: 'Deferred', class: 'deferred' };
  if (desc.includes('hearing')) return { text: 'Hearing', class: 'hearing' };
  if (desc.includes('referred to')) return { text: 'Referred', class: 'referred' };
  if (desc.includes('recommitted')) return { text: 'Recommitted', class: 'referred' };
  if (desc.includes('reported from')) return { text: 'Reported', class: 'progress' };
  if (desc.includes('introduced')) return { text: 'Introduced', class: 'new' };
  return { text: 'Update', class: 'update' };
}

function toDescription(title) {
  const parts = title.split(': ');
  let desc = parts.length > 1 ? parts.slice(1).join(': ') : title;
  desc = desc.replace(/\s*with\s+Representative\(s\)[^.]*\./g, '');
  desc = desc.replace(/\s*with\s+Senator\(s\)[^.]*\./g, '');
  desc = desc.replace(/\s*voting\s+[^.]*\./g, '');
  return desc.replace(/\s+/g, ' ').trim();
}

function isHearingTitle(titleLower) {
  return ['hearing', 'scheduled', 'notice', 'decision', 'public', 'hold'].some((kw) => titleLower.includes(kw));
}

async function fetchBillStatus(type, number, year) {
  const rssUrl = `${RSS_BASE_URL}${year}/rss/${type}${number}.xml`;
  try {
    const response = await fetchWithTimeout(rssUrl, FETCH_TIMEOUT_MS);
    if (!response.ok) {
      return { error: `HTTP ${response.status}` };
    }
    const xmlText = await response.text();
    if (!xmlText.includes('<rss') && !xmlText.includes('<item>')) {
      return { error: 'invalid RSS response' };
    }

    const rawItems = parseRssItems(xmlText)
      .map((item) => ({
        title: item.title,
        description: toDescription(item.title),
        date: new Date(item.pubDate).toISOString(),
      }))
      .sort((a, b) => new Date(b.date) - new Date(a.date));

    let hasScheduledHearing = false;
    let hasHadHearing = false;
    let isDeferred = false;
    const now = new Date();
    now.setHours(0, 0, 0, 0);

    for (const item of rawItems) {
      const titleLower = item.title.toLowerCase();
      if (isHearingTitle(titleLower)) {
        hasHadHearing = true;
        const dateMatch = item.title.match(/(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})/);
        if (dateMatch) {
          const parts = dateMatch[1].split(/[-/]/);
          if (parts.length === 3) {
            const month = parseInt(parts[0], 10) - 1;
            const day = parseInt(parts[1], 10);
            const yr = parts[2].length === 2 ? 2000 + parseInt(parts[2], 10) : parseInt(parts[2], 10);
            const hearingDate = new Date(yr, month, day);
            hearingDate.setHours(0, 0, 0, 0);
            if (hearingDate >= now) hasScheduledHearing = true;
          }
        }
      }
    }
    if (rawItems.length > 0) {
      const latestLower = rawItems[0].title.toLowerCase();
      isDeferred = latestLower.includes('deferred') || latestLower.includes('carried over');
    }

    const updates = rawItems.map((item) => ({
      ...item,
      badge: getStatusBadge(item.description),
    }));

    return {
      updates,
      hasScheduledHearing,
      hasHadHearing,
      isDeferred,
      isAlive: !isDeferred && hasHadHearing,
    };
  } catch (err) {
    return { error: err.message };
  }
}

async function main() {
  const { trackers, extraBills } = await loadTrackers();
  const bills = uniqueBills(trackers, extraBills);

  const billStatus = {};
  for (const bill of bills) {
    const key = `${bill.type}${bill.number}`;
    console.log(`Fetching ${key} (${bill.year})...`);
    billStatus[key] = { type: bill.type, number: bill.number, year: bill.year, ...(await fetchBillStatus(bill.type, bill.number, bill.year)) };
  }

  const output = {
    generatedAt: new Date().toISOString(),
    source: 'capitol.hawaii.gov RSS, fetched via GitHub Actions',
    trackers: trackers.map((t) => ({
      trackerId: t.trackerId,
      issueArea: t.issueArea,
      year: t.year,
      hbNumbers: t.hbNumbers,
      sbNumbers: t.sbNumbers,
    })),
    bills: billStatus,
  };

  await writeFile(OUTPUT_PATH, JSON.stringify(output, null, 2) + '\n');
  console.log(`Wrote ${OUTPUT_PATH} (${bills.length} bills, ${trackers.length} trackers)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
