export type MatchStatus =
  | 'MATCH'
  | 'MISMATCH'
  | 'ONLY_IN_PDF1'
  | 'ONLY_IN_PDF2'
  | 'EBM_PAPST'
  | 'EXACT'
  | 'NORMALIZED_MATCH'
  | 'REVIEW_REQUIRED'
  | 'NO_MATCH';

export interface EquipmentOccurrence {
  equipmentId: string;
  normalized: string;
  page: number;
  source: string;
}

export interface AHUDiscovery {
  equipmentIds: EquipmentOccurrence[];
  uniqueIds: string[];
}

export interface ProjectCandidate {
  value: string;
  normalized: string;
  source: string;
  page: number;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'REVIEW';
}

export interface ProjectDiscovery {
  projectName: string | null;
  projectNameNormalized: string | null;
  projectSource: string | null;
  projectPage: number | null;
  confidence: string;
  candidates: ProjectCandidate[];
}

export interface MotorPowerResult {
  pageNumber: number;
  valueKw: number | null;
  rawValue: string;
  quantity: string | null; // e.g., "1x1", "2x1"
  field: string;
  confidence: string;
  sourceText: string;
  componentType: string; // "Vantilatör" or "Aspiratör"
  componentRole: string; // "supply_fan" or "exhaust_fan" / "return_fan"
  equipmentId: string | null;
  modelBrand: string | null;
}

export interface MotorRecord {
  equipmentId: string;
  equipmentType: string;
  componentType: string;
  componentLabel: string;
  componentIndex: number;
  powerKw: number;
  sourcePage: number;
  sourceGroup: string;
  modelBrand: string | null;
  sourceText: string;
}

export interface MotorComparison {
  equipmentId: string;
  componentType: string;
  componentLabel: string;
  componentIndex: number;
  pdf1Kw: number | null;
  pdf2Kw: number | null;
  differenceKw: number | null;
  status: 'MATCH' | 'MISMATCH' | 'ONLY_IN_PDF1' | 'ONLY_IN_PDF2' | 'EBM_PAPST';
  pdf1Page: number | null;
  pdf2Page: number | null;
  pdf1Group: string | null;
  pdf2Group: string | null;
  explanation: string;
  projectName?: string;
  pdf1File?: string;
  pdf2File?: string;
}

export interface AHUMatch {
  leftId: string | null;
  rightId: string | null;
  leftNormalized: string | null;
  rightNormalized: string | null;
  score: number;
  status: 'EXACT' | 'NORMALIZED_MATCH' | 'REVIEW_REQUIRED' | 'NO_MATCH' | 'USER_APPROVED';
  reason: string;
  leftPage?: number | null;
  rightPage?: number | null;
}

export interface ProjectMatch {
  leftName: string | null;
  rightName: string | null;
  leftNormalized: string | null;
  rightNormalized: string | null;
  score: number;
  status: string;
  reason: string;
  leftSource?: string | null;
  rightSource?: string | null;
}

export interface BatchDocument {
  id: string;
  name: string;
  path: string;
  side: 'PDF1' | 'PDF2';
  pageCount: number;
  pageTexts: string[];
  project: ProjectDiscovery;
  equipment: AHUDiscovery;
  pdf1Motors: MotorPowerResult[];
  pdf2Motors: MotorPowerResult[];
  ebmPages: number[];
  isVoclean: boolean;
  isSysreco: boolean;
  file?: File;
}

export interface BatchAHU {
  projectName: string | null;
  match: AHUMatch;
  pdf1Files: string[];
  pdf2Files: string[];
}

export interface BatchAnalysisResult {
  pdf1Documents: BatchDocument[];
  pdf2Documents: BatchDocument[];
  projectMatches: ProjectMatch[];
  ahuMatches: BatchAHU[];
  motorComparisons: MotorComparison[];
  ebmRows: EbmRow[];
  vocleanRows: VocleanRow[];
  sysrecoRows: SysrecoRow[];
  unmatchedPdfs: UnmatchedPdfRow[];
}

export interface EbmRow {
  projectName: string;
  ahu: string;
  pdf1File: string;
  pdf2Files: string;
  status: string;
}

export interface VocleanRow {
  projectName: string;
  pdf1File: string;
  vocleanKw: string;
  pdf1Page: string;
  pdf2File: string;
  ahu: string;
  status: string;
}

export interface SysrecoRow {
  projectName: string;
  ahu: string;
  pdfFile: string;
  sysrecoModel: string;
}

export interface UnmatchedPdfRow {
  side: 'PDF1' | 'PDF2';
  pdfName: string;
  projectName: string;
  ahu: string;
  reason: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  message: string;
  details?: Record<string, any>;
}
