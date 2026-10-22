import { useAuth } from '../context/AuthContext';

export default function ProfileTab() {
  const { user, setUser } = useAuth();

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
      setUser(null);
    } catch (error) {
      console.error('Ошибка при выходе из аккаунта', error);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-white/80 backdrop-blur-md rounded-2xl p-6 shadow-lg border border-orange-200/50 flex items-center space-x-6">
        <div className="w-24 h-24 bg-orange-200 rounded-full flex items-center justify-center text-orange-700 text-3xl font-bold uppercase shadow-inner">
          {user?.name?.substring(0, 2) || 'МВ'}
        </div>
        <div>
          <h2 className="text-2xl font-bold text-stone-800">{user?.name}</h2>
          <p className="text-stone-600 font-medium">{user?.email}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white/80 backdrop-blur-md rounded-2xl p-6 shadow-lg border border-orange-200/50">
          <p className="text-stone-600 text-sm mb-1 font-medium">Обработано изображений</p>
          <p className="text-3xl font-bold text-orange-600">0</p>
        </div>
        <div className="bg-white/80 backdrop-blur-md rounded-2xl p-6 shadow-lg border border-orange-200/50">
          <p className="text-stone-600 text-sm mb-1 font-medium">Сэкономлено трафика</p>
          <p className="text-3xl font-bold text-orange-500">0 МБ</p>
        </div>
      </div>
      
      <button 
        onClick={handleLogout}
        className="w-full py-3 mt-2 bg-red-100/80 text-red-600 rounded-xl font-bold hover:bg-red-200 transition-colors border border-red-200/50 shadow-sm"
      >
        Выйти из аккаунта
      </button>
    </div>
  );
}