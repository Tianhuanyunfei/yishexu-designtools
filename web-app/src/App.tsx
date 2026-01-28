import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import BrbDesigner from './pages/BrbDesigner';
import BrbDrawing from './pages/BrbDrawing';
import BrbStabilityChecker from './pages/BrbStabilityChecker';
import VfdDesigner from './pages/VfdDesigner';
import VfdPeriodFrequencyCalculator from './pages/VfdPeriodFrequencyCalculator';
import DxfToCsvConverter from './pages/DxfToCsvConverter';
import CsvToDxfConverter from './pages/CsvToDxfConverter';
import CsvEditor from './pages/CsvEditor';
import Settings from './pages/Settings';
import Login from './pages/Login';
import Register from './pages/Register';
import './index.css';

interface User {
  userId: number;
  username: string;
  role: string;
  permissions: string[];
}

const PERMISSIONS: { [key: string]: string } = {
  'brb-designer': 'brb_designer',
  'brb-drawing': 'brb_drawing',
  'brb-stability': 'brb_stability',
  'vfd-designer': 'vfd_designer',
  'vfd-period-frequency': 'vfd_period',
  'dxf-to-csv': 'dxf_csv',
  'csv-to-dxf': 'csv_dxf',
  'csv-editor': 'csv_editor',
  'settings': 'settings'
};

function App() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const savedColor = localStorage.getItem('backgroundColor');
    if (savedColor) {
      document.body.style.backgroundColor = savedColor;
      
      const minHeightDivs = document.querySelectorAll('.min-h-screen');
      minHeightDivs.forEach((div) => {
        div.classList.remove('bg-gray-50');
        (div as HTMLElement).style.backgroundColor = savedColor;
      });
      
      const mainElement = document.querySelector('main');
      if (mainElement) {
        (mainElement as HTMLElement).style.backgroundColor = savedColor;
      }
      
      const mainDiv = document.querySelector('main > div');
      if (mainDiv) {
        (mainDiv as HTMLElement).style.backgroundColor = savedColor;
      }
      
      const cards = document.querySelectorAll('.card');
      cards.forEach((card) => {
        card.classList.remove('bg-white');
        (card as HTMLElement).style.backgroundColor = '#ffffff';
      });
      
      const dashboardContainers = document.querySelectorAll('.max-w-7xl.mx-auto');
      dashboardContainers.forEach((container) => {
        (container as HTMLElement).style.backgroundColor = savedColor;
      });
    }

    const savedUser = localStorage.getItem('user');
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('user');
        localStorage.removeItem('token');
      }
    }
  }, []);

  const handleLogin = (loggedInUser: User) => {
    setUser(loggedInUser);
  };

  const handleLogout = () => {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    setUser(null);
  };

  const AuthenticatedLayout = () => {
    if (!user) {
      return <Navigate to="/login" replace />;
    }
    return <Layout user={user} onLogout={handleLogout} />;
  };

  const ProtectedPage = ({ children }: { children: React.ReactNode }) => {
    const location = useLocation();
    
    if (!user) {
      return <Navigate to="/login" replace />;
    }

    const path = location.pathname.substring(1);
    const requiredPermission = PERMISSIONS[path];

    if (requiredPermission) {
      const isAdmin = user.role === 'admin';
      const hasPermission = isAdmin || (user.permissions && user.permissions.includes(requiredPermission));
      
      if (!hasPermission) {
        return (
          <div className="flex flex-col items-center justify-center h-64">
            <div className="bg-red-100 border border-red-400 text-red-700 px-8 py-6 rounded-lg shadow-md">
              <h2 className="text-xl font-bold mb-2">无权限访问</h2>
              <p className="mb-4">您没有权限访问此功能，请联系管理员开通权限。</p>
              <p className="text-sm text-gray-600">当前页面: {location.pathname}</p>
            </div>
            <a href="/" className="mt-4 text-blue-600 hover:text-blue-800 underline">
              返回主页
            </a>
          </div>
        );
      }
    }

    return <>{children}</>;
  };

  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/login" element={
          user ? <Navigate to="/" replace /> : <Login onLogin={handleLogin} />
        } />
        <Route path="/register" element={
          user ? <Navigate to="/" replace /> : <Register onRegister={handleLogin} />
        } />
        
        <Route path="/" element={<AuthenticatedLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="brb-designer" element={<ProtectedPage><BrbDesigner /></ProtectedPage>} />
          <Route path="brb-drawing" element={<ProtectedPage><BrbDrawing /></ProtectedPage>} />
          <Route path="brb-stability" element={<ProtectedPage><BrbStabilityChecker /></ProtectedPage>} />
          <Route path="vfd-designer" element={<ProtectedPage><VfdDesigner /></ProtectedPage>} />
          <Route path="vfd-period-frequency" element={<ProtectedPage><VfdPeriodFrequencyCalculator /></ProtectedPage>} />
          <Route path="dxf-to-csv" element={<ProtectedPage><DxfToCsvConverter /></ProtectedPage>} />
          <Route path="csv-to-dxf" element={<ProtectedPage><CsvToDxfConverter /></ProtectedPage>} />
          <Route path="csv-editor" element={<ProtectedPage><CsvEditor /></ProtectedPage>} />
          <Route path="settings" element={<ProtectedPage><Settings /></ProtectedPage>} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
