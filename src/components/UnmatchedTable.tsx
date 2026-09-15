import React from 'react';
import { UnmatchedPdfRow } from '../types';
import { AlertTriangle } from 'lucide-react';

interface UnmatchedTableProps {
  rows: UnmatchedPdfRow[];
}

export const UnmatchedTable: React.FC<UnmatchedTableProps> = ({ rows }) => {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 bg-[#f8fafc] border border-slate-200/80 rounded-lg text-xs text-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
          <span>
            <strong>Sahipsiz ve Eşleşmeyen PDF'ler:</strong>{' '}
            <span className="text-slate-600">
              Hiçbir başarılı AHU eşleşmesine giremeyen PDF'ler burada teşhis amacıyla listelenir.
            </span>
          </span>
        </div>
        <span className="font-bold px-2.5 py-0.5 bg-slate-200/80 text-slate-700 rounded-full text-xs">
          {rows.length} PDF
        </span>
      </div>

      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200/80 bg-white">
        <table className="w-full text-xs text-left border-collapse">
          <thead className="bg-[#f8fafc] text-slate-800 font-bold border-b border-slate-200/80">
            <tr>
              <th className="py-2.5 px-4 font-bold">Taraf</th>
              <th className="py-2.5 px-4 font-bold">PDF Dosyası</th>
              <th className="py-2.5 px-4 font-bold">Proje</th>
              <th className="py-2.5 px-4 font-bold">Tespit Edilen AHU</th>
              <th className="py-2.5 px-4 font-bold">Neden</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-14 text-center text-slate-400 italic text-xs">
                  Eşleşmeyen sahipsiz PDF bulunmuyor. Tüm PDF'ler başarıyla eşleşti!
                </td>
              </tr>
            ) : (
              rows.map((r, i) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="py-2.5 px-4 font-semibold">
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] ${
                        r.side === 'PDF1'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-indigo-100 text-indigo-800'
                      }`}
                    >
                      {r.side}
                    </span>
                  </td>
                  <td className="py-2.5 px-4 text-slate-800 font-mono font-medium">{r.pdfName}</td>
                  <td className="py-2.5 px-4 text-slate-700">{r.projectName || '-'}</td>
                  <td className="py-2.5 px-4 font-bold text-slate-900">{r.ahu}</td>
                  <td className="py-2.5 px-4 text-rose-700 font-medium">{r.reason}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
