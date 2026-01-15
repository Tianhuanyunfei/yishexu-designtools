import React, { useState, useEffect } from 'react';
import { useToast } from '../components/Toast';

const Settings: React.FC = () => {
  const [backgroundColor, setBackgroundColor] = useState('#f9fafb'); // 默认的bg-gray-50的十六进制颜色
  const [customColor, setCustomColor] = useState('#f9fafb');
  const { showToast } = useToast();

  // 预设颜色选项
  const presetColors = [
    { name: '浅灰色', value: '#f9fafb' },
    { name: '浅粉色', value: '#fdf2f8' },
    { name: '浅黄色', value: '#fffbeb' },
    { name: '浅绿色', value: '#f0fdf4' },
    { name: '浅蓝色', value: '#eff6ff' },
    { name: '浅紫色', value: '#f5f3ff' },
  ];

  // 加载保存的背景色
  useEffect(() => {
    const savedColor = localStorage.getItem('backgroundColor');
    if (savedColor) {
      setBackgroundColor(savedColor);
      setCustomColor(savedColor);
      applyBackgroundColor(savedColor);
    }
  }, []);

  // 应用背景色到所有相关元素
  const applyBackgroundColor = (color: string) => {
    // 应用到body元素
    document.body.style.backgroundColor = color;
    
    // 应用到所有带有min-h-screen类的div元素（包括Layout和Dashboard组件中的）
    const minHeightDivs = document.querySelectorAll('.min-h-screen');
    minHeightDivs.forEach(div => {
      div.classList.remove('bg-gray-50');
      (div as HTMLElement).style.backgroundColor = color;
    });
    
    // 应用到main元素
    const mainElement = document.querySelector('main');
    if (mainElement) {
      mainElement.style.backgroundColor = color;
    }
    
    // 应用到main内的div容器
    const mainDiv = document.querySelector('main > div');
    if (mainDiv) {
      (mainDiv as HTMLElement).style.backgroundColor = color;
    }
    
    // 应用到所有卡片元素
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
      card.classList.remove('bg-white');
      (card as HTMLElement).style.backgroundColor = '#ffffff'; // 保持卡片为白色，以便与背景形成对比
    });
    
    // 应用到Dashboard组件中的内容容器
    const dashboardContainers = document.querySelectorAll('.max-w-7xl.mx-auto');
    dashboardContainers.forEach(container => {
      (container as HTMLElement).style.backgroundColor = color;
    });
  };

  // 保存背景色并应用
  const saveBackgroundColor = () => {
    localStorage.setItem('backgroundColor', customColor);
    setBackgroundColor(customColor);
    applyBackgroundColor(customColor);
  };

  // 重置背景色为默认值
  const resetBackgroundColor = () => {
    const defaultColor = '#f9fafb';
    localStorage.setItem('backgroundColor', defaultColor);
    setBackgroundColor(defaultColor);
    setCustomColor(defaultColor);
    applyBackgroundColor(defaultColor);
  };

  // 清除所有localStorage数据
  const clearAllLocalStorageData = () => {
    // 弹出确认对话框
    if (window.confirm('确定要清除所有本地缓存数据吗？此操作不可恢复，将清除所有设计参数和设置。')) {
      try {
        // 清除所有与应用相关的localStorage数据
        const keysToRemove = [
          // 应用设置
          'backgroundColor',
          // BRB设计器数据
          'brb_projectName',
          'brb_totalQuantity',
          'brb_parameterTables',
          // BRB图纸绘制数据
          'brb_drawing_projectName',
          'brb_drawing_totalQuantity',
          'brb_drawing_parameterTables',
          // VFD设计器数据
          'vfd_projectName',
          'vfd_projectFolder',
          'vfd_selectedModel',
          'vfd_parameters',
          // CSV编辑器数据
          'csv_editor_data',
          'csv_editor_headers'
        ];

        // 移除所有相关键
        keysToRemove.forEach(key => {
          localStorage.removeItem(key);
        });

        // 刷新页面以应用更改
        window.location.reload();
      } catch (error) {
        console.error('清除本地数据时出错:', error);
        showToast('清除本地数据失败', 'error');
      }
    }
  };

  return (
    <div className="card p-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">系统设置</h1>
      
      <div className="space-y-8">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">界面设置</h2>
          <div className="space-y-6">
            <div className="space-y-4">
              <label className="block text-sm font-medium text-gray-700">背景颜色</label>
              
              {/* 预设颜色选择 */}
              <div className="flex flex-wrap gap-4 mb-6">
                {presetColors.map((color) => (
                  <button
                    key={color.value}
                    onClick={() => {
                      setCustomColor(color.value);
                      // 实时应用背景色预览
                      applyBackgroundColor(color.value);
                    }}
                    className={`w-12 h-12 rounded-lg border-2 flex items-center justify-center transition-all duration-200 ${
                      customColor === color.value
                        ? 'border-gray-600 scale-110'
                        : 'border-transparent hover:border-gray-400'
                    }`}
                    style={{ backgroundColor: color.value }}
                    title={color.name}
                  >
                    {customColor === color.value && (
                      <div className="w-4 h-4 rounded-full bg-white shadow-lg"></div>
                    )}
                  </button>
                ))}
              </div>

              {/* 自定义颜色选择器 */}
              <div className="flex items-center space-x-4">
                <input
                  type="color"
                  value={customColor}
                  onChange={(e) => {
                    setCustomColor(e.target.value);
                    // 实时应用背景色预览
                    applyBackgroundColor(e.target.value);
                  }}
                  className="w-20 h-10 border-2 border-gray-300 rounded-lg cursor-pointer"
                />
                <input
                  type="text"
                  value={customColor}
                  onChange={(e) => {
                    setCustomColor(e.target.value);
                    // 实时应用背景色预览
                    applyBackgroundColor(e.target.value);
                  }}
                  className="input-field flex-1"
                  placeholder="输入十六进制颜色值 (如 #f9fafb)"
                />
              </div>

              {/* 当前颜色预览 */}
              <div className="mt-4 p-4 border border-gray-200 rounded-lg">
                <div className="flex items-center space-x-4">
                  <div className="text-sm text-gray-600">当前预览:</div>
                  <div
                    className="w-20 h-12 rounded-lg border border-gray-300"
                    style={{ backgroundColor: customColor }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 数据管理部分 */}
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">数据管理</h2>
          <div className="space-y-6">
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800 mb-4">
                <strong>注意：</strong>清除本地缓存数据将删除所有设计参数、项目设置和CSV编辑内容，此操作不可恢复。
              </p>
              <button
                onClick={clearAllLocalStorageData}
                className="bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-6 rounded-lg transition-colors duration-200"
              >
                清除所有本地缓存数据
              </button>
            </div>
          </div>
        </div>

        <div className="flex justify-end space-x-4">
          <button className="btn-secondary" onClick={resetBackgroundColor}>重置为默认</button>
          <button className="btn-primary" onClick={saveBackgroundColor}>保存设置</button>
        </div>
      </div>
    </div>
  );
};

export default Settings;