import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
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
import ProtectedRoute from './components/ProtectedRoute';
import './index.css';

interface User {
  userId: number;
  username: string;
}

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

  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/login" element={
          user ? <Navigate to="/" replace /> : <Login onLogin={handleLogin} />
        } />
        <Route path="/register" element={
          user ? <Navigate to="/" replace /> : <Register onRegister={handleLogin} />
        } />
        
        <Route element={<ProtectedRoute isAuthenticated={!!user} />}>
          <Route path="/" element={<Layout user={user} onLogout={handleLogout} />}>
            <Route index element={<Dashboard />} />
            <Route path="brb-designer" element={<BrbDesigner />} />
            <Route path="brb-drawing" element={<BrbDrawing />} />
            <Route path="brb-stability" element={<BrbStabilityChecker />} />
            <Route path="vfd-designer" element={<VfdDesigner />} />
            <Route path="vfd-period-frequency" element={<VfdPeriodFrequencyCalculator />} />
            <Route path="dxf-to-csv" element={<DxfToCsvConverter />} />
            <Route path="csv-to-dxf" element={<CsvToDxfConverter />} />
            <Route path="csv-editor" element={<CsvEditor />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Route>
      </Routes>
    </Router>
  );
}

export default App;