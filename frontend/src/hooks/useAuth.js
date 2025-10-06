import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '@/lib/axios';

export const useAuth = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      
      login: async (email, password) => {
        const response = await api.post(`/auth/login`, { email, password });
        const token = response.data.access_token;
        set({ user: response.data.user, token });
        return response.data;
      },
      
      register: async (email, password, full_name) => {
        const response = await api.post(`/auth/register`, { 
          email, 
          password, 
          full_name 
        });
        const token = response.data.access_token;
        set({ user: response.data.user, token });
        return response.data;
      },
      
      logout: () => {
        set({ user: null, token: null });
      },
      
      setAuth: (user, token) => {
        set({ user, token });
      },
    }),
    {
      name: 'auth-storage',
    }
  )
);
