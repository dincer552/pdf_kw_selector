import React, { useState } from 'react';
import { CheckCircle2, XCircle, AlertCircle, Search, Info } from 'lucide-react';
import { MotorComparison } from '../types';
import { StatusBadge } from './StatusBadge';

interface ResultsTableProps {
  comparisons: MotorComparison[];
  onSelectRow?: (row: MotorComparison) => void;
  onSelectPdfPage?: (row: MotorComparison, side: 'PDF1' | 'PDF2') => void;
}

export const ResultsTable: React.FC<ResultsTableProps> = ({ comparisons, onSelectRow, onSelectPdfPage }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'MATCH' | 'MISMATCH' | 'SPECIAL'>('ALL');

  const filtered = comparisons.filter((c) => {
    const matchesSearch =
      (c.projectName || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.equipmentId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.componentLabel.toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    if (statusFilter === 'MATCH') return c.status === 'MATCH';
    if (statusFilter === 'MISMATCH') return c.status === 'MISMATCH';
    if (statusFilter === 'SPECIAL') return c.status === 'EBM_PAPST' || c.status.startsWith('ONLY_IN');
    return true;
  });

  const totalCount = comparisons.length;
  const matchCount = comparisons.filter((c) => c.status === 'MATCH').length;
  const mismatchCount = comparisons.filter((c) => c.status === 'MISMATCH').length;
  const otherCount = totalCount - matchCount - mismatchCount;

  return (
    <div className="flex flex-col h-full space-y-3">
      {/* Metric summary badges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs flex items-center justify-between">
          <span className="text-slate-600 font-medium">Toplam Motor</span>
          <span className="text-sm font-bold text-slate-800">{totalCount}</span>
        </div>
        <div className="bg-emerald-50/70 p-2.5 rounded-lg border border-emerald-200 shadow-2xs flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-emerald-800 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>Eşleşen (Match)</span>
          </div>
          <span className="text-sm font-bold text-emerald-700">{matchCount}</span>
        </div>
        <div className="bg-rose-50/70 p-2.5 rounded-lg border border-rose-200 shadow-2xs flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-rose-800 font-medium">
            <XCircle className="w-3.5 h-3.5 text-rose-600" />
            <span>Farklı (Mismatch)</span>
          </div>
          <span className="text-sm font-bold text-rose-700">{mismatchCount}</span>
        </div>
        <div className="bg-amber-50/70 p-2.5 rounded-lg border border-amber-200 shadow-2xs flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-amber-800 font-medium">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
            <span>Özel / Tek Taraf</span>
          </div>
          <span className="text-sm font-bold text-amber-700">{otherCount}</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Proje veya AHU ara..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-300 rounded-md focus:outline-hidden focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-1 self-end sm:self-auto text-xs">
          <button
            type="button"
            onClick={() => setStatusFilter('ALL')}
            className={`px-2.5 py-1 rounded transition-colors ${
              statusFilter === 'ALL'
                ? 'bg-slate-800 text-white font-semibold'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Tümü ({totalCount})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('MATCH')}
            className={`px-2.5 py-1 rounded transition-colors ${
              statusFilter === 'MATCH'
                ? 'bg-emerald-600 text-white font-semibold'
                : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
            }`}
          >
            Eşleşen ({matchCount})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('MISMATCH')}
            className={`px-2.5 py-1 rounded transition-colors ${
              statusFilter === 'MISMATCH'
                ? 'bg-rose-600 text-white font-semibold'
                : 'bg-rose-50 text-rose-700 hover:bg-rose-100'
            }`}
          >
            Uyuşmayan ({mismatchCount})
          </button>
        </div>
      </div>

      {/* Results Table */}
      <div className="flex-1 overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-2xs">
        <table className="w-full text-xs text-left border-collapse">
          <thead className="bg-slate-100/90 text-slate-700 font-semibold border-b border-slate-200 sticky top-0">
            <tr>
              <th className="py-2.5 px-3">Proje</th>
              <th className="py-2.5 px-3">AHU / Ekipman</th>
              <th className="py-2.5 px-3">Motor / Rol</th>
              <th className="py-2.5 px-3 text-right">Seçim kW</th>
              <th className="py-2.5 px-3 text-right">Elektrik P. kW</th>
              <th className="py-2.5 px-3 text-right">Fark</th>
              <th className="py-2.5 px-3 text-center">Durum</th>
              <th className="py-2.5 px-3">Açıklama</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-slate-400 italic">
                  {comparisons.length === 0
                    ? 'Henüz analiz yapılmadı. Lütfen PDF ekleyip "ANALİZ BAŞLA" butonuna basın.'
                    : 'Filtreye uygun motor bulunamadı.'}
                </td>
              </tr>
            ) : (
              filtered.map((item, idx) => {
                const isMismatch = item.status === 'MISMATCH';
                const isMatch = item.status === 'MATCH';

                // Original Tkinter color style: mismatch is highlighted in #ffb3b3
                const rowBg = isMismatch
                  ? 'bg-[#ffe4e6] hover:bg-[#fecdd3]'
                  : isMatch
                  ? 'hover:bg-slate-50'
                  : 'bg-amber-50/40 hover:bg-amber-50';

                return (
                  <tr
                    key={`${item.equipmentId}-${item.componentIndex}-${idx}`}
                    onClick={() => onSelectRow?.(item)}
                    className={`${rowBg} transition-colors cursor-pointer`}
                  >
                    <td className="py-2 px-3 font-medium text-slate-800">
                      {item.projectName || '-'}
                    </td>
                    <td className="py-2 px-3 font-bold text-slate-900">
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200">
                        {item.equipmentId}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-700">
                      <span className="font-medium">{item.componentLabel}</span>
                      {item.pdf1Group && (
                        <span className="text-[10px] text-slate-400 ml-1.5">
                          ({item.pdf1Group})
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-right font-mono font-semibold text-slate-800">
                      {item.pdf1Kw !== null ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectPdfPage ? onSelectPdfPage(item, 'PDF1') : onSelectRow?.(item);
                          }}
                          className="pdf-openable-cell inline-flex items-center gap-1 font-bold text-blue-700 hover:text-blue-900 bg-blue-50 hover:bg-blue-100 px-2 py-0.5 rounded border border-blue-200 transition-all cursor-pointer"
                          title={item.pdf1File ? `Sayfa ${item.pdf1Page || 1} aç (${item.pdf1File})` : 'Kaynak sayfayı görüntüle'}
                        >
                          <span>{item.pdf1Kw} kW</span>
                        </button>
                      ) : '-'}
                    </td>
                    <td className="py-2 px-3 text-right font-mono font-semibold text-slate-800">
                      {item.pdf2Kw !== null ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectPdfPage ? onSelectPdfPage(item, 'PDF2') : onSelectRow?.(item);
                          }}
                          className="pdf-openable-cell inline-flex items-center gap-1 font-bold text-indigo-700 hover:text-indigo-900 bg-indigo-50 hover:bg-indigo-100 px-2 py-0.5 rounded border border-indigo-200 transition-all cursor-pointer"
                          title={item.pdf2File ? `Sayfa ${item.pdf2Page || 1} aç (${item.pdf2File})` : 'Kaynak sayfayı görüntüle'}
                        >
                          <span>{item.pdf2Kw} kW</span>
                        </button>
                      ) : '-'}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-slate-600">
                      {item.differenceKw !== null
                        ? `${item.differenceKw.toFixed(2)} kW`
                        : '-'}
                    </td>
                    <td className="py-2 px-3 text-center whitespace-nowrap">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="py-2 px-3 text-slate-600 max-w-xs truncate" title={item.explanation}>
                      {item.explanation}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
