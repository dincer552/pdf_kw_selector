import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { FileDropZone } from './components/FileDropZone';
import { ResultsTable } from './components/ResultsTable';
import { EbmTable } from './components/EbmTable';
import { VocleanTable } from './components/VocleanTable';
import { SysrecoTable } from './components/SysrecoTable';
import { UnmatchedTable } from './components/UnmatchedTable';
import { LogsViewer } from './components/LogsViewer';
import { DocumentModal } from './components/DocumentModal';
import { BatchDocument, BatchAnalysisResult, LogEntry, MotorComparison } from './types';
import { extractPdfData, parsePdfDocument } from './utils/pdfParser';
import { runBatchAnalysis } from './utils/batchAnalysis';
import { getSampleDocuments } from './data/sampleData';
import { Cpu, Fan, Sparkles, Layers, AlertTriangle } from 'lucide-react';

export function App() {
  const samples = getSampleDocuments();
  const initialPdf1 = samples.pdf1.filter((d) => d.name === 'HKS-12.pdf');
  const initialPdf2 = samples.pdf2.filter((d) => d.name === 'HKS_12.pdf');

  const [pdf1Docs, setPdf1Docs] = useState<BatchDocument[]>(initialPdf1);
  const [pdf2Docs, setPdf2Docs] = useState<BatchDocument[]>(initialPdf2);
  const [activeTab, setActiveTab] = useState<'DANFOSS' | 'EBM' | 'VOCLEAN' | 'SYSRECO' | 'UNMATCHED' | 'LOGS'>('DANFOSS');
  const [tolerance, setTolerance] = useState<number>(0.01);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [progressPercent, setProgressPercent] = useState<number>(0);

  // Initial pre-analyzed result for HKS-12
  const initialResult = runBatchAnalysis(initialPdf1, initialPdf2, 0.01);
  const [analysisResult, setAnalysisResult] = useState<BatchAnalysisResult | null>(initialResult);

  const initialLogs: LogEntry[] = [
    { id: '1', timestamp: '20:58:12', level: 'INFO', message: 'PDF kW Selector v0.2.4 başlatıldı. Hazır.' },
    { id: '2', timestamp: '20:58:14', level: 'INFO', message: 'PDF1 dokümanı yüklendi: HKS-12.pdf (Sayfa: 3)' },
    { id: '3', timestamp: '20:58:15', level: 'INFO', message: 'PDF2 dokümanı yüklendi: HKS_12.pdf (Sayfa: 3)' },
    { id: '4', timestamp: '20:58:15', level: 'INFO', message: 'Proje tespiti: Ekol Sada Hastanesi (PDF1)' },
    { id: '5', timestamp: '20:58:15', level: 'INFO', message: 'AHU tespiti: HKS-12, AHU-KIT (PDF1)' },
    { id: '6', timestamp: '20:58:16', level: 'INFO', message: 'AHU tespiti: HKS-12 (PDF2)' },
    { id: '7', timestamp: '20:58:16', level: 'INFO', message: 'Motor koordinat taraması: 2 adet motor bulundu (HKS-12)' },
    { id: '8', timestamp: '20:58:16', level: 'INFO', message: 'Danfoss motor gücü doğrulandı: 7.50 kW (Vantilatör)' },
    { id: '9', timestamp: '20:58:16', level: 'INFO', message: 'Danfoss motor gücü doğrulandı: 4.00 kW (Aspiratör)' },
    { id: '10', timestamp: '20:58:17', level: 'INFO', message: 'Proje eşleştirmesi tamamlandı: HKS-12 ↔ HKS_12' },
    { id: '11', timestamp: '20:58:17', level: 'INFO', message: 'Analiz tamamlandı: 2 motor eşleşti, 0 hata, 0 sahipsiz PDF' },
  ];
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);

  const [selectedDoc, setSelectedDoc] = useState<BatchDocument | null>(null);
  const [selectedComparison, setSelectedComparison] = useState<MotorComparison | null>(null);

  const addLog = (level: LogEntry['level'], message: string, details?: Record<string, any>) => {
    const entry: LogEntry = {
      id: Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toLocaleTimeString(),
      level,
      message,
      details,
    };
    setLogs((prev) => [entry, ...prev]);
  };

  // Handle file uploads
  const handleAddFiles = async (files: FileList | File[], side: 'PDF1' | 'PDF2') => {
    setIsAnalyzing(true);
    setProgressPercent(10);
    setProgressMessage(`${files.length} dosya okunuyor...`);

    const newDocs: BatchDocument[] = [];
    const fileArray = Array.from(files);

    for (let idx = 0; idx < fileArray.length; idx++) {
      const file = fileArray[idx];
      const pct = Math.round(10 + ((idx + 1) / fileArray.length) * 80);
      setProgressPercent(pct);
      setProgressMessage(`Sayfalar ve koordinatlar ayrıştırılıyor: ${file.name}`);

      try {
        const pages = await extractPdfData(file, file.name);
        const doc = parsePdfDocument(file.name, side, pages, file);
        newDocs.push(doc);
        addLog('INFO', `PDF başarıyla işlendi (${side}): ${file.name}`, {
          pages: pages.length,
          ahus: doc.equipment.uniqueIds,
          project: doc.project.projectName,
        });
      } catch (err: any) {
        addLog('ERROR', `PDF işleme hatası: ${file.name}`, { error: err.message || String(err) });
      }
    }

    if (side === 'PDF1') {
      setPdf1Docs((prev) => [...prev, ...newDocs]);
    } else {
      setPdf2Docs((prev) => [...prev, ...newDocs]);
    }

    setIsAnalyzing(false);
    setProgressPercent(100);
    setProgressMessage('Dosyalar eklendi.');
  };

  // Remove single file
  const handleRemoveDoc = (id: string, side: 'PDF1' | 'PDF2') => {
    if (side === 'PDF1') {
      setPdf1Docs((prev) => prev.filter((d) => d.id !== id));
    } else {
      setPdf2Docs((prev) => prev.filter((d) => d.id !== id));
    }
  };

  // Clear all inputs
  const handleClearInputs = () => {
    setPdf1Docs([]);
    setPdf2Docs([]);
    setAnalysisResult(null);
    addLog('INFO', 'Girdiler ve analiz sonuçları temizlendi.');
  };

  // Load sample dataset
  const handleLoadSamples = () => {
    const s = getSampleDocuments();
    setPdf1Docs(s.pdf1);
    setPdf2Docs(s.pdf2);
    addLog('INFO', 'Örnek mühendislik veri seti yüklendi (8 PDF1, 6 PDF2).');

    setTimeout(() => {
      executeAnalysis(s.pdf1, s.pdf2, tolerance);
    }, 100);
  };

  // Load HKS-12 regression files
  const handleLoadHks12Only = async () => {
    setIsAnalyzing(true);
    setProgressPercent(20);
    setProgressMessage('HKS-12 PDF dosyaları getiriliyor...');

    try {
      const [res1, res2] = await Promise.all([
        fetch('/HKS-12.pdf'),
        fetch('/HKS_12.pdf'),
      ]);

      if (res1.ok && res2.ok) {
        const [buf1, buf2] = await Promise.all([res1.arrayBuffer(), res2.arrayBuffer()]);
        setProgressPercent(50);
        setProgressMessage('PDF sayfaları çözümleniyor...');

        const [p1Pages, p2Pages] = await Promise.all([
          extractPdfData(buf1, 'HKS-12.pdf'),
          extractPdfData(buf2, 'HKS_12.pdf'),
        ]);

        const doc1 = parsePdfDocument('HKS-12.pdf', 'PDF1', p1Pages);
        const doc2 = parsePdfDocument('HKS_12.pdf', 'PDF2', p2Pages);

        setPdf1Docs([doc1]);
        setPdf2Docs([doc2]);
        addLog('INFO', 'Gerçek HKS-12 dosyaları PDF.js ile çözümlendi.');
        setIsAnalyzing(false);

        executeAnalysis([doc1], [doc2], tolerance);
        return;
      }
    } catch (e) {
      console.warn('Real file fetch error, falling back to pre-parsed HKS-12', e);
    }

    const s = getSampleDocuments();
    const hks1 = s.pdf1.filter((d) => d.name === 'HKS-12.pdf');
    const hks2 = s.pdf2.filter((d) => d.name === 'HKS_12.pdf');
    setPdf1Docs(hks1);
    setPdf2Docs(hks2);
    addLog('INFO', 'HKS-12 örnekleri yüklendi.');
    setIsAnalyzing(false);
    executeAnalysis(hks1, hks2, tolerance);
  };

  // Execute Analysis
  const executeAnalysis = (
    p1: BatchDocument[] = pdf1Docs,
    p2: BatchDocument[] = pdf2Docs,
    tol: number = tolerance
  ) => {
    if (p1.length === 0 || p2.length === 0) {
      addLog('WARNING', 'Analiz başlatılamadı: Her iki tarafta da en az bir PDF bulunmalıdır.');
      return;
    }

    setIsAnalyzing(true);
    setProgressPercent(30);
    setProgressMessage('Proje eşleştirmesi yapılıyor...');

    setTimeout(() => {
      setProgressPercent(60);
      setProgressMessage('AHU ve motor anma güçleri eşleştiriliyor...');

      setTimeout(() => {
        const result = runBatchAnalysis(p1, p2, tol, (entry) => {
          setLogs((prev) => [entry, ...prev]);
        });

        setAnalysisResult(result);
        setIsAnalyzing(false);
        setProgressPercent(100);
        setProgressMessage('Analiz tamamlandı.');
      }, 200);
    }, 200);
  };

  const comparisons = analysisResult?.motorComparisons || [];
  const ebmRows = analysisResult?.ebmRows || [];
  const vocleanRows = analysisResult?.vocleanRows || [];
  const sysrecoRows = analysisResult?.sysrecoRows || [];
  const unmatchedRows = analysisResult?.unmatchedPdfs || [];

  const handleSelectPdfPage = (comparison: MotorComparison, side: 'PDF1' | 'PDF2') => {
    const fileName = side === 'PDF1' ? comparison.pdf1File : comparison.pdf2File;
    const doc = side === 'PDF1'
      ? pdf1Docs.find((d) => d.name === fileName || d.path === fileName)
      : pdf2Docs.find((d) => d.name === fileName || d.path === fileName);

    const page = side === 'PDF1' ? comparison.pdf1Page : comparison.pdf2Page;
    const kw = side === 'PDF1' ? comparison.pdf1Kw : comparison.pdf2Kw;
    addLog('INFO', `Kullanıcı ${side} kW değerine tıkladı: ${kw} kW (Sayfa: ${page || 1}, Dosya: ${fileName || '-'})`);

    if (doc) {
      setSelectedDoc(doc);
    }
    setSelectedComparison(comparison);
  };

  const handleOpenPdfByName = (fileName: string, side?: 'PDF1' | 'PDF2') => {
    if (!fileName || fileName === '-') return;
    const doc = (side === 'PDF2' ? pdf2Docs : pdf1Docs).find(
      (d) => d.name === fileName || d.path === fileName
    ) || (side ? (side === 'PDF1' ? pdf2Docs : pdf1Docs) : [...pdf1Docs, ...pdf2Docs]).find(
      (d) => d.name === fileName || d.path === fileName
    );
    addLog('INFO', `Kullanıcı PDF dosya hücresine tıkladı: ${fileName}`);
    if (doc) {
      setSelectedDoc(doc);
    }
  };

  return (
    <div className="min-h-screen bg-[#f0f4f9] flex flex-col font-sans text-slate-800">
      {/* Top Header */}
      <Header
        version="v0.2.4"
        tolerance={tolerance}
        onToleranceChange={(val) => {
          setTolerance(val);
          if (analysisResult) {
            executeAnalysis(pdf1Docs, pdf2Docs, val);
          }
        }}
        onRunAnalysis={() => executeAnalysis()}
        onClearInputs={handleClearInputs}
        onLoadSamples={handleLoadSamples}
        onLoadHks12Only={handleLoadHks12Only}
        isAnalyzing={isAnalyzing}
        progressMessage={progressMessage}
        progressPercent={progressPercent}
        pdf1Count={pdf1Docs.length}
        pdf2Count={pdf2Docs.length}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 py-4 flex flex-col gap-4">
        {/* PDF Drop Zones */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FileDropZone
            title="Seçim Çıktısı (PDF1)"
            side="PDF1"
            subtitle="Ekipman ve motor seçim dokümanları"
            documents={pdf1Docs}
            onAddFiles={handleAddFiles}
            onRemoveDocument={handleRemoveDoc}
            onViewDocument={(doc) => setSelectedDoc(doc)}
            disabled={isAnalyzing}
          />
          <FileDropZone
            title="Elektrik Projesi (PDF2)"
            side="PDF2"
            subtitle="Bağlantı şemaları ve pano çizimleri"
            documents={pdf2Docs}
            onAddFiles={handleAddFiles}
            onRemoveDocument={handleRemoveDoc}
            onViewDocument={(doc) => setSelectedDoc(doc)}
            disabled={isAnalyzing}
          />
        </div>

        {/* Tab Navigation & Results Container */}
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs flex flex-col overflow-hidden flex-1 min-h-[450px]">
          <div className="border-b border-slate-200/90 bg-white px-6 pt-3 flex items-center gap-6 overflow-x-auto">
            <button
              type="button"
              onClick={() => setActiveTab('DANFOSS')}
              className={`text-xs flex items-center gap-1.5 pb-2.5 cursor-pointer transition-colors whitespace-nowrap ${
                activeTab === 'DANFOSS'
                  ? 'text-[#0f172a] font-bold border-b-2 border-[#0f172a] -mb-px'
                  : 'text-slate-700 hover:text-slate-900 font-semibold border-b-2 border-transparent'
              }`}
            >
              <Cpu className="w-4 h-4 text-blue-600" />
              <span>DANFOSS / MOTOR ({comparisons.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('EBM')}
              className={`text-xs flex items-center gap-1.5 pb-2.5 cursor-pointer transition-colors whitespace-nowrap ${
                activeTab === 'EBM'
                  ? 'text-[#0f172a] font-bold border-b-2 border-[#0f172a] -mb-px'
                  : 'text-slate-700 hover:text-slate-900 font-semibold border-b-2 border-transparent'
              }`}
            >
              <Fan className="w-4 h-4 text-amber-500" />
              <span>EBM-PAPST ({ebmRows.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('VOCLEAN')}
              className={`text-xs flex items-center gap-1.5 pb-2.5 cursor-pointer transition-colors whitespace-nowrap ${
                activeTab === 'VOCLEAN'
                  ? 'text-[#0f172a] font-bold border-b-2 border-[#0f172a] -mb-px'
                  : 'text-slate-700 hover:text-slate-900 font-semibold border-b-2 border-transparent'
              }`}
            >
              <Sparkles className="w-4 h-4 text-purple-600" />
              <span>VOCLEAN ({vocleanRows.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('SYSRECO')}
              className={`text-xs flex items-center gap-1.5 pb-2.5 cursor-pointer transition-colors whitespace-nowrap ${
                activeTab === 'SYSRECO'
                  ? 'text-[#0f172a] font-bold border-b-2 border-[#0f172a] -mb-px'
                  : 'text-slate-700 hover:text-slate-900 font-semibold border-b-2 border-transparent'
              }`}
            >
              <Layers className="w-4 h-4 text-cyan-600" />
              <span>SYSRECO ({sysrecoRows.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('UNMATCHED')}
              className={`text-xs flex items-center gap-1.5 pb-2.5 cursor-pointer transition-colors whitespace-nowrap ${
                activeTab === 'UNMATCHED'
                  ? 'text-[#0f172a] font-bold border-b-2 border-[#0f172a] -mb-px'
                  : 'text-slate-700 hover:text-slate-900 font-semibold border-b-2 border-transparent'
              }`}
            >
              <AlertTriangle className="w-4 h-4 text-slate-700" />
              <span>EŞLEŞMEYEN PDF'LER ({unmatchedRows.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('LOGS')}
              className={`ml-auto text-xs flex items-center gap-1 pb-2.5 cursor-pointer transition-colors whitespace-nowrap ${
                activeTab === 'LOGS'
                  ? 'text-[#0f172a] font-bold border-b-2 border-[#0f172a] -mb-px'
                  : 'text-slate-700 hover:text-slate-900 font-semibold border-b-2 border-transparent'
              }`}
            >
              <span className="font-mono text-xs text-slate-500 font-bold">&gt;_</span>
              <span>LOGLAR ({logs.length})</span>
            </button>
          </div>

          {/* Tab Panes */}
          <div className="p-6 flex-1 flex flex-col overflow-hidden bg-white">
            {activeTab === 'DANFOSS' && (
              <ResultsTable
                comparisons={comparisons}
                onSelectRow={(row) => setSelectedComparison(row)}
                onSelectPdfPage={handleSelectPdfPage}
              />
            )}

            {activeTab === 'EBM' && (
              <EbmTable rows={ebmRows} onOpenPdf={handleOpenPdfByName} />
            )}

            {activeTab === 'VOCLEAN' && (
              <VocleanTable rows={vocleanRows} onOpenPdf={handleOpenPdfByName} />
            )}

            {activeTab === 'SYSRECO' && (
              <SysrecoTable rows={sysrecoRows} onOpenPdf={handleOpenPdfByName} />
            )}

            {activeTab === 'UNMATCHED' && (
              <UnmatchedTable rows={unmatchedRows} onOpenPdf={handleOpenPdfByName} />
            )}

            {activeTab === 'LOGS' && (
              <LogsViewer
                logs={logs}
                analysisResult={analysisResult}
                onClearLogs={() => setLogs([])}
              />
            )}
          </div>
        </div>
      </main>

      {/* Detail / Document Modal */}
      {(selectedDoc || selectedComparison) && (
        <DocumentModal
          document={selectedDoc}
          comparison={selectedComparison}
          onClose={() => {
            setSelectedDoc(null);
            setSelectedComparison(null);
          }}
        />
      )}
    </div>
  );
}
