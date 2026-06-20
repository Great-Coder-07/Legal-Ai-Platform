import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api'; // Your updated Axios instance with the interceptor

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user token and profile exists on app load
    const token = localStorage.getItem('user_token');
    const savedUser = localStorage.getItem('username');
    if (token && savedUser) {
      setUser({ username: savedUser });
    }
    setLoading(false);
  }, []);

  const login = async (username, password) => {
    // FastAPI OAuth2 implementation expects standard urlencoded FormData parameters
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await api.post('/api/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    const { access_token, username: returnedUsername } = response.data;
    
    localStorage.setItem('user_token', access_token);
    localStorage.setItem('username', returnedUsername);
    setUser({ username: returnedUsername });
    return response.data;
  };

  const register = async (username, password) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await api.post('/api/auth/register', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  };

  const logout = () => {
    localStorage.removeItem('user_token');
    localStorage.removeItem('username');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);