import React from 'react';
import { Play, RotateCcw, Sparkles, Sliders, CheckCircle2, AlertTriangle, FileText } from 'lucide-react';

interface HeaderProps {
  version: string;
  tolerance: number;
  onToleranceChange: (val: number) => void;
  onRunAnalysis: () => void;
  onClearInputs: () => void;
  onLoadSamples: () => void;
  onLoadHks12Only: () => void;
  isAnalyzing: boolean;
  progressMessage: string;
  progressPercent: number;
  pdf1Count: number;
  pdf2Count: number;
}

export const Header: React.FC<HeaderProps> = ({
  version,
  tolerance,
  onToleranceChange,
  onRunAnalysis,
  onClearInputs,
  onLoadSamples,
  onLoadHks12Only,
  isAnalyzing,
  progressMessage,
  progressPercent,
  pdf1Count,
  pdf2Count,
}) => {
  const [toleranceInput, setToleranceInput] = React.useState<string>('0,01');

  React.useEffect(() => {
    // Keep formatted with comma like in European engineering tools
    const formatted = tolerance.toString().replace('.', ',');
    setToleranceInput(formatted);
  }, [tolerance]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const valStr = e.target.value;
    setToleranceInput(valStr);
    const parsed = parseFloat(valStr.replace(',', '.'));
    if (!isNaN(parsed)) {
      onToleranceChange(parsed);
    }
  };

  const canRun = pdf1Count > 0 && pdf2Count > 0;

  return (
    <header className="bg-white border-b border-slate-200/80 shadow-2xs sticky top-0 z-20">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-2.5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          {/* Title and version */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#1a56db] text-white flex items-center justify-center font-black text-lg shadow-xs select-none">
              kW
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-[17px] font-extrabold text-[#0f172a] tracking-tight">
                  PDF kW SELECTOR
                </h1>
                <span className="px-2 py-0.5 text-[11px] font-semibold bg-blue-50/80 text-blue-600 border border-blue-200 rounded-full">
                  {version}
                </span>
              </div>
              <p className="text-xs text-slate-500 font-normal">
                Project → AHU → Motor Anma Gücü Karşılaştırma ve Doğrulama
              </p>
            </div>
          </div>

          {/* Quick presets & action buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Tolerance Control */}
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-white border border-slate-200/90 rounded-md text-xs shadow-2xs">
              <Sliders className="w-3.5 h-3.5 text-slate-500" />
              <span className="text-slate-600 font-normal">Tolerans:</span>
              <input
                type="text"
                value={toleranceInput}
                onChange={handleInputChange}
                className="w-12 px-1 py-0.5 text-xs bg-white border border-slate-300 rounded font-medium text-slate-800 text-center focus:outline-hidden focus:border-blue-500"
              />
              <span className="text-slate-500 font-normal">kW</span>
            </div>

            {/* Örnek Set Button */}
            <button
              type="button"
              onClick={onLoadSamples}
              title="Tüm senaryoları içeren örnek seti yükle"
              className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 bg-white border border-slate-200/90 rounded-md shadow-2xs transition-colors flex items-center gap-1.5 cursor-pointer active:scale-98"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>Örnek Set</span>
            </button>

            {/* HKS-12 Testi Button */}
            <button
              type="button"
              onClick={onLoadHks12Only}
              title="Depodaki gerçek HKS-12 test dosyalarını yükle"
              className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 bg-white border border-slate-200/90 rounded-md shadow-2xs transition-colors flex items-center gap-1.5 cursor-pointer active:scale-98"
            >
              <FileText className="w-3.5 h-3.5 text-blue-600" />
              <span>HKS-12 Testi</span>
            </button>

            {/* Clear Inputs */}
            <button
              type="button"
              onClick={onClearInputs}
              className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 bg-white border border-slate-200/90 rounded-md shadow-2xs transition-colors flex items-center gap-1.5 cursor-pointer active:scale-98"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-600" />
              <span>TEMİZLE</span>
            </button>

            {/* Run Analysis Button */}
            <button
              type="button"
              onClick={onRunAnalysis}
              disabled={isAnalyzing}
              className={`px-4 py-1.5 text-xs font-bold rounded-md shadow-sm transition-all flex items-center gap-1.5 ${
                !isAnalyzing
                  ? 'bg-[#1a56db] hover:bg-blue-700 text-white cursor-pointer active:scale-98'
                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }`}
            >
              <Play className={`w-3 h-3 fill-white text-white ${isAnalyzing ? 'animate-pulse' : ''}`} />
              <span>{isAnalyzing ? 'ANALİZ EDİLİYOR...' : 'ANALİZ BAŞLA'}</span>
            </button>
          </div>
        </div>

        {/* Progress bar if analyzing */}
        {isAnalyzing && (
          <div className="mt-3 pt-2 border-t border-slate-100">
            <div className="flex items-center justify-between text-xs text-slate-600 mb-1">
              <span className="font-medium flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
                {progressMessage}
              </span>
              <span className="font-semibold text-blue-700">{progressPercent}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-blue-600 h-1.5 transition-all duration-300 ease-out"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
