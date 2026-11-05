export default function WelcomeTab({ onStart }: { onStart: () => void }) {
  return (
    <div className="max-w-6xl mx-auto space-y-20 pb-16 pt-8">
      <div className="relative border-l-4 border-orange-500 pl-8 md:pl-12 py-4">
        <div className="absolute top-0 left-0 w-8 h-8 border-t-4 border-orange-500 -translate-y-4 -translate-x-1"></div>
        <span className="text-orange-500 font-mono text-sm uppercase tracking-[0.3em] font-bold">/// Система апскейла v6.7</span>
        
        <h1 className="mt-6 text-5xl md:text-7xl font-black text-white uppercase leading-[1.1] tracking-tighter">
          Один клик. <br/>
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-orange-600">Лучшее качество.</span> <br/>
          Готово.
        </h1>
        
        <p className="mt-6 text-zinc-400 text-lg md:text-xl max-w-2xl font-medium">
          Animeshka Upscale использует передовые нейросети. Мы устраняем шумы, повышаем разрешение и возвращаем детали. Никакого мыла — только звенящая резкость.
        </p>
        
        <button 
          onClick={onStart} 
          className="mt-10 bg-orange-500 text-black px-10 py-4 font-black uppercase tracking-wider text-lg transition-transform hover:-translate-y-1 hover:translate-x-1 shadow-[6px_6px_0px_#fff] hover:shadow-[10px_10px_0px_#fff] flex items-center space-x-3"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
          <span>Инициализировать</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="border border-zinc-800 bg-zinc-900 p-2 group hover:border-orange-500 transition-colors">
          <div className="relative h-80 bg-zinc-950 overflow-hidden">
            <img src="/example-after.jpg" className="absolute inset-0 w-full h-full object-cover" alt="После" />
            <div className="absolute inset-y-0 left-0 w-1/2 border-r-2 border-orange-500 z-10 overflow-hidden">
              <img src="/example-before.jpg" className="absolute inset-0 w-[200%] max-w-none h-full object-cover" alt="До" />
            </div>
            <div className="absolute top-4 left-4 bg-black text-white font-mono text-xs px-2 py-1 border border-zinc-700 z-20">INPUT_LOW_RES</div>
            <div className="absolute top-4 right-4 bg-orange-500 text-black font-mono text-xs font-bold px-2 py-1 z-20">OUTPUT</div>
          </div>
          <div className="p-6">
            <h3 className="font-bold text-2xl text-white mb-2 uppercase tracking-tight">Восстановление</h3>
            <p className="text-zinc-400">Моментальное шумоподавление и устранение артефактов сжатия для любых форматов.</p>
          </div>
        </div>
        
        <div className="border border-zinc-800 bg-zinc-900 p-2 group hover:border-orange-500 transition-colors">
          <div className="relative h-80 bg-zinc-950 overflow-hidden">
             <img src="/example-4k.jpg" className="absolute inset-0 w-full h-full object-cover" alt="4K Upscale" />
             <div className="absolute bottom-4 right-4 bg-black/80 backdrop-blur border border-orange-500/50 text-orange-500 font-mono text-sm px-4 py-2 flex items-center gap-2 z-10">
               <span className="w-2 h-2 bg-orange-500 rounded-full animate-pulse"></span>
               UPSCALE_ACTIVE
             </div>
          </div>
          <div className="p-6">
            <h3 className="font-bold text-2xl text-white mb-2 uppercase tracking-tight">Детализация x4</h3>
            <p className="text-zinc-400">Генерация недостающих пикселей с идеальным сохранением оригинальной рисовки.</p>
          </div>
        </div>
      </div>
    </div>
  );
}