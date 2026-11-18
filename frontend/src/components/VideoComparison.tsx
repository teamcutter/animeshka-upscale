import { useEffect, useRef, useState } from 'react';
import { Loader2, Pause, Play, Volume2, VolumeX } from 'lucide-react';
import { ReactCompareSlider } from 'react-compare-slider';

import { videoTime } from '../hooks';

interface Props {
  originalUrl: string;
  resultUrl: string;
}

/** Two aligned clips with one timeline; only the enhanced version plays audio. */
export default function VideoComparison({ originalUrl, resultUrl }: Props) {
  const original = useRef<HTMLVideoElement>(null);
  const result = useRef<HTMLVideoElement>(null);
  const wantsPlayback = useRef(false);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [muted, setMuted] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState('');

  const players = () => [original.current, result.current].filter((video): video is HTMLVideoElement => video !== null);

  const pause = () => {
    wantsPlayback.current = false;
    players().forEach((video) => video.pause());
    if (original.current && result.current && original.current.readyState >= 1) {
      original.current.currentTime = result.current.currentTime;
      original.current.playbackRate = 1;
    }
    setPlaying(false);
    setBuffering(false);
  };

  const resume = () => {
    const videos = players();
    const available = videos.length === 2 && videos.every((video) => video.readyState >= 3 && !video.seeking);
    setReady(available);
    if (!wantsPlayback.current || !available) return;
    void Promise.all(videos.map((video) => video.play()))
      .then(() => setBuffering(false))
      .catch((err: unknown) => {
        // Seeking or pausing can interrupt a pending play request.
        if (err instanceof DOMException && err.name === 'AbortError') return;
        pause();
        setError('Не удалось запустить видео. Попробуйте открыть результат отдельно.');
      });
  };

  const toggle = () => {
    if (wantsPlayback.current) {
      pause();
      return;
    }
    if (result.current?.ended) players().forEach((video) => { video.currentTime = 0; });
    wantsPlayback.current = true;
    setPlaying(true);
    setBuffering(true);
    resume();
  };

  const seek = (value: number) => {
    players().forEach((video) => {
      video.pause();
      video.currentTime = value;
    });
    setTime(value);
    if (wantsPlayback.current) setBuffering(true);
  };

  const wait = () => {
    if (!wantsPlayback.current) return;
    players().forEach((video) => video.pause());
    setBuffering(true);
  };

  useEffect(() => {
    const before = original.current;
    const after = result.current;
    let animation: number;
    const sync = () => {
      if (before && after && !before.paused && !after.paused && !before.seeking && !after.seeking) {
        const drift = before.currentTime - after.currentTime;
        if (Math.abs(drift) > 0.1) before.currentTime = after.currentTime;
        else before.playbackRate = drift > 0.02 ? 0.98 : drift < -0.02 ? 1.02 : 1;
      }
      animation = requestAnimationFrame(sync);
    };
    animation = requestAnimationFrame(sync);
    return () => {
      cancelAnimationFrame(animation);
      wantsPlayback.current = false;
      before?.pause();
      after?.pause();
    };
  }, [originalUrl, resultUrl]);

  const failed = () => {
    pause();
    setError('Не удалось загрузить видео для сравнения.');
  };

  return (
    <div className="h-full w-full flex flex-col bg-black text-zinc-100">
      <div className="relative flex-1 min-h-0">
        <ReactCompareSlider
          aria-label="Сравнение видео до и после улучшения"
          className="h-full w-full"
          itemOne={(
            <video
              ref={original}
              src={originalUrl}
              muted playsInline preload="auto"
              aria-label="Видео до улучшения"
              className="h-full w-full object-contain pointer-events-none"
              onCanPlay={resume} onSeeked={resume} onWaiting={wait} onError={failed}
            />
          )}
          itemTwo={(
            <video
              ref={result}
              src={resultUrl}
              muted={muted} playsInline preload="auto"
              aria-label="Видео после улучшения"
              className="h-full w-full object-contain pointer-events-none"
              onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
              onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
              onCanPlay={resume} onSeeked={resume} onWaiting={wait} onEnded={pause} onError={failed}
            />
          )}
        />
        {(!ready || buffering) && !error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/40 pointer-events-none" role="status">
            <Loader2 className="animate-spin text-orange-500" aria-label="Загрузка видео" />
          </div>
        )}
      </div>
      <div className="shrink-0 border-t border-zinc-800 bg-zinc-950 p-3 space-y-2">
        {error ? (
          <p role="alert" className="text-red-400 text-xs font-mono">
            {error} <a href={resultUrl} target="_blank" rel="noreferrer" className="underline">Открыть результат</a>
          </p>
        ) : (
          <div className="flex items-center gap-3">
            <button onClick={toggle} disabled={!ready && !playing} aria-label={playing ? 'Пауза' : 'Воспроизвести сравнение'} className="text-orange-500 hover:text-white disabled:opacity-40 p-1">
              {playing ? <Pause size={20} /> : <Play size={20} />}
            </button>
            <input aria-label="Позиция видео" type="range" min={0} max={duration || 0} step="0.01" value={Math.min(time, duration)} onChange={(event) => seek(Number(event.target.value))} disabled={!duration} className="flex-1 min-w-0 accent-orange-500" />
            <span className="font-mono text-xs whitespace-nowrap">{videoTime(time)} / {videoTime(duration)}</span>
            <button onClick={() => setMuted(!muted)} aria-label={muted ? 'Включить звук' : 'Выключить звук'} className="text-zinc-400 hover:text-white p-1">
              {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
            </button>
          </div>
        )}
        <p className="font-mono text-[10px] text-zinc-500 text-center">Перетащите разделитель, чтобы сравнить качество</p>
      </div>
    </div>
  );
}
