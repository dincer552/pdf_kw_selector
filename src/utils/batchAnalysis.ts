import {
  BatchDocument,
  BatchAnalysisResult,
  ProjectMatch,
  BatchAHU,
  MotorComparison,
  EbmRow,
  VocleanRow,
  SysrecoRow,
  UnmatchedPdfRow,
  LogEntry,
  MotorRecord,
} from '../types';
import { matchAhuLists, normalizeEquipmentId } from './ahuMatching';
import { matchDiscoveries } from './projectMatching';
import { compareMotorRecords, expandMotorGroup, isEbmPapst } from './motorCompare';

export function runBatchAnalysis(
  pdf1Docs: BatchDocument[],
  pdf2Docs: BatchDocument[],
  toleranceKw: number = 0.01,
  onLog?: (entry: LogEntry) => void
): BatchAnalysisResult {
  const log = (level: LogEntry['level'], message: string, details?: Record<string, any>) => {
    if (onLog) {
      onLog({
        id: Math.random().toString(36).substring(2, 9),
        timestamp: new Date().toLocaleTimeString(),
        level,
        message,
        details,
      });
    }
  };

  log('INFO', 'Batch analizi başladı', {
    pdf1Count: pdf1Docs.length,
    pdf2Count: pdf2Docs.length,
    toleranceKw,
  });

  // Group by project name
  const leftGroups = new Map<string, BatchDocument[]>();
  const rightGroups = new Map<string, BatchDocument[]>();

  pdf1Docs.forEach(d => {
    const key = d.project.projectNameNormalized || '__UNRESOLVED__';
    if (!leftGroups.has(key)) leftGroups.set(key, []);
    leftGroups.get(key)!.push(d);
  });

  pdf2Docs.forEach(d => {
    const key = d.project.projectNameNormalized || '__UNRESOLVED__';
    if (!rightGroups.has(key)) rightGroups.set(key, []);
    rightGroups.get(key)!.push(d);
  });

  log('INFO', 'Proje grupları oluşturuldu', {
    leftProjectKeys: Array.from(leftGroups.keys()),
    rightProjectKeys: Array.from(rightGroups.keys()),
  });

  // Pair project groups
  const projectMatches: ProjectMatch[] = [];
  const projectPairDocs = new Map<string, { match: ProjectMatch; left: BatchDocument[]; right: BatchDocument[] }>();
  const usedRightKeys = new Set<string>();

  // 1. Exact project name matching
  leftGroups.forEach((lDocs, lKey) => {
    if (lKey !== '__UNRESOLVED__' && rightGroups.has(lKey)) {
      const rDocs = rightGroups.get(lKey)!;
      const match = matchDiscoveries(lDocs[0].project, rDocs[0].project);
      projectMatches.push(match);
      projectPairDocs.set(lKey, { match, left: lDocs, right: rDocs });
      usedRightKeys.add(lKey);
      log('INFO', `Proje eşleşti (EXACT): ${lKey}`, { score: match.score, reason: match.reason });
    }
  });

  // 2. Pair unresolved or remaining groups by AHU overlap
  leftGroups.forEach((lDocs, lKey) => {
    if (projectPairDocs.has(lKey)) return;
    const lAhus = new Set(lDocs.flatMap(d => d.equipment.uniqueIds));

    let bestRightKey: string | null = null;
    let maxOverlap = 0;

    rightGroups.forEach((rDocs, rKey) => {
      if (usedRightKeys.has(rKey)) return;
      const rAhus = new Set(rDocs.flatMap(d => d.equipment.uniqueIds));
      let overlapCount = 0;
      lAhus.forEach(ahu => {
        if (rAhus.has(ahu)) overlapCount++;
      });
      if (overlapCount > maxOverlap) {
        maxOverlap = overlapCount;
        bestRightKey = rKey;
      }
    });

    if (bestRightKey && maxOverlap > 0) {
      const rDocs = rightGroups.get(bestRightKey)!;
      const pMatch: ProjectMatch = {
        leftName: lDocs[0].project.projectName,
        rightName: rDocs[0].project.projectName,
        leftNormalized: lKey,
        rightNormalized: bestRightKey,
        score: Math.round((maxOverlap / Math.max(1, lAhus.size)) * 100) / 100,
        status: 'INFERRED_FROM_AHU',
        reason: `AHU referansları örtüşmesiyle proje eşleştirildi (${maxOverlap} AHU)`,
      };
      projectMatches.push(pMatch);
      projectPairDocs.set(lKey, { match: pMatch, left: lDocs, right: rDocs });
      usedRightKeys.add(bestRightKey);
      log('INFO', `Proje AHU örtüşmesiyle eşleştirildi: ${lKey} ↔ ${bestRightKey}`, { maxOverlap });
    } else {
      // Unpaired project in PDF1
      const pMatch: ProjectMatch = {
        leftName: lDocs[0].project.projectName,
        rightName: null,
        leftNormalized: lKey,
        rightNormalized: null,
        score: 0,
        status: 'NO_MATCH',
        reason: 'Eşleşen PDF2 projesi bulunamadı',
      };
      projectMatches.push(pMatch);
      projectPairDocs.set(lKey, { match: pMatch, left: lDocs, right: [] });
    }
  });

  // Match AHUs and Motor comparisons
  const ahuMatches: BatchAHU[] = [];
  const motorComparisons: MotorComparison[] = [];
  const matchedPdf1Paths = new Set<string>();
  const matchedPdf2Paths = new Set<string>();

  // Special sets
  const ebmPdf1Set = new Set<string>();
  const vocleanPdf1Set = new Set<string>();
  const sysrecoPdf1Set = new Set<string>();

  pdf1Docs.forEach(d => {
    if (d.ebmPages.length > 0) ebmPdf1Set.add(d.path);
    if (d.isVoclean) vocleanPdf1Set.add(d.path);
    if (d.isSysreco) sysrecoPdf1Set.add(d.path);
  });

  // Process paired projects
  projectPairDocs.forEach(({ match: pMatch, left: lDocs, right: rDocs }) => {
    const lOccurrences = lDocs.flatMap(d => d.equipment.equipmentIds);
    const rOccurrences = rDocs.flatMap(d => d.equipment.equipmentIds);

    const aMatches = matchAhuLists(lOccurrences, rOccurrences);

    aMatches.forEach(am => {
      const leftFiles = lDocs
        .filter(d => am.leftNormalized && d.equipment.uniqueIds.includes(am.leftNormalized))
        .map(d => d.path);
      const rightFiles = rDocs
        .filter(d => am.rightNormalized && d.equipment.uniqueIds.includes(am.rightNormalized))
        .map(d => d.path);

      ahuMatches.push({
        projectName: pMatch.leftName || pMatch.rightName || 'Proje',
        match: am,
        pdf1Files: leftFiles,
        pdf2Files: rightFiles,
      });

      if (am.status === 'EXACT' || am.status === 'NORMALIZED_MATCH' || am.status === 'USER_APPROVED') {
        leftFiles.forEach(f => matchedPdf1Paths.add(f));
        rightFiles.forEach(f => matchedPdf2Paths.add(f));

        // Check if any left files are EBM
        const hasEbm = leftFiles.some(f => ebmPdf1Set.has(f));
        if (hasEbm) {
          log('INFO', `EBM-Papst tespit edildi, motor kW karşılaştırması atlandı: AHU ${am.leftNormalized}`);
          return;
        }

        // Build physical motor records
        const leftMotors: MotorRecord[] = [];
        const rightMotors: MotorRecord[] = [];

        lDocs
          .filter(d => leftFiles.includes(d.path))
          .forEach(d => {
            d.pdf1Motors.forEach(m => {
              if (m.valueKw !== null) {
                const records = expandMotorGroup(
                  am.leftNormalized || 'AHU',
                  m.componentType,
                  m.valueKw,
                  m.quantity,
                  m.pageNumber,
                  m.modelBrand,
                  m.sourceText
                );
                leftMotors.push(...records);
              }
            });
          });

        rDocs
          .filter(d => rightFiles.includes(d.path))
          .forEach(d => {
            d.pdf2Motors.forEach(m => {
              if (m.valueKw !== null) {
                const records = expandMotorGroup(
                  am.rightNormalized || 'AHU',
                  m.componentType,
                  m.valueKw,
                  m.quantity,
                  m.pageNumber,
                  m.modelBrand,
                  m.sourceText
                );
                rightMotors.push(...records);
              }
            });
          });

        // Run motor comparison
        const comparisons = compareMotorRecords(leftMotors, rightMotors, toleranceKw);
        comparisons.forEach(c => {
          c.projectName = pMatch.leftName || pMatch.rightName || undefined;
          c.pdf1File = leftFiles[0] ? leftFiles[0].split('/').pop() : undefined;
          c.pdf2File = rightFiles[0] ? rightFiles[0].split('/').pop() : undefined;
          motorComparisons.push(c);
        });
      }
    });
  });

  // Prepare EBM Rows
  const ebmRows: EbmRow[] = [];
  pdf1Docs.forEach(d => {
    if (!ebmPdf1Set.has(d.path)) return;
    const matchingP2: string[] = [];
    ahuMatches.forEach(am => {
      if (am.pdf1Files.includes(d.path)) {
        matchingP2.push(...am.pdf2Files);
      }
    });
    const p2Names = Array.from(new Set(matchingP2)).map(p => p.split('/').pop() || p).join(', ') || '-';
    const status = matchingP2.length > 0
      ? 'PDF2 AHU eşleşti; motor kW karşılaştırması yapılmadı'
      : 'PDF2 AHU eşleşmesi yok';

    d.equipment.uniqueIds.forEach(ahuId => {
      ebmRows.push({
        projectName: d.project.projectName || '-',
        ahu: ahuId || '-',
        pdf1File: d.name,
        pdf2Files: p2Names,
        status,
      });
    });
  });

  // Prepare VOClean Rows
  const vocleanRows: VocleanRow[] = [];
  pdf1Docs.forEach(d => {
    if (!vocleanPdf1Set.has(d.path)) return;
    if (d.pdf1Motors.length === 0) {
      vocleanRows.push({
        projectName: d.project.projectName || '-',
        pdf1File: d.name,
        vocleanKw: '-',
        pdf1Page: '-',
        pdf2File: '-',
        ahu: '-',
        status: 'VOClean bulundu; Plug fan kW bulunamadı',
      });
      return;
    }

    d.pdf1Motors.forEach(m => {
      if (m.valueKw === null) return;
      // BA prefix format: e.g. 0.75 -> BA075-
      const prefix = `BA${String(Math.round(m.valueKw * 100)).padStart(3, '0')}-`;
      let matchedP2 = false;

      pdf2Docs.forEach(p2 => {
        p2.equipment.uniqueIds.forEach(ahu => {
          if (ahu.toUpperCase().startsWith(prefix)) {
            matchedP2 = true;
            vocleanRows.push({
              projectName: d.project.projectName || '-',
              pdf1File: d.name,
              vocleanKw: `${m.valueKw} kW`,
              pdf1Page: String(m.pageNumber),
              pdf2File: p2.name,
              ahu,
              status: `BA kodu eşleşti (${prefix.slice(0, -1)})`,
            });
          }
        });
      });

      if (!matchedP2) {
        vocleanRows.push({
          projectName: d.project.projectName || '-',
          pdf1File: d.name,
          vocleanKw: `${m.valueKw} kW`,
          pdf1Page: String(m.pageNumber),
          pdf2File: '-',
          ahu: '-',
          status: `PDF2 AHU eşleşmesi yok; beklenen ${prefix.slice(0, -1)}-xxxxx`,
        });
      }
    });
  });

  // Prepare SysReco Rows
  const sysrecoRows: SysrecoRow[] = [];
  pdf1Docs.forEach(d => {
    if (!sysrecoPdf1Set.has(d.path)) return;
    const fullText = d.pageTexts.join('\n');
    const models = Array.from(fullText.matchAll(/\bSysReco\s+FX\d+\b/gi)).map(m => m[0]);
    const uniqueModels = Array.from(new Set(models));
    const modelStr = uniqueModels.length > 0 ? uniqueModels.join(', ') : 'SysReco modeli bulundu';

    sysrecoRows.push({
      projectName: d.project.projectName || '-',
      ahu: d.equipment.uniqueIds.join(', ') || '-',
      pdfFile: d.name,
      sysrecoModel: modelStr,
    });
  });

  // Prepare Unmatched PDFs
  const unmatchedPdfs: UnmatchedPdfRow[] = [];

  pdf1Docs.forEach(d => {
    if (!matchedPdf1Paths.has(d.path)) {
      unmatchedPdfs.push({
        side: 'PDF1',
        pdfName: d.name,
        projectName: d.project.projectName || 'Bilinmiyor',
        ahu: d.equipment.uniqueIds.join(', ') || '-',
        reason: d.equipment.uniqueIds.length === 0
          ? 'PDF1 Unit Reference / AHU tespit edilemedi'
          : 'Eşleşen PDF2 AHU bulunamadı',
      });
    }
  });

  pdf2Docs.forEach(d => {
    if (!matchedPdf2Paths.has(d.path)) {
      unmatchedPdfs.push({
        side: 'PDF2',
        pdfName: d.name,
        projectName: d.project.projectName || 'Bilinmiyor',
        ahu: d.equipment.uniqueIds.join(', ') || '-',
        reason: d.equipment.uniqueIds.length === 0
          ? 'PDF2 Ekipman ID tespit edilemedi'
          : 'Eşleşen PDF1 AHU / Proje bulunamadı',
      });
    }
  });

  log('INFO', 'Batch analizi tamamlandı', {
    matchedMotorCount: motorComparisons.length,
    matchCount: motorComparisons.filter(m => m.status === 'MATCH').length,
    mismatchCount: motorComparisons.filter(m => m.status === 'MISMATCH').length,
    ebmCount: ebmRows.length,
    vocleanCount: vocleanRows.length,
    sysrecoCount: sysrecoRows.length,
    unmatchedCount: unmatchedPdfs.length,
  });

  return {
    pdf1Documents: pdf1Docs,
    pdf2Documents: pdf2Docs,
    projectMatches,
    ahuMatches,
    motorComparisons,
    ebmRows,
    vocleanRows,
    sysrecoRows,
    unmatchedPdfs,
  };
}
