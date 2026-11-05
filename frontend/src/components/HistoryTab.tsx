import { useEffect, useState } from 'react';
import { Download, Loader2, RefreshCw, Trash2 } from 'lucide-react';

import { deleteJob, errorMessage, isAbort, listJobs, type Job, type JobStatus } from '../api';
import { formatBytes, formatDate } from '../hooks';

const STATUS: Record<JobStatus, { label: string; className: string }> = {
  queued: { label: 'В очереди', className: 'bg-stone-100 text-stone-600 border-stone-200' },
  processing: { label: 'Обработка', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  done: { label: 'Готово', className: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  failed: { label: 'Ошибка', className: 'bg-red-100 text-red-700 border-red-200' },
};

export default function HistoryTab() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = () => setRefreshKey((k) => k + 1);

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
    const timer = setTimeout(refresh, 2000);
    return () => clearTimeout(timer);
  }, [jobs]);

  const remove = async (job: Job) => {
    try {
      await deleteJob(job.id);
      setJobs((current) => current?.filter((j) => j.id !== job.id) ?? null);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div className="inline-block bg-white/80 backdrop-blur-md px-6 py-3 rounded-2xl shadow-lg border border-orange-200/50">
          <h2 className="text-2xl font-bold text-stone-800">История обработок</h2>
        </div>
        <button
          onClick={refresh}
          className="flex items-center gap-2 text-sm bg-white/80 backdrop-blur-md px-4 py-2 rounded-xl border border-orange-200/50 text-stone-600 hover:text-orange-700 transition-colors"
        >
          <RefreshCw size={16} /> Обновить
        </button>
      </div>

      {error && <p className="text-red-700 bg-red-100/80 border border-red-200 rounded-xl p-4 mb-6">{error}</p>}
      {!jobs && !error && (
        <div className="flex justify-center p-12 text-orange-500">
          <Loader2 className="animate-spin w-8 h-8" />
        </div>
      )}
      {jobs && jobs.length === 0 && (
        <p className="text-stone-600 bg-white/80 backdrop-blur-md rounded-2xl border border-orange-200/50 p-12 text-center">
          Пока пусто — загрузите первое изображение на главной.
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {jobs?.map((job) => (
          <div key={job.id} className="bg-white/80 backdrop-blur-md rounded-2xl shadow-lg border border-orange-200/50 overflow-hidden group flex flex-col">
            <div className="h-48 bg-orange-100/30 flex items-center justify-center overflow-hidden border-b border-orange-100/50">
              {job.result_url && job.kind === 'image' ? (
                <img src={job.result_url} alt={job.filename} className="h-full w-full object-cover" loading="lazy" />
              ) : (
                <span className="text-stone-600 text-sm font-medium bg-white/70 backdrop-blur-sm px-4 py-2 rounded-xl shadow-sm border border-orange-100 mx-4 text-center">
                  {job.status === 'failed' ? job.error : `${job.kind === 'video' ? 'Видео' : 'Изображение'} · ${STATUS[job.status].label}`}
                </span>
              )}
            </div>
            <div className="p-5 flex-1 flex flex-col">
              <h3 className="font-bold text-stone-800 truncate" title={job.filename}>
                {job.filename}
              </h3>
              <div className="flex justify-between items-center mt-2 text-sm text-stone-600">
                <span>{formatDate(job.created_at)}</span>
                <span className="flex gap-1">
                  <span className="bg-orange-100 text-orange-700 px-2 py-1 rounded-lg text-xs font-bold border border-orange-200/50">{job.mode}</span>
                  <span className={`px-2 py-1 rounded-lg text-xs font-bold border ${STATUS[job.status].className}`}>{STATUS[job.status].label}</span>
                </span>
              </div>
              <div className="mt-2 text-xs text-stone-500">
                {job.input.width}×{job.input.height}
                {job.output && ` → ${job.output.width}×${job.output.height}`}
                {job.metrics.processing_seconds !== undefined && ` · ${job.metrics.processing_seconds.toFixed(1)} с`}
                {job.metrics.psnr_db !== undefined && ` · PSNR ${job.metrics.psnr_db.toFixed(1)}`}
                {job.metrics.ssim !== undefined && ` · SSIM ${job.metrics.ssim.toFixed(3)}`}
              </div>
              <div className="mt-5 pt-4 border-t border-orange-100/50 mt-auto flex gap-2">
                {job.result_url ? (
                  <a
                    href={job.result_url}
                    download={`${job.filename.replace(/\.[^.]+$/, '')}_${job.mode}.png`}
                    className="flex-1 flex items-center justify-center gap-2 bg-orange-100 text-orange-700 py-2.5 rounded-xl text-sm font-bold hover:bg-orange-200 transition-colors shadow-sm"
                  >
                    <Download size={14} /> Скачать{job.output ? ` (${formatBytes(job.output.size_bytes)})` : ''}
                  </a>
                ) : (
                  <span className="flex-1" />
                )}
                {job.status !== 'processing' && (
                  <button
                    onClick={() => void remove(job)}
                    title="Удалить работу и её файлы"
                    className="px-3 py-2.5 rounded-xl text-sm bg-white/60 border border-orange-200 text-stone-500 hover:text-red-600 hover:border-red-200 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
