import React from 'react';
import { EbmRow } from '../types';
import { Fan, CheckCircle2 } from 'lucide-react';

interface EbmTableProps {
  rows: EbmRow[];
  onOpenPdf?: (fileName: string, side: 'PDF1' | 'PDF2') => void;
}

export const EbmTable: React.FC<EbmTableProps> = ({ rows, onOpenPdf }) => {
  return (
    <div className="flex flex-col h-full space-y-2">
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Fan className="w-4 h-4 text-amber-600" />
          <span>
            <strong>EBM-Papst Kuralı:</strong> PDF1'de EBM-Papst fan motoru tespit edilen AHU'lar için motor kW karşılaştırması atlanır; proje ve AHU eşleşmesi doğrulanır.
          </span>
        </div>
        <span className="font-bold px-2 py-0.5 bg-amber-100 rounded-full border border-amber-300">
          {rows.length} Kayıt
        </span>
      </div>

      <div className="flex-1 overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-2xs">
        <table className="w-full text-xs text-left border-collapse">
          <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200 sticky top-0">
            <tr>
              <th className="py-2.5 px-3">Proje</th>
              <th className="py-2.5 px-3">AHU</th>
              <th className="py-2.5 px-3">Seçim Çıktısı (PDF1)</th>
              <th className="py-2.5 px-3">Elektrik P. (PDF2)</th>
              <th className="py-2.5 px-3">Durum</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-400 italic">
                  EBM-Papst ekipman kaydı bulunamadı.
                </td>
              </tr>
            ) : (
              rows.map((r, i) => (
                <tr key={i} className="hover:bg-amber-50/40 transition-colors">
                  <td className="py-2 px-3 font-medium text-slate-800">{r.projectName}</td>
                  <td className="py-2 px-3 font-bold text-slate-900">
                    <span className="px-1.5 py-0.5 rounded bg-amber-100/70 border border-amber-200">
                      {r.ahu}
                    </span>
                  </td>
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
                  <td className="py-2 px-3 text-slate-700 font-mono">
                    {r.pdf2Files && r.pdf2Files !== '-' ? (
                      <button
                        type="button"
                        onClick={() => onOpenPdf?.(r.pdf2Files, 'PDF2')}
                        className="pdf-openable-cell px-1.5 py-0.5 inline-block text-left text-indigo-700 font-medium hover:text-indigo-950 rounded cursor-pointer transition-all"
                        title={`${r.pdf2Files} dosyasını görüntüle`}
                      >
                        {r.pdf2Files}
                      </button>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="py-2 px-3">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
