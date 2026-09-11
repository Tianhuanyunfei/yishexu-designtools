import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Toast } from '../components/Toast';

const Register: React.FC = () => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [toast, setToast] = useState<{ show: boolean; message: string; type: 'success' | 'error' }>({
    show: false,
    message: '',
    type: 'success',
  });

  const navigate = useNavigate();
  const { register, isAuthenticated } = useAuth();

  // 如果用户已经登录，重定向到首页
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // 表单验证
    if (!username || !password || !confirmPassword) {
      setToast({
        show: true,
        message: '请填写所有必填字段',
        type: 'error',
      });
      return;
    }

    if (password !== confirmPassword) {
      setToast({
        show: true,
        message: '两次输入的密码不一致',
        type: 'error',
      });
      return;
    }

    if (username.length < 2 || username.length > 20) {
      setToast({
        show: true,
        message: '用户名长度必须在2-20个字符之间',
        type: 'error',
      });
      return;
    }

    if (password.length < 6) {
      setToast({
        show: true,
        message: '密码长度必须至少为6个字符',
        type: 'error',
      });
      return;
    }

    setIsLoading(true);

    try {
      const result = await register(username, password);
      if (result.success) {
        setToast({
          show: true,
          message: result.message,
          type: 'success',
        });
        // 注册成功后重定向到首页
        setTimeout(() => {
          navigate('/');
        }, 1000);
      } else {
        setToast({
          show: true,
          message: result.message,
          type: 'error',
        });
      }
    } catch (error) {
      setToast({
        show: true,
        message: '注册失败，请稍后重试',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold text-center mb-6 text-gray-800">用户注册</h1>
        
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
              用户名
            </label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="请输入用户名（2-20个字符）"
              disabled={isLoading}
            />
          </div>

          <div className="mb-4">
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              密码
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="请输入密码（至少6个字符）"
              disabled={isLoading}
            />
          </div>

          <div className="mb-6">
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
              确认密码
            </label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="请再次输入密码"
              disabled={isLoading}
            />
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400 disabled:cursor-not-allowed"
            disabled={isLoading}
          >
            {isLoading ? '注册中...' : '注册'}
          </button>

          <div className="mt-4 text-center">
            <p className="text-gray-600">
              已有账号？
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="text-blue-600 hover:underline ml-1"
              >
                立即登录
              </button>
            </p>
          </div>
        </form>
      </div>

      {toast.show && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast({ ...toast, show: false })}
        />
      )}
    </div>
  );
};

export default Register;