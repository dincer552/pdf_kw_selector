import * as pdfjsLib from 'pdfjs-dist';
import { BatchDocument, MotorPowerResult } from '../types';
import { discoverEquipmentFromText, discoverEquipmentFromFilename } from './ahuMatching';
import { discoverProjectFromText } from './projectMatching';
import { parseRatedPower } from './motorCompare';

// Configure pdfjs worker
if (typeof window !== 'undefined') {
  pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`;
}

export interface ExtractedPage {
  pageNumber: number;
  text: string;
  items: Array<{ str: string; x: number; y: number; width: number; height: number }>;
}

export async function extractPdfData(file: File | ArrayBuffer, fileName: string): Promise<ExtractedPage[]> {
  try {
    const data = file instanceof File ? await file.arrayBuffer() : file;
    const loadingTask = pdfjsLib.getDocument({ data });
    const pdfDoc = await loadingTask.promise;
    const pages: ExtractedPage[] = [];

    for (let i = 1; i <= pdfDoc.numPages; i++) {
      const page = await pdfDoc.getPage(i);
      const textContent = await page.getTextContent();
      const viewport = page.getViewport({ scale: 1.0 });

      let pageText = '';
      const items: ExtractedPage['items'] = [];

      for (const item of textContent.items as any[]) {
        if ('str' in item && item.str) {
          pageText += item.str + ' ';
          items.push({
            str: item.str,
            x: item.transform[4],
            y: item.transform[5],
            width: item.width,
            height: item.height,
          });
        }
      }

      pages.push({
        pageNumber: i,
        text: pageText,
        items,
      });
    }

    return pages;
  } catch (err) {
    console.error('PDF extraction failed for ' + fileName, err);
    throw err;
  }
}

export function parsePdfDocument(
  fileName: string,
  side: 'PDF1' | 'PDF2',
  pages: ExtractedPage[],
  file?: File
): BatchDocument {
  const pageTexts = pages.map(p => p.text);
  const fullText = pageTexts.join('\n');

  // Discover Project
  const project = discoverProjectFromText(pageTexts);

  // Discover AHU
  let equipment = discoverEquipmentFromText(pageTexts);
  if (equipment.uniqueIds.length === 0) {
    const fnOccurrence = discoverEquipmentFromFilename(fileName);
    if (fnOccurrence) {
      equipment = {
        equipmentIds: [fnOccurrence],
        uniqueIds: [fnOccurrence.normalized],
      };
    }
  }

  const defaultAhu = equipment.uniqueIds[0] || null;

  // Motors discovery
  const pdf1Motors: MotorPowerResult[] = [];
  const pdf2Motors: MotorPowerResult[] = [];
  const ebmPages: number[] = [];

  // Check special equipment: VOClean, SysReco
  const isVoclean = /\bVOC\s*LEAN\b/i.test(fullText);
  const isSysreco = /\bSysReco\b/i.test(fullText);

  if (side === 'PDF1') {
    pages.forEach(p => {
      const text = p.text;
      const hasPlugFan = /\bplug\s+fan\b/i.test(text);
      const isSupply = /\bsupply\s+air\b/i.test(text);
      const isExhaust = /\b(?:exhaust|return)\s+air\b/i.test(text);

      const isEbm = /ebm[- ]?papst/i.test(text);
      if (isEbm) {
        ebmPages.push(p.pageNumber);
      }

      if (hasPlugFan || isSupply || isExhaust) {
        // Look for Rated Power [kW]
        const ratedMatch = text.match(/Rated\s+Power\s*(?:\[kW\])?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?(?:\s*[x×]\s*\(\s*\d+\s*[x×]\s*\d+\s*\))?)/i);
        if (ratedMatch) {
          const parsed = parseRatedPower(ratedMatch[1]);
          if (parsed) {
            const compType = isSupply ? 'Vantilatör' : isExhaust ? 'Aspiratör' : 'Vantilatör';
            const compRole = isSupply ? 'supply_fan' : 'exhaust_fan';
            const brandMatch = text.match(/Model\s*Brand\s*[:=]?\s*([A-Za-z0-9-_ ]{2,20})/i);

            pdf1Motors.push({
              pageNumber: p.pageNumber,
              valueKw: parsed.valueKw,
              rawValue: parsed.rawValue,
              quantity: parsed.quantity,
              field: 'Rated Power [kW]',
              confidence: 'high',
              sourceText: ratedMatch[0],
              componentType: compType,
              componentRole: compRole,
              equipmentId: defaultAhu,
              modelBrand: isEbm ? 'EBM-Papst' : (brandMatch ? brandMatch[1].trim() : null),
            });
          }
        }
      }
    });

    // Fallback: If no plug fan pages detected but keywords exist (like HKS-12 sample)
    if (pdf1Motors.length === 0) {
      pages.forEach(p => {
        const text = p.text;
        const matches = text.matchAll(/(Supply|Return|Exhaust)\s*(?:Air)?\s*(?:Fan)?.*?([0-9]+(?:[.,][0-9]+)?)\s*kW/gi);
        for (const m of matches) {
          const role = m[1].toLowerCase().includes('supply') ? 'supply_fan' : 'return_fan';
          const type = role === 'supply_fan' ? 'Vantilatör' : 'Aspiratör';
          const kw = parseFloat(m[2].replace(',', '.'));
          pdf1Motors.push({
            pageNumber: p.pageNumber,
            valueKw: kw,
            rawValue: m[2],
            quantity: '1x1',
            field: 'Inline kW discovery',
            confidence: 'medium',
            sourceText: m[0],
            componentType: type,
            componentRole: role,
            equipmentId: defaultAhu,
            modelBrand: null,
          });
        }
      });
    }
  } else {
    // Side === 'PDF2' (Electrical schematics)
    pages.forEach(p => {
      const text = p.text;

      // Pattern: "Supply Motor Connections-1" or "Supply Motor Connections"
      const connPatterns = [
        { label: 'Supply Motor Connections-1', type: 'Vantilatör', role: 'supply_fan' },
        { label: 'Supply Motor Connections-2', type: 'Vantilatör', role: 'supply_fan' },
        { label: 'Return Motor Connections-1', type: 'Aspiratör', role: 'return_fan' },
        { label: 'Return Motor Connections-2', type: 'Aspiratör', role: 'return_fan' },
        { label: 'Supply Fan Motor', type: 'Vantilatör', role: 'supply_fan' },
        { label: 'Return Fan Motor', type: 'Aspiratör', role: 'return_fan' },
      ];

      connPatterns.forEach(({ label, type, role }) => {
        const re = new RegExp(`${label}[\\s\\S]{0,100}?([0-9]+(?:[.,][0-9]+)?)\\s*kW`, 'i');
        const match = text.match(re);
        if (match) {
          const kw = parseFloat(match[1].replace(',', '.'));
          pdf2Motors.push({
            pageNumber: p.pageNumber,
            valueKw: kw,
            rawValue: match[1],
            quantity: '1x1',
            field: label,
            confidence: 'high',
            sourceText: match[0],
            componentType: type,
            componentRole: role,
            equipmentId: defaultAhu,
            modelBrand: null,
          });
        }
      });

      // Fallback if specific connection labels not present
      if (pdf2Motors.length === 0) {
        const genMatches = text.matchAll(/(Supply|Return|Vantilatör|Aspiratör)[^0-9]{1,40}?([0-9]+(?:[.,][0-9]+)?)\s*kW/gi);
        for (const m of genMatches) {
          const isSup = /supply|vantilatör/i.test(m[1]);
          const kw = parseFloat(m[2].replace(',', '.'));
          pdf2Motors.push({
            pageNumber: p.pageNumber,
            valueKw: kw,
            rawValue: m[2],
            quantity: '1x1',
            field: 'Motor Connection kW',
            confidence: 'medium',
            sourceText: m[0],
            componentType: isSup ? 'Vantilatör' : 'Aspiratör',
            componentRole: isSup ? 'supply_fan' : 'return_fan',
            equipmentId: defaultAhu,
            modelBrand: null,
          });
        }
      }
    });
  }

  return {
    id: `${side}_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    name: fileName,
    path: fileName,
    side,
    pageCount: pages.length,
    pageTexts,
    project,
    equipment,
    pdf1Motors,
    pdf2Motors,
    ebmPages,
    isVoclean,
    isSysreco,
    file,
  };
}
