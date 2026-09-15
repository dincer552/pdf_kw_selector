import { MotorRecord, MotorComparison, MotorPowerResult } from '../types';

export function parseRatedPower(raw: string): { valueKw: number; quantity: string | null; rawValue: string } | null {
  if (!raw) return null;
  const compact = raw.trim().replace(/\s+/g, ' ');

  // e.g. "7,500 x (1x1)" or "7.5 x (2x1)"
  const mQty = compact.match(/^([0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)/i);
  if (mQty) {
    const val = parseFloat(mQty[1].replace(',', '.'));
    return {
      valueKw: val,
      quantity: `${mQty[2]}x${mQty[3]}`,
      rawValue: mQty[1],
    };
  }

  // e.g. "7.5 kW" or "7,5 kW"
  const mKw = compact.match(/^([0-9]+(?:[.,][0-9]+)?)\s*(?:kw)?$/i);
  if (mKw) {
    const val = parseFloat(mKw[1].replace(',', '.'));
    return {
      valueKw: val,
      quantity: null,
      rawValue: mKw[1],
    };
  }

  const num = compact.match(/([0-9]+(?:[.,][0-9]+)?)/);
  const qty = compact.match(/\(\s*(\d+)\s*[x×]\s*(\d+)\s*\)/i);
  if (num) {
    const val = parseFloat(num[1].replace(',', '.'));
    return {
      valueKw: val,
      quantity: qty ? `${qty[1]}x${qty[2]}` : null,
      rawValue: num[1],
    };
  }

  return null;
}

export function isEbmPapst(modelBrand: string | null | undefined): boolean {
  if (!modelBrand) return false;
  const brand = modelBrand.toLowerCase().replace(/[\s-_]/g, '');
  return brand.includes('ebmpapst') || brand.includes('ebm');
}

export function expandMotorGroup(
  equipmentId: string,
  componentType: string,
  powerKw: number,
  quantityStr: string | null | undefined,
  sourcePage: number,
  modelBrand: string | null = null,
  sourceText: string = ''
): MotorRecord[] {
  let count = 1;
  const group = quantityStr || '1x1';

  if (quantityStr) {
    const match = quantityStr.match(/^(\d+)[x×](\d+)$/i);
    if (match) {
      count = Math.max(1, parseInt(match[1], 10));
    }
  }

  const records: MotorRecord[] = [];
  for (let i = 1; i <= count; i++) {
    const label = count > 1 ? `${componentType} ${i}` : componentType;
    records.push({
      equipmentId,
      equipmentType: 'AHU',
      componentType,
      componentLabel: label,
      componentIndex: i,
      powerKw,
      sourcePage,
      sourceGroup: group,
      modelBrand,
      sourceText,
    });
  }

  return records;
}

function canonicalKey(record: MotorRecord): string {
  const eq = (record.equipmentId || '').toUpperCase().replace(/_/g, '-');
  const ct = (record.componentType || '').trim().toLowerCase();
  return `${eq}::${ct}::${record.componentIndex}`;
}

export function compareMotorRecords(
  pdf1Records: MotorRecord[],
  pdf2Records: MotorRecord[],
  toleranceKw: number = 0.01
): MotorComparison[] {
  const leftMap = new Map<string, MotorRecord>();
  const rightMap = new Map<string, MotorRecord>();

  pdf1Records.forEach(r => {
    const key = canonicalKey(r);
    if (!leftMap.has(key)) leftMap.set(key, r);
  });

  pdf2Records.forEach(r => {
    const key = canonicalKey(r);
    if (!rightMap.has(key)) rightMap.set(key, r);
  });

  const allKeys = Array.from(new Set([...leftMap.keys(), ...rightMap.keys()])).sort();
  const comparisons: MotorComparison[] = [];

  for (const key of allKeys) {
    const a = leftMap.get(key);
    const b = rightMap.get(key);
    const template = (a || b)!;
    const aKw = a ? a.powerKw : null;
    const bKw = b ? b.powerKw : null;
    const isEbm = isEbmPapst(a?.modelBrand);

    let status: MotorComparison['status'];
    let difference: number | null = null;
    let explanation: string;

    if (a === undefined) {
      status = 'ONLY_IN_PDF2';
      difference = null;
      explanation = 'PDF1 tarafında karşılığı bulunamadı.';
    } else if (b === undefined) {
      status = 'ONLY_IN_PDF1';
      difference = null;
      explanation = 'PDF2 tarafında karşılığı bulunamadı.';
    } else if (isEbm) {
      status = 'EBM_PAPST';
      difference = null;
      explanation = 'PDF1 Model Brand = EBM-Papst; normal kW karşılaştırması yapılmadı. PDF2 motoru eşleştirildi.';
    } else {
      difference = Math.round(Math.abs((aKw || 0) - (bKw || 0)) * 1000) / 1000;
      // Special legacy equivalence: PDF1 1.1 kW and PDF2 1.5 kW
      if (aKw !== null && bKw !== null && Math.abs(aKw - 1.1) <= 0.001 && Math.abs(bKw - 1.5) <= 0.001) {
        status = 'MATCH';
        explanation = 'Özel eşdeğerlik: PDF1 1.1 kW, PDF2 1.5 kW kabul edildi. Bu istisna yalnızca 1.1→1.5 için geçerlidir.';
      } else if (difference <= toleranceKw) {
        status = 'MATCH';
        explanation = 'Normal kW karşılaştırması yapıldı (tolerans dahilinde).';
      } else {
        status = 'MISMATCH';
        explanation = `kW farkı toleransı (${toleranceKw} kW) aşıyor. Fark: ${difference} kW.`;
      }
    }

    const label = `${template.componentLabel}${isEbm ? ' [EBM]' : ''}`;

    comparisons.push({
      equipmentId: template.equipmentId,
      componentType: template.componentType,
      componentLabel: label,
      componentIndex: template.componentIndex,
      pdf1Kw: aKw,
      pdf2Kw: bKw,
      differenceKw: difference,
      status,
      pdf1Page: a?.sourcePage ?? null,
      pdf2Page: b?.sourcePage ?? null,
      pdf1Group: a?.sourceGroup ?? null,
      pdf2Group: b?.sourceGroup ?? null,
      explanation,
    });
  }

  return comparisons;
}
