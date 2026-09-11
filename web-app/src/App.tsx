import React, { type ReactElement } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import { useApplySavedBackgroundColor } from './hooks/useApplySavedBackgroundColor';
import Dashboard from './pages/Dashboard';
import BrbDrawing from './pages/BrbDrawing';
import BrbStabilityChecker from './pages/BrbStabilityChecker';
import BrbConnectorDrawing from './pages/BrbConnectorDrawing';
import VfdDesigner from './pages/VfdDesigner';
import VfdPeriodFrequencyCalculator from './pages/VfdPeriodFrequencyCalculator';
import DxfToCsvConverter from './pages/DxfToCsvConverter';
import CsvToDxfConverter from './pages/CsvToDxfConverter';
import CsvEditor from './pages/CsvEditor';
import TestFiles from './pages/TestFiles';
import ExcelEditor from './pages/ExcelEditor';
import ExcelDataEditor from './pages/ExcelDataEditor';
import WordEditor from './pages/WordEditor';
import Settings from './pages/Settings';
import Login from './pages/Login';
import Register from './pages/Register';
import { AuthProvider } from './context/AuthContext';
import './index.css';

function withProtectedLayout(page: ReactElement) {
  return (
    <ProtectedRoute>
      <Layout>{page}</Layout>
    </ProtectedRoute>
  );
}

function App() {
  useApplySavedBackgroundColor();

  return (
    <AuthProvider>
      <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          {/* 无需Layout的公共路由 */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* 需要 Layout 与登录校验的受保护路由 */}
          <Route path="/" element={withProtectedLayout(<Dashboard />)} />
          <Route path="/brb-drawing" element={withProtectedLayout(<BrbDrawing />)} />
          <Route path="/brb-connector-drawing" element={withProtectedLayout(<BrbConnectorDrawing />)} />
          <Route path="/brb-stability" element={withProtectedLayout(<BrbStabilityChecker />)} />
          <Route path="/vfd-designer" element={withProtectedLayout(<VfdDesigner />)} />
          <Route path="/vfd-period-frequency" element={withProtectedLayout(<VfdPeriodFrequencyCalculator />)} />
          <Route path="/test-files" element={withProtectedLayout(<TestFiles />)} />
          <Route path="/dxf-to-csv" element={withProtectedLayout(<DxfToCsvConverter />)} />
          <Route path="/csv-to-dxf" element={withProtectedLayout(<CsvToDxfConverter />)} />
          <Route path="/csv-editor" element={withProtectedLayout(<CsvEditor />)} />
          <Route path="/excel-editor" element={withProtectedLayout(<ExcelEditor />)} />
          <Route path="/excel-data-editor" element={withProtectedLayout(<ExcelDataEditor />)} />
          <Route path="/word-editor" element={withProtectedLayout(<WordEditor />)} />
          <Route path="/settings" element={withProtectedLayout(<Settings />)} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;