import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Upload, Save, FileSpreadsheet, X, Download } from 'lucide-react';
import LuckyExcel from 'luckyexcel';
import * as XLSX from 'xlsx';
import './ExcelEditor.css';

declare global {
  interface Window {
    luckysheet: any;
  }
}

const ExcelDataEditor: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [sheetData, setSheetData] = useState<any[]>([]);
  const [luckySheetLoaded, setLuckySheetLoaded] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [fileName, setFileName] = useState<string>('');
  const [hasFile, setHasFile] = useState(false);

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

  // 初始化 Luckysheet
  const initLuckysheet = useCallback((data: any[]) => {
    console.log('初始化 Luckysheet, 数据:', data);

    if (!window.luckysheet) {
      console.error('Luckysheet 未加载');
      setError('编辑器未加载，请刷新页面重试');
      return;
    }
    // 确保容器元素存在
    const container = document.getElementById('luckysheet-data-container');
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
        container: 'luckysheet-data-container',
        title: fileName || '未命名',
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
  }, [fileName, isInitialized]);

  // 处理文件上传
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // 检查文件类型
    const validTypes = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'application/wps-office.xlsx',
      'application/wps-office.xls'
    ];

    if (!validTypes.includes(file.type) && !file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      setError('请上传 Excel 文件 (.xlsx 或 .xls)');
      return;
    }

    setFileName(file.name);
    setError(null);

    // 使用 LuckyExcel 转换文件
    LuckyExcel.transformExcelToLucky(file, (exportJson: any) => {
      console.log('Excel 转换成功:', exportJson);

      if (exportJson.sheets === undefined || exportJson.sheets.length === 0) {
        setError('读取文件失败：文件为空或格式不正确');
        return;
      }

      // 如果有已初始化的实例，先销毁
      if (isInitialized && window.luckysheet) {
        try {
          window.luckysheet.destroy();
          setIsInitialized(false);
        } catch (e) {
          console.log('销毁旧实例:', e);
        }
      }

      // 保存数据并标记为已加载
      setSheetData(exportJson.sheets);
      setDataLoaded(true);
      setHasFile(true);
    }, (error: any) => {
      console.error('转换 Excel 文件失败:', error);
      setError('转换 Excel 文件失败');
    });
  };

  // 创建新文件
  const handleNewFile = () => {
    // 先重置所有状态
    setDataLoaded(false);
    setIsInitialized(false);
    setSheetData([]);
    setError(null);

    // 如果有已初始化的实例，先销毁
    if (window.luckysheet) {
      try {
        window.luckysheet.destroy();
      } catch (e) {
        console.log('销毁旧实例:', e);
      }
    }

    setFileName('新建表格.xlsx');

    // 使用 setTimeout 确保状态更新和 DOM 清理完成后再创建新实例
    setTimeout(() => {
      // 创建空白表格数据
      const emptyData = [{
        name: 'Sheet1',
        color: '',
        status: 1,
        order: 0,
        celldata: [],
        config: {},
        index: 0
      }];

      setSheetData(emptyData);
      setHasFile(true);
      setDataLoaded(true);
    }, 100);
  };

  // 关闭当前文件
  const handleCloseFile = () => {
    // 先重置状态
    setDataLoaded(false);
    setIsInitialized(false);

    // 销毁 Luckysheet 实例
    if (window.luckysheet) {
      try {
        window.luckysheet.destroy();
      } catch (e) {
        console.log('销毁实例:', e);
      }
    }

    // 使用 setTimeout 确保 DOM 清理完成后再重置其他状态
    setTimeout(() => {
      setSheetData([]);
      setFileName('');
      setHasFile(false);
      setError(null);

      // 重置文件输入
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }, 50);
  };

  // 保存文件
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
        // 下载文件
        const downloadResponse = await fetch('/api/test-files/download', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ filename: fileName }),
        });

        if (downloadResponse.ok) {
          const blob = await downloadResponse.blob();
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = fileName;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
        }

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

  // 导出为Excel（前端直接导出）
  const handleExport = () => {
    if (!window.luckysheet) {
      alert('编辑器未初始化');
      return;
    }

    try {
      const allSheets = window.luckysheet.getAllSheets();

      // 创建工作簿
      const workbook = XLSX.utils.book_new();

      allSheets.forEach((sheet: any) => {
        // 将 Luckysheet 数据转换为二维数组
        const data: any[][] = [];
        const maxRow = sheet.data.length;
        const maxCol = Math.max(...sheet.data.map((row: any[]) => row.length));

        for (let r = 0; r < maxRow; r++) {
          const row: any[] = [];
          for (let c = 0; c < maxCol; c++) {
            const cell = sheet.data[r]?.[c];
            row.push(cell?.v || cell?.m || '');
          }
          data.push(row);
        }

        const worksheet = XLSX.utils.aoa_to_sheet(data);
        XLSX.utils.book_append_sheet(workbook, worksheet, sheet.name);
      });

      // 导出文件
      XLSX.writeFile(workbook, fileName || '导出文件.xlsx');
    } catch (err) {
      console.error('导出文件失败:', err);
      alert('导出文件失败');
    }
  };

  // 触发文件选择
  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* 页面标题 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center">
            <FileSpreadsheet className="inline-block mr-3 text-green-600" />
            Excel 数据编辑器
          </h1>
          <p className="mt-2 text-lg text-gray-600">
            上传、编辑和导出 Excel 文件
          </p>
        </div>

        {/* 工具栏 */}
        <div className="bg-white rounded-xl shadow-md p-4 mb-6 border border-gray-200">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              {/* 上传按钮 */}
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".xlsx,.xls"
                className="hidden"
              />
              <button
                onClick={triggerFileInput}
                className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-all duration-300"
              >
                <Upload className="mr-2 h-5 w-5" />
                上传 Excel
              </button>

              {/* 新建按钮 */}
              <button
                onClick={handleNewFile}
                className="flex items-center px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-all duration-300"
              >
                <FileSpreadsheet className="mr-2 h-5 w-5" />
                新建表格
              </button>

              {/* 保存按钮 */}
              {hasFile && (
                <>
                  <button
                    onClick={handleSave}
                    disabled={saving || !isInitialized}
                    className="flex items-center px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-all duration-300 disabled:opacity-50"
                  >
                    <Save className="mr-2 h-5 w-5" />
                    {saving ? '保存中...' : '保存到服务器'}
                  </button>

                  <button
                    onClick={handleExport}
                    disabled={!isInitialized}
                    className="flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-all duration-300 disabled:opacity-50"
                  >
                    <Download className="mr-2 h-5 w-5" />
                    导出 Excel
                  </button>

                  <button
                    onClick={handleCloseFile}
                    className="flex items-center px-4 py-2 bg-red-100 hover:bg-red-200 text-red-700 font-medium rounded-lg transition-all duration-300"
                  >
                    <X className="mr-2 h-5 w-5" />
                    关闭
                  </button>
                </>
              )}
            </div>

            {/* 文件名显示 */}
            {fileName && (
              <div className="text-lg font-semibold text-gray-700 bg-gray-100 px-4 py-2 rounded-lg">
                {fileName}
              </div>
            )}
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            <div className="flex items-center">
              <X className="h-5 w-5 mr-2" />
              {error}
            </div>
          </div>
        )}

        {/* 编辑器区域 */}
        <div className="bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden">
          {hasFile ? (
            <div className="excel-editor-wrapper">
              {/* Luckysheet 容器 */}
              <div
                ref={containerRef}
                id="luckysheet-data-container"
                className="luckysheet-container"
                style={{ height: '600px' }}
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
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-gray-500">
              <FileSpreadsheet className="h-20 w-20 mb-4 text-gray-300" />
              <p className="text-lg mb-2">请上传 Excel 文件或创建新表格</p>
              <p className="text-sm text-gray-400">支持 .xlsx 和 .xls 格式</p>
              <div className="mt-6 flex gap-4">
                <button
                  onClick={triggerFileInput}
                  className="flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-all duration-300"
                >
                  <Upload className="mr-2 h-5 w-5" />
                  上传文件
                </button>
                <button
                  onClick={handleNewFile}
                  className="flex items-center px-6 py-3 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-all duration-300"
                >
                  <FileSpreadsheet className="mr-2 h-5 w-5" />
                  新建表格
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 使用说明 */}
        <div className="mt-8 bg-blue-50 rounded-xl p-6 border border-blue-200">
          <h3 className="text-lg font-semibold text-blue-900 mb-3">使用说明</h3>
          <ul className="space-y-2 text-blue-800">
            <li className="flex items-start">
              <span className="mr-2">•</span>
              <span>点击"上传 Excel"按钮选择本地 Excel 文件进行编辑</span>
            </li>
            <li className="flex items-start">
              <span className="mr-2">•</span>
              <span>点击"新建表格"创建空白表格</span>
            </li>
            <li className="flex items-start">
              <span className="mr-2">•</span>
              <span>编辑完成后可选择"保存到服务器"或"导出 Excel"下载到本地</span>
            </li>
            <li className="flex items-start">
              <span className="mr-2">•</span>
              <span>支持多工作表、公式计算、单元格格式化等功能</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default ExcelDataEditor;
