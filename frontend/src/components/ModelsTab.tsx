import { useEffect, useRef, useState } from 'react';
import { Download, FlaskConical, Loader2, Upload } from 'lucide-react';

import {
  errorMessage, getQopModels, isAbort, predictQop,
  type QopCatalog, type QopPrediction, type QopSource,
} from '../api';

const CONTENT_LABELS: Record<string, string> = {
  anime: 'Аниме', portrait: 'Портрет', landscape: 'Пейзаж',
  text: 'Текст', noise: 'Шум', unknown: 'Без категории',
};
const INPUT = 'w-full border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-100 focus:border-teal-400 focus:outline-none';
const metric = (value: number | null | undefined) => value == null ? '—' : value.toFixed(3);
const STATUS_LABELS = {
  pending: 'Подключение к базе', disabled: 'Автообучение отключено',
  collecting: 'Подготовка измерений', insufficient_data: 'Недостаточно данных',
  training: 'Обучение моделей', ready: 'Модели обновлены', error: 'Ошибка обновления',
};

export default function ModelsTab() {
  const [source, setSource] = useState<QopSource>('trained');
  const [catalog, setCatalog] = useState<QopCatalog | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [contentType, setContentType] = useState('anime');
  const [maxSize, setMaxSize] = useState(2048);
  const [result, setResult] = useState<QopPrediction | null>(null);
  const [error, setError] = useState('');
  const [catalogError, setCatalogError] = useState('');
  const [busy, setBusy] = useState(false);
  const prediction = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;
    let version: string | undefined;
    async function refresh() {
      if (inFlight || controller.signal.aborted) return;
      inFlight = true;
      try {
        const data = await getQopModels(source, controller.signal);
        if (controller.signal.aborted) return;
        setCatalog(data);
        setCatalogError('');
        if (data.available && data.created_at !== version) {
          version = data.created_at;
          prediction.current?.abort();
          setBusy(false);
          setResult(null);
          setContentType(data.content_types?.includes('anime') ? 'anime' : data.content_types?.[0] ?? 'unknown');
          setMaxSize(data.training_max_sizes?.[0] ?? 2048);
        }
      } catch (err: unknown) {
        if (!isAbort(err)) setCatalogError(errorMessage(err));
      } finally {
        inFlight = false;
      }
    }
    void refresh();
    const timer = source === 'trained' ? window.setInterval(() => void refresh(), 2000) : undefined;
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [source]);

  useEffect(() => () => prediction.current?.abort(), []);

  function changeSource(next: QopSource) {
    if (next === source) return;
    prediction.current?.abort();
    setSource(next);
    setCatalog(null);
    setResult(null);
    setBusy(false);
    setError('');
    setCatalogError('');
  }

  function clearResult() {
    prediction.current?.abort();
    setBusy(false);
    setResult(null);
    setError('');
  }

  async function run() {
    if (!file) return;
    prediction.current?.abort();
    const controller = new AbortController();
    prediction.current = controller;
    setBusy(true);
    setResult(null);
    setError('');
    try {
      setResult(await predictQop(source, file, contentType, maxSize, controller.signal));
    } catch (err: unknown) {
      if (!isAbort(err)) setError(errorMessage(err));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="border-l-4 border-teal-400 pl-6 py-2">
        <p className="font-mono text-xs uppercase tracking-widest text-teal-400">Quality lab / QoP</p>
        <h2 className="mt-2 text-3xl font-black uppercase tracking-tighter text-white">Модели качества</h2>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">
          Сравните OLS, Ridge и Lasso и оцените качество изображения до апскейла.
          QoP — расчётный показатель от 0 до 1, а не оценка зрителей.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        {(['trained', 'demo'] as const).map(value => (
          <button key={value} onClick={() => changeSource(value)} aria-pressed={source === value}
            className={`border px-5 py-3 text-xs font-bold uppercase tracking-widest ${source === value ? 'border-teal-400 bg-teal-400/10 text-teal-400' : 'border-zinc-700 text-zinc-400 hover:text-white'}`}>
            {value === 'trained' ? 'Обученные модели' : 'Демо на синтетических данных'}
          </button>
        ))}
        {catalog?.available && (
          <a href={`/api/qop/models/download?source=${source}`} className="ml-auto flex items-center gap-2 border border-zinc-700 px-4 py-3 text-xs text-zinc-300 hover:border-teal-400">
            <Download size={15} /> Скачать модели
          </a>
        )}
      </div>

      {source === 'demo' && (
        <div className="flex gap-3 border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-200">
          <FlaskConical size={22} className="shrink-0" />
          <p>Демонстрация на синтетических данных. Прогнозы и метрики показывают работу моделей;
            они не подтверждают качество реального апскейла.</p>
        </div>
      )}

      {(error || catalogError) && <p role="alert" className="border border-red-500/50 bg-red-500/10 p-4 text-sm text-red-300">{error || catalogError}</p>}
      {!catalog && !catalogError && <p role="status" className="flex items-center gap-2 text-zinc-400"><Loader2 className="animate-spin" size={18} /> Загрузка моделей…</p>}

      {source === 'trained' && catalog?.automatic && (
        <section className="border border-zinc-800 bg-zinc-900 p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-lg font-bold text-white">Данные из сохранённых работ</h3>
            <span role="status" className="text-xs font-mono text-teal-400">{STATUS_LABELS[catalog.automatic.state]}</span>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-zinc-400">Метрики загружаются из базы автоматически.
            Недостающие измерения восстанавливаются по исходным и готовым изображениям.
            Новые результаты обработки автоматически обновляют модели.</p>
          <dl className="mt-5 grid gap-4 sm:grid-cols-3">
            <div><dt className="text-xs text-zinc-500">Завершённые изображения</dt><dd className="mt-1 font-mono text-xl text-white">{catalog.automatic.completed_images}</dd></div>
            <div><dt className="text-xs text-zinc-500">Работы с пригодными метриками</dt><dd className="mt-1 font-mono text-xl text-white">{catalog.automatic.usable_jobs}</dd></div>
            <div><dt className="text-xs text-zinc-500">Разные изображения / минимум для обучения</dt><dd className="mt-1 font-mono text-xl text-white">{catalog.automatic.distinct_images} / {catalog.automatic.min_images}</dd></div>
          </dl>
          {catalog.automatic.missing_quality > 0 && <p className="mt-4 text-xs text-amber-300">
            Недостаточно измерений для {catalog.automatic.missing_quality} работ.
            {catalog.automatic.missing_files > 0 && ` Файлы недоступны для ${catalog.automatic.missing_files} работ.`}
          </p>}
          {catalog.automatic.last_checked && <p className="mt-4 text-xs text-zinc-500">Последняя проверка: {new Date(catalog.automatic.last_checked).toLocaleTimeString()}</p>}
        </section>
      )}

      {catalog && !catalog.available && (
        <div className="border border-zinc-800 bg-zinc-900 p-8">
          <h3 className="text-xl font-bold text-white">{catalog.automatic?.state === 'training' ? 'Модели обучаются' : 'Модели появятся автоматически'}</h3>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-zinc-400">
            Для обучения нужно достаточно разных изображений с измерениями качества.
            Экспортировать данные или запускать обучение вручную не требуется.
            Пока можно сравнить регрессии и попробовать прогноз в демо.
          </p>
          <button onClick={() => changeSource('demo')} className="mt-6 bg-teal-400 px-6 py-3 text-sm font-bold text-black">Открыть демо</button>
        </div>
      )}

      {catalog?.available && <>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ['Наблюдения', catalog.rows],
            ['Изображения / обучение', catalog.train_images],
            ['Изображения / тест', catalog.test_images],
          ].map(([label, value]) => <div key={label} className="border border-zinc-800 bg-zinc-900 p-5">
            <p className="text-xs text-zinc-400">{label}</p><p className="mt-2 font-mono text-2xl text-white">{value}</p>
          </div>)}
        </div>

        <section className="border border-zinc-800 bg-zinc-900 p-5 sm:p-6">
          <h3 className="text-lg font-bold uppercase text-white">Сравнение моделей</h3>
          <p className="mt-2 text-xs leading-relaxed text-zinc-400">
            Запуски одного изображения остаются в одной выборке. Меньше RMSE — лучше;
            R² ближе к 1 — лучше. Модель выбирается по RMSE кросс-валидации.
          </p>
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[550px] text-left text-sm">
              <thead className="border-b border-zinc-700 text-xs text-zinc-400"><tr>
                <th className="py-3">Модель</th><th>R² / тест</th><th>MAE / тест</th><th>RMSE / тест</th><th>RMSE / CV</th>
              </tr></thead>
              <tbody>{catalog.models?.map(model => <tr key={model.name} className="border-b border-zinc-800 font-mono text-zinc-300">
                <th className="py-4 font-medium text-white">{model.name}{catalog.best_model === model.name && <span className="ml-2 text-xs text-teal-400">★ CV</span>}</th>
                <td>{metric(model.metrics.R2_test)}</td><td>{metric(model.metrics.MAE_test)}</td>
                <td>{metric(model.metrics.RMSE_test)}</td><td>{metric(model.metrics.RMSE_cv_mean)}</td>
              </tr>)}</tbody>
            </table>
          </div>
          <p className="mt-4 text-xs text-zinc-500">Цель: {catalog.target === 'qop' ? 'QoP, 0–1' : 'PSNR, dB'} · Экспорт: {catalog.created_at ? new Date(catalog.created_at).toLocaleDateString() : '—'}</p>
        </section>

        <section className="grid gap-6 border border-zinc-800 bg-zinc-900 p-5 sm:p-6 lg:grid-cols-2">
          <div>
            <h3 className="text-lg font-bold uppercase text-white">Прогноз для изображения</h3>
            <p className="mt-2 text-sm text-zinc-400">Загрузите изображение: модели оценят {catalog.training_modes?.map(mode => mode === '4k' ? '×4' : '×2').join(' и ')} без запуска апскейла.</p>
            <label className="mt-5 block text-sm text-zinc-300">Изображение
              <input type="file" accept="image/png,image/jpeg,image/webp,image/bmp" className={`${INPUT} mt-2 file:mr-3 file:border-0 file:bg-zinc-800 file:px-3 file:py-2 file:text-zinc-200`}
                onChange={event => { clearResult(); setFile(event.target.files?.[0] ?? null); }} />
            </label>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm text-zinc-300">Тип изображения
                <select value={contentType} onChange={event => { clearResult(); setContentType(event.target.value); }} className={`${INPUT} mt-2`}>
                  {catalog.content_types?.map(type => <option key={type} value={type}>{CONTENT_LABELS[type] ?? type}</option>)}
                </select>
              </label>
              <label className="text-sm text-zinc-300">Предел длинной стороны
                <select value={maxSize} onChange={event => { clearResult(); setMaxSize(Number(event.target.value)); }} className={`${INPUT} mt-2`}>
                  {catalog.training_max_sizes?.map(size => <option key={size} value={size}>{size} px</option>)}
                </select>
              </label>
            </div>
            <button onClick={() => void run()} disabled={!file || busy} className="mt-5 flex w-full items-center justify-center gap-2 bg-teal-400 px-6 py-4 text-sm font-black uppercase text-black hover:bg-teal-300 disabled:cursor-not-allowed disabled:opacity-40">
              {busy ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
              {busy ? 'Расчёт…' : 'Оценить качество'}
            </button>
          </div>
          <div aria-live="polite" className="border border-zinc-800 bg-zinc-950 p-5">
            <h4 className="font-mono text-sm uppercase text-zinc-400">{result ? `Прогноз · ${result.width} × ${result.height}` : 'Результаты прогноза'}</h4>
            {result ? <>
              <div className="mt-4 space-y-5">{catalog.models?.map(model => <div key={model.name}>
                <p className="mb-2 text-sm font-bold text-white">{model.name}</p>
                <div className="space-y-2">{result.predictions.filter(item => item.model === model.name).map(item => <div key={item.mode} className="flex items-center gap-3">
                  <span className="w-7 text-xs text-zinc-500">{item.mode === '4k' ? '×4' : '×2'}</span>
                  <div className="h-2 flex-1 bg-zinc-800"><div className={`h-full ${item.mode === '4k' ? 'bg-teal-400' : 'bg-zinc-400'}`} style={{ width: `${Math.max(0, Math.min(100, result.target === 'qop' ? item.value * 100 : item.value))}%` }} /></div>
                  <span className="w-14 text-right font-mono text-sm text-white">{item.value.toFixed(3)}</span>
                </div>)}</div></div>)}</div>
              <p className="mt-5 text-xs leading-relaxed text-zinc-500">{result.target === 'qop' ? 'QoP: 0–1. Значения ограничены этим диапазоном.' : 'PSNR в dB.'} Прогноз — оценка модели, а не измеренное качество результата.</p>
            </> : <p className="mt-8 text-sm leading-relaxed text-zinc-500">После загрузки появятся прогнозы всех моделей для доступных масштабов.</p>}
          </div>
        </section>
      </>}
    </div>
  );
}