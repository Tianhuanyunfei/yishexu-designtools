import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Building2, User, Menu, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface HeaderProps {
  toggleSidebar: () => void;
  sidebarVisible: boolean;
}

const Header: React.FC<HeaderProps> = ({ toggleSidebar, sidebarVisible }) => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-12 bg-white shadow-brb border-b border-gray-200">
      <div className="flex h-full items-center justify-between px-4">
        <Link to="/" className="flex items-center space-x-2 hover:no-underline">
          <Building2 className="h-5 w-5 text-brb-blue-600 shrink-0" />
          <div className="leading-tight">
            <h1 className="text-base font-bold text-gray-900 hover:text-brb-blue-600 transition-colors">阻尼器设计工具</h1>
          </div>
        </Link>
        
        <div className="flex items-center space-x-3">
          {isAuthenticated ? (
            <div className="flex items-center space-x-3">
              <Link to="/settings" className="flex items-center space-x-1.5 text-sm text-gray-600 hover:text-brb-blue-600 transition-colors">
                <User className="h-3.5 w-3.5" />
                <span>{user?.username}</span>
              </Link>
              <div className="w-6 h-6 bg-brb-blue-600 rounded-full flex items-center justify-center">
                <span className="text-white text-xs font-semibold">{user?.username?.charAt(0) || '用'}</span>
              </div>
              <button
                onClick={handleLogout}
                className="px-2.5 py-0.5 bg-gray-200 text-gray-800 rounded-md text-xs hover:bg-gray-300 transition-colors"
              >
                退出登录
              </button>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <Link to="/login" className="px-2.5 py-0.5 bg-gray-200 text-gray-800 rounded-md text-xs hover:bg-gray-300 transition-colors">
                登录
              </Link>
              <Link to="/register" className="px-2.5 py-0.5 bg-brb-blue-600 text-white rounded-md text-xs hover:bg-brb-blue-700 transition-colors">
                注册
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;