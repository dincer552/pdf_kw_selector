import { AHUDiscovery, EquipmentOccurrence, AHUMatch } from '../types';

export function normalizeEquipmentId(value: string | null | undefined): string {
  if (!value) return '';
  let str = value.normalize('NFKC').toUpperCase().trim();
  str = str.replace(/\s+/g, '').replace(/_/g, '-');
  str = str.replace(/-+/g, '-');

  if (str.startsWith('KS')) {
    const tail = str.slice(2).replace(/^-+/, '');
    return tail ? `KS-${tail}` : 'KS';
  }

  if (str.startsWith('AHU')) {
    const tailRaw = str.slice(3).replace(/^-+/, '');
    const tail = tailRaw.replace(/(?<![A-Z0-9])0+(?=\d)/g, '');
    return tail ? `AHU-${tail}` : 'AHU';
  }

  return str.replace(/(?<![A-Z0-9])0+(?=\d)/g, '');
}

export function isSupportedEquipmentId(normalized: string): boolean {
  if (!normalized) return false;
  return (
    normalized.startsWith('AHU-') ||
    /^[A-Z0-9]+-AHU-[A-Z]?\d+(?:\.\d+)?$/.test(normalized) ||
    /^HKS-\d+$/.test(normalized) ||
    /^KS-[A-Z]?\d+(?:\.\d+)?$/.test(normalized) ||
    /^SS-[A-Z]?\d+(?:\.\d+)?$/.test(normalized) ||
    /^PW-[A-Z]?\d+(?:\.\d+)?$/.test(normalized)
  );
}

function stringSimilarity(s1: string, s2: string): number {
  if (s1 === s2) return 1.0;
  if (!s1 || !s2) return 0;
  let longer = s1.length >= s2.length ? s1 : s2;
  let shorter = s1.length < s2.length ? s1 : s2;
  if (longer.length === 0) return 1.0;

  // Simple bigram similarity
  const getBigrams = (str: string) => {
    const s = str.toLowerCase();
    const v = new Map<string, number>();
    for (let i = 0; i < s.length - 1; i++) {
      const bigram = s.substring(i, i + 2);
      v.set(bigram, (v.get(bigram) || 0) + 1);
    }
    return v;
  };

  const b1 = getBigrams(longer);
  const b2 = getBigrams(shorter);
  let intersection = 0;
  b1.forEach((count, key) => {
    if (b2.has(key)) {
      intersection += Math.min(count, b2.get(key)!);
    }
  });

  const total = (longer.length - 1) + (shorter.length - 1);
  return total > 0 ? (2.0 * intersection) / total : 0;
}

export function scoreAhuIds(left: string | null | undefined, right: string | null | undefined): { score: number; status: AHUMatch['status']; reason: string } {
  const l = normalizeEquipmentId(left);
  const r = normalizeEquipmentId(right);
  if (!l || !r) {
    return { score: 0.0, status: 'NO_MATCH', reason: 'Missing equipment reference' };
  }
  if (l === r) {
    return { score: 1.0, status: 'EXACT', reason: 'Normalized equipment references are identical' };
  }

  const lnums = l.match(/\d+/g) || [];
  const rnums = r.match(/\d+/g) || [];
  if (lnums.length > 0 && rnums.length > 0 && lnums[lnums.length - 1] !== rnums[rnums.length - 1]) {
    return { score: 0.2, status: 'NO_MATCH', reason: 'Equipment numeric suffix differs' };
  }

  const ratio = stringSimilarity(l, r);
  if (ratio >= 0.78) {
    return { score: Math.round(ratio * 100) / 100, status: 'REVIEW_REQUIRED', reason: 'Similar equipment reference requires confirmation' };
  }

  return { score: Math.round(ratio * 100) / 100, status: 'NO_MATCH', reason: 'Insufficient equipment agreement' };
}

export function matchAhuIds(left: string | null | undefined, right: string | null | undefined, leftPage?: number, rightPage?: number): AHUMatch {
  const { score, status, reason } = scoreAhuIds(left, right);
  return {
    leftId: left || null,
    rightId: right || null,
    leftNormalized: normalizeEquipmentId(left) || null,
    rightNormalized: normalizeEquipmentId(right) || null,
    score,
    status,
    reason,
    leftPage: leftPage ?? null,
    rightPage: rightPage ?? null,
  };
}

export function discoverEquipmentFromText(pages: string[]): AHUDiscovery {
  const occurrences: EquipmentOccurrence[] = [];
  const seenPage = new Set<string>();

  const patterns = [
    { source: 'unit_reference', re: /\bunit\s+reference\s*[:=]?\s*([A-Z0-9][A-Z0-9_.-]{1,})/gi },
    { source: 'unit_number', re: /\bunit\s+number\s*[:=]?\s*([A-Z0-9][A-Z0-9_.-]{1,})/gi },
    { source: 'hks_token', re: /(?<![A-Z0-9])(HKS(?:[_ -]?\d+))\b/gi },
    { source: 'ks_token', re: /(?<![A-Z0-9])(KS(?:[_ -]?[A-Z]?\d+(?:\.\d+)?))\b/gi },
    { source: 'ss_token', re: /(?<![A-Z0-9])(SS(?:[_ -]?[A-Z]?\d+(?:\.\d+)?))\b/gi },
    { source: 'pw_token', re: /(?<![A-Z0-9])(PW(?:[_ -]?\d+(?:\.\d+)?))\b/gi },
    { source: 'ahu_token', re: /(?<![A-Z0-9])(AHU(?:[_ -]+[A-Z0-9][A-Z0-9_.-]*|\d[A-Z0-9_.-]*))\b/gi },
  ];

  pages.forEach((pageText, pageIdx) => {
    const pageNo = pageIdx + 1;
    for (const { source, re } of patterns) {
      const matches = pageText.matchAll(new RegExp(re));
      for (const m of matches) {
        const raw = m[1].replace(/[.,:;)\\}\\]/g, '').trim();
        const norm = normalizeEquipmentId(raw);
        if (!isSupportedEquipmentId(norm) || norm.length < 4) continue;
        const key = `${norm}:${pageNo}`;
        if (seenPage.has(key)) continue;
        seenPage.add(key);
        occurrences.push({
          equipmentId: raw,
          normalized: norm,
          page: pageNo,
          source,
        });
      }
    }
  });

  const uniqueIds: string[] = [];
  const uniqueSeen = new Set<string>();
  occurrences.forEach(item => {
    if (!uniqueSeen.has(item.normalized)) {
      uniqueSeen.add(item.normalized);
      uniqueIds.push(item.normalized);
    }
  });

  return { equipmentIds: occurrences, uniqueIds };
}

export function discoverEquipmentFromFilename(filename: string): EquipmentOccurrence | null {
  const base = filename.replace(/\.[^/.]+$/, '').trim();
  const m1 = base.match(/^([A-Z0-9]+)[_ -]+(AHU)[_ -]?([A-Z]?\d+(?:\.\d+)?)$/i);
  if (m1) {
    const raw = `${m1[1].toUpperCase()}-AHU-${m1[3].toUpperCase()}`;
    return { equipmentId: raw, normalized: normalizeEquipmentId(raw), page: 1, source: 'filename' };
  }
  const m2 = base.match(/^(HKS|KS|SS|PW)[_ -]?([A-Z]?\d+(?:\.\d+)?)$/i);
  if (m2) {
    const raw = `${m2[1].toUpperCase()}-${m2[2].toUpperCase()}`;
    return { equipmentId: raw, normalized: normalizeEquipmentId(raw), page: 1, source: 'filename' };
  }
  return null;
}

export function matchAhuLists(left: EquipmentOccurrence[], right: EquipmentOccurrence[]): AHUMatch[] {
  const leftUnique = new Map<string, EquipmentOccurrence>();
  const rightUnique = new Map<string, EquipmentOccurrence>();
  left.forEach(l => { if (!leftUnique.has(l.normalized)) leftUnique.set(l.normalized, l); });
  right.forEach(r => { if (!rightUnique.has(r.normalized)) rightUnique.set(r.normalized, r); });

  const output: AHUMatch[] = [];
  const usedL = new Set<string>();
  const usedR = new Set<string>();

  // 1. Exact matches
  leftUnique.forEach((lo, norm) => {
    if (rightUnique.has(norm)) {
      const ro = rightUnique.get(norm)!;
      output.push(matchAhuIds(norm, norm, lo.page, ro.page));
      usedL.add(norm);
      usedR.add(norm);
    }
  });

  // 2. Remaining candidates
  const remainingL = Array.from(leftUnique.entries()).filter(([k]) => !usedL.has(k));
  const remainingR = Array.from(rightUnique.entries()).filter(([k]) => !usedR.has(k));

  for (const [lid, lo] of remainingL) {
    for (const [rid, ro] of remainingR) {
      if (usedL.has(lid) || usedR.has(rid)) continue;
      const m = matchAhuIds(lid, rid, lo.page, ro.page);
      if (m.status === 'EXACT' || m.status === 'NORMALIZED_MATCH' || m.score >= 0.8) {
        output.push(m);
        usedL.add(lid);
        usedR.add(rid);
      }
    }
  }

  // 3. Unmatched leftovers
  remainingL.forEach(([lid, lo]) => {
    if (!usedL.has(lid)) {
      output.push({
        leftId: lid,
        rightId: null,
        leftNormalized: lid,
        rightNormalized: null,
        score: 0,
        status: 'NO_MATCH',
        reason: 'Only in PDF1',
        leftPage: lo.page,
      });
    }
  });

  remainingR.forEach(([rid, ro]) => {
    if (!usedR.has(rid)) {
      output.push({
        leftId: null,
        rightId: rid,
        leftNormalized: null,
        rightNormalized: rid,
        score: 0,
        status: 'NO_MATCH',
        reason: 'Only in PDF2',
        rightPage: ro.page,
      });
    }
  });

  return output;
}
