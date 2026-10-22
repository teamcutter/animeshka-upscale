import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function AuthScreen() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const { setUser } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const endpoint = isLogin ? '/api/auth/login' : '/api/auth/register';
    const body = isLogin ? { email, password } : { email, password, name };
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Ошибка авторизации. Проверьте данные.');
      const userData = await res.json();
      setUser(userData);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white/80 backdrop-blur-md rounded-2xl shadow-lg border border-orange-200/50 p-8 z-10">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-stone-800">
            {isLogin ? 'Вход в систему' : 'Регистрация'}
          </h2>
          <p className="text-stone-600 mt-2">Animeshka Upscale</p>
        </div>
        {error && (
          <div className="bg-red-100/80 text-red-700 p-3 rounded-xl text-sm mb-4 text-center border border-red-200">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <input type="text" placeholder="Ваше имя" required value={name} onChange={(e) => setName(e.target.value)}
              className="w-full bg-white/60 border border-orange-200 text-stone-800 rounded-xl p-3 focus:ring-2 focus:ring-orange-400 focus:outline-none placeholder-stone-400" />
          )}
          <input type="email" placeholder="Email" required value={email} onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-white/60 border border-orange-200 text-stone-800 rounded-xl p-3 focus:ring-2 focus:ring-orange-400 focus:outline-none placeholder-stone-400" />
          <input type="password" placeholder="Пароль" required value={password} onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-white/60 border border-orange-200 text-stone-800 rounded-xl p-3 focus:ring-2 focus:ring-orange-400 focus:outline-none placeholder-stone-400" />
          <button type="submit" className="w-full bg-orange-500 text-white rounded-xl py-3 font-medium hover:bg-orange-600 transition-colors shadow-sm">
            {isLogin ? 'Войти' : 'Создать аккаунт'}
          </button>
        </form>
        <p className="text-center text-sm text-stone-600 mt-6">
          {isLogin ? 'Нет аккаунта? ' : 'Уже зарегистрированы? '}
          <button onClick={() => { setIsLogin(!isLogin); setError(''); }} className="text-orange-600 font-bold hover:underline">
            {isLogin ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </p>
      </div>
    </div>
  );
}