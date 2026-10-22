import { useState } from 'react';
import MainTab from './components/MainTab';
import ProfileTab from './components/ProfileTab';
import HistoryTab from './components/HistoryTab';
import AuthScreen from './components/AuthScreen';
import FallingLeaves from './components/FallingLeaves';
import { useAuth } from './context/AuthContext';
import { useHealth } from './hooks';

export default function App() {
  const [activeTab, setActiveTab] = useState<'main' | 'history' | 'profile'>('main');
  const { user, isLoading } = useAuth();
  const { health } = useHealth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-stone-500 font-medium animate-pulse">Загрузка...</p>
      </div>
    );
  }

  
  if (!user) {
    return (
      <>
        <FallingLeaves />
        <AuthScreen />
      </>
    );
  }
  

  return (
    <div className="min-h-screen flex flex-col relative">
      <div className="bg-overlay"></div>
      <FallingLeaves />
      
      <header className="bg-orange-200/70 backdrop-blur-md border-b border-orange-300/50 sticky top-0 z-10 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-orange-900 font-bold text-xl tracking-tight">
            <span>Animeshka Upscale</span>
          </div>
          
          <nav className="flex space-x-1 bg-orange-900/10 p-1 rounded-xl">
            <button 
              onClick={() => setActiveTab('main')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'main' ? 'bg-orange-50 text-orange-800 shadow-sm' : 'text-orange-900/70 hover:bg-orange-900/10'
              }`}
            >
              Главная
            </button>
            <button 
              onClick={() => setActiveTab('history')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'history' ? 'bg-orange-50 text-orange-800 shadow-sm' : 'text-orange-900/70 hover:bg-orange-900/10'
              }`}
            >
              Мои работы
            </button>
            <button 
              onClick={() => setActiveTab('profile')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'profile' ? 'bg-orange-50 text-orange-800 shadow-sm' : 'text-orange-900/70 hover:bg-orange-900/10'
              }`}
            >
              Профиль
            </button>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 mt-4 z-10">
        {activeTab === 'main' && <MainTab health={health} />}
        {activeTab === 'history' && <HistoryTab />}
        {activeTab === 'profile' && <ProfileTab />}
      </main>
    </div>
  );
}