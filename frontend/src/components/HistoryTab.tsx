import { useEffect, useRef, useState } from 'react';
import { Download, Eye, Loader2, Send, Undo2 } from 'lucide-react';

import {
  downloadName,
  errorMessage,
  isAbort,
  listJobs,
  publishJob,
  unpublishJob,
  type Job,
} from '../api';
import { formatDate } from '../hooks';
import JobPreviewModal from './JobPreviewModal';

const PAGE = 20;

const STATUS: Record<Job['status'], { label: string; className: string }> = {
  done: { label: 'COMPLETED', className: 'text-green-500 border-green-500/30 bg-green-500/10' },
  failed: { label: 'FAILED', className: 'text-red-500 border-red-500/30 bg-red-500/10' },
  processing: { label: 'PROCESSING', className: 'text-yellow-500 border-yellow-500/30 bg-yellow-500/10' },
  queued: { label: 'QUEUED', className: 'text-zinc-400 border-zinc-700 bg-zinc-800/40' },
};

/** My jobs; any finished one, however old, can be put into or taken out of the feed. */
export default function HistoryTab() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<Job | null>(null);
  const controller = useRef<AbortController | null>(null);

  const fetchPage = async (offset: number) => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    try {
      const page = await listJobs({ limit: PAGE, offset }, request.signal);
      setError('');
      setJobs((prev) => [...(offset ? prev : []), ...page]);
      setHasMore(page.length === PAGE);
    } catch (err) {
      if (!isAbort(err)) setError(errorMessage(err));
    } finally {
      if (!request.signal.aborted) setLoading(false);
    }
  };

  const loadMore = () => {
    setLoading(true);
    setError('');
    void fetchPage(jobs.length);
  };

  useEffect(() => {
    const request = new AbortController();
    controller.current = request;
    listJobs({ limit: PAGE, offset: 0 }, request.signal)
      .then((page) => {
        setJobs(page);
        setHasMore(page.length === PAGE);
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(errorMessage(err));
      })
      .finally(() => {
        if (!request.signal.aborted) setLoading(false);
      });
    return () => controller.current?.abort();
  }, []);

  const togglePublish = async (job: Job) => {
    setBusyId(job.id);
    setError('');
    try {
      const updated = job.published ? await unpublishJob(job.id) : await publishJob(job.id);
      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-8">
      <div className="border-l-4 border-orange-500 pl-6 py-2">
        <h2 className="text-3xl font-black text-white uppercase tracking-tighter">Мои работы</h2>
        <p className="text-zinc-500 font-mono text-sm uppercase mt-1">USER_ARCHIVE</p>
      </div>

      {error && (
        <div className="border border-red-500/50 bg-red-500/10 text-red-400 font-mono text-sm p-4">{error}</div>
      )}

      {!loading && !error && jobs.length === 0 && (
        <div className="border border-dashed border-zinc-800 p-12 text-center font-mono text-sm text-zinc-500 uppercase">
          Здесь пока пусто — обработайте первый файл на главной.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {jobs.map((job) => {
          const done = job.status === 'done' && job.result_url;
          return (
            <div
              key={job.id}
              className={`border bg-zinc-900 p-5 flex flex-col sm:flex-row sm:items-center justify-between transition-colors gap-4 ${
                job.published ? 'border-orange-500/60' : 'border-zinc-800 hover:border-zinc-600'
              }`}
            >
              <div className="flex items-center space-x-4 min-w-0">
                <div className="w-14 h-14 bg-zinc-950 border border-zinc-800 flex items-center justify-center text-zinc-500 font-mono text-xs shrink-0 overflow-hidden">
                  {done && job.kind === 'image' ? (
                    <img src={job.result_url!} alt="" loading="lazy" className="w-full h-full object-cover" />
                  ) : job.kind === 'video' ? 'VID' : 'IMG'}
                </div>
                <div className="min-w-0">
                  <h4 className="text-white font-bold truncate" title={job.filename}>{job.filename}</h4>
                  <div className="text-zinc-500 font-mono text-xs mt-1">
                    {formatDate(job.created_at)} · {job.mode.toUpperCase()}
                  </div>
                  {job.published && job.published_at && (
                    <div className="text-orange-500 font-mono text-[10px] mt-1 uppercase">
                      В ленте с {formatDate(job.published_at)}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3 sm:ml-auto flex-wrap">
                <span className={`font-mono text-xs border px-2 py-1 ${STATUS[job.status].className}`} title={job.error ?? undefined}>
                  {STATUS[job.status].label}
                </span>
                {done && (
                  <>
                    <button onClick={() => setPreview(job)} className="flex items-center gap-1.5 px-3 py-1 border border-zinc-700 text-zinc-300 hover:border-orange-500 hover:text-orange-500 text-xs font-bold uppercase">
                      <Eye size={14} /> Сравнить
                    </button>
                    <button
                      onClick={() => void togglePublish(job)}
                      disabled={busyId === job.id}
                      className={`flex items-center gap-1.5 px-3 py-1 border text-xs font-bold uppercase transition-colors disabled:opacity-50 ${
                        job.published
                          ? 'border-zinc-700 text-zinc-300 hover:border-red-500 hover:text-red-500'
                          : 'border-orange-500 text-orange-500 hover:bg-orange-500 hover:text-black'
                      }`}
                    >
                      {busyId === job.id ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : job.published ? (
                        <Undo2 size={14} />
                      ) : (
                        <Send size={14} />
                      )}
                      {job.published ? 'Снять' : 'В ленту'}
                    </button>
                    <a
                      href={job.result_url!}
                      download={downloadName(job)}
                      title="Скачать"
                      className="p-1.5 border border-zinc-800 text-zinc-400 hover:text-white hover:border-zinc-600"
                    >
                      <Download size={14} />
                    </a>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {loading && (
        <div className="flex justify-center py-6 text-orange-500">
          <Loader2 className="animate-spin" />
        </div>
      )}
      {!loading && hasMore && (
        <div className="flex justify-center">
          <button
            onClick={loadMore}
            className="border border-zinc-800 px-6 py-3 font-mono text-xs font-bold uppercase text-zinc-300 hover:border-orange-500 hover:text-orange-500 transition-colors"
          >
            Показать ещё
          </button>
        </div>
      )}
      {preview && <JobPreviewModal key={preview.id} job={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}
