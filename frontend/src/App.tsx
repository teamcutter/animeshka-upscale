import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider';
import { UploadCloud, Loader2, AlertCircle, Download } from 'lucide-react';

type AppState = 'Idle' | 'Uploading' | 'Processing/Inference' | 'Success' | 'Error';

export default function App() {
  const [appState, setAppState] = useState<AppState>('Idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [scale, setScale] = useState('x2');

  const onDrop = useCallback((acceptedFiles: File[], fileRejections: any[]) => {
    if (fileRejections.length > 0) {
      setAppState('Error');
      setErrorMsg('Неверный формат (только PNG/JPG/WEBP) или файл слишком большой.');
      return;
    }
    const file = acceptedFiles[0];
    simulateApiCall(file);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/jpeg': [], 'image/png': [], 'image/webp': [] },
    maxSize: 5 * 1024 * 1024,
    multiple: false
  });

  const simulateApiCall = (_file: File) => {
    setAppState('Uploading');
    setTimeout(() => {
      setAppState('Processing/Inference');
      setTimeout(() => {
        setAppState('Success');
      }, 3000);
    }, 1500);
  };

  const reset = () => setAppState('Idle');

  return (
    <div className="min-h-screen bg-dark text-white p-8 font-sans selection:bg-neon selection:text-white">
      <header className="max-w-4xl mx-auto flex justify-between items-center mb-12 border-b border-slate pb-4">
        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-neon to-cyan">
          Animeshka Upscale
        </h1>
        <div className="flex gap-4">
          <button className="text-sm px-4 py-2 bg-slate rounded-lg hover:bg-opacity-80 transition">Апскейлинг</button>
          <button className="text-sm px-4 py-2 border border-slate rounded-lg opacity-50 cursor-not-allowed">Мониторинг</button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto">
        <div className="mb-6 flex gap-4 bg-slate p-4 rounded-xl border border-gray-800 bg-opacity-50 backdrop-blur-md">
          <select 
            value={scale} 
            onChange={(e) => setScale(e.target.value)}
            className="bg-dark border border-gray-700 rounded-lg px-4 py-2 outline-none focus:border-neon transition"
            disabled={appState !== 'Idle'}
          >
            <option value="x2">Увеличение: x2</option>
            <option value="x4">Увеличение: x4</option>
          </select>
          <select className="bg-dark border border-gray-700 rounded-lg px-4 py-2 outline-none focus:border-neon transition" disabled={appState !== 'Idle'}>
            <option>Модель: Anime (REAL-ESRGAN)</option>
            <option>Модель: Photo</option>
          </select>
        </div>

        <div className="bg-slate p-1 rounded-2xl border border-gray-800 shadow-2xl">
          {appState === 'Idle' && (
            <div {...getRootProps()} className={`border-2 border-dashed rounded-xl p-24 text-center cursor-pointer transition-all duration-300 ${isDragActive ? 'border-cyan bg-cyan/5' : 'border-gray-600 hover:border-neon hover:bg-neon/5'}`}>
              <input {...getInputProps()} />
              <UploadCloud className="mx-auto h-16 w-16 text-gray-400 mb-4" />
              <p className="text-lg font-medium">Перетащите изображение сюда</p>
              <p className="text-sm text-gray-400 mt-2">Поддерживается PNG, JPG, WEBP до 5 MB</p>
            </div>
          )}

          {(appState === 'Uploading' || appState === 'Processing/Inference') && (
            <div className="p-24 text-center flex flex-col items-center justify-center">
              <Loader2 className="animate-spin h-16 w-16 text-neon mb-6" />
              <h2 className="text-xl font-semibold mb-2">
                {appState === 'Uploading' ? 'Загрузка на сервер...' : 'Магия REAL-ESRGAN в процессе...'}
              </h2>
              <p className="text-gray-400">Пожалуйста, подождите. Это может занять несколько секунд.</p>
            </div>
          )}

          {appState === 'Success' && (
            <div className="p-4">
              <div className="rounded-xl overflow-hidden mb-6 h-[500px] bg-dark relative">
                 <ReactCompareSlider
                  itemOne={<ReactCompareSliderImage src="https://images.unsplash.com/photo-1578632767115-351597cf2477?w=800&q=80" alt="До" style={{ filter: 'blur(2px)' }} />}
                  itemTwo={<ReactCompareSliderImage src="https://images.unsplash.com/photo-1578632767115-351597cf2477?w=1600&q=100" alt="После" />}
                  className="h-full w-full object-cover"
                />
                <div className="absolute top-4 left-4 bg-black/60 px-3 py-1 rounded text-xs">До (Оригинал)</div>
                <div className="absolute top-4 right-4 bg-black/60 px-3 py-1 rounded text-xs text-neon">После (Апскейл)</div>
              </div>
              <div className="flex justify-between items-center">
                <button onClick={reset} className="px-6 py-3 border border-gray-600 rounded-lg hover:bg-gray-800 transition">
                  Загрузить другое
                </button>
                <button className="px-6 py-3 bg-neon hover:bg-purple-600 rounded-lg font-medium flex items-center gap-2 transition shadow-[0_0_15px_rgba(138,43,226,0.4)]">
                  <Download size={18} /> Скачать результат
                </button>
              </div>
            </div>
          )}

          {appState === 'Error' && (
            <div className="p-24 text-center flex flex-col items-center">
              <AlertCircle className="h-16 w-16 text-error mb-4" />
              <h2 className="text-xl font-semibold text-error mb-2">Произошла ошибка</h2>
              <p className="text-gray-400 mb-6">{errorMsg}</p>
              <button onClick={reset} className="px-6 py-2 bg-slate border border-gray-600 rounded-lg hover:bg-gray-700">
                Попробовать снова
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}