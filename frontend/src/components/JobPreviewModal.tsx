import { useEffect } from 'react';
import { Download, X } from 'lucide-react';

import { downloadName, type Job } from '../api';
import MediaComparison from './MediaComparison';

export default function JobPreviewModal({ job, onClose }: { job: Job; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);

  if (!job.result_url) return null;

  return (
    <div role="dialog" aria-modal="true" aria-label="Сравнение до и после" onClick={onClose} className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-4">
      <div onClick={(event) => event.stopPropagation()} className="w-full max-w-5xl max-h-[92vh] overflow-y-auto border border-zinc-800 bg-zinc-950 shadow-[8px_8px_0px_#ea580c]">
        <div className="flex items-center justify-between gap-4 p-4 border-b border-zinc-800">
          <h3 className="font-bold text-white truncate" title={job.filename}>{job.filename}</h3>
          <div className="flex items-center gap-3 shrink-0">
            <a href={job.result_url} download={downloadName(job)} aria-label="Скачать результат" className="text-orange-500 hover:text-white"><Download size={18} /></a>
            <button onClick={onClose} aria-label="Закрыть" className="text-zinc-400 hover:text-white"><X size={20} /></button>
          </div>
        </div>
        <MediaComparison kind={job.kind} originalUrl={job.original_url} resultUrl={job.result_url} input={job.input} output={job.output} className="h-[65vh] min-h-[280px]" />
      </div>
    </div>
  );
}
