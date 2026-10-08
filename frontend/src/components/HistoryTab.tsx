import { useEffect, useState } from 'react';
import { Download, Loader2, RefreshCw } from 'lucide-react';

import { errorMessage, isAbort, listJobs, type Job, type JobStatus } from '../api';
import { formatBytes, formatDate } from '../hooks';

const STATUS: Record<JobStatus, { label: string; className: string }> = {
  queued: { label: 'В очереди', className: 'bg-slate-100 text-slate-600' },
  processing: { label: 'Обработка', className: 'bg-amber-50 text-amber-600' },
  done: { label: 'Готово', className: 'bg-emerald-50 text-emerald-600' },
  failed: { label: 'Ошибка', className: 'bg-rose-50 text-rose-600' },
};

export default function HistoryTab() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    listJobs({ limit: 60 }, controller.signal)
      .then((data) => {
        setJobs(data);
        setError('');
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(errorMessage(err));
      });
    return () => controller.abort();
  }, [refreshKey]);

  // Jobs still running change on the server: poll while any are pending.
  useEffect(() => {
    if (!jobs?.some((job) => job.status === 'queued' || job.status === 'processing')) return;
    const timer = setTimeout(() => setRefreshKey((k) => k + 1), 2000);
    return () => clearTimeout(timer);
  }, [jobs]);

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-slate-800">История обработок</h2>
        <button
          onClick={() => setRefreshKey((k) => k + 1)}
          className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition-colors"
        >
          <RefreshCw size={16} /> Обновить
        </button>
      </div>

      {error && <p className="text-rose-600 bg-rose-50 rounded-xl p-4 mb-6">{error}</p>}
      {!jobs && !error && (
        <div className="flex justify-center p-12 text-indigo-500">
          <Loader2 className="animate-spin w-8 h-8" />
        </div>
      )}
      {jobs && jobs.length === 0 && (
        <p className="text-slate-500 bg-white rounded-2xl border border-slate-100 p-12 text-center">
          Пока пусто — загрузите первое изображение на главной.
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {jobs?.map((job) => (
          <div key={job.id} className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden group">
            <div className="h-48 bg-slate-100 flex items-center justify-center overflow-hidden">
              {job.result_url && job.kind === 'image' ? (
                <img src={job.result_url} alt={job.filename} className="h-full w-full object-cover" loading="lazy" />
              ) : (
                <span className="text-slate-400 text-sm px-4 text-center">
                  {job.status === 'failed' ? job.error : `${job.kind === 'video' ? 'Видео' : 'Изображение'} · ${STATUS[job.status].label}`}
                </span>
              )}
            </div>
            <div className="p-4">
              <h3 className="font-semibold text-slate-800 truncate" title={job.filename}>
                {job.filename}
              </h3>
              <div className="flex justify-between items-center mt-2 text-sm text-slate-500">
                <span>{formatDate(job.created_at)}</span>
                <span className="flex gap-1">
                  <span className="bg-indigo-50 text-indigo-600 px-2 py-1 rounded-md text-xs font-medium">{job.mode}</span>
                  <span className={`px-2 py-1 rounded-md text-xs font-medium ${STATUS[job.status].className}`}>
                    {STATUS[job.status].label}
                  </span>
                </span>
              </div>
              <div className="mt-2 text-xs text-slate-400">
                {job.input.width}×{job.input.height}
                {job.output && ` → ${job.output.width}×${job.output.height}`}
                {job.metrics.processing_seconds !== undefined && ` · ${job.metrics.processing_seconds.toFixed(2)} с`}
              </div>
              {job.result_url && (
                <a
                  href={job.result_url}
                  download={`${job.filename.replace(/\.[^.]+$/, '')}_${job.mode}.png`}
                  className="mt-4 flex items-center justify-center gap-2 bg-indigo-50 text-indigo-600 py-2 rounded-lg text-sm font-medium hover:bg-indigo-100 transition-colors"
                >
                  <Download size={14} /> Скачать{job.output ? ` (${formatBytes(job.output.size_bytes)})` : ''}
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
