import React, { useRef } from 'react';
import { Upload, FileText, Trash2, Plus, Check } from 'lucide-react';
import { BatchDocument } from '../types';

interface FileDropZoneProps {
  title: string;
  side: 'PDF1' | 'PDF2';
  subtitle: string;
  documents: BatchDocument[];
  onAddFiles: (files: FileList | File[], side: 'PDF1' | 'PDF2') => void;
  onRemoveDocument: (id: string, side: 'PDF1' | 'PDF2') => void;
  onViewDocument?: (doc: BatchDocument) => void;
  disabled?: boolean;
}

export const FileDropZone: React.FC<FileDropZoneProps> = ({
  title,
  side,
  subtitle,
  documents,
  onAddFiles,
  onRemoveDocument,
  onViewDocument,
  disabled = false,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = React.useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (disabled) return;
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onAddFiles(e.dataTransfer.files, side);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddFiles(e.target.files, side);
      e.target.value = ''; // Reset input
    }
  };

  return (
    <div className="flex-1 bg-white rounded-xl border border-slate-200/90 shadow-2xs p-4 flex flex-col">
      {/* Box Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center">
            <span
              className={`text-[11px] font-bold px-2 py-0.5 rounded mr-2 ${
                side === 'PDF1'
                  ? 'bg-blue-50 text-blue-600'
                  : 'bg-[#eff6ff] text-[#4f46e5]'
              }`}
            >
              {side}
            </span>
            <h2 className="text-sm font-bold text-slate-900 tracking-tight">{title}</h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-600 bg-white px-2.5 py-1 rounded-md border border-slate-200 shadow-2xs">
            {documents.length} PDF
          </span>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            className="px-2.5 py-1 text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-md shadow-2xs transition-colors flex items-center gap-1 active:scale-98 disabled:opacity-50 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-slate-500" />
            <span>PDF EKLE</span>
          </button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,application/pdf"
        onChange={handleFileChange}
        className="hidden"
      />

      {/* File List and Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`flex-1 bg-[#f8fafc] border border-slate-200/60 rounded-xl p-2.5 min-h-[95px] max-h-[220px] overflow-y-auto mt-3 transition-colors flex flex-col justify-center ${
          isDragOver ? 'bg-blue-50/70 border-dashed border-blue-400' : ''
        }`}
      >
        {documents.length === 0 ? (
          <div
            onClick={() => fileInputRef.current?.click()}
            className="text-center cursor-pointer py-3 group flex flex-col items-center justify-center"
          >
            <Upload className="w-6 h-6 text-slate-400 group-hover:text-blue-500 transition-colors mb-1" />
            <p className="text-xs font-medium text-slate-600 group-hover:text-blue-600">
              PDF dosyalarını buraya sürükleyin
            </p>
            <p className="text-[11px] text-slate-400">veya dosya seçmek için tıklayın</p>
          </div>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => {
              const uniqueAhus = doc.equipment.uniqueIds;
              const hasEbm = doc.ebmPages.length > 0;
              return (
                <div
                  key={doc.id}
                  className="bg-white border border-slate-200/80 rounded-lg p-2.5 flex items-center justify-between shadow-2xs hover:border-slate-300 transition-colors"
                >
                  <div
                    className="flex items-center gap-2.5 min-w-0 flex-1 cursor-pointer"
                    onClick={() => onViewDocument?.(doc)}
                  >
                    <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <span className="font-bold text-slate-800 hover:text-blue-700 text-xs block truncate">
                        {doc.name}
                      </span>
                      <div className="flex items-center flex-wrap gap-1.5 mt-0.5 text-[11px] text-slate-500">
                        {doc.project.projectName && (
                          <span className="text-slate-500 truncate max-w-[170px]">
                            Proje: {doc.project.projectName} ...
                          </span>
                        )}
                        {uniqueAhus.length > 0 && (
                          <span className="bg-slate-100 border border-slate-200/60 text-slate-600 px-1.5 py-0.5 rounded text-[10px] font-medium">
                            {uniqueAhus.join(', ')}
                          </span>
                        )}
                        {hasEbm && (
                          <span className="bg-amber-100 text-amber-800 font-semibold px-1 rounded text-[10px]">
                            EBM
                          </span>
                        )}
                        {doc.isVoclean && (
                          <span className="bg-purple-100 text-purple-800 font-semibold px-1 rounded text-[10px]">
                            VOCLEAN
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemoveDocument(doc.id, side);
                    }}
                    title="Dosyayı kaldır"
                    className="p-1 text-slate-400 hover:text-red-500 rounded transition-colors cursor-pointer ml-2"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
