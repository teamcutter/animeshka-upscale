import { useState } from 'react';
import MainTab from './components/MainTab';
import ProfileTab from './components/ProfileTab';
import HistoryTab from './components/HistoryTab';
import ServerStatus from './components/ServerStatus';
import { useHealth } from './hooks';

export default function App() {
  const [activeTab, setActiveTab] = useState<'main' | 'history' | 'profile'>('main');
  // Re-check the server (backend, available modes) whenever the user switches tabs.
  const { health, unreachable } = useHealth(activeTab);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-indigo-600 font-bold text-xl">
              <span>✨ Animeshka Upscale</span>
            </div>
            <ServerStatus health={health} unreachable={unreachable} />
          </div>
          
          <nav className="flex space-x-1 bg-slate-100 p-1 rounded-xl">
            <button 
              onClick={() => setActiveTab('main')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'main' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Главная
            </button>
            <button 
              onClick={() => setActiveTab('history')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'history' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Мои работы
            </button>
            <button 
              onClick={() => setActiveTab('profile')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'profile' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Профиль
            </button>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 mt-4">
        {activeTab === 'main' && <MainTab health={health} />}
        {activeTab === 'history' && <HistoryTab />}
        {activeTab === 'profile' && <ProfileTab />}
      </main>
    </div>
  );
}