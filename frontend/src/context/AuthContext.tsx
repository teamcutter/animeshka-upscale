import { createContext, useState, useEffect, useContext, type ReactNode } from 'react';

interface User {
  email: string;
  name: string;
  id?: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  setUser: (user: User | null) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Старые строки (ожидание ответа сервера):
// const [user, setUser] = useState<User | null>(null);
// const [isLoading, setIsLoading] = useState(true);

// Новые строки (режим разработчика):
const [user, setUser] = useState<User | null>({ email: 'dev@test.ru', name: 'Разработчик' });
const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // Проверяем, авторизован ли пользователь при загрузке страницы
    fetch('/api/auth/me', { credentials: 'include' })
      .then(res => {
        if (res.ok) return res.json();
        throw new Error('Not authenticated');
      })
      .then(data => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth должен использоваться внутри AuthProvider');
  }
  return context;
};