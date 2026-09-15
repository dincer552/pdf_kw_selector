import React from 'react';
import { SysrecoRow } from '../types';
import { Layers } from 'lucide-react';

interface SysrecoTableProps {
  rows: SysrecoRow[];
  onOpenPdf?: (fileName: string, side?: 'PDF1' | 'PDF2') => void;
}

export const SysrecoTable: React.FC<SysrecoTableProps> = ({ rows, onOpenPdf }) => {
  return (
    <div className="flex flex-col h-full space-y-2">
      <div className="p-3 bg-cyan-50 border border-cyan-200 rounded-lg text-xs text-cyan-900 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan-600" />
          <span>
            <strong>SysReco Kuralı:</strong> Isı geri kazanım SysReco FX serisi modelleri tespit edilir ve proje bazında listelenir.
          </span>
        </div>
        <span className="font-bold px-2 py-0.5 bg-cyan-100 rounded-full border border-cyan-300">
          {rows.length} Kayıt
        </span>
      </div>

      <div className="flex-1 overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-2xs">
        <table className="w-full text-xs text-left border-collapse">
          <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200 sticky top-0">
            <tr>
              <th className="py-2.5 px-3">Proje</th>
              <th className="py-2.5 px-3">AHU</th>
              <th className="py-2.5 px-3">PDF Dosyası</th>
              <th className="py-2.5 px-3">SysReco Model</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-8 text-center text-slate-400 italic">
                  SysReco model kaydı bulunamadı.
                </td>
              </tr>
            ) : (
              rows.map((r, i) => (
                <tr key={i} className="hover:bg-cyan-50/40 transition-colors">
                  <td className="py-2 px-3 font-medium text-slate-800">{r.projectName}</td>
                  <td className="py-2 px-3 font-bold text-slate-900">{r.ahu}</td>
                  <td className="py-2 px-3 text-slate-700 font-mono">
                    {r.pdfFile && r.pdfFile !== '-' ? (
                      <button
                        type="button"
                        onClick={() => onOpenPdf?.(r.pdfFile, 'PDF1')}
                        className="pdf-openable-cell px-1.5 py-0.5 inline-block text-left text-cyan-800 font-medium hover:text-cyan-950 rounded cursor-pointer transition-all"
                        title={`${r.pdfFile} dosyasını görüntüle`}
                      >
                        {r.pdfFile}
                      </button>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td className="py-2 px-3">
                    <span className="inline-flex px-2 py-0.5 rounded font-mono font-bold bg-cyan-100 text-cyan-900 border border-cyan-300">
                      {r.sysrecoModel}
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
