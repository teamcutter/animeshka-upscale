import { useState, type FormEvent } from 'react';
import { Loader2 } from 'lucide-react';
import { errorMessage, login, register } from '../api';
import { useAuth } from '../context/useAuth';

const INPUT = 'w-full bg-zinc-950 border border-zinc-800 text-white rounded-none p-3 focus:border-orange-500 focus:outline-none placeholder-zinc-600 font-mono text-sm';

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
    <div className="min-h-screen flex items-center justify-center p-4 bg-zinc-950">
      <div className="max-w-md w-full border border-zinc-800 bg-zinc-900 p-8 shadow-2xl relative z-10">
        <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-orange-500"></div>
        <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-orange-500"></div>
        <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-orange-500"></div>
        <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-orange-500"></div>

        <div className="text-center mb-8">
          <h2 className="text-2xl font-black text-white uppercase tracking-tighter">
            {isLogin ? 'Вход в систему' : 'Регистрация'}
          </h2>
          <p className="text-orange-500 font-mono text-xs uppercase mt-2">Animeshka_Upscale</p>
        </div>

        {error && (
          <div className="border border-red-500/50 bg-red-500/10 text-red-500 p-3 text-xs mb-6 text-center font-mono">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div>
              <label className="block text-zinc-400 font-mono text-xs uppercase mb-1">Имя</label>
              <input type="text" placeholder="Ваше имя" required maxLength={64} value={name} onChange={(e) => setName(e.target.value)} className={INPUT} />
            </div>
          )}
          
          <div>
            <label className="block text-zinc-400 font-mono text-xs uppercase mb-1">Email</label>
            <input type="email" placeholder="Email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={INPUT} />
          </div>

          <div>
            <label className="block text-zinc-400 font-mono text-xs uppercase mb-1">Пароль</label>
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
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-full bg-orange-500 text-black font-black uppercase tracking-widest py-4 hover:bg-orange-400 transition-transform shadow-[4px_4px_0px_#fff] active:translate-y-1 active:shadow-none disabled:opacity-60 flex items-center justify-center gap-2 mt-6"
          >
            {busy && <Loader2 size={16} className="animate-spin" />}
            {isLogin ? 'Войти' : 'Создать аккаунт'}
          </button>
        </form>

        <p className="text-center text-xs font-mono text-zinc-500 mt-6">
          {isLogin ? 'Нет аккаунта? ' : 'Уже зарегистрированы? '}
          <button
            type="button"
            onClick={() => {
              setIsLogin(!isLogin);
              setError('');
            }}
            className="text-orange-500 font-bold hover:underline uppercase"
          >
            {isLogin ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </p>
      </div>
    </div>
  );
}