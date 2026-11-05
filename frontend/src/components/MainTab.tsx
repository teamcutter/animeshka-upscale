import { useEffect, useRef, useState } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider';
import { AlertCircle, Download, Loader2, UploadCloud } from 'lucide-react';

import {
  errorMessage,
  isAbort,
  uploadMedia,
  waitForJob,
  type Health,
  type Job,
  type MediaKind,
  type Mode,
} from '../api';
import { formatBytes } from '../hooks';

type Phase = 'idle' | 'uploading' | 'queued' | 'processing' | 'done' | 'error';

// Match image.max_size_mb / video.max_size_mb in backend/config.yml.
const LIMITS: Record<MediaKind, { mb: number; accept: Record<string, string[]>; hint: string }> = {
  image: {
    mb: 10,
    accept: { 'image/jpeg': [], 'image/png': [], 'image/webp': [], 'image/bmp': [] },
    hint: 'PNG, JPG, WEBP до 10 MB',
  },
  video: {
    mb: 200,
    accept: { 'video/mp4': ['.mp4'], 'video/quicktime': ['.mov'], 'video/webm': ['.webm'], 'video/x-matroska': ['.mkv'] },
    hint: 'MP4, MOV, WEBM, MKV до 200 MB',
  },
};

const MODE_LABEL: Record<Mode, string> = { '2k': 'Улучшение в 2K (x2)', '4k': 'Улучшение в 4K (x4)' };

const SELECT =
  'bg-white/60 border border-orange-200 text-stone-700 text-sm rounded-xl focus:ring-orange-400 focus:border-orange-400 block p-2.5 outline-none disabled:opacity-60';

function downloadName(job: Job): string {
  const base = job.filename.replace(/\.[^.]+$/, '') || 'upscaled';
  return `${base}_${job.mode}.png`;
}

export default function MainTab({ health }: { health: Health | null }) {
  const [kind, setKind] = useState<MediaKind>('image');
  const [mode, setMode] = useState<Mode>('2k');
  const [phase, setPhase] = useState<Phase>('idle');
  const [progress, setProgress] = useState(0);
  const [job, setJob] = useState<Job | null>(null);
  const [beforeUrl, setBeforeUrl] = useState<string | null>(null);
  const [error, setError] = useState('');

  // Cancels the upload/polling of the current job on reset or unmount.
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);

  // The browser keeps the original for the "before" side; the "after" side comes from the API.
  useEffect(() => {
    if (!beforeUrl) return;
    return () => URL.revokeObjectURL(beforeUrl);
  }, [beforeUrl]);

  const modeAvailable = (candidate: Mode) => health?.modes[candidate] ?? true;
  // If the server has no weights for the selected mode, use one it has (derived, not stored).
  const effectiveMode: Mode = modeAvailable(mode)
    ? mode
    : ((Object.keys(MODE_LABEL) as Mode[]).find(modeAvailable) ?? mode);

  const fail = (message: string) => {
    setError(message);
    setPhase('error');
  };

  const run = async (file: File) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setBeforeUrl(kind === 'image' ? URL.createObjectURL(file) : null);
    setJob(null);
    setProgress(0);
    setPhase('uploading');

    try {
      const created = await uploadMedia(file, kind, effectiveMode, {
        signal: controller.signal,
        onProgress: setProgress,
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
      fail(
        code === 'file-too-large'
          ? `Файл слишком большой (максимум ${LIMITS[kind].mb} MB).`
          : `Неверный формат: поддерживается ${LIMITS[kind].hint}.`,
      );
      return;
    }
    void run(accepted[0]);
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
    setBeforeUrl(null);
    setError('');
    setPhase('idle');
  };

  const busy = phase === 'uploading' || phase === 'queued' || phase === 'processing';
  const metric = (key: string, digits = 2) =>
    job?.metrics[key] !== undefined ? job.metrics[key].toFixed(digits) : '—';

  return (
    <div className="max-w-3xl mx-auto bg-white/80 backdrop-blur-md rounded-2xl shadow-lg border border-orange-200/50 p-8">
      <div className="flex flex-wrap justify-between items-center gap-3 mb-6">
        <h2 className="text-2xl font-bold text-stone-800">Создать работу</h2>
        <div className="flex space-x-2">
          <select value={effectiveMode} onChange={(e) => setMode(e.target.value as Mode)} disabled={phase !== 'idle'} className={SELECT}>
            {(Object.keys(MODE_LABEL) as Mode[]).map((candidate) => (
              <option key={candidate} value={candidate} disabled={!modeAvailable(candidate)}>
                {MODE_LABEL[candidate]}
                {modeAvailable(candidate) ? '' : ' — нет весов'}
              </option>
            ))}
          </select>
          <select value={kind} onChange={(e) => setKind(e.target.value as MediaKind)} disabled={phase !== 'idle'} className={SELECT}>
            <option value="image">Тип: Изображение</option>
            <option value="video">Тип: Видео</option>
          </select>
        </div>
      </div>

      {phase === 'idle' && (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-2xl p-12 text-center transition-colors cursor-pointer ${
            isDragActive ? 'border-orange-400 bg-orange-100/80' : 'border-orange-300 bg-orange-50/50 hover:bg-orange-100/60'
          }`}
        >
          <input {...getInputProps()} />
          <div className="w-16 h-16 bg-white/90 rounded-full flex items-center justify-center mx-auto mb-4 shadow-sm text-orange-500">
            <UploadCloud className="w-8 h-8" />
          </div>
          <p className="text-lg font-bold text-stone-800 mb-1">
            {kind === 'video' ? 'Перетащите видео сюда' : 'Перетащите изображение сюда'}
          </p>
          <p className="text-sm text-stone-600">Поддерживается {LIMITS[kind].hint}</p>
        </div>
      )}

      {busy && (
        <div className="rounded-2xl bg-orange-50/50 border border-orange-200/50 p-12 text-center flex flex-col items-center">
          <Loader2 className="animate-spin w-12 h-12 text-orange-500 mb-4" />
          <p className="text-lg font-bold text-stone-800 mb-1">
            {phase === 'uploading' && `Загрузка на сервер… ${Math.round(progress * 100)}%`}
            {phase === 'queued' && 'В очереди на обработку…'}
            {phase === 'processing' && 'Real-ESRGAN обрабатывает файл…'}
          </p>
          <p className="text-sm text-stone-600">
            {phase === 'queued' ? 'Задача принята, ждём свободный воркер.' : 'Это может занять от нескольких секунд до минуты.'}
          </p>
          {job && <p className="text-xs text-stone-400 mt-4 font-mono">job {job.id}</p>}
        </div>
      )}

      {phase === 'done' && job && job.result_url && (
        <div>
          <div className="rounded-2xl overflow-hidden mb-4 h-[480px] bg-stone-900 relative">
            {beforeUrl ? (
              <ReactCompareSlider
                itemOne={<ReactCompareSliderImage src={beforeUrl} alt="До" />}
                itemTwo={<ReactCompareSliderImage src={job.result_url} alt="После" />}
                className="h-full w-full"
              />
            ) : (
              <video src={job.result_url} controls className="h-full w-full" />
            )}
            <div className="absolute top-3 left-3 bg-black/60 text-white px-3 py-1 rounded-md text-xs pointer-events-none">
              До · {job.input.width}×{job.input.height}
            </div>
            <div className="absolute top-3 right-3 bg-orange-600/90 text-white px-3 py-1 rounded-md text-xs pointer-events-none">
              После ({job.mode}) · {job.output?.width}×{job.output?.height}
            </div>
          </div>

          <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6 text-sm">
            {[
              ['Время', `${metric('processing_seconds')} с`],
              ['Размер', job.output ? formatBytes(job.output.size_bytes) : '—'],
              ['Мегапиксели', metric('output_megapixels')],
              ['PSNR', `${metric('psnr_db', 1)} дБ`],
              ['SSIM', metric('ssim', 3)],
              ['Файл', job.filename],
            ].map(([label, value]) => (
              <div key={label} className="bg-orange-50/60 border border-orange-100 rounded-xl p-3">
                <dt className="text-stone-500 text-xs mb-1">{label}</dt>
                <dd className="font-bold text-stone-800 truncate" title={value}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>

          <div className="flex justify-between items-center">
            <button onClick={reset} className="bg-white/60 text-stone-700 border border-orange-200 px-6 py-2 rounded-xl font-medium hover:bg-orange-50 transition-colors">
              Загрузить новый
            </button>
            <a
              href={job.result_url}
              download={downloadName(job)}
              className="bg-orange-500 text-white px-6 py-2 rounded-xl font-medium hover:bg-orange-600 transition-colors shadow-sm flex items-center gap-2"
            >
              <Download size={16} /> Скачать результат
            </a>
          </div>
        </div>
      )}

      {phase === 'error' && (
        <div className="rounded-2xl bg-red-50/80 border border-red-200 p-12 text-center flex flex-col items-center">
          <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
          <p className="text-lg font-bold text-red-700 mb-1">Произошла ошибка</p>
          <p className="text-sm text-red-600 mb-6">{error}</p>
          <button onClick={reset} className="bg-white/80 border border-red-200 text-red-600 px-6 py-2 rounded-xl font-medium hover:bg-red-100 transition-colors">
            Попробовать снова
          </button>
        </div>
      )}
    </div>
  );
}
