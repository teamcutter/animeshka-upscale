import { useEffect, useRef, useState } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { Download, Loader2, Send, Undo2 } from 'lucide-react';

import {
  downloadName,
  errorMessage,
  isAbort,
  publishJob,
  unpublishJob,
  uploadMedia,
  waitForJob,
  type Health,
  type Job,
  type MediaKind,
  type Mode,
} from '../api';
import { formatBytes } from '../hooks';
import VideoSelection from './VideoSelection';
import MediaComparison from './MediaComparison';

type Phase = 'idle' | 'selecting' | 'uploading' | 'queued' | 'processing' | 'done' | 'error';

// Match image.max_size_mb / video.max_size_mb in backend/config.yml.
const LIMITS: Record<MediaKind, { mb: number; accept: Record<string, string[]>; hint: string }> = {
  image: {
    mb: 10,
    accept: { 'image/jpeg': [], 'image/png': [], 'image/webp': [], 'image/bmp': [] },
    hint: 'PNG, JPG, WEBP ДО 10MB',
  },
  video: {
    mb: 200,
    accept: { 'video/mp4': ['.mp4'], 'video/quicktime': ['.mov'], 'video/webm': ['.webm'], 'video/x-matroska': ['.mkv'], 'video/x-msvideo': ['.avi'] },
    hint: 'MP4, MOV, WEBM, MKV, AVI ДО 200MB',
  },
};

const MODES: Mode[] = ['2k', '4k'];

const OPTION = (active: boolean) =>
  `w-full text-left px-4 py-3 font-mono text-sm uppercase transition-colors flex justify-between items-center disabled:opacity-40 disabled:cursor-not-allowed ${
    active ? 'border border-orange-500 bg-orange-500/10 text-orange-500 font-bold' : 'border border-zinc-800 text-zinc-400 hover:border-zinc-600'
  }`;

export default function MainTab({ health }: { health: Health | null }) {
  const [kind, setKind] = useState<MediaKind>('image');
  const [mode, setMode] = useState<Mode>('2k');
  const [phase, setPhase] = useState<Phase>('idle');
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState('');
  const [publishing, setPublishing] = useState(false);

  // Cancels the upload/polling of the current job on reset or unmount.
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);
  useEffect(() => () => { if (sourceUrl) URL.revokeObjectURL(sourceUrl); }, [sourceUrl]);
  useEffect(() => () => { if (videoPreviewUrl) URL.revokeObjectURL(videoPreviewUrl); }, [videoPreviewUrl]);

  const modeAvailable = (candidate: Mode) => health?.modes[candidate] ?? true;
  const effectiveMode: Mode = modeAvailable(mode) ? mode : (MODES.find(modeAvailable) ?? mode);

  const fail = (message: string) => {
    setError(message);
    setPhase('error');
  };

  const run = async (selected: File, startSeconds?: number, endSeconds?: number) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setJob(null);
    setProgress(0);
    setPhase('uploading');
    try {
      const created = await uploadMedia(selected, kind, effectiveMode, {
        signal: controller.signal,
        onProgress: setProgress,
        startSeconds,
        endSeconds,
      });
      setJob(created);
      setPhase(created.status === 'processing' ? 'processing' : 'queued');
      const finished = await waitForJob(created.id, {
        signal: controller.signal,
        onUpdate: (current) => {
          setJob(current);
          if (current.status === 'processing') setPhase('processing');
        },
      });
      if (finished.status === 'failed') {
        fail(finished.error ?? 'Обработка не удалась');
        return;
      }
      setJob(finished);
      setPhase('done');
    } catch (err) {
      if (!isAbort(err)) fail(errorMessage(err));
    }
  };

  const onDrop = (accepted: File[], rejections: FileRejection[]) => {
    if (rejections.length > 0) {
      const code = rejections[0].errors[0]?.code;
      fail(code === 'file-too-large' ? `Файл больше ${LIMITS[kind].mb} MB` : `Неверный формат: ${LIMITS[kind].hint}`);
      return;
    }
    const selected = accepted[0];
    if (!selected) return;
    setFile(selected);
    setSourceUrl(URL.createObjectURL(selected));
    setPhase(kind === 'video' ? 'selecting' : 'idle');
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: LIMITS[kind].accept,
    maxSize: LIMITS[kind].mb * 1024 * 1024,
    multiple: false,
    disabled: phase !== 'idle',
  });

  const reset = () => {
    controllerRef.current?.abort();
    setJob(null);
    setFile(null);
    setSourceUrl(null);
    setVideoPreviewUrl(null);
    setError('');
    setPhase('idle');
  };

  const togglePublish = async () => {
    if (!job) return;
    setPublishing(true);
    try {
      setJob(job.published ? await unpublishJob(job.id) : await publishJob(job.id));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPublishing(false);
    }
  };

  const busy = phase === 'uploading' || phase === 'queued' || phase === 'processing';
  const metric = (key: string, digits = 2) =>
    job?.metrics[key] !== undefined ? job.metrics[key].toFixed(digits) : '—';

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex justify-between items-end border-l-4 border-orange-500 pl-6 py-2">
        <div>
          <h2 className="text-3xl font-black text-white uppercase tracking-tighter">Терминал обработки</h2>
          <p className="text-zinc-500 font-mono text-sm uppercase mt-1">MAIN_WORKSPACE</p>
        </div>
        {health && (
          <div className="items-center space-x-2 border border-zinc-800 bg-zinc-900 px-3 py-1.5 hidden md:flex">
            <div className={`w-2 h-2 rounded-full ${health.status === 'ok' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className="font-mono text-xs text-zinc-400">API: {health.status.toUpperCase()}</span>
          </div>
        )}
      </div>

      {phase === 'idle' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div
            {...getRootProps()}
            className={`lg:col-span-2 border border-dashed bg-zinc-900 p-6 flex flex-col items-center justify-center min-h-[350px] transition-colors cursor-pointer relative group ${
              isDragActive ? 'border-orange-500 bg-orange-500/5' : 'border-zinc-800 hover:border-orange-500'
            }`}
          >
            <input {...getInputProps()} />
            {file && sourceUrl && kind === 'image' ? (
              <img src={sourceUrl} alt="Выбранный файл" className="max-h-[300px] object-contain" />
            ) : (
              <div className="w-16 h-16 bg-zinc-950 border border-zinc-800 flex items-center justify-center text-zinc-500 group-hover:text-orange-500 group-hover:border-orange-500 transition-all mb-4">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
              </div>
            )}
            <h3 className="font-bold text-white uppercase tracking-widest text-xl group-hover:text-orange-500 transition-colors mt-4">
              {file ? 'Заменить файл' : 'Выбрать медиа'}
            </h3>
            <p className="text-zinc-500 font-mono text-xs mt-3 uppercase tracking-wider">
              {file ? `${file.name} · ${formatBytes(file.size)}` : LIMITS[kind].hint}
            </p>
          </div>

          <div className="space-y-6 flex flex-col justify-between">
            <div className="border border-zinc-800 bg-zinc-900 p-6 flex-1 space-y-6">
              <div>
                <h4 className="text-zinc-400 font-mono text-xs uppercase mb-3 border-b border-zinc-800 pb-2">Тип</h4>
                <div className="grid grid-cols-2 gap-2">
                  {(['image', 'video'] as MediaKind[]).map((candidate) => (
                    <button key={candidate} onClick={() => { setKind(candidate); setFile(null); setSourceUrl(null); }} className={OPTION(kind === candidate)}>
                      {candidate === 'image' ? 'IMG' : 'VIDEO'}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <h4 className="text-zinc-400 font-mono text-xs uppercase mb-3 border-b border-zinc-800 pb-2">Режим апскейла</h4>
                <div className="space-y-2">
                  {MODES.map((candidate) => (
                    <button key={candidate} onClick={() => setMode(candidate)} disabled={!modeAvailable(candidate)} className={OPTION(effectiveMode === candidate)}>
                      <span>x{candidate === '4k' ? 4 : 2}_{candidate}{modeAvailable(candidate) ? '' : ' · нет весов'}</span>
                      {effectiveMode === candidate && <span className="w-2 h-2 bg-orange-500"></span>}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <button
              onClick={() => file && void run(file)}
              disabled={!file || kind !== 'image'}
              className="w-full bg-orange-500 text-black font-black uppercase tracking-widest py-5 hover:bg-orange-400 transition-transform shadow-[6px_6px_0px_#fff] hover:shadow-[8px_8px_0px_#fff] hover:-translate-y-0.5 active:translate-y-1 active:shadow-none disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0"
            >
              Инициализация
            </button>
          </div>
        </div>
      )}

      {phase === 'selecting' && file && sourceUrl && (
        <div className="border border-zinc-800 bg-zinc-900 p-6">
          <VideoSelection
            file={file}
            sourceUrl={sourceUrl}
            previewUrl={videoPreviewUrl}
            onPreview={(blob) => setVideoPreviewUrl(URL.createObjectURL(blob))}
            onSubmit={(start, end) => void run(file, start, end)}
            onCancel={reset}
          />
        </div>
      )}

      {busy && (
        <div className="border border-zinc-800 bg-zinc-900 p-12 flex flex-col items-center text-center">
          <Loader2 className="animate-spin w-12 h-12 text-orange-500 mb-6" />
          <p className="font-black text-white uppercase tracking-widest">
            {phase === 'uploading' && `Загрузка… ${Math.round(progress * 100)}%`}
            {phase === 'queued' && 'В очереди'}
            {phase === 'processing' && 'Real-ESRGAN обрабатывает файл'}
          </p>
          {phase === 'uploading' && (
            <div className="w-full max-w-md h-1 bg-zinc-800 mt-4">
              <div className="h-full bg-orange-500 transition-all" style={{ width: `${progress * 100}%` }} />
            </div>
          )}
          {job && <p className="text-xs text-zinc-600 mt-4 font-mono">JOB_{job.id}</p>}
        </div>
      )}

      {phase === 'done' && job?.result_url && (
        <div className="space-y-6">
          <MediaComparison
            key={job.id}
            kind={job.kind}
            originalUrl={job.original_url}
            resultUrl={job.result_url}
            input={job.input}
            output={job.output}
            className="border border-zinc-800 h-[540px]"
          />

          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-sm">
            {[
              ['TIME', `${metric('processing_seconds')} s`],
              ['SIZE', job.output ? formatBytes(job.output.size_bytes) : '—'],
              ['PSNR', `${metric('psnr_db', 1)} dB`],
              ['SSIM', metric('ssim', 3)],
            ].map(([label, value]) => (
              <div key={label} className="border border-zinc-800 bg-zinc-900 p-3">
                <dt className="text-zinc-500 text-xs">{label}</dt>
                <dd className="text-white font-bold truncate">{value}</dd>
              </div>
            ))}
          </dl>

          {error && <p className="text-red-400 font-mono text-sm">{error}</p>}

          <div className="flex flex-wrap justify-between gap-3">
            <button onClick={reset} className="border border-zinc-800 px-6 py-3 font-mono text-xs font-bold uppercase text-zinc-300 hover:border-zinc-600 hover:text-white">
              Новый файл
            </button>
            <div className="flex gap-3">
              <button
                onClick={() => void togglePublish()}
                disabled={publishing}
                className={`flex items-center gap-2 px-6 py-3 border font-mono text-xs font-bold uppercase transition-colors disabled:opacity-50 ${
                  job.published
                    ? 'border-zinc-700 text-zinc-300 hover:border-red-500 hover:text-red-500'
                    : 'border-orange-500 text-orange-500 hover:bg-orange-500 hover:text-black'
                }`}
              >
                {job.published ? <Undo2 size={14} /> : <Send size={14} />}
                {job.published ? 'Снять с ленты' : 'Опубликовать в ленту'}
              </button>
              <a
                href={job.result_url}
                download={downloadName(job)}
                className="flex items-center gap-2 bg-orange-500 text-black px-6 py-3 font-black text-xs uppercase hover:bg-orange-400"
              >
                <Download size={14} /> Скачать
              </a>
            </div>
          </div>
        </div>
      )}

      {phase === 'error' && (
        <div className="border border-red-500/50 bg-red-500/10 p-12 flex flex-col items-center text-center">
          <p className="font-black text-red-500 uppercase tracking-widest mb-2">Ошибка</p>
          <p className="text-red-300 font-mono text-sm mb-6">{error}</p>
          <button onClick={reset} className="border border-red-500 text-red-500 px-6 py-3 font-mono text-xs font-bold uppercase hover:bg-red-500 hover:text-black">
            Попробовать снова
          </button>
        </div>
      )}
    </div>
  );
}
