import { useState, useRef } from 'react';

export default function MainTab({ health }: { health: any }) {
  const [file, setFile] = useState<File | null>(null);
  const [preset, setPreset] = useState('x4_anime');
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex justify-between items-end border-l-4 border-orange-500 pl-6 py-2">
        <div>
          <h2 className="text-3xl font-black text-white uppercase tracking-tighter">Терминал обработки</h2>
          <p className="text-zinc-500 font-mono text-sm uppercase mt-1">MAIN_WORKSPACE </p>
        </div>
        {health && (
          <div className="flex items-center space-x-2 border border-zinc-800 bg-zinc-900 px-3 py-1.5 hidden md:flex">
            <div className={`w-2 h-2 rounded-full ${health.status === 'ok' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className="font-mono text-xs text-zinc-400">API: {health.status.toUpperCase()}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div 
          className="lg:col-span-2 border border-zinc-800 bg-zinc-900 p-6 flex flex-col items-center justify-center min-h-[350px] border-dashed hover:border-orange-500 transition-colors cursor-pointer relative group" 
          onClick={() => fileInputRef.current?.click()}
        >
          <input type="file" className="hidden" ref={fileInputRef} onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <div className="w-16 h-16 bg-zinc-950 border border-zinc-800 flex items-center justify-center text-zinc-500 group-hover:text-orange-500 group-hover:border-orange-500 transition-all mb-4">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
          </div>
          <h3 className="font-bold text-white uppercase tracking-widest text-xl group-hover:text-orange-500 transition-colors">Выбрать медиа</h3>
          <p className="text-zinc-500 font-mono text-xs mt-3 uppercase tracking-wider">
            {file ? file.name : 'PNG, JPG, MP4 ДО 50MB'}
          </p>
        </div>

        <div className="space-y-6 flex flex-col justify-between">
          <div className="border border-zinc-800 bg-zinc-900 p-6 flex-1">
            <h4 className="text-zinc-400 font-mono text-xs uppercase mb-4 border-b border-zinc-800 pb-2">Модель апскейла</h4>
            <div className="space-y-3">
              {['x4_anime', 'x2_photo', 'x4_art'].map(p => (
                <button 
                  key={p} 
                  onClick={() => setPreset(p)}
                  className={`w-full text-left px-4 py-3 font-mono text-sm uppercase transition-colors flex justify-between items-center ${
                    preset === p 
                      ? 'border border-orange-500 bg-orange-500/10 text-orange-500 font-bold' 
                      : 'border border-zinc-800 text-zinc-400 hover:border-zinc-600'
                  }`}
                >
                  <span>{p}</span>
                  {preset === p && <span className="w-2 h-2 bg-orange-500"></span>}
                </button>
              ))}
            </div>
          </div>

          <button className="w-full bg-orange-500 text-black font-black uppercase tracking-widest py-5 hover:bg-orange-400 transition-transform shadow-[6px_6px_0px_#fff] hover:shadow-[8px_8px_0px_#fff] hover:-translate-y-0.5 active:translate-y-1 active:shadow-none">
            Инициализация
          </button>
        </div>
      </div>
    </div>
  );
}