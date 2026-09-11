import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Save, ArrowLeft } from 'lucide-react';
import LuckyExcel from 'luckyexcel';
import './ExcelEditor.css';

declare global {
  interface Window {
    luckysheet: any;
  }
}

const ExcelEditor: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const fileName = searchParams.get('file') || '';
  
  const containerRef = useRef<HTMLDivElement>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [sheetData, setSheetData] = useState<any[]>([]);
  const [luckySheetLoaded, setLuckySheetLoaded] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);

  // 检查 Luckysheet 是否加载
  useEffect(() => {
    console.log('检查 Luckysheet 加载状态...');
    const checkLuckysheet = setInterval(() => {
      if (window.luckysheet) {
        console.log('Luckysheet 已加载');
        clearInterval(checkLuckysheet);
        setLuckySheetLoaded(true);
      }
    }, 100);

    // 10秒超时
    const timeout = setTimeout(() => {
      clearInterval(checkLuckysheet);
      if (!window.luckysheet) {
        console.error('Luckysheet 加载超时');
        setError('编辑器加载超时，请刷新页面重试');
      }
    }, 10000);
    return () => {
      clearInterval(checkLuckysheet);
      clearTimeout(timeout);
    };
  }, []);
  // 加载 Excel 文件
  useEffect(() => {
    if (fileName) {
      loadExcelFile();
    }
  }, [fileName]);
  // 当 Luckysheet 加载完成且有数据时初始化
  useEffect(() => {
    console.log('状态检查:', { luckySheetLoaded, dataLoaded, sheetDataLength: sheetData.length, isInitialized });
    
    if (luckySheetLoaded && dataLoaded && sheetData.length > 0 && !isInitialized) {
      console.log('准备初始化 Luckysheet...');
      // 等待 DOM 更新
      const timer = setTimeout(() => {
        initLuckysheet(sheetData);
      }, 300);
      
      return () => clearTimeout(timer);
    }
  }, [luckySheetLoaded, dataLoaded, sheetData, isInitialized]);
  const loadExcelFile = async () => {
    console.log('开始加载 Excel 文件:', fileName);
    
    try {
      const response = await fetch('/api/test-files/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ filename: fileName }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || '下载文件失败');
      }
      const blob = await response.blob();
      console.log('文件下载成功，开始转换...');
      // 使用 LuckyExcel 直接转换 Excel 文件
      LuckyExcel.transformExcelToLucky(blob, (exportJson: any) => {
        console.log('Excel 转换成功:', exportJson);
        
        if (exportJson.sheets === undefined || exportJson.sheets.length === 0) {
          setError('读取文件失败：文件为空或格式不正确');
          return;
        }
        // 保存数据
        setSheetData(exportJson.sheets);
        setDataLoaded(true);
      }, (error: any) => {
        console.error('转换 Excel 文件失败:', error);
        setError('转换 Excel 文件失败');
      });
    } catch (err) {
      console.error('加载Excel文件失败:', err);
      setError(err instanceof Error ? err.message : '加载文件失败');
    }
  };
  const initLuckysheet = (data: any[]) => {
    console.log('初始化 Luckysheet, 数据:', data);
    
    if (!window.luckysheet) {
      console.error('Luckysheet 未加载');
      setError('编辑器未加载，请刷新页面重试');
      return;
    }
    // 确保容器元素存在
    const container = document.getElementById('luckysheet-container');
    if (!container) {
      console.error('容器元素不存在');
      setError('容器元素不存在，请刷新页面重试');
      return;
    }
    try {
      // 销毁之前的实例
      if (isInitialized) {
        try {
          window.luckysheet.destroy();
        } catch (e) {
          console.log('销毁旧实例:', e);
        }
      }
      console.log('创建 Luckysheet 实例...');
      window.luckysheet.create({
        container: 'luckysheet-container',
        title: fileName,
        lang: 'zh',
        showinfobar: false,
        showsheetbar: true,
        showstatisticBar: true,
        sheetFormulaBar: true,
        enableAddRow: true,
        enableAddBackTop: true,
        userInfo: false,
        showConfigWindowResize: true,
        forceCalculation: false,
        rowHeaderWidth: 46,
        columnHeaderHeight: 25,
        defaultColWidth: 73,
        defaultRowHeight: 19,
        data: data
      });
      
      console.log('Luckysheet 初始化成功');
      setIsInitialized(true);
    } catch (err) {
      console.error('初始化 Luckysheet 失败:', err);
      setError('初始化编辑器失败: ' + (err instanceof Error ? err.message : String(err)));
    }
  };
  const handleSave = async () => {
    if (!window.luckysheet) {
      alert('编辑器未初始化');
      return;
    }
    setSaving(true);
    try {
      // 获取所有工作表数据
      const allSheets = window.luckysheet.getAllSheets();
      
      // 调用后端API导出Excel
      const response = await fetch('/api/test-files/export-excel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename: fileName,
          sheets: allSheets
        }),
      });
      
      const result = await response.json();
      
      if (result.status === 'success') {
        alert('文件保存成功');
      } else {
        throw new Error(result.message || '保存失败');
      }
    } catch (err) {
      console.error('保存文件失败:', err);
      alert(err instanceof Error ? err.message : '保存文件失败');
    } finally {
      setSaving(false);
    }
  };
  const handleBack = () => {
    // 销毁 Luckysheet 实例
    if (window.luckysheet && isInitialized) {
      try {
        window.luckysheet.destroy();
      } catch (err) {
        console.error('销毁 Luckysheet 失败:', err);
      }
    }
    navigate(-1);
  };
  if (error) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-600 mb-4">{error}</div>
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            返回
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="excel-editor-container">
      {/* 顶部工具栏 */}
      <div className="excel-toolbar">
        <div className="flex items-center space-x-4">
          <button
            onClick={handleBack}
            className="flex items-center space-x-2 px-3 py-2 text-gray-600 hover:text-gray-800 transition-colors"
          >
            <ArrowLeft size={20} />
            <span>返回</span>
          </button>
          <div className="text-lg font-semibold text-gray-900">
            {fileName}
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !isInitialized}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          <Save size={18} />
          <span>{saving ? '保存中...' : '保存'}</span>
        </button>
      </div>
      {/* Luckysheet 容器 */}
      <div 
        ref={containerRef}
        id="luckysheet-container" 
        className="luckysheet-container"
      >
        {!isInitialized && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <div className="text-gray-600">初始化编辑器...</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
export default ExcelEditor;