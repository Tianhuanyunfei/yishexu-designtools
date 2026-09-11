import React, { useState } from 'react';
import { Save, FolderOpen, Plus, ChevronDown, ChevronUp, Download } from 'lucide-react';
import * as XLSX from 'xlsx';

interface ParameterRow {
  id: string;
  编号: string;
  水平长L1: string;
  竖直长L2: string;
  厚2: string;
  长B1: string;
  宽: string;
  厚3: string;
  长B2: string;
  宽2: string;
  厚4: string;
  长B3: string;
  宽3: string;
  厚5: string;
  长A1: string;
  宽4: string;
  厚6: string;
  长A2: string;
  宽5: string;
  厚7: string;
  方向: string;
  预览: string;
}

interface ParameterTable {
  id: string;
  type: 'large' | 'small';
  rows: ParameterRow[];
}

const BrbConnectorDrawing: React.FC = () => {
  const [projectName, setProjectName] = useState('');
  const [parameterTables, setParameterTables] = useState<ParameterTable[]>([
    {
      id: '1',
      type: 'large',
      rows: [
        {
          id: Date.now().toString(),
          编号: '',
          水平长L1: '',
          竖直长L2: '',
          厚2: '',
          长B1: '',
          宽: '',
          厚3: '',
          长B2: '',
          宽2: '',
          厚4: '',
          长B3: '',
          宽3: '',
          厚5: '',
          长A1: '',
          宽4: '',
          厚6: '',
          长A2: '',
          宽5: '',
          厚7: '',
          方向: '上',
          预览: '',
        },
      ],
    },
  ]);

  const handleNewProject = () => {
    setProjectName('');
    const defaultType: 'large' | 'small' = 'large';
    setParameterTables([
      {
        id: '1',
        type: defaultType,
        rows: [
          {
            id: Date.now().toString(),
            编号: '',
            水平长L1: '',
            竖直长L2: '',
            厚2: '',
            长B1: '',
            宽: '',
            厚3: '',
            长B2: '',
            宽2: '',
            厚4: '',
            长B3: '',
            宽3: '',
            厚5: '',
            长A1: '',
            宽4: '',
            厚6: '',
            长A2: '',
            宽5: '',
            厚7: '',
            方向: '上',
            预览: '',
          },
        ],
      },
    ]);
  };

  const handleOpenProject = () => {
    // 创建文件选择器
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.xlsx, .xls';
    
    // 处理文件选择
    input.onchange = (e) => {
      const target = e.target as HTMLInputElement;
      const file = target.files?.[0];
      
      if (file) {
        const reader = new FileReader();
        
        reader.onload = (e) => {
          try {
            const data = e.target?.result;
            // 读取Excel文件
            const wb = XLSX.read(data, { type: 'binary' });
            
            // 解析工作表
            const parameterTables: ParameterTable[] = [];
            
            wb.SheetNames.forEach((sheetName, index) => {
              // 读取工作表数据
              const ws = wb.Sheets[sheetName];
              const jsonData = XLSX.utils.sheet_to_json(ws, { header: 1 });
              
              // 跳过表头行（前两行）
              const rowsData = jsonData.slice(2);
              
              // 解析连接件类型
              let type: 'large' | 'small' = 'large';
              if (sheetName.includes('小连接件')) {
                type = 'small';
              }
              
              // 解析行数据
              const rows: ParameterRow[] = rowsData.map((row: any) => {
                return {
                  id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
                  编号: row[0] || '',
                  水平长L1: row[1] || '',
                  竖直长L2: row[2] || '',
                  厚2: row[3] || '',
                  长B1: row[4] || '',
                  宽: row[5] || '',
                  厚3: row[6] || '',
                  长B2: row[7] || '',
                  宽2: row[8] || '',
                  厚4: row[9] || '',
                  长B3: row[10] || '',
                  宽3: row[11] || '',
                  厚5: row[12] || '',
                  长A1: row[13] || '',
                  宽4: row[14] || '',
                  厚6: row[15] || '',
                  长A2: row[16] || '',
                  宽5: row[17] || '',
                  厚7: row[18] || '',
                  方向: row[19] || (type === 'small' ? '左上' : '上'),
                  预览: ''
                };
              });
              
              // 创建参数表
              parameterTables.push({
                id: (index + 1).toString(),
                type,
                rows
              });
            });
            
            // 更新状态
            if (parameterTables.length > 0) {
              setParameterTables(parameterTables);
              // 从文件名中提取项目名称（去除日期和扩展名）
              const fileName = file.name;
              // 先去除扩展名
              let projectName = fileName.replace(/\.xlsx$|\.xls$/, '');
              // 再尝试去除时间戳部分
              projectName = projectName.replace(/_.+$/, '');
              setProjectName(projectName);
            }
          } catch (error) {
            console.error('读取Excel文件失败:', error);
            alert('读取Excel文件失败，请确保文件格式正确');
          }
        };
        
        reader.readAsBinaryString(file);
      }
    };
    
    // 触发文件选择
    input.click();
  };

  const handleSaveProject = () => {
    // 创建Excel工作簿
    const wb = XLSX.utils.book_new();
    
    // 为每个参数表创建工作表
    parameterTables.forEach((table, tableIndex) => {
      // 准备两行表头
      const headerRow1 = ['编号', '连接板 mm', '', '', '翼缘板1 mm', '', '', '翼缘板2 mm', '', '', '翼缘板3 mm', '', '', '肋板1 mm', '', '', '肋板2 mm', '', '', '方向'];
      const headerRow2 = ['', '水平长L1', '竖直长L2', '厚', '长B1', '宽', '厚', '长B2', '宽', '厚', '长B3', '宽', '厚', '长A1', '宽', '厚', '长A2', '宽', '厚', ''];
      
      // 准备数据
      const data = table.rows.map(row => [
        row.编号,
        row.水平长L1,
        row.竖直长L2,
        row.厚2,
        row.长B1,
        row.宽,
        row.厚3,
        row.长B2,
        row.宽2,
        row.厚4,
        row.长B3,
        row.宽3,
        row.厚5,
        row.长A1,
        row.宽4,
        row.厚6,
        row.长A2,
        row.宽5,
        row.厚7,
        row.方向
      ]);
      
      // 添加表头到数据
      const worksheetData = [headerRow1, headerRow2, ...data];
      
      // 创建工作表
      const ws = XLSX.utils.aoa_to_sheet(worksheetData);
      
      // 合并单元格
      const merges = [
        // 第一行合并
        { s: { r: 0, c: 0 }, e: { r: 1, c: 0 } }, // 编号
        { s: { r: 0, c: 1 }, e: { r: 0, c: 3 } }, // 连接板 mm
        { s: { r: 0, c: 4 }, e: { r: 0, c: 6 } }, // 翼缘板1 mm
        { s: { r: 0, c: 7 }, e: { r: 0, c: 9 } }, // 翼缘板2 mm
        { s: { r: 0, c: 10 }, e: { r: 0, c: 12 } }, // 翼缘板3 mm
        { s: { r: 0, c: 13 }, e: { r: 0, c: 15 } }, // 肋板1 mm
        { s: { r: 0, c: 16 }, e: { r: 0, c: 18 } }, // 肋板2 mm
        { s: { r: 0, c: 19 }, e: { r: 1, c: 19 } }, // 方向
      ];
      
      // 设置合并单元格
      ws['!merges'] = merges;
      
      // 设置工作表名称
      const sheetName = `参数表${tableIndex + 1}_${table.type === 'large' ? '大连接件' : '小连接件'}`;
      
      // 将工作表添加到工作簿
      XLSX.utils.book_append_sheet(wb, ws, sheetName);
    });
    
    // 生成Excel文件并下载
    const fileName = `${projectName || 'BRB连接件项目'}_${new Date().toISOString().slice(0, 10)}.xlsx`;
    XLSX.writeFile(wb, fileName);
  };

  const handleAddParameterTable = () => {
    const newId = (parameterTables.length + 1).toString();
    const defaultType: 'large' | 'small' = 'large';
    setParameterTables([
      ...parameterTables,
      {
        id: newId,
        type: defaultType,
        rows: [
          {
            id: Date.now().toString(),
            编号: '',
            水平长L1: '',
            竖直长L2: '',
            厚2: '',
            长B1: '',
            宽: '',
            厚3: '',
            长B2: '',
            宽2: '',
            厚4: '',
            长B3: '',
            宽3: '',
            厚5: '',
            长A1: '',
            宽4: '',
            厚6: '',
            长A2: '',
            宽5: '',
            厚7: '',
            方向: '上',
            预览: '',
          },
        ],
      },
    ]);
  };

  const handleRemoveParameterTable = (id: string) => {
    setParameterTables(parameterTables.filter(table => table.id !== id));
  };

  const handleParameterChange = (tableId: string, rowId: string, parameterName: string, value: string) => {
    setParameterTables(
      parameterTables.map(table => 
        table.id === tableId 
          ? { 
              ...table, 
              rows: table.rows.map(row => 
                row.id === rowId 
                  ? { ...row, [parameterName]: value } 
                  : row
              ) 
            } 
          : table
      )
    );
  };

  const handleConnectorTypeChange = (tableId: string, type: 'large' | 'small') => {
    setParameterTables(
      parameterTables.map(table => 
        table.id === tableId 
          ? { 
              ...table, 
              type, 
              rows: table.rows.map(row => ({
                ...row,
                方向: type === 'small' ? '左上' : '上'
              }))
            } 
          : table
      )
    );
  };

  const handleAddRow = (tableId: string, rowId: string) => {
    setParameterTables(
      parameterTables.map(table => 
        table.id === tableId 
          ? { 
              ...table, 
              rows: (() => {
                const newRows = [...table.rows];
                const rowIndex = newRows.findIndex(row => row.id === rowId);
                const newRow = {
                  id: Date.now().toString(),
                  编号: '',
                  水平长L1: '',
                  竖直长L2: '',
                  厚2: '',
                  长B1: '',
                  宽: '',
                  厚3: '',
                  长B2: '',
                  宽2: '',
                  厚4: '',
                  长B3: '',
                  宽3: '',
                  厚5: '',
                  长A1: '',
                  宽4: '',
                  厚6: '',
                  长A2: '',
                  宽5: '',
                  厚7: '',
                  方向: table.type === 'small' ? '左上' : '上',
                  预览: '',
                };
                if (rowIndex >= 0) {
                  newRows.splice(rowIndex + 1, 0, newRow);
                } else {
                  newRows.push(newRow);
                }
                return newRows;
              })(),
            } 
          : table
      )
    );
  };

  const handleRemoveRow = (tableId: string, rowId: string) => {
    setParameterTables(
      parameterTables.map(table => 
        table.id === tableId 
          ? { 
              ...table, 
              rows: table.rows.filter(row => row.id !== rowId),
            } 
          : table
      )
    );
  };

  const handleGenerateDrawing = async () => {
    try {
      // 发送请求到后端API
      const response = await fetch('/api/brb/connector-drawing', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ projectName, parameterTables }),
      });

      if (!response.ok) {
        throw new Error('生成图纸失败');
      }

      // 处理响应，下载文件
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${projectName}_connector.dxf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('生成图纸时出错:', error);
      alert('生成图纸失败，请重试');
    }
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">BRB连接件绘制</h1>
        
        {/* 项目管理 */}
        <div className="mb-8">
          <div className="flex items-center space-x-4 mb-4">
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="项目名称"
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleNewProject}
              className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
            >
              <Plus size={18} />
              <span>新建项目</span>
            </button>
            <button
              onClick={handleOpenProject}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <FolderOpen size={18} />
              <span>打开项目</span>
            </button>
            <button
              onClick={handleSaveProject}
              className="flex items-center space-x-2 px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 transition-colors"
            >
              <Save size={18} />
              <span>保存项目</span>
            </button>
          </div>
        </div>
        
        {/* 参数表 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">参数表</h2>
            <button
              onClick={handleAddParameterTable}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <Plus size={18} />
              <span>添加参数表</span>
            </button>
          </div>
          
          {parameterTables.map((table) => (
            <div key={table.id} className="mb-6 border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-4">
                  <h3 className="text-lg font-medium text-gray-900">参数表 {table.id}</h3>
                  <div className="flex items-center space-x-2">
                    <span className="text-gray-600">连接件类型：</span>
                    <select
                      value={table.type}
                      onChange={(e) => handleConnectorTypeChange(table.id, e.target.value as 'large' | 'small')}
                      className="px-3 py-1 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="large">大连接件</option>
                      <option value="small">小连接件</option>
                    </select>
                  </div>
                </div>
                <button
                  onClick={() => handleRemoveParameterTable(table.id)}
                  className="px-3 py-1 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                >
                  删除
                </button>
              </div>
              
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" rowSpan={2}>编号</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" colSpan={3}>连接板 mm</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" colSpan={3}>翼缘板1 mm</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" colSpan={3}>翼缘板2 mm</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" colSpan={3}>翼缘板3 mm</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" colSpan={3}>肋板1 mm</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" colSpan={3}>肋板2 mm</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" rowSpan={2}>方向</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700" rowSpan={2}>预览</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700 w-16" rowSpan={2}>操作</th>
                    </tr>
                    <tr>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700 w-20">水平长L1</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700 w-20">竖直长L2</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">厚</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">长B1</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">宽</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">厚</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">长B2</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">宽</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">厚</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">长B3</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">宽</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">厚</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">长A1</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">宽</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">厚</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">长A2</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">宽</th>
                      <th className="border border-gray-300 px-1 py-2 text-center text-sm font-medium text-gray-700">厚</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white">
                    {table.rows.map((row) => (
                      <tr key={row.id}>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '编号', e.currentTarget.textContent || '')}>
                          {row.编号}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '水平长L1', e.currentTarget.textContent || '')}>
                          {row.水平长L1}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '竖直长L2', e.currentTarget.textContent || '')}>
                          {row.竖直长L2}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '厚2', e.currentTarget.textContent || '')}>
                          {row.厚2}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '长B1', e.currentTarget.textContent || '')}>
                          {row.长B1}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '宽', e.currentTarget.textContent || '')}>
                          {row.宽}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '厚3', e.currentTarget.textContent || '')}>
                          {row.厚3}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '长B2', e.currentTarget.textContent || '')}>
                          {row.长B2}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '宽2', e.currentTarget.textContent || '')}>
                          {row.宽2}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '厚4', e.currentTarget.textContent || '')}>
                          {row.厚4}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '长B3', e.currentTarget.textContent || '')}>
                          {row.长B3}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '宽3', e.currentTarget.textContent || '')}>
                          {row.宽3}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '厚5', e.currentTarget.textContent || '')}>
                          {row.厚5}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '长A1', e.currentTarget.textContent || '')}>
                          {row.长A1}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '宽4', e.currentTarget.textContent || '')}>
                          {row.宽4}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '厚6', e.currentTarget.textContent || '')}>
                          {row.厚6}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '长A2', e.currentTarget.textContent || '')}>
                          {row.长A2}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '宽5', e.currentTarget.textContent || '')}>
                          {row.宽5}
                        </td>
                        <td className="border border-gray-300 px-1 py-2" contentEditable="true" onBlur={(e) => handleParameterChange(table.id, row.id, '厚7', e.currentTarget.textContent || '')}>
                          {row.厚7}
                        </td>
                        <td className="border border-gray-300 px-1 py-2">
                          <select
                            value={row.方向 || (table.type === 'small' ? '左上' : '上')}
                            onChange={(e) => handleParameterChange(table.id, row.id, '方向', e.target.value)}
                            className="w-full px-0 py-0 border-none focus:outline-none text-center"
                          >
                            {table.type === 'small' ? (
                              <>
                                <option value="左上">左上</option>
                                <option value="右上">右上</option>
                                <option value="左下">左下</option>
                                <option value="右下">右下</option>
                              </>
                            ) : (
                              <>
                                <option value="上">上</option>
                                <option value="下">下</option>
                              </>
                            )}
                          </select>
                        </td>
                        <td className="border border-gray-300 px-1 py-2">
                          {row.方向 === '上' && (
                            <div className="w-13 h-0 flex items-center justify-center">
                              <svg width="61" height="31" viewBox="0 0 61 31" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M1 1 L60 1 V20 L45 30 H15 L1 20 Z" stroke="black" strokeWidth="2"/>
                              </svg>
                            </div>
                          )}
                          {row.方向 === '下' && (
                            <div className="w-13 h-0 flex items-center justify-center">
                              <svg width="61" height="31" viewBox="0 0 61 31" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M1 30 L60 30 V11 L45 1 H15 L1 11 Z" stroke="black" strokeWidth="2"/>
                              </svg>
                            </div>
                          )}
                          {row.方向 === '左上' && (
                            <div className="w-13 h-0 flex items-center justify-center">
                              <svg width="61" height="31" viewBox="0 0 61 31" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M1 1 L30 1 V20 L15 30 H1 L1 1 Z" stroke="black" strokeWidth="2"/>
                              </svg>
                            </div>
                          )}
                          {row.方向 === '右上' && (
                            <div className="w-13 h-0 flex items-center justify-center">
                              <svg width="61" height="31" viewBox="0 0 61 31" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M60 1 L31 1 V20 L46 30 H60 L60 1 Z" stroke="black" strokeWidth="2"/>
                              </svg>
                            </div>
                          )}
                          {row.方向 === '左下' && (
                            <div className="w-13 h-0 flex items-center justify-center">
                              <svg width="61" height="31" viewBox="0 0 61 31" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M1 30 L30 30 V11 L16 1 H1 L1 30 Z" stroke="black" strokeWidth="2"/>
                              </svg>
                            </div>
                          )}
                          {row.方向 === '右下' && (
                            <div className="w-13 h-0 flex items-center justify-center">
                              <svg width="61" height="31" viewBox="0 0 61 31" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M60 30 L31 30 V11 L46 1 H60 L60 30 Z" stroke="black" strokeWidth="2"/>
                              </svg>
                            </div>
                          )}
                        </td>
                        <td className="border border-gray-300 px-1 py-2 flex space-x-1 justify-start">
                          <button
                            onClick={() => handleAddRow(table.id, row.id)}
                            className="w-6 h-6 flex items-center justify-center bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-xs"
                          >
                            +
                          </button>
                          <button
                            onClick={() => handleRemoveRow(table.id, row.id)}
                            className={`w-6 h-6 flex items-center justify-center rounded-md transition-colors text-xs ${table.rows.length > 1 ? 'bg-red-600 text-white hover:bg-red-700' : 'bg-gray-300 text-gray-500 cursor-not-allowed'}`}
                            disabled={table.rows.length <= 1}
                          >
                            -
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
        
        {/* 生成图纸按钮 */}
        <div className="flex justify-center">
          <button
            onClick={handleGenerateDrawing}
            className="flex items-center space-x-2 px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-lg font-medium"
          >
            <Download size={20} />
            <span>生成连接件图纸</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default BrbConnectorDrawing;