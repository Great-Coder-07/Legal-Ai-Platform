import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export const AuthScreen = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const { login, register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');

    try {
      if (isLogin) {
        await login(username, password);
        // Page view automatically flips via global context update
      } else {
        await register(username, password);
        setMessage('Registration successful! Please log in.');
        setIsLogin(true);
        setPassword('');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'An authentication error occurred.');
    }
  };

  return (
    <div style={{ maxWidth: '400px', margin: '100px auto', padding: '20px', border: '1px solid #ccc', borderRadius: '8px' }}>
      <h2>{isLogin ? 'Login to Legal AI' : 'Create Account'}</h2>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {message && <p style={{ color: 'green' }}>{message}</p>}
      
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px' }}>Username</label>
          <input 
            type="text" 
            value={username} 
            onChange={(e) => setUsername(e.target.value)} 
            required 
            style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
          />
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px' }}>Password</label>
          <input 
            type="password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            required 
            style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
          />
        </div>
        <button type="submit" style={{ width: '100%', padding: '10px', background: '#007bff', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          {isLogin ? 'Sign In' : 'Sign Up'}
        </button>
      </form>

      <p style={{ marginTop: '15px', textAlign: 'center' }}>
        {isLogin ? "Don't have an account? " : "Already have an account? "}
        <span 
          style={{ color: '#007bff', cursor: 'pointer', textDecoration: 'underline' }} 
          onClick={() => { setIsLogin(!isLogin); setError(''); setMessage(''); }}
        >
          {isLogin ? 'Register here' : 'Login here'}
        </span>
      </p>
    </div>
  );
};