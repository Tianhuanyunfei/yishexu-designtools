import React, { useState } from 'react';
import { normalizeSectionTemplate } from '../utils/sectionTemplate';

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

/** 方管排布：大项目 deep 搜索可能需数分钟，结果优先于速度 */
const TUBE_LAYOUT_FETCH_TIMEOUT_MS = 5 * 60 * 1000;

function getTubeLayoutProgressHint(elapsedSec: number): string {
  if (elapsedSec < 15) return '正在生成方管排布图…';
  if (elapsedSec < 45) return '并联算法竞选中（含深度搜索），计时增加表示仍在计算…';
  if (elapsedSec < 120) return '深度搜索耗时较长属正常，请稍候…';
  return '仍在计算最优方案，请勿关闭页面…';
}

const BrbTubeLayout: React.FC<BrbTubeLayoutProps> = ({
  projectName,
  parameterTables,
  totalQuantity,
  onFilesGenerated
}) => {
  const showToast = (message: string, type: 'success' | 'error' | 'info', duration = 3000) => {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 transition-all duration-300 ease-in-out transform translate-y-0 opacity-100 ${type === 'success' ? 'bg-green-500 text-white' : type === 'error' ? 'bg-red-500 text-white' : 'bg-blue-500 text-white'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('translate-y-[-20px]', 'opacity-0');
      setTimeout(() => {
        if (document.body.contains(toast)) {
          document.body.removeChild(toast);
        }
      }, 300);
    }, duration);
  };

  const handleFilesGenerated = (files: GeneratedFile[]) => {
    if (files.length > 0) {
      onFilesGenerated(files);
    }
  };

  const [isGeneratingTubeLayout, setIsGeneratingTubeLayout] = useState(false);
  const [tubeLayoutElapsedSec, setTubeLayoutElapsedSec] = useState(0);
  const [tubeLayoutStatus, setTubeLayoutStatus] = useState('');

  const generateTubeLayout = async () => {
    if (!projectName) {
      showToast('请输入项目名称！', 'error');
      return;
    }

    if (parameterTables.length === 0) {
      showToast('请添加至少一个参数表！', 'error');
      return;
    }

    let progressTimer: ReturnType<typeof setInterval> | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    try {
      setIsGeneratingTubeLayout(true);
      setTubeLayoutElapsedSec(0);
      setTubeLayoutStatus('正在启动排布计算…');
      showToast('方管排布已开始计算，请查看按钮下方进度提示', 'info', 4000);

      const validParameterTables = parameterTables.map(table => {
        const templateValue = normalizeSectionTemplate(table.template);
        return {
          ...table,
          template: templateValue,
          template_type: templateValue
        };
      });

      const startedAt = Date.now();
      const tickProgress = () => {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000);
        setTubeLayoutElapsedSec(elapsed);
        setTubeLayoutStatus(getTubeLayoutProgressHint(elapsed));
      };
      tickProgress();
      progressTimer = setInterval(tickProgress, 1000);

      const controller = new AbortController();
      timeoutId = setTimeout(() => {
        controller.abort();
      }, TUBE_LAYOUT_FETCH_TIMEOUT_MS);

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

      if (timeoutId) clearTimeout(timeoutId);

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
      if (timeoutId) clearTimeout(timeoutId);
      if (error?.name === 'AbortError') {
        showToast(
          `生成超时（已等待 ${Math.floor(TUBE_LAYOUT_FETCH_TIMEOUT_MS / 1000)} 秒）。若计时曾持续增加，多半是深度搜索过久而非卡死，可稍后重试。`,
          'error',
          8000
        );
      } else {
        showToast(`生成方管排布图失败: ${error.message}`, 'error');
      }
    } finally {
      if (progressTimer) clearInterval(progressTimer);
      setTubeLayoutStatus('');
      setTubeLayoutElapsedSec(0);
      setIsGeneratingTubeLayout(false);
    }
  };

  return (
    <div className="mt-6">
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">方管排布图生成</h3>
        <div className="flex flex-col items-end gap-3">
          <button 
            className="btn-primary flex items-center space-x-2 disabled:opacity-70 disabled:cursor-not-allowed"
            onClick={generateTubeLayout}
            disabled={isGeneratingTubeLayout}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 ${isGeneratingTubeLayout ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>
              {isGeneratingTubeLayout
                ? `排布计算中 ${tubeLayoutElapsedSec}s`
                : '生成方管排布图'}
            </span>
          </button>
          {isGeneratingTubeLayout && (
            <div className="w-full rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
              <div className="font-medium">方管排布计算进行中 · {tubeLayoutElapsedSec} 秒</div>
              <div className="mt-1 text-blue-800">{tubeLayoutStatus || '正在启动排布计算…'}</div>
              <div className="mt-1 text-xs text-blue-600">秒数持续增加表示仍在深度搜索，并非卡住。</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BrbTubeLayout;
