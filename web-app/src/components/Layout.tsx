import React, { useState } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';

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
        <Sidebar visible={sidebarVisible} />
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