import React from 'react';
import { VocleanRow } from '../types';
import { Sparkles } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface VocleanTableProps {
  rows: VocleanRow[];
  onOpenPdf?: (fileName: string, side: 'PDF1' | 'PDF2') => void;
}

export const VocleanTable: React.FC<VocleanTableProps> = ({ rows, onOpenPdf }) => {
  return (
    <div className="flex flex-col h-full space-y-2">
      <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg text-xs text-purple-900 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-600" />
          <span>
            <strong>VOClean Kuralı:</strong> VOClean ekipmanlarında motor gücü BA öneki koduna dönüştürülür (örneğin 0.75 kW → <code>BA075-</code>) ve PDF2 ekipman kodlarıyla doğrulanır.
          </span>
        </div>
        <span className="font-bold px-2 py-0.5 bg-purple-100 rounded-full border border-purple-300">
          {rows.length} Kayıt
        </span>
      </div>

      <div className="flex-1 overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-2xs">
        <table className="w-full text-xs text-left border-collapse">
          <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200 sticky top-0">
            <tr>
              <th className="py-2.5 px-3">Proje</th>
              <th className="py-2.5 px-3">PDF1 (Seçim)</th>
              <th className="py-2.5 px-3 text-right">VOClean kW</th>
              <th className="py-2.5 px-3 text-center">PDF1 Sayfa</th>
              <th className="py-2.5 px-3">PDF2 (Elektrik)</th>
              <th className="py-2.5 px-3">AHU / BA Kodu</th>
              <th className="py-2.5 px-3">Durum</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-slate-400 italic">
                  VOClean ekipman kaydı bulunamadı.
                </td>
              </tr>
            ) : (
              rows.map((r, i) => {
                const isMatched = r.status.includes('eşleşti');
                return (
                  <tr key={i} className="hover:bg-purple-50/40 transition-colors">
                    <td className="py-2 px-3 font-medium text-slate-800">{r.projectName}</td>
                    <td className="py-2 px-3 text-slate-700 font-mono">
                      {r.pdf1File && r.pdf1File !== '-' ? (
                        <button
                          type="button"
                          onClick={() => onOpenPdf?.(r.pdf1File, 'PDF1')}
                          className="pdf-openable-cell px-1.5 py-0.5 inline-block text-left text-blue-700 font-medium hover:text-blue-950 rounded cursor-pointer transition-all"
                          title={`${r.pdf1File} dosyasını görüntüle`}
                        >
                          {r.pdf1File}
                        </button>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="py-2 px-3 text-right font-mono font-semibold text-purple-900">
                      {r.vocleanKw}
                    </td>
                    <td className="py-2 px-3 text-center text-slate-600">{r.pdf1Page}</td>
                    <td className="py-2 px-3 text-slate-700 font-mono">
                      {r.pdf2File && r.pdf2File !== '-' ? (
                        <button
                          type="button"
                          onClick={() => onOpenPdf?.(r.pdf2File, 'PDF2')}
                          className="pdf-openable-cell px-1.5 py-0.5 inline-block text-left text-indigo-700 font-medium hover:text-indigo-950 rounded cursor-pointer transition-all"
                          title={`${r.pdf2File} dosyasını görüntüle`}
                        >
                          {r.pdf2File}
                        </button>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="py-2 px-3 font-bold text-slate-900">
                      <span className="px-1.5 py-0.5 rounded bg-purple-100/70 border border-purple-200">
                        {r.ahu}
                      </span>
                    </td>
                    <td className="py-2 px-3 whitespace-nowrap">
                      <StatusBadge status={r.status} isMatch={isMatched} />
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
