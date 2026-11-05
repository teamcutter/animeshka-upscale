import { useEffect, useRef, useState } from 'react';
import { Loader2, Play } from 'lucide-react';
import { errorMessage, isAbort, previewVideo } from '../api';
import { videoTime } from '../hooks';

const INPUT = 'w-full rounded-none border border-zinc-800 bg-zinc-950 p-3 text-white font-mono text-sm focus:border-orange-500 focus:outline-none';

interface Props {
  file: File;
  sourceUrl: string;
  previewUrl: string | null;
  onPreview: (blob: Blob, start: number) => void;
  onSubmit: (start: number, end?: number) => void;
  onCancel: () => void;
}

export default function VideoSelection({ file, sourceUrl, previewUrl, onPreview, onSubmit, onCancel }: Props) {
  const [duration, setDuration] = useState<number | null>(null);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(10);
  const [needsConversion, setNeedsConversion] = useState(false);
  const [previewStart, setPreviewStart] = useState(0);
  const [previewLength, setPreviewLength] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const player = useRef<HTMLVideoElement>(null);
  const controller = useRef<AbortController | null>(null);
  const attemptedFallback = useRef(false);
  useEffect(() => () => controller.current?.abort(), []);

  const valid = Number.isFinite(start) && Number.isFinite(end)
    && start >= 0 && end > start && (duration === null || end <= duration + 0.001);

  const loadPreview = async (from: number, length: number) => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setLoading(true);
    setError('');
    try {
      const result = await previewVideo(file, from, Math.min(30, length), request.signal);
      if (request.signal.aborted) return false;
      setDuration(result.duration);
      setEnd((value) => Math.min(value, result.duration));
      setPreviewStart(from);
      setPreviewLength(Math.min(30, length, result.duration - from));
      onPreview(result.blob, from);
      return true;
    } catch (err) {
      if (!isAbort(err)) setError(errorMessage(err));
      return false;
    } finally {
      if (!request.signal.aborted) setLoading(false);
    }
  };

  const submitSelection = async () => {
    if (!valid || loading) return;
    if (needsConversion && (previewStart !== start || previewLength < Math.min(30, end - start))) {
      if (!await loadPreview(start, end - start)) return;
    }
    onSubmit(start, end === duration ? undefined : end);
  };

  const previewSelection = () => {
    if (!valid) return;
    if (needsConversion) {
      void loadPreview(start, end - start);
    } else if (player.current) {
      player.current.currentTime = start;
      void player.current.play().catch(() => {});
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 border border-zinc-800 bg-zinc-900 p-8">
      <div className="border-l-4 border-orange-500 pl-4 py-1">
        <h3 className="font-black text-white text-xl truncate uppercase" title={file.name}>{file.name}</h3>
        <p className="text-xs font-mono text-zinc-500 mt-1 uppercase">VIDEO_TRIMMER // ВЫБЕРИТЕ ОТРЕЗОК ДЛЯ ОБРАБОТКИ (ПО УМОЛЧАНИЮ — 10 СЕКУНД)</p>
      </div>

      <div className="rounded-none overflow-hidden bg-zinc-950 border border-zinc-800 aspect-video relative">
        <video
          ref={player}
          src={needsConversion ? previewUrl ?? undefined : sourceUrl}
          controls playsInline preload="metadata" className="h-full w-full object-contain"
          aria-label="Предпросмотр выбранного видео"
          onLoadedMetadata={(event) => {
            if (needsConversion) return;
            const value = event.currentTarget.duration;
            if (Number.isFinite(value) && value > 0) {
              setDuration(value);
              setEnd((current) => Math.min(current, value));
            }
          }}
          onError={() => {
            if (!attemptedFallback.current) {
              attemptedFallback.current = true;
              setNeedsConversion(true);
              void loadPreview(start, end - start);
            } else if (previewUrl) {
              setError('Не удалось воспроизвести предпросмотр. Можно выбрать отрезок по времени.');
            }
          }}
          onPlay={(event) => {
            if (!needsConversion && (event.currentTarget.currentTime < start || event.currentTarget.currentTime >= end)) {
              event.currentTarget.currentTime = start;
            }
          }}
          onTimeUpdate={(event) => {
            if (!needsConversion && event.currentTarget.currentTime >= end) event.currentTarget.pause();
          }}
        />
        {loading && (
          <div className="absolute inset-0 bg-black/80 text-white flex flex-col items-center justify-center gap-3 font-mono">
            <Loader2 className="animate-spin text-orange-500" />
            <p className="text-xs uppercase tracking-wider">Готовим совместимый предпросмотр...</p>
          </div>
        )}
      </div>

      {needsConversion && (
        <p className="text-xs font-mono text-zinc-400 border-l-2 border-orange-500 pl-3">
          Для этого формата создаётся MP4-предпросмотр до 30 секунд без улучшения.
          {previewUrl && ` Текущий: ${videoTime(previewStart)}–${videoTime(previewStart + previewLength)}.`}
          {' '}После изменения границ нажмите «Предпросмотр отрезка».
        </p>
      )}

      {error && <p role="alert" className="text-xs font-mono text-red-500 border border-red-500/50 bg-red-500/10 p-3">[ERROR]: {error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
        <label className="text-xs font-mono text-zinc-400 space-y-2 uppercase">
          <span className="block text-zinc-300">Начало (секунды)</span>
          <input type="number" min={0} max={duration ?? undefined} step="0.1" value={Number.isFinite(start) ? start : ''} onChange={(e) => setStart(e.target.valueAsNumber)} className={INPUT} />
          {duration !== null && <input aria-label="Начало отрезка" type="range" min={0} max={duration} step="0.1" value={Number.isFinite(start) ? start : 0} onChange={(e) => setStart(Number(e.target.value))} className="w-full accent-orange-500 bg-zinc-950 cursor-pointer" />}
        </label>
        <label className="text-xs font-mono text-zinc-400 space-y-2 uppercase">
          <span className="block text-zinc-300">Конец (секунды)</span>
          <input type="number" min={0} max={duration ?? undefined} step="0.1" value={Number.isFinite(end) ? end : ''} onChange={(e) => setEnd(e.target.valueAsNumber)} className={INPUT} />
          {duration !== null && <input aria-label="Конец отрезка" type="range" min={0} max={duration} step="0.1" value={Number.isFinite(end) ? end : 0} onChange={(e) => setEnd(Number(e.target.value))} className="w-full accent-orange-500 bg-zinc-950 cursor-pointer" />}
        </label>
      </div>

      <div className="flex flex-wrap gap-4 items-center justify-between text-xs font-mono pt-2 border-t border-zinc-800">
        <span className="text-zinc-400">{valid ? `Выбрано: ${(end - start).toFixed(1)} с` : 'Ошибка границ диапазона.'}{duration !== null && ` // ВСЕГО: ${videoTime(duration)}`}</span>
        {duration !== null && <button onClick={() => { setStart(0); setEnd(duration); }} className="text-orange-500 uppercase hover:underline">Всё видео</button>}
        <button disabled={!valid || loading} onClick={previewSelection} className="inline-flex items-center gap-1.5 text-orange-500 hover:text-white uppercase disabled:opacity-50">
          <Play size={14} /> Предпросмотр отрезка
        </button>
      </div>

      <div className="flex flex-wrap justify-between gap-4 pt-4 border-t border-zinc-800">
        <button onClick={onCancel} className="border border-zinc-800 px-6 py-3 text-zinc-400 hover:text-white hover:border-zinc-600 font-mono text-xs uppercase transition-colors">Другой файл</button>
        <button disabled={!valid || loading} onClick={() => void submitSelection()} className="bg-orange-500 text-black font-black uppercase tracking-widest px-8 py-3 hover:bg-orange-400 transition-transform shadow-[4px_4px_0px_#fff] active:translate-y-1 active:shadow-none disabled:opacity-50">
          Улучшить выбранный отрезок
        </button>
      </div>
    </div>
  );
}