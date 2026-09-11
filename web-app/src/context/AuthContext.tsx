import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';

interface User {
  id: string;
  username: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; message: string }>;
  register: (username: string, password: string) => Promise<{ success: boolean; message: string }>;
  logout: () => void;
  verifyToken: () => Promise<boolean>;
  checkPermission: (permission: string) => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  // 从localStorage加载用户信息和令牌
  useEffect(() => {
    const loadUser = async () => {
      try {
        const storedToken = localStorage.getItem('token');
        const storedUser = localStorage.getItem('user');

        if (storedToken && storedUser) {
          setToken(storedToken);
          setUser(JSON.parse(storedUser));
          // 验证令牌是否有效
          const isValid = await verifyToken(storedToken);
          setIsAuthenticated(isValid);
        } else {
          setIsAuthenticated(false);
        }
      } catch (error) {
        console.error('加载用户信息失败:', error);
        // 清除无效的存储
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    loadUser();
  }, []);

  const login = async (username: string, password: string) => {
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (data.status === 'success') {
        setUser(data.user);
        setToken(data.access_token);
        setIsAuthenticated(true);
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        return { success: true, message: data.message };
      } else {
        setIsAuthenticated(false);
        return { success: false, message: data.message || '登录失败' };
      }
    } catch (error) {
      console.error('登录失败:', error);
      setIsAuthenticated(false);
      return { success: false, message: '网络错误，请稍后重试' };
    }
  };

  const register = async (username: string, password: string) => {
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (data.status === 'success') {
        setUser(data.user);
        setToken(data.access_token);
        setIsAuthenticated(true);
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        return { success: true, message: data.message };
      } else {
        setIsAuthenticated(false);
        return { success: false, message: data.message || '注册失败' };
      }
    } catch (error) {
      console.error('注册失败:', error);
      setIsAuthenticated(false);
      return { success: false, message: '网络错误，请稍后重试' };
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    setIsAuthenticated(false);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  };

  const verifyToken = async (storedToken?: string) => {
    try {
      const tokenToVerify = storedToken || token;
      if (!tokenToVerify) {
        setIsAuthenticated(false);
        return false;
      }

      const response = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token: tokenToVerify }),
      });

      const data = await response.json();

      if (data.status === 'success') {
        setIsAuthenticated(true);
        return true;
      } else {
        // 令牌无效，清除用户信息
        logout();
        return false;
      }
    } catch (error) {
      console.error('验证令牌失败:', error);
      logout();
      return false;
    }
  };

  const checkPermission = async (permission: string) => {
    try {
      if (!token) {
        return false;
      }

      const response = await fetch('/api/auth/check-permission', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token, permission }),
      });

      const data = await response.json();

      if (data.status === 'success') {
        return data.has_permission || false;
      } else {
        return false;
      }
    } catch (error) {
      console.error('检查权限失败:', error);
      return false;
    }
  };

  const value: AuthContextType = {
    user,
    token,
    isLoading,
    isAuthenticated,
    login,
    register,
    logout,
    verifyToken,
    checkPermission,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};