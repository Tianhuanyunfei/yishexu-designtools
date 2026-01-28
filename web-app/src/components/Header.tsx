import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Building2, User, Menu, X, LogOut } from 'lucide-react';

interface HeaderProps {
  toggleSidebar: () => void;
  sidebarVisible: boolean;
  user: { username: string } | null;
  onLogout: () => void;
}

const Header: React.FC<HeaderProps> = ({ toggleSidebar, sidebarVisible, user, onLogout }) => {
  const navigate = useNavigate();

  const handleLogout = () => {
    onLogout();
    navigate('/login');
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white shadow-brb-lg border-b border-gray-200">
      <div className="flex items-center justify-between px-6 py-4">
        <Link to="/" className="flex items-center space-x-4 hover:no-underline">
          <div className="flex items-center space-x-3">
            <Building2 className="h-8 w-8 text-brb-blue-600" />
            <div>
              <h1 className="text-xl font-bold text-gray-900 hover:text-brb-blue-600 transition-colors">阻尼器设计工具</h1>
              <p className="text-sm text-gray-600">专业的阻尼器辅助设计平台</p>
            </div>
          </div>
        </Link>
        
        <div className="flex items-center space-x-4">
          {user ? (
            <>
              <div className="flex items-center space-x-2 text-sm text-gray-600">
                <User className="h-4 w-4" />
                <span>{user.username}</span>
              </div>
              <div className="w-8 h-8 bg-brb-blue-600 rounded-full flex items-center justify-center">
                <span className="text-white text-sm font-semibold">{user.username.charAt(0).toUpperCase()}</span>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center space-x-1 px-3 py-1.5 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                <LogOut className="h-4 w-4" />
                <span>退出</span>
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="flex items-center space-x-1 px-3 py-1.5 text-sm text-gray-600 hover:text-brb-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
              >
                <User className="h-4 w-4" />
                <span>登录</span>
              </Link>
              <Link
                to="/register"
                className="px-4 py-1.5 text-sm text-white bg-brb-blue-600 hover:bg-brb-blue-700 rounded-lg transition-colors"
              >
                注册
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;