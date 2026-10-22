import { useEffect, useState, type ReactNode } from 'react';

import { getMe, isAbort, type User } from '../api';
import { AuthContext } from './auth-context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    // The session cookie decides: a logged-in user (or the guest when AUTH__REQUIRED=false).
    getMe(controller.signal)
      .then(setUser)
      .catch((error: unknown) => {
        if (!isAbort(error)) setUser(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, []);

  return <AuthContext.Provider value={{ user, isLoading, setUser }}>{children}</AuthContext.Provider>;
}
