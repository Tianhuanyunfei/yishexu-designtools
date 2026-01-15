import React, { useState } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  // 侧边栏显示状态，默认为显示
  const [sidebarVisible, setSidebarVisible] = useState(true);
  
  // 切换侧边栏显示/隐藏
  const toggleSidebar = () => {
    setSidebarVisible(!sidebarVisible);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header toggleSidebar={toggleSidebar} sidebarVisible={sidebarVisible} />
      <div className="flex">
        {/* 侧边栏，根据状态显示/隐藏 */}
        <Sidebar visible={sidebarVisible} toggleSidebar={toggleSidebar} />
        {/* 侧边栏折叠按钮，位于侧边栏外侧 */}
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
        {/* 主内容区域，根据侧边栏状态调整左侧边距 */}
        <main className={`flex-1 min-h-screen pt-16 transition-all duration-300 ease-in-out ${sidebarVisible ? 'ml-64' : 'ml-0'}`}>
          <div className="p-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;