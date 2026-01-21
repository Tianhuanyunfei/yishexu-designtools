import React, { useState, useEffect } from 'react';

interface ParameterTable {
  id: string;
  designForce: string;
  width: string;
  height: string;
  thickness: string;
  tubeWidth: string;
  tubeThickness: string;
  weld: string;
  coreMaterial: string;
  template: string;
  lengthQuantityTable: Array<{ length: string; quantity: string }>;
}

interface GeneratedFile {
  id: string;
  name: string;
  path: string;
  type: 'drawing' | 'materials' | 'tube_layout';
  tableIndex?: number;
}

interface BrbTubeLayoutProps {
  projectName: string;
  parameterTables: ParameterTable[];
  totalQuantity: number;
  onFilesGenerated: (files: GeneratedFile[]) => void;
}

const BrbTubeLayout: React.FC<BrbTubeLayoutProps> = ({
  projectName,
  parameterTables,
  totalQuantity,
  onFilesGenerated
}) => {
  // 简单的toast消息显示函数
  const showToast = (message: string, type: 'success' | 'error' | 'info') => {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 transition-all duration-300 ease-in-out transform translate-y-0 opacity-100 ${type === 'success' ? 'bg-green-500 text-white' : type === 'error' ? 'bg-red-500 text-white' : 'bg-blue-500 text-white'}`;
    toast.textContent = message;
    
    // 添加到文档
    document.body.appendChild(toast);
    
    // 3秒后移除
    setTimeout(() => {
      toast.classList.add('translate-y-[-20px]', 'opacity-0');
      setTimeout(() => {
        if (document.body.contains(toast)) {
          document.body.removeChild(toast);
        }
      }, 300);
    }, 3000);
  };

  // 处理文件生成的函数
  const handleFilesGenerated = (files: GeneratedFile[]) => {
    if (files.length > 0) {
      onFilesGenerated(files);
    }
  };
  const [isGeneratingTubeLayout, setIsGeneratingTubeLayout] = useState(false);

  const generateTubeLayout = async () => {
    if (!projectName) {
      showToast('请输入项目名称！', 'error');
      return;
    }

    if (parameterTables.length === 0) {
      showToast('请添加至少一个参数表！', 'error');
      return;
    }

    try {
      setIsGeneratingTubeLayout(true);
      showToast('正在生成方管排布图，请稍候...', 'info');

      const validParameterTables = parameterTables.map(table => {
        const templateValue = table.template || '王一';
        return {
          ...table,
          template: templateValue,
          template_type: templateValue
        };
      });

      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        controller.abort();
      }, 60000);

      const response = await fetch('/api/brb/tube-layout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          projectName,
          parameterTables: validParameterTables,
          totalQuantity: totalQuantity
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch (parseError) {
          errorData = { message: '服务器返回错误响应' };
        }
        throw new Error(errorData.message || '生成方管排布图失败');
      }

      const contentType = response.headers.get('content-type');

      if (contentType && contentType.includes('application/json')) {
        const result = await response.json();
        console.log('生成方管排布图结果:', result);

        if (result.result && result.result.length > 0) {
          console.log('生成的文件:', result.result);

          const newFiles: GeneratedFile[] = result.result.map((fileName: string, index: number) => ({
            id: Date.now().toString() + Math.random().toString(36).substring(2, 9) + index,
            name: fileName,
            path: `tube_layout_${Date.now()}_${index}.dxf`,
            type: 'tube_layout',
            tableIndex: index
          }));

          handleFilesGenerated(newFiles);

          setTimeout(() => {
            const filesContainer = document.getElementById('generated-files-container');
            if (filesContainer) {
              filesContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
          }, 100);

          const fileNames = newFiles.map(file => `• ${file.name}`).join('\n');
          showToast(`方管排布图生成成功！\n\n生成的文件:\n${fileNames}`, 'success');
        } else {
          showToast('方管排布图生成成功！', 'success');
        }
      } else {
        console.log('直接返回了文件流');

        const contentDisposition = response.headers.get('content-disposition');
        let fileName = `${projectName} 方管排布图.dxf`;
        if (contentDisposition) {
          const matches = /filename="([^"]+)"/.exec(contentDisposition);
          if (matches && matches[1]) {
            fileName = matches[1];
          }
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        const newFile: GeneratedFile = {
          id: Date.now().toString() + Math.random().toString(36).substring(2, 9),
          name: fileName,
          path: `tube_layout_${Date.now()}.dxf`,
          type: 'tube_layout',
          tableIndex: 0
        };

        handleFilesGenerated([newFile]);

        setTimeout(() => {
          const filesContainer = document.getElementById('generated-files-container');
          if (filesContainer) {
            filesContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        }, 100);

        showToast(`方管排布图生成成功！文件: ${newFile.name}`, 'success');
      }
    } catch (error: any) {
      clearTimeout((error as any).timeoutId);
      if ((error as any).name === 'AbortError') {
        showToast('生成方管排布图超时，请检查网络连接或稍后重试', 'error');
      } else {
        showToast(`生成方管排布图失败: ${error.message}`, 'error');
      }
    } finally {
      setIsGeneratingTubeLayout(false);
    }
  };

  return (
    <div className="mt-6">
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">方管排布图生成</h3>
        <div className="flex justify-end">
          <button 
            className="btn-primary flex items-center space-x-2 disabled:opacity-70 disabled:cursor-not-allowed"
            onClick={generateTubeLayout}
            disabled={isGeneratingTubeLayout}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>{isGeneratingTubeLayout ? '生成中...' : '生成方管排布图'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default BrbTubeLayout;