import { useState } from 'react';
import MainTab from './components/MainTab';
import ProfileTab from './components/ProfileTab';
import HistoryTab from './components/HistoryTab';
import FeedTab from './components/FeedTab';
import AuthScreen from './components/AuthScreen';
import FallingLeaves from './components/FallingLeaves';
import WelcomeTab from './components/WelcomeTab';
import { useAuth } from './context/useAuth';
import { useHealth } from './hooks';

export default function App() {
  const [activeTab, setActiveTab] = useState<'welcome' | 'main' | 'feed' | 'history' | 'profile'>('welcome');
  const { user, isLoading } = useAuth();
  const { health } = useHealth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <p className="text-orange-500 font-mono animate-pulse uppercase tracking-widest">Загрузка системы...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="relative min-h-screen bg-stone-900">
        <div 
          className="absolute inset-0 z-0 opacity-40 bg-cover bg-center" 
          style={{ backgroundImage: "url('/bg.jpg')" }}
        ></div>
        <FallingLeaves />
        <div className="relative z-10">
          <AuthScreen />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans selection:bg-orange-500 selection:text-black">
      <header className="border-b border-zinc-800 bg-zinc-950 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          
          <div className="flex-1 flex items-center">
            <button 
              onClick={() => setActiveTab('welcome')} 
              className="text-white font-black text-xl tracking-tighter hover:text-orange-500 transition-colors uppercase"
            >
              Animeshka<span className="text-orange-500">_Upscale</span>
            </button>
          </div>
          
          <nav className="flex-none flex space-x-2">
            {['main', 'feed', 'history'].map(tab => (
              <button 
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={`px-5 py-5 text-xs font-bold uppercase tracking-widest transition-all border-b-2 ${
                  activeTab === tab 
                    ? 'border-orange-500 text-orange-500 bg-orange-500/10' 
                    : 'border-transparent text-zinc-400 hover:text-white hover:bg-zinc-900'
                }`}
              >
                {tab === 'main' ? 'Главная' : tab === 'feed' ? 'Лента' : 'Мои работы'}
              </button>
            ))}
          </nav>

          <div className="flex-1 flex justify-end">
            <button 
              onClick={() => setActiveTab('profile')}
              className={`p-2 transition-all border ${
                activeTab === 'profile' 
                  ? 'border-orange-500 text-orange-500 bg-orange-500/10' 
                  : 'border-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-white'
              }`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
              </svg>
            </button>
          </div>

        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 mt-4">
        {activeTab === 'welcome' && <WelcomeTab onStart={() => setActiveTab('main')} />}
        {activeTab === 'main' && <MainTab health={health} />}
        {activeTab === 'feed' && <FeedTab />}
        {activeTab === 'history' && <HistoryTab />}
        {activeTab === 'profile' && <ProfileTab />}
      </main>
    </div>
  );
}