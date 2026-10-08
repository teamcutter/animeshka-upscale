import { useState } from 'react';

export default function MainTab() {
  // Создаем состояние, чтобы помнить, какая модель сейчас выбрана
  const [model, setModel] = useState('Photo');

  return (
    <div className="max-w-3xl mx-auto bg-white rounded-2xl shadow-sm border border-slate-100 p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-slate-800">Новый апскейл</h2>
        <div className="flex space-x-2">
          {/* Обновили текст увеличения */}
          <select className="bg-slate-50 border border-slate-200 text-slate-700 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block p-2.5">
            <option>Улучшение в 4к</option>
            <option>Улучшение в 2к</option>
          </select>
          
          {/* Привязали выбор модели к состоянию */}
          <select 
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block p-2.5"
          >
            <option value="Photo">Модель: Photo</option>
            <option value="Anime">Модель: Anime</option>
          </select>
        </div>
      </div>

      <div className="border-2 border-dashed border-indigo-200 bg-indigo-50/50 rounded-2xl p-12 text-center hover:bg-indigo-50 transition-colors cursor-pointer">
        <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center mx-auto mb-4 shadow-sm text-indigo-500">
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
        </div>
        
        {/* Динамически меняем текст в зависимости от выбранной модели */}
        <p className="text-lg font-medium text-slate-700 mb-1">
          {model === 'Anime' ? 'Перетащите видео сюда' : 'Перетащите изображение сюда'}
        </p>
        <p className="text-sm text-slate-500">
          {model === 'Anime' 
            ? 'Поддерживается MP4, MOV, WEBM до 50 MB' 
            : 'Поддерживается PNG, JPG, WEBP до 5 MB'}
        </p>
      </div>
    </div>
  );
}