import { createContext } from 'react';

import type { User } from '../api';

export interface AuthContextType {
  user: User | null;
  /** True until the first /api/auth/me answer: the app shows neither the login nor the tabs. */
  isLoading: boolean;
  setUser: (user: User | null) => void;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
