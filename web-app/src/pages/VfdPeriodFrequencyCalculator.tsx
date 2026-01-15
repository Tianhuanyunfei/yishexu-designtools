import React, { useState } from 'react';
import { Calculator, Table, Download, RefreshCw, Trash2, XCircle } from 'lucide-react';
import * as XLSX from 'xlsx';

const VfdPeriodFrequencyCalculator: React.FC = () => {
  // 计算参数状态
  const [parameters, setParameters] = useState({
    maxForce: '',
    dampingCoefficient: '',
    dampingExponent: '',
    designDisplacement: ''
  });

  // 单位切换状态 (true: 使用标准单位, false: 使用公制小单位)
  const [useStandardUnits, setUseStandardUnits] = useState(false);

  // 计算结果状态
  const [results, setResults] = useState<{[key: string]: string | boolean}>({});

  // 从localStorage读取历史记录
  const loadHistory = (): {[key: string]: string | boolean}[] => {
    const saved = localStorage.getItem('vfdCalculatorHistory');
    return saved ? JSON.parse(saved) : [];
  };

  // 将历史记录保存到localStorage
  const saveHistory = (historyData: {[key: string]: string | boolean}[]) => {
    localStorage.setItem('vfdCalculatorHistory', JSON.stringify(historyData));
  };

  // 计算历史记录（从localStorage初始化）
  const [history, setHistory] = useState<{[key: string]: string | boolean}[]>(loadHistory);

  // 处理参数输入变化
  const handleParameterChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setParameters(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // 执行计算
  const calculate = () => {
    const { maxForce, dampingCoefficient, dampingExponent, designDisplacement } = parameters;
    
    // 验证输入
    if (!maxForce || !dampingCoefficient || !dampingExponent || !designDisplacement) {
      alert('请输入所有参数');
      return;
    }

    // 将输入参数转换为数值，使用更具描述性的变量名
    const force = parseFloat(maxForce);
    const coeff = parseFloat(dampingCoefficient);
    const exponent = parseFloat(dampingExponent);
    const disp = parseFloat(designDisplacement);

    // 直接使用输入的单位进行计算
    // 根据黏滞阻尼器公式 F = C * v^α，求解 v
    const velocity = Math.pow(force / coeff, 1 / exponent);
    
    // 计算相关周期频率参数（使用用户指定的公式）
    const PI = 3.14;
    
    // 所有中间计算都使用精确的浮点值，不进行四舍五入
    const angularVelocity = velocity / disp; // W = V / d
    const period = (2 * PI) / angularVelocity; // T = 2×3.14 / W
    const frequency = 1 / period; // f = 1 / T

    // 只在最终结果展示时进行四舍五入到三位小数
    const newResults = {
      maxForce: maxForce,
      dampingCoefficient: dampingCoefficient,
      dampingExponent: dampingExponent,
      designDisplacement: designDisplacement,
      velocity: velocity.toFixed(3),
      angularVelocity: angularVelocity.toFixed(3),
      period: period.toFixed(3),
      frequency: frequency.toFixed(3),
      useStandardUnits: useStandardUnits // 保存单位信息
    };

    setResults(newResults);
    setHistory(prev => {
      const updatedHistory = [...prev, newResults];
      saveHistory(updatedHistory);
      return updatedHistory;
    });
  };

  // 清除输入和结果
  const clearAll = () => {
    setParameters({ maxForce: '', dampingCoefficient: '', dampingExponent: '', designDisplacement: '' });
    setResults({});
  };

  // 删除单个历史记录
  const deleteHistoryRecord = (index: number) => {
    setHistory(prev => {
      const updatedHistory = prev.filter((_, i) => i !== index);
      saveHistory(updatedHistory);
      return updatedHistory;
    });
  };

  // 清空所有历史记录
  const clearAllHistory = () => {
    setHistory([]);
    saveHistory([]);
  };

  // 导出计算结果为Excel
  const exportToExcel = () => {
    if (history.length === 0) return;

    // 创建数据数组，按照用户要求的格式组织
    let data: any[] = [];
    history.forEach((result, index) => {
      // 第1行：记录标题和表头
      data.push([
        `记录 ${index + 1}`,
        '最大阻尼力(KN)',
        `阻尼系数(${result.useStandardUnits ? 'KN/(m/s)α' : 'KN/(mm/s)α'})`,
        '阻尼指数(α)',
        `设计位移(${result.useStandardUnits ? 'm' : 'mm'})`,
        `速度V(${result.useStandardUnits ? 'm/s' : 'mm/s'})`,
        '角速度W(弧度/s)',
        '周期T(s)',
        '频率f(Hz)'
      ]);
      
      // 第2行：型号和数据
      data.push([
        `型号: VFD-${String(result.maxForce)}-${result.useStandardUnits ? (parseFloat(String(result.designDisplacement)) * 1000).toString() : String(result.designDisplacement)}`,
        result.maxForce,
        result.dampingCoefficient,
        result.dampingExponent,
        result.designDisplacement,
        result.velocity,
        result.angularVelocity,
        result.period,
        result.frequency
      ]);
      
      // 记录间不使用空行分隔
    });

    // 创建Workbook和Worksheet
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.aoa_to_sheet(data);

    // 设置列宽
    const columnWidths = [
      { wch: 15 }, // 记录/型号
      { wch: 12 }, // 最大阻尼力
      { wch: 20 }, // 阻尼系数
      { wch: 12 }, // 阻尼指数
      { wch: 12 }, // 设计位移
      { wch: 12 }, // 速度V
      { wch: 15 }, // 角速度W
      { wch: 10 }, // 周期T
      { wch: 10 }  // 频率f
    ];
    worksheet['!cols'] = columnWidths;

    // 设置边框样式
    const borderStyle = {
      top: { style: 'thin' },
      bottom: { style: 'thin' },
      left: { style: 'thin' },
      right: { style: 'thin' }
    };

    // 为每个记录设置样式
    history.forEach((_, index) => {
      // 计算当前记录的起始行号（每条记录占2行，无空行分隔）
      const recordStartRow = index * 2;
      
      // 设置记录标题单元格样式（第1列，第1行）
      const titleCellRef = XLSX.utils.encode_cell({ r: recordStartRow, c: 0 });
      if (worksheet[titleCellRef]) {
        worksheet[titleCellRef].s = {
          font: { bold: true, size: 12 },
          border: borderStyle,
          fill: { bgColor: { rgb: 'CCCCCC' } },
          alignment: { horizontal: 'center', vertical: 'center' }
        };
      }
      
      // 设置表头样式（第2-9列，第1行）
      for (let col = 1; col < 9; col++) {
        const headerCellRef = XLSX.utils.encode_cell({ r: recordStartRow, c: col });
        if (worksheet[headerCellRef]) {
          worksheet[headerCellRef].s = {
            font: { bold: true, size: 11 },
            border: borderStyle,
            fill: { bgColor: { rgb: 'F2F2F2' } },
            alignment: { horizontal: 'center', vertical: 'center' }
          };
        }
      }
      
      // 设置型号单元格样式（第1列，第2行）
      const modelCellRef = XLSX.utils.encode_cell({ r: recordStartRow + 1, c: 0 });
      if (worksheet[modelCellRef]) {
        worksheet[modelCellRef].s = {
          font: { bold: true, size: 11, color: { rgb: '0000FF' } },
          border: borderStyle,
          fill: { bgColor: { rgb: 'E6F2FF' } },
          alignment: { horizontal: 'left', vertical: 'center' }
        };
      }
      
      // 设置数据单元格样式（第2-9列，第2行）
      for (let col = 1; col < 9; col++) {
        const dataCellRef = XLSX.utils.encode_cell({ r: recordStartRow + 1, c: col });
        if (worksheet[dataCellRef]) {
          worksheet[dataCellRef].s = {
            font: { size: 11 },
            border: borderStyle,
            alignment: { horizontal: 'right', vertical: 'center' }
          };
        }
      }
    });

    // 添加Worksheet到Workbook
    XLSX.utils.book_append_sheet(workbook, worksheet, '计算记录');

    // 导出Excel文件
    XLSX.writeFile(workbook, `VFD频率计算_${new Date().toISOString().slice(0, 10)}.xlsx`);
  };

  // 导出单个计算记录
  const exportSingleRecord = (record: {[key: string]: string | boolean}, recordNumber: number) => {
    // 创建数据数组，与批量导出保持一致的格式
    const data = [
      // 第1行：记录标题和表头
      [
        `记录 ${recordNumber}`,
        '最大阻尼力(KN)',
        `阻尼系数(${record.useStandardUnits ? 'KN/(m/s)α' : 'KN/(mm/s)α'})`,
        '阻尼指数(α)',
        `设计位移(${record.useStandardUnits ? 'm' : 'mm'})`,
        `速度V(${record.useStandardUnits ? 'm/s' : 'mm/s'})`,
        '角速度W(弧度/s)',
        '周期T(s)',
        '频率f(Hz)'
      ],
      // 第2行：型号和数据
      [
        `型号: VFD-${String(record.maxForce)}-${record.useStandardUnits ? (parseFloat(String(record.designDisplacement)) * 1000).toString() : String(record.designDisplacement)}`,
        record.maxForce,
        record.dampingCoefficient,
        record.dampingExponent,
        record.designDisplacement,
        record.velocity,
        record.angularVelocity,
        record.period,
        record.frequency
      ]
    ];

    // 创建Workbook和Worksheet
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.aoa_to_sheet(data);

    // 设置列宽，与批量导出保持一致
    const columnWidths = [
      { wch: 15 }, // 记录/型号
      { wch: 12 }, // 最大阻尼力
      { wch: 20 }, // 阻尼系数
      { wch: 12 }, // 阻尼指数
      { wch: 12 }, // 设计位移
      { wch: 12 }, // 速度V
      { wch: 15 }, // 角速度W
      { wch: 10 }, // 周期T
      { wch: 10 }  // 频率f
    ];
    worksheet['!cols'] = columnWidths;

    // 设置边框样式
    const borderStyle = {
      top: { style: 'thin' },
      bottom: { style: 'thin' },
      left: { style: 'thin' },
      right: { style: 'thin' }
    };

    // 设置记录标题单元格样式（第1列，第1行）
    const titleCellRef = XLSX.utils.encode_cell({ r: 0, c: 0 });
    if (worksheet[titleCellRef]) {
      worksheet[titleCellRef].s = {
        font: { bold: true, size: 12 },
        border: borderStyle,
        fill: { bgColor: { rgb: 'CCCCCC' } },
        alignment: { horizontal: 'center', vertical: 'center' }
      };
    }
    
    // 设置表头样式（第2-9列，第1行）
    for (let col = 1; col < 9; col++) {
      const headerCellRef = XLSX.utils.encode_cell({ r: 0, c: col });
      if (worksheet[headerCellRef]) {
        worksheet[headerCellRef].s = {
          font: { bold: true, size: 11 },
          border: borderStyle,
          fill: { bgColor: { rgb: 'F2F2F2' } },
          alignment: { horizontal: 'center', vertical: 'center' }
        };
      }
    }
    
    // 设置型号单元格样式（第1列，第2行）
    const modelCellRef = XLSX.utils.encode_cell({ r: 1, c: 0 });
    if (worksheet[modelCellRef]) {
      worksheet[modelCellRef].s = {
        font: { bold: true, size: 11, color: { rgb: '0000FF' } },
        border: borderStyle,
        fill: { bgColor: { rgb: 'E6F2FF' } },
        alignment: { horizontal: 'left', vertical: 'center' }
      };
    }
    
    // 设置数据单元格样式（第2-9列，第2行）
    for (let col = 1; col < 9; col++) {
      const dataCellRef = XLSX.utils.encode_cell({ r: 1, c: col });
      if (worksheet[dataCellRef]) {
        worksheet[dataCellRef].s = {
          font: { size: 11 },
          border: borderStyle,
          alignment: { horizontal: 'right', vertical: 'center' }
        };
      }
    }

    // 添加Worksheet到Workbook
    XLSX.utils.book_append_sheet(workbook, worksheet, '计算记录');

    // 导出Excel文件
    XLSX.writeFile(workbook, `VFD频率计算_记录${recordNumber}_${new Date().toISOString().slice(0, 10)}.xlsx`);
  };

  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* 页面标题 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            <Calculator className="inline-block mr-3" />
            VFD频率计算
          </h1>
          <p className="mt-2 text-lg text-gray-600">
            用于计算黏滞阻尼器的周期频率相关参数
          </p>
        </div>

        {/* 左右布局容器 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
          {/* 左边：计算参数区域 */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-900">计算参数</h2>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-600">单位：</span>
                <button
                  onClick={() => setUseStandardUnits(!useStandardUnits)}
                  className="px-4 py-2 bg-brb-blue-100 hover:bg-brb-blue-200 text-brb-blue-700 font-medium rounded-lg transition-all duration-300 text-sm"
                >
                  {useStandardUnits ? 'm' : 'mm'}
                </button>
              </div>
            </div>
            <div className="space-y-6">
              <div className="space-y-2">
                <label htmlFor="maxForce" className="block text-sm font-medium text-gray-700">最大阻尼力 F (KN)</label>
                <input
                  type="number"
                  id="maxForce"
                  name="maxForce"
                  value={parameters.maxForce}
                  onChange={handleParameterChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="请输入最大阻尼力"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="dampingCoefficient" className="block text-sm font-medium text-gray-700">
                  阻尼系数 C ({useStandardUnits ? 'KN/(m/s)α' : 'KN/(mm/s)α'})
                </label>
                <input
                  type="number"
                  id="dampingCoefficient"
                  name="dampingCoefficient"
                  value={parameters.dampingCoefficient}
                  onChange={handleParameterChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="请输入阻尼系数"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="dampingExponent" className="block text-sm font-medium text-gray-700">阻尼指数 ɑ</label>
                <input
                  type="number"
                  id="dampingExponent"
                  name="dampingExponent"
                  value={parameters.dampingExponent}
                  onChange={handleParameterChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="请输入阻尼指数"
                  step="0.1"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="designDisplacement" className="block text-sm font-medium text-gray-700">
                  设计位移 d ({useStandardUnits ? 'm' : 'mm'})
                </label>
                <input
                  type="number"
                  id="designDisplacement"
                  name="designDisplacement"
                  value={parameters.designDisplacement}
                  onChange={handleParameterChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="请输入设计位移"
                />
              </div>

              {/* 计算按钮区域 */}
              <div className="pt-4 flex flex-col sm:flex-row gap-4">
                <button
                  onClick={calculate}
                  className="flex items-center justify-center px-6 py-3 bg-brb-blue-600 hover:bg-brb-blue-700 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all duration-300 flex-1"
                >
                  <Calculator className="mr-2 h-5 w-5" />
                  执行计算
                </button>
                <button
                  onClick={clearAll}
                  className="flex items-center justify-center px-6 py-3 bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium rounded-lg transition-all duration-300 flex-1"
                >
                  <RefreshCw className="mr-2 h-5 w-5" />
                  清空参数
                </button>
              </div>
            </div>
          </div>

          {/* 右边：计算结果区域 */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">计算结果</h2>
            <div className="space-y-5">
              <div className="bg-blue-50 p-5 rounded-lg flex items-center justify-between min-h-[74px]">
                <div className="text-lg text-gray-600">速度 V</div>
                <div className="flex items-center space-x-2">
                  <div className="text-2xl font-bold text-blue-600">{results.velocity || '---'}</div>
                  <div className="text-sm text-gray-500">{useStandardUnits ? 'm/s' : 'mm/s'}</div>
                </div>
              </div>
              <div className="bg-blue-50 p-5 rounded-lg flex items-center justify-between min-h-[74px]">
                <div className="text-lg text-gray-600">角速度 W</div>
                <div className="flex items-center space-x-2">
                  <div className="text-2xl font-bold text-blue-600">{results.angularVelocity || '---'}</div>
                  <div className="text-sm text-gray-500">弧度/s</div>
                </div>
              </div>
              <div className="bg-green-50 p-5 rounded-lg flex items-center justify-between min-h-[74px]">
                <div className="text-lg text-gray-600">周期 T</div>
                <div className="flex items-center space-x-2">
                  <div className="text-2xl font-bold text-green-600">{results.period || '---'}</div>
                  <div className="text-sm text-gray-500">s</div>
                </div>
              </div>
              <div className="bg-green-50 p-5 rounded-lg flex items-center justify-between min-h-[74px]">
                <div className="text-lg text-gray-600">频率 f</div>
                <div className="flex items-center space-x-2">
                  <div className="text-2xl font-bold text-green-600">{results.frequency || '---'}</div>
                  <div className="text-sm text-gray-500">Hz</div>
                </div>
              </div>
              
              {/* 计算公式区域 */}
              <div className="bg-gray-50 p-5 rounded-lg border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-800 mb-3">计算公式</h3>
                <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-gray-700">
                  <div>• F = C·V^α</div>
                  <div>• W = V / d</div>
                  <div>• T = 2×3.14 / W</div>
                  <div>• f = 1 / T</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 计算历史记录区域 */}
        {history.length > 0 && (
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <div className="flex flex-wrap justify-between items-center mb-4 gap-4">
              <h2 className="text-xl font-semibold text-gray-900">计算历史记录</h2>
              <div className="flex gap-3">
                <button
                  onClick={exportToExcel}
                  className="flex items-center px-4 py-2 bg-green-500 hover:bg-green-600 text-white font-medium rounded-lg transition-all duration-300"
                >
                  <Download className="mr-2 h-5 w-5" />
                  导出所有
                </button>
                <button
                  onClick={clearAllHistory}
                  className="flex items-center px-4 py-2 bg-red-500 hover:bg-red-600 text-white font-medium rounded-lg transition-all duration-300"
                >
                  <Trash2 className="mr-2 h-5 w-5" />
                  清空所有
                </button>
              </div>
            </div>
            <div className="space-y-4">
              {history.map((record, index) => (
                <div key={index} className="bg-white rounded-lg border border-gray-300 overflow-hidden">
                  <div className="flex">
                    {/* 记录标识（左侧） */}
                    <div className="bg-gray-200 border-r border-gray-300 p-4 flex flex-col items-center justify-center">
                      <div className="text-lg font-bold text-gray-700">记录 {index + 1}</div>
                      <div className="text-xs text-gray-500 mt-1">编号</div>
                    </div>
                    
                    {/* 主要内容区域 */}
                    <div className="flex-1 p-4">
                      {/* 型号信息 */}
                      <div className="flex items-center justify-between mb-4">
                        <div className="p-2 bg-blue-50 border border-blue-200 rounded-lg">
                          <div className="flex items-center">
                            <span className="text-sm font-medium text-blue-800 mr-2">型号:</span>
                            <span className="text-sm font-semibold text-blue-900">
                                VFD-{String(record.maxForce)}-{record.useStandardUnits ? (parseFloat(String(record.designDisplacement)) * 1000).toString() : String(record.designDisplacement)}
                              </span>
                          </div>
                        </div>
                        
                        {/* 操作按钮 */}
                        <div className="flex gap-2">
                          <button
                            onClick={() => exportSingleRecord(record, index + 1)}
                            className="flex items-center px-3 py-1 bg-green-100 hover:bg-green-200 text-green-600 hover:text-green-800 font-medium rounded-lg transition-all duration-300 text-xs"
                            title="导出记录"
                          >
                            <Download className="h-4 w-4 mr-1" />
                            导出
                          </button>
                          <button
                            onClick={() => deleteHistoryRecord(index)}
                            className="flex items-center px-3 py-1 bg-red-100 hover:bg-red-200 text-red-600 hover:text-red-800 font-medium rounded-lg transition-all duration-300 text-xs"
                            title="删除记录"
                          >
                            <XCircle className="h-4 w-4 mr-1" />
                            删除
                          </button>
                        </div>
                      </div>
                      
                      {/* 参数和结果区域 */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* 计算参数（表格样式） */}
                        <div className="border border-gray-300 rounded-lg overflow-hidden">
                          <div className="bg-gray-100 px-3 py-2 border-b border-gray-300">
                            <h4 className="text-sm font-medium text-gray-800">
                              计算参数
                            </h4>
                          </div>
                          <div className="divide-y divide-gray-300">
                            <div className="flex items-center px-3 py-2">
                              <span className="text-sm text-gray-600 flex-1">最大阻尼力 F:</span>
                              <div className="flex items-center justify-end flex-1">
                                <span className="text-sm font-medium text-gray-900 flex-1 text-center">{record.maxForce}</span>
                                <span className="text-sm text-gray-500 flex-1 text-right">(KN)</span>
                              </div>
                            </div>
                            <div className="flex items-center px-3 py-2">
                              <span className="text-sm text-gray-600 flex-1">阻尼系数 C:</span>
                              <div className="flex items-center justify-end flex-1">
                                <span className="text-sm font-medium text-gray-900 flex-1 text-center">{record.dampingCoefficient}</span>
                                <span className="text-sm text-gray-500 flex-1 text-right">({record.useStandardUnits ? 'KN/(m/s)α' : 'KN/(mm/s)α'})</span>
                              </div>
                            </div>
                            <div className="flex items-center px-3 py-2">
                              <span className="text-sm text-gray-600 flex-1">阻尼指数 ɑ:</span>
                              <div className="flex items-center justify-end flex-1">
                                <span className="text-sm font-medium text-gray-900 flex-1 text-center">{record.dampingExponent}</span>
                                <span className="text-sm flex-1"></span> {/* 空单位占位符，保持布局一致 */}
                              </div>
                            </div>
                            <div className="flex items-center px-3 py-2">
                              <span className="text-sm text-gray-600 flex-1">设计位移 d:</span>
                              <div className="flex items-center justify-end flex-1">
                                <span className="text-sm font-medium text-gray-900 flex-1 text-center">{record.designDisplacement}</span>
                                <span className="text-sm text-gray-500 flex-1 text-right">({record.useStandardUnits ? 'm' : 'mm'})</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        {/* 计算结果（表格样式） */}
                        <div className="border border-gray-300 rounded-lg overflow-hidden">
                          <div className="bg-gray-100 px-3 py-2 border-b border-gray-300">
                            <h4 className="text-sm font-medium text-gray-800">
                              计算结果
                            </h4>
                          </div>
                          <div className="divide-y divide-gray-300">
                            <div className="flex items-center px-3 py-2">
                              <span className="text-sm text-gray-600 flex-1">速度 V:</span>
                              <div className="flex items-center justify-end flex-1">
                                <span className="text-sm font-medium text-gray-900 flex-1 text-center">{record.velocity}</span>
                                <span className="text-sm text-gray-500 flex-1 text-right">({record.useStandardUnits ? 'm/s' : 'mm/s'})</span>
                              </div>
                            </div>
                            <div className="flex items-center px-3 py-2">
                              <span className="text-sm text-gray-600 flex-1">角速度 W:</span>
                              <div className="flex items-center justify-end flex-1">
                                <span className="text-sm font-medium text-gray-900 flex-1 text-center">{record.angularVelocity}</span>
                                <span className="text-sm text-gray-500 flex-1 text-right">(弧度/s)</span>
                              </div>
                            </div>
                            <div className="flex items-center px-3 py-2">
                              <span className="text-sm text-gray-600 flex-1">周期 T:</span>
                              <div className="flex items-center justify-end flex-1">
                                <span className="text-sm font-medium text-gray-900 flex-1 text-center">{record.period}</span>
                                <span className="text-sm text-gray-500 flex-1 text-right">(s)</span>
                              </div>
                            </div>
                            <div className="flex items-center px-3 py-2">
                              <span className="text-sm text-gray-600 flex-1">频率 f:</span>
                              <div className="flex items-center justify-end flex-1">
                                <span className="text-sm font-medium text-gray-900 flex-1 text-center">{record.frequency}</span>
                                <span className="text-sm text-gray-500 flex-1 text-right">(Hz)</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default VfdPeriodFrequencyCalculator;