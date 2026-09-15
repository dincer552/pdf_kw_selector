import React, { useState } from 'react';
import { Download, Trash2, Copy, Check, Terminal, FileCode } from 'lucide-react';
import { LogEntry, BatchAnalysisResult } from '../types';

interface LogsViewerProps {
  logs: LogEntry[];
  analysisResult: BatchAnalysisResult | null;
  onClearLogs: () => void;
}

export const LogsViewer: React.FC<LogsViewerProps> = ({ logs, analysisResult, onClearLogs }) => {
  const [levelFilter, setLevelFilter] = useState<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL');
  const [copied, setCopied] = useState(false);
  const [showTechnicalJson, setShowTechnicalJson] = useState(false);

  const filteredLogs = logs.filter((log) => {
    if (levelFilter === 'ALL') return true;
    return log.level === levelFilter;
  });

  const handleDownloadJson = () => {
    const dataToExport = {
      exportedAt: new Date().toISOString(),
      logs,
      analysis: analysisResult,
    };
    const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pdf_kw_analysis_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopyJson = () => {
    const jsonStr = JSON.stringify(analysisResult, null, 2);
    navigator.clipboard.writeText(jsonStr).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="flex flex-col h-full space-y-3">
      {/* Top Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 bg-white p-2.5 rounded-lg border border-slate-200">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-slate-500" />
          <span className="text-xs font-semibold text-slate-800">İşlem & Teşhis Logları</span>
          <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
            {logs.length} Giriş
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Level filters */}
          <div className="flex items-center bg-slate-100 p-0.5 rounded-md">
            {(['ALL', 'INFO', 'WARNING', 'ERROR'] as const).map((lvl) => (
              <button
                key={lvl}
                type="button"
                onClick={() => setLevelFilter(lvl)}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  levelFilter === lvl
                    ? 'bg-white text-slate-800 font-bold shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {lvl === 'ALL' ? 'Tümü' : lvl}
              </button>
            ))}
          </div>

          {/* Toggle JSON preview */}
          <button
            type="button"
            onClick={() => setShowTechnicalJson(!showTechnicalJson)}
            className="px-2.5 py-1 text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-300 rounded font-medium transition-colors flex items-center gap-1"
          >
            <FileCode className="w-3.5 h-3.5 text-blue-600" />
            <span>{showTechnicalJson ? 'Logları Göster' : 'Teknik JSON'}</span>
          </button>

          {/* Export JSON */}
          <button
            type="button"
            onClick={handleDownloadJson}
            disabled={!analysisResult && logs.length === 0}
            className="px-2.5 py-1 text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded font-medium transition-colors flex items-center gap-1 disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            <span>JSON KAYDET</span>
          </button>

          {/* Clear logs */}
          <button
            type="button"
            onClick={onClearLogs}
            disabled={logs.length === 0}
            className="px-2.5 py-1 text-slate-600 hover:text-red-600 bg-white hover:bg-red-50 border border-slate-300 rounded font-medium transition-colors flex items-center gap-1 disabled:opacity-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>LOGLARI TEMİZLE</span>
          </button>
        </div>
      </div>

      {/* Main Console Box */}
      {showTechnicalJson ? (
        <div className="flex-1 bg-slate-900 text-slate-100 p-4 rounded-lg font-mono text-xs overflow-auto border border-slate-800 shadow-inner relative">
          <div className="sticky top-0 right-0 flex justify-end mb-2">
            <button
              type="button"
              onClick={handleCopyJson}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs flex items-center gap-1 transition-colors"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copied ? 'Kopyalandı' : 'JSON Kopyala'}</span>
            </button>
          </div>
          <pre>{JSON.stringify(analysisResult, null, 2)}</pre>
        </div>
      ) : (
        <div className="flex-1 bg-slate-950 text-slate-200 p-3 rounded-lg font-mono text-xs overflow-y-auto border border-slate-800 shadow-inner space-y-1.5 min-h-[300px]">
          {filteredLogs.length === 0 ? (
            <div className="text-slate-500 py-8 text-center italic">Henüz log kaydı yok.</div>
          ) : (
            filteredLogs.map((log) => {
              let badgeColor = 'text-blue-400';
              if (log.level === 'WARNING') badgeColor = 'text-amber-400 font-bold';
              if (log.level === 'ERROR') badgeColor = 'text-rose-400 font-bold';
              if (log.level === 'DEBUG') badgeColor = 'text-slate-400';

              return (
                <div key={log.id} className="flex items-start gap-2 hover:bg-slate-900/60 p-1 rounded">
                  <span className="text-slate-500 text-[11px] shrink-0">[{log.timestamp}]</span>
                  <span className={`text-[11px] shrink-0 w-16 ${badgeColor}`}>[{log.level}]</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-slate-200">{log.message}</span>
                    {log.details && (
                      <div className="text-[11px] text-slate-400 mt-0.5 overflow-x-auto">
                        {JSON.stringify(log.details)}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
