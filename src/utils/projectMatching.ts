import { ProjectDiscovery, ProjectMatch, ProjectCandidate } from '../types';

export function normalizeProjectName(value: string | null | undefined): string {
  if (!value) return '';
  let str = value
    .normalize('NFKC')
    .replace(/İ/g, 'I')
    .replace(/ı/g, 'i')
    .replace(/[–—−]/g, '-')
    .toLowerCase();

  // Remove diacritics
  str = str.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
  str = str.replace(/[^a-z0-9]+/g, ' ');
  str = str.replace(/\s+/g, ' ').trim();
  str = str.replace(/^(?:project|proje)\s+/i, '');
  return str;
}

export function discoverProjectFromText(pages: string[]): ProjectDiscovery {
  const candidates: ProjectCandidate[] = [];
  const seen = new Set<string>();

  const patterns = [
    { re: /^\s*(?:proje\s*adı|proje\s*name|project\s*name)\s*[:=]?\s*(.*?)\s*$/im, source: 'project_name_label' },
    { re: /^\s*project\b\s*[:=]?\s*(.*?)\s*$/im, source: 'project_label' },
    { re: /project\s*[:=]\s*([A-Za-z0-9\s._-]{3,40})/i, source: 'inline_project' },
  ];

  pages.forEach((pageText, pageIdx) => {
    const pageNo = pageIdx + 1;
    for (const { re, source } of patterns) {
      const match = pageText.match(re);
      if (match && match[1]) {
        const raw = match[1].trim();
        // Ignore generic labels
        if (/^(?:number|no|date|reference|unit)$/i.test(raw)) continue;
        const normalized = normalizeProjectName(raw);
        if (normalized.length >= 2 && !seen.has(normalized)) {
          seen.add(normalized);
          candidates.push({
            value: raw,
            normalized,
            source,
            page: pageNo,
            confidence: pageNo === 1 ? 'HIGH' : 'MEDIUM',
          });
        }
      }
    }
  });

  if (candidates.length === 0) {
    return {
      projectName: null,
      projectNameNormalized: null,
      projectSource: null,
      projectPage: null,
      confidence: 'REVIEW',
      candidates: [],
    };
  }

  const best = candidates[0];
  return {
    projectName: best.value,
    projectNameNormalized: best.normalized,
    projectSource: best.source,
    projectPage: best.page,
    confidence: best.confidence,
    candidates,
  };
}

export function matchDiscoveries(left: ProjectDiscovery, right: ProjectDiscovery): ProjectMatch {
  const lNorm = left.projectNameNormalized;
  const rNorm = right.projectNameNormalized;

  if (lNorm && rNorm && lNorm === rNorm) {
    return {
      leftName: left.projectName,
      rightName: right.projectName,
      leftNormalized: lNorm,
      rightNormalized: rNorm,
      score: 1.0,
      status: 'EXACT',
      reason: 'Proje isimleri birebir eşleşti',
      leftSource: left.projectSource,
      rightSource: right.projectSource,
    };
  }

  if (lNorm && rNorm) {
    // Check if one contains the other
    if (lNorm.includes(rNorm) || rNorm.includes(lNorm)) {
      return {
        leftName: left.projectName,
        rightName: right.projectName,
        leftNormalized: lNorm,
        rightNormalized: rNorm,
        score: 0.9,
        status: 'SUBSTRING_MATCH',
        reason: 'Proje isimleri alt küme olarak eşleşti',
        leftSource: left.projectSource,
        rightSource: right.projectSource,
      };
    }
  }

  return {
    leftName: left.projectName,
    rightName: right.projectName,
    leftNormalized: lNorm,
    rightNormalized: rNorm,
    score: 0.0,
    status: 'NO_MATCH',
    reason: 'Proje isimleri eşleşmedi',
    leftSource: left.projectSource,
    rightSource: right.projectSource,
  };
}
