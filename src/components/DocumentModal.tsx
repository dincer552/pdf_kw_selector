import React from 'react';
import { X, FileText, CheckCircle2, AlertCircle, Layers } from 'lucide-react';
import { BatchDocument, MotorComparison } from '../types';

interface DocumentModalProps {
  document?: BatchDocument | null;
  comparison?: MotorComparison | null;
  onClose: () => void;
}

export const DocumentModal: React.FC<DocumentModalProps> = ({
  document,
  comparison,
  onClose,
}) => {
  if (!document && !comparison) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-600" />
            <h3 className="text-sm font-bold text-slate-800">
              {document ? `Belge İnceleme: ${document.name}` : `Motor Detayı: ${comparison?.equipmentId} - ${comparison?.componentLabel}`}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-700 rounded-md transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 overflow-y-auto space-y-4 text-xs">
          {comparison && (
            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 grid grid-cols-2 gap-3">
                <div>
                  <span className="text-slate-500 font-medium block">Proje Adı:</span>
                  <span className="font-semibold text-slate-900">{comparison.projectName || '-'}</span>
                </div>
                <div>
                  <span className="text-slate-500 font-medium block">Ekipman ID (AHU):</span>
                  <span className="font-semibold text-slate-900">{comparison.equipmentId}</span>
                </div>
                <div>
                  <span className="text-slate-500 font-medium block">Bileşen / Rol:</span>
                  <span className="font-semibold text-slate-900">{comparison.componentLabel}</span>
                </div>
                <div>
                  <span className="text-slate-500 font-medium block">Durum:</span>
                  <span className="font-bold text-slate-900">{comparison.status}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg border border-blue-200 bg-blue-50/50">
                  <div className="font-bold text-blue-900 mb-1">Seçim Çıktısı (PDF1)</div>
                  <div className="text-slate-700">Motor Gücü: <strong className="text-blue-950 font-mono">{comparison.pdf1Kw !== null ? `${comparison.pdf1Kw} kW` : '-'}</strong></div>
                  <div className="text-slate-600 text-[11px] mt-1">Dosya: {comparison.pdf1File || '-'}</div>
                  <div className="text-slate-600 text-[11px]">Grup / Adet: {comparison.pdf1Group || '-'}</div>
                  <div className="text-slate-600 text-[11px]">Sayfa: {comparison.pdf1Page || '-'}</div>
                </div>

                <div className="p-3 rounded-lg border border-indigo-200 bg-indigo-50/50">
                  <div className="font-bold text-indigo-900 mb-1">Elektrik Projesi (PDF2)</div>
                  <div className="text-slate-700">Motor Gücü: <strong className="text-indigo-950 font-mono">{comparison.pdf2Kw !== null ? `${comparison.pdf2Kw} kW` : '-'}</strong></div>
                  <div className="text-slate-600 text-[11px] mt-1">Dosya: {comparison.pdf2File || '-'}</div>
                  <div className="text-slate-600 text-[11px]">Grup / Adet: {comparison.pdf2Group || '-'}</div>
                  <div className="text-slate-600 text-[11px]">Sayfa: {comparison.pdf2Page || '-'}</div>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-amber-50/60 border border-amber-200">
                <span className="font-semibold text-amber-900 block mb-1">Doğrulama Notu / Gerekçe:</span>
                <p className="text-slate-700">{comparison.explanation}</p>
              </div>
            </div>
          )}

          {document && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2 p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <div>
                  <span className="text-slate-500 font-medium block">Taraf:</span>
                  <span className="font-bold text-slate-800">{document.side}</span>
                </div>
                <div>
                  <span className="text-slate-500 font-medium block">Sayfa Sayısı:</span>
                  <span className="font-semibold text-slate-800">{document.pageCount}</span>
                </div>
                <div>
                  <span className="text-slate-500 font-medium block">Tespit Edilen Proje:</span>
                  <span className="font-semibold text-slate-800">{document.project.projectName || 'Belirsiz'}</span>
                </div>
              </div>

              <div>
                <span className="font-bold text-slate-800 block mb-1">Tespit Edilen AHU / Ekipmanlar:</span>
                <div className="flex flex-wrap gap-1.5">
                  {document.equipment.uniqueIds.length === 0 ? (
                    <span className="text-slate-400 italic">Ekipman ID bulunamadı</span>
                  ) : (
                    document.equipment.uniqueIds.map((ahu, i) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-blue-100 text-blue-900 font-bold border border-blue-200">
                        {ahu}
                      </span>
                    ))
                  )}
                </div>
              </div>

              {document.side === 'PDF1' && document.pdf1Motors.length > 0 && (
                <div>
                  <span className="font-bold text-slate-800 block mb-1">PDF1 Motor Kayıtları:</span>
                  <div className="space-y-1">
                    {document.pdf1Motors.map((m, i) => (
                      <div key={i} className="p-2 bg-slate-50 border border-slate-200 rounded flex justify-between">
                        <div>
                          <strong className="text-slate-800">{m.componentType}</strong> ({m.componentRole}) - Sayfa {m.pageNumber}
                          <div className="text-[11px] text-slate-500 font-mono">{m.sourceText}</div>
                        </div>
                        <span className="font-mono font-bold text-blue-700">{m.valueKw} kW ({m.quantity || '1x1'})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {document.side === 'PDF2' && document.pdf2Motors.length > 0 && (
                <div>
                  <span className="font-bold text-slate-800 block mb-1">PDF2 Motor Kayıtları:</span>
                  <div className="space-y-1">
                    {document.pdf2Motors.map((m, i) => (
                      <div key={i} className="p-2 bg-slate-50 border border-slate-200 rounded flex justify-between">
                        <div>
                          <strong className="text-slate-800">{m.componentType}</strong> - Sayfa {m.pageNumber}
                          <div className="text-[11px] text-slate-500 font-mono">{m.sourceText}</div>
                        </div>
                        <span className="font-mono font-bold text-indigo-700">{m.valueKw} kW</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <span className="font-bold text-slate-800 block mb-1">Metin Önizleme (İlk 3 Sayfa):</span>
                <div className="bg-slate-900 text-slate-200 p-3 rounded-md font-mono text-[11px] max-h-48 overflow-y-auto whitespace-pre-wrap">
                  {document.pageTexts.slice(0, 3).map((txt, idx) => (
                    <div key={idx} className="mb-2 pb-2 border-b border-slate-800">
                      <span className="text-blue-400 font-bold block">--- SAYFA {idx + 1} ---</span>
                      {txt || '(Boş sayfa)'}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 bg-white border border-slate-300 rounded shadow-2xs transition-colors"
          >
            Kapat
          </button>
        </div>
      </div>
    </div>
  );
};
