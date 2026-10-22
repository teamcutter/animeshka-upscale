import { useState } from 'react';

export default function MainTab({ health }: { health: any }) {
  const [model, setModel] = useState('Photo');
  const [status, setStatus] = useState<'idle' | 'success'>('idle');

  return (
    <div className="max-w-3xl mx-auto bg-white/80 backdrop-blur-md rounded-2xl shadow-lg border border-orange-200/50 p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-stone-800">Создать работу</h2>
        <div className="flex space-x-2">
          <select className="bg-white/60 border border-orange-200 text-stone-700 text-sm rounded-xl focus:ring-orange-400 focus:border-orange-400 block p-2.5 outline-none">
            <option>Улучшение в 4к</option>
            <option>Улучшение в 2к</option>
          </select>
          <select 
            value={model} onChange={(e) => setModel(e.target.value)}
            className="bg-white/60 border border-orange-200 text-stone-700 text-sm rounded-xl focus:ring-orange-400 focus:border-orange-400 block p-2.5 outline-none"
          >
            <option value="Photo">Модель: Photo</option>
            <option value="Anime">Модель: Video</option>
          </select>
        </div>
      </div>

      {status === 'idle' ? (
        <div 
          onClick={() => setStatus('success')}
          className="border-2 border-dashed border-orange-300 bg-orange-50/50 rounded-2xl p-12 text-center hover:bg-orange-100/60 transition-colors cursor-pointer"
        >
          <div className="w-16 h-16 bg-white/90 rounded-full flex items-center justify-center mx-auto mb-4 shadow-sm text-orange-500">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
          </div>
          <p className="text-lg font-bold text-stone-800 mb-1">
            {model === 'Anime' ? 'Перетащите видео сюда' : 'Перетащите изображение сюда'}
          </p>
          <p className="text-sm text-stone-600">
            {model === 'Anime' ? 'Поддерживается MP4, MOV, WEBM до 50 MB' : 'Поддерживается PNG, JPG, WEBP до 5 MB'}
          </p>
        </div>
      ) : (
        <div className="bg-orange-50/50 rounded-2xl p-8 text-center border border-orange-200/50">
          <h3 className="text-xl font-bold text-stone-800 mb-2">Готово!</h3>
          <p className="text-stone-600 mb-6">Ваш файл успешно улучшен.</p>
          <div className="flex justify-center space-x-4">
            <button className="bg-orange-500 text-white px-6 py-2 rounded-xl font-medium hover:bg-orange-600 transition-colors shadow-sm">
              Скачать результат
            </button>
            <button onClick={() => setStatus('idle')} className="bg-white/60 text-stone-700 border border-orange-200 px-6 py-2 rounded-xl font-medium hover:bg-orange-50 transition-colors">
              Загрузить новый
            </button>
          </div>
        </div>
      )}
    </div>
  );
}