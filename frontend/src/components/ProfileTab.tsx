import { useState } from 'react';
import { errorMessage, logout } from '../api';
import { useAuth } from '../context/useAuth';

export default function ProfileTab() {
  const { user, setUser } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [error, setError] = useState('');
  
  const handleLogout = async () => {
    setError('');
    setIsLoggingOut(true);
    try {
      await logout();
      setUser(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-8">
      <div className="border-l-4 border-orange-500 pl-6 py-2">
        <h2 className="text-3xl font-black text-white uppercase tracking-tighter">Профиль</h2>
        <p className="text-zinc-500 font-mono text-sm uppercase mt-1">IDENTIFICATION</p>
      </div>
      
      <div className="border border-zinc-800 bg-zinc-900 p-8">
        <div className="flex items-center space-x-6 mb-8 border-b border-zinc-800 pb-8">
          <div className="w-20 h-20 bg-zinc-950 border-2 border-orange-500 flex items-center justify-center text-orange-500 font-black text-3xl uppercase shadow-[4px_4px_0px_#ea580c]">
            {user?.name.charAt(0) || 'U'}
          </div>
          <div>
            <h3 className="text-2xl font-black text-white uppercase">{user?.name || 'GUEST'}</h3>
            <p className="text-zinc-500 font-mono text-sm mt-1">ID: {user?.id || 'UNKNOWN'}</p>
          </div>
        </div>
        
        <div className="space-y-4 font-mono text-sm">
          <div className="flex justify-between border-b border-zinc-800/50 pb-2">
            <span className="text-zinc-500">SYSTEM_STATUS</span>
            <span className="text-green-500">ONLINE</span>
          </div>
          <div className="flex justify-between border-b border-zinc-800/50 pb-2">
            <span className="text-zinc-500">ACCESS_LEVEL</span>
            <span className="text-orange-500">STANDARD</span>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-zinc-800">
          {error && (
            <p role="alert" className="mb-4 text-red-500 font-mono text-sm">{error}</p>
          )}
          <button 
            onClick={handleLogout}
            disabled={isLoggingOut}
            className="w-full bg-zinc-950 border border-red-500/50 text-red-500 hover:bg-red-500 hover:text-white font-bold font-mono py-4 uppercase transition-colors disabled:opacity-60 disabled:cursor-wait"
          >
            {isLoggingOut ? 'Завершение сеанса...' : 'Завершить сеанс'}
          </button>
        </div>
      </div>
    </div>
  );
}
