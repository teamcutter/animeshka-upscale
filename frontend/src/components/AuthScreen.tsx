import { useState, type FormEvent } from 'react';
import { Loader2 } from 'lucide-react';

import { errorMessage, login, register } from '../api';
import { useAuth } from '../context/useAuth';

const INPUT =
  'w-full bg-white/60 border border-orange-200 text-stone-800 rounded-xl p-3 focus:ring-2 focus:ring-orange-400 focus:outline-none placeholder-stone-400';

export default function AuthScreen() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { setUser } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      setUser(isLogin ? await login(email, password) : await register(email, password, name));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white/80 backdrop-blur-md rounded-2xl shadow-lg border border-orange-200/50 p-8 z-10">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-stone-800">{isLogin ? 'Вход в систему' : 'Регистрация'}</h2>
          <p className="text-stone-600 mt-2">Animeshka Upscale</p>
        </div>
        {error && (
          <div className="bg-red-100/80 text-red-700 p-3 rounded-xl text-sm mb-4 text-center border border-red-200">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <input type="text" placeholder="Ваше имя" required maxLength={64} value={name} onChange={(e) => setName(e.target.value)} className={INPUT} />
          )}
          <input type="email" placeholder="Email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={INPUT} />
          <input
            type="password"
            placeholder={isLogin ? 'Пароль' : 'Пароль (не меньше 8 символов)'}
            required
            minLength={isLogin ? undefined : 8}
            autoComplete={isLogin ? 'current-password' : 'new-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={INPUT}
          />
          <button
            type="submit"
            disabled={busy}
            className="w-full bg-orange-500 text-white rounded-xl py-3 font-medium hover:bg-orange-600 transition-colors shadow-sm disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {busy && <Loader2 size={16} className="animate-spin" />}
            {isLogin ? 'Войти' : 'Создать аккаунт'}
          </button>
        </form>
        <p className="text-center text-sm text-stone-600 mt-6">
          {isLogin ? 'Нет аккаунта? ' : 'Уже зарегистрированы? '}
          <button
            type="button"
            onClick={() => {
              setIsLogin(!isLogin);
              setError('');
            }}
            className="text-orange-600 font-bold hover:underline"
          >
            {isLogin ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </p>
      </div>
    </div>
  );
}
