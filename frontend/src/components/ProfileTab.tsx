import { useEffect, useState } from 'react';

import { GUEST_EMAIL, isAbort, listJobs, logout, type Job } from '../api';
import { useAuth } from '../context/useAuth';
import { formatBytes } from '../hooks';

export default function ProfileTab() {
  const { user, setUser } = useAuth();
  const [done, setDone] = useState<Job[] | null>(null);
  const isGuest = user?.email === GUEST_EMAIL;

  useEffect(() => {
    const controller = new AbortController();
    listJobs({ status: 'done', limit: 200 }, controller.signal)
      .then(setDone)
      .catch((err: unknown) => {
        if (!isAbort(err)) setDone([]);
      });
    return () => controller.abort();
  }, []);

  const outputBytes = done?.reduce((sum, job) => sum + (job.output?.size_bytes ?? 0), 0) ?? 0;

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Ошибка при выходе из аккаунта', error);
    }
    // With AUTH__REQUIRED=false the next /me answers the guest again, so just reload the state.
    setUser(null);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-white/80 backdrop-blur-md rounded-2xl p-6 shadow-lg border border-orange-200/50 flex items-center space-x-6">
        <div className="w-24 h-24 bg-orange-200 rounded-full flex items-center justify-center text-orange-700 text-3xl font-bold uppercase shadow-inner">
          {user?.name?.substring(0, 2) || '??'}
        </div>
        <div>
          <h2 className="text-2xl font-bold text-stone-800">{user?.name}</h2>
          <p className="text-stone-600 font-medium">{user?.email}</p>
          {isGuest && (
            <p className="text-xs text-orange-700 mt-1">
              Вход на сервере отключён (AUTH__REQUIRED=false): все работы общие.
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white/80 backdrop-blur-md rounded-2xl p-6 shadow-lg border border-orange-200/50">
          <p className="text-stone-600 text-sm mb-1 font-medium">Обработано изображений</p>
          <p className="text-3xl font-bold text-orange-600">{done ? done.length : '…'}</p>
        </div>
        <div className="bg-white/80 backdrop-blur-md rounded-2xl p-6 shadow-lg border border-orange-200/50">
          <p className="text-stone-600 text-sm mb-1 font-medium">Объём результатов</p>
          <p className="text-3xl font-bold text-orange-500">{done ? formatBytes(outputBytes) : '…'}</p>
        </div>
      </div>

      {!isGuest && (
        <button
          onClick={() => void handleLogout()}
          className="w-full py-3 mt-2 bg-red-100/80 text-red-600 rounded-xl font-bold hover:bg-red-200 transition-colors border border-red-200/50 shadow-sm"
        >
          Выйти из аккаунта
        </button>
      )}
    </div>
  );
}
