import { useEffect, useRef, useState } from 'react';
import { Loader2, Play } from 'lucide-react';
import { errorMessage, isAbort, previewVideo } from '../api';
import { videoTime } from '../hooks';

const INPUT = 'w-full rounded-xl border border-orange-200 bg-white/80 p-2.5 text-stone-800';

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
    <div className="space-y-5">
      <div>
        <h3 className="font-bold text-stone-800 truncate" title={file.name}>{file.name}</h3>
        <p className="text-sm text-stone-600 mt-1">Выберите отрезок перед обработкой. По умолчанию — первые 10 секунд.</p>
      </div>
      <div className="rounded-2xl overflow-hidden bg-stone-900 aspect-video relative">
        <video
          ref={player}
          src={needsConversion ? previewUrl ?? undefined : sourceUrl}
          controls playsInline preload="metadata" className="h-full w-full"
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
          <div className="absolute inset-0 bg-black/70 text-white flex flex-col items-center justify-center gap-3">
            <Loader2 className="animate-spin" />
            <p className="text-sm px-4 text-center">Готовим совместимый предпросмотр…</p>
          </div>
        )}
      </div>
      {needsConversion && (
        <p className="text-xs text-stone-500">
          Для этого формата создаётся MP4-предпросмотр до 30 секунд без улучшения.
          {previewUrl && ` Сейчас: ${videoTime(previewStart)}–${videoTime(previewStart + previewLength)}.`}
          {' '}После изменения границ нажмите «Предпросмотр отрезка».
        </p>
      )}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <div className="grid grid-cols-2 gap-4">
        <label className="text-sm text-stone-700 space-y-2">
          <span className="block">Начало, секунды</span>
          <input type="number" min={0} max={duration ?? undefined} step="0.1" value={Number.isFinite(start) ? start : ''} onChange={(e) => setStart(e.target.valueAsNumber)} className={INPUT} />
          {duration !== null && <input aria-label="Начало отрезка" type="range" min={0} max={duration} step="0.1" value={Number.isFinite(start) ? start : 0} onChange={(e) => setStart(Number(e.target.value))} className="w-full accent-orange-500" />}
        </label>
        <label className="text-sm text-stone-700 space-y-2">
          <span className="block">Конец, секунды</span>
          <input type="number" min={0} max={duration ?? undefined} step="0.1" value={Number.isFinite(end) ? end : ''} onChange={(e) => setEnd(e.target.valueAsNumber)} className={INPUT} />
          {duration !== null && <input aria-label="Конец отрезка" type="range" min={0} max={duration} step="0.1" value={Number.isFinite(end) ? end : 0} onChange={(e) => setEnd(Number(e.target.value))} className="w-full accent-orange-500" />}
        </label>
      </div>
      <div className="flex flex-wrap gap-3 items-center text-sm">
        <span className="text-stone-600">{valid ? `Выбрано ${(end - start).toFixed(1)} с` : 'Конец должен быть после начала и в пределах видео.'}{duration !== null && ` · Всего ${videoTime(duration)}`}</span>
        {duration !== null && <button onClick={() => { setStart(0); setEnd(duration); }} className="text-orange-700 underline">Всё видео</button>}
        <button disabled={!valid || loading} onClick={previewSelection} className="inline-flex items-center gap-1 text-orange-700 disabled:opacity-50"><Play size={15} /> Предпросмотр отрезка</button>
      </div>
      <div className="flex flex-wrap justify-between gap-3">
        <button onClick={onCancel} className="border border-orange-200 px-5 py-2.5 rounded-xl text-stone-700">Другой файл</button>
        <button disabled={!valid || loading} onClick={() => void submitSelection()} className="bg-orange-500 hover:bg-orange-600 text-white px-5 py-2.5 rounded-xl font-medium disabled:opacity-50">Улучшить выбранный отрезок</button>
      </div>
    </div>
  );
}
