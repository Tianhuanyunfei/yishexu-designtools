import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header';
import Sidebar from './Sidebar';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface UserInfo {
  username: string;
  role?: string;
  permissions?: string[];
}

interface LayoutProps {
  user: UserInfo | null;
  onLogout: () => void;
}

const Layout: React.FC<LayoutProps> = ({ user, onLogout }) => {
  const [sidebarVisible, setSidebarVisible] = useState(false);
  
  const toggleSidebar = () => {
    setSidebarVisible(!sidebarVisible);
  };

  const userPermissions = user?.permissions || [];
  const userRole = user?.role || 'user';

  return (
    <div className="min-h-screen bg-gray-50">
      <Header toggleSidebar={toggleSidebar} sidebarVisible={sidebarVisible} user={user} onLogout={onLogout} />
      <div className="flex">
        <Sidebar visible={sidebarVisible} toggleSidebar={toggleSidebar} userRole={userRole} userPermissions={userPermissions} />
        <button
          onClick={toggleSidebar}
          className={`fixed top-20 left-0 z-40 p-2 bg-white rounded-r-lg shadow-brb-lg hover:bg-gray-100 transition-all duration-300 ease-in-out transform ${sidebarVisible ? 'translate-x-64' : 'translate-x-0'} border border-l-0 border-gray-200`}
          aria-label={sidebarVisible ? '隐藏侧边栏' : '显示侧边栏'}
        >
          {sidebarVisible ? (
            <ChevronLeft className="h-5 w-5 text-gray-600" />
          ) : (
            <ChevronRight className="h-5 w-5 text-gray-600" />
          )}
        </button>
        <main className={`flex-1 min-h-screen pt-16 transition-all duration-300 ease-in-out ${sidebarVisible ? 'ml-64' : 'ml-0'}`}>
          <div className="p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;