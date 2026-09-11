import React, { useState, useEffect, useRef } from 'react';
import { Box, FolderOpen, Download, Plus, Trash2, FileSpreadsheet, Copy } from 'lucide-react';
import { useToast } from '../components/Toast';
import WangSectionParams from '../components/WangSectionParams';
import {
  SECTION_TEMPLATE_OPTIONS,
  normalizeSectionTemplate,
  isShiSectionTemplate,
  usesWangSectionDiagram,
} from '../utils/sectionTemplate';

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
  yieldStrength: string; // 屈服强度 MPa，默认 294
  template: string; // 新增：选择的截面模板
  lengthQuantityTable: Array<{ length: string; quantity: string }>;
}

interface GeneratedFile {
  id: string;
  name: string;
  path: string;
  type: 'drawing' | 'materials' | 'tube_layout';
  tableIndex?: number; // 新增：参数表索引，用于标识该文件对应的参数表
}

// 格式化数字，去除多余的零和小数点，与后端保持一致
const formatNumber = (num: number | string): string => {
  if (typeof num === 'string') {
    num = parseInt(num, 10);
  }
  if (typeof num === 'number' && !isNaN(num)) {
    return num.toFixed(3).replace(/\.?0+$/, '');
  }
  return String(num);
};

const getBaseName = (filePath: string): string => {
  const parts = filePath.split(/[\\/]/);
  return parts[parts.length - 1] || filePath;
};

/** 方管排布：大项目 deep 搜索可能需数分钟，结果优先于速度 */
const TUBE_LAYOUT_FETCH_TIMEOUT_MS = 5 * 60 * 1000;

function getTubeLayoutProgressHint(elapsedSec: number): string {
  if (elapsedSec < 15) return '正在生成方管排布图…';
  if (elapsedSec < 45) return '并联算法竞选中（含深度搜索），计时增加表示仍在计算…';
  if (elapsedSec < 120) return '深度搜索耗时较长属正常，请稍候…';
  return '仍在计算最优方案，请勿关闭页面…';
}

const PARAM_CARD_STEP_PX = 320 + 24; // w-80 + gap-6

/** 芯板材料 LYXXX → 强度 XXX；匹配不到返回 null */
function yieldStrengthFromCoreMaterial(material: string): string | null {
  const m = material.trim().match(/^LY(\d+)/i);
  return m ? m[1] : null;
}

/**
 * 拖拽预览：按「抽出 from、插入到 to」后的视觉位置，计算各表应平移的距离。
 * 效果：落点后的表后移腾空，中间表补上原位空缺。
 */
function getDragLayoutShift(
  index: number,
  from: number | null,
  to: number | null,
): number {
  if (from === null || to === null) return 0;
  if (to === from || to === from + 1) return 0;
  if (index === from) return 0;

  const insertAt = to > from ? to - 1 : to;
  const compact = index > from ? index - 1 : index;
  const visual = compact >= insertAt ? compact + 1 : compact;
  return (visual - index) * PARAM_CARD_STEP_PX;
}

const BrbDrawing: React.FC = () => {
  // 从localStorage加载初始状态
  const loadInitialState = () => {
    try {
      const savedProjectName = localStorage.getItem('brb_drawing_projectName') || '';
      const savedTotalQuantity = parseInt(localStorage.getItem('brb_drawing_totalQuantity') || '0', 10);
      const savedParameterTables = localStorage.getItem('brb_drawing_parameterTables');
      
      const initialParameterTables = (savedParameterTables
        ? (JSON.parse(savedParameterTables) as ParameterTable[])
        : [{
          id: '1',
          designForce: '',
          width: '',
          height: '',
          thickness: '',
          tubeWidth: '',
          tubeThickness: '',
          weld: '',
          coreMaterial: 'Q235B',
          yieldStrength: '294',
          template: '王（丨）',
          lengthQuantityTable: [{ length: '', quantity: '' }]
        }]
      ).map((table) => ({
        ...table,
        template: normalizeSectionTemplate(table.template),
        yieldStrength: table.yieldStrength || '294',
        coreMaterial: table.coreMaterial || 'Q235B',
      }));
      
      return {
        projectName: savedProjectName,
        totalQuantity: savedTotalQuantity,
        parameterTables: initialParameterTables
      };
    } catch (error) {
      console.error('加载BRB图纸绘制初始状态失败:', error);
      return {
        projectName: '',
        totalQuantity: 0,
        parameterTables: [{
          id: '1',
          designForce: '',
          width: '',
          height: '',
          thickness: '',
          tubeWidth: '',
          tubeThickness: '',
          weld: '',
          coreMaterial: 'Q235B',
          yieldStrength: '294',
          template: '王（丨）',
          lengthQuantityTable: [{ length: '', quantity: '' }]
        }]
      };
    }
  };
  
  const initialState = loadInitialState();
  
  const [projectName, setProjectName] = useState(initialState.projectName);
  const [totalQuantity, setTotalQuantity] = useState(initialState.totalQuantity);
  const { showToast } = useToast();
  // 添加生成文件列表状态
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([]);
  
  const [parameterTables, setParameterTables] = useState<ParameterTable[]>(initialState.parameterTables);
  
  // 监听状态变化并保存到localStorage
  useEffect(() => {
    localStorage.setItem('brb_drawing_projectName', projectName);
  }, [projectName]);
  
  useEffect(() => {
    localStorage.setItem('brb_drawing_totalQuantity', totalQuantity.toString());
  }, [totalQuantity]);
  
  useEffect(() => {
    localStorage.setItem('brb_drawing_parameterTables', JSON.stringify(parameterTables));
  }, [parameterTables]);
  useEffect(() => {
    return () => {
      if (removeTableTimerRef.current) {
        clearTimeout(removeTableTimerRef.current);
      }
      if (enterTableTimerRef.current) {
        clearTimeout(enterTableTimerRef.current);
      }
    };
  }, []);
  const [dragFromIndex, setDragFromIndex] = useState<number | null>(null);
  const [dragToIndex, setDragToIndex] = useState<number | null>(null);
  const [justMovedTableId, setJustMovedTableId] = useState<string | null>(null);
  const justMovedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [removingTableId, setRemovingTableId] = useState<string | null>(null);
  const [enteringTableId, setEnteringTableId] = useState<string | null>(null);
  const [enterReady, setEnterReady] = useState(false);
  const removeTableTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const enterTableTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 添加加载状态
  const [isGeneratingDrawings, setIsGeneratingDrawings] = useState(false);
  const [isGeneratingMaterials, setIsGeneratingMaterials] = useState(false);
  const [isGeneratingTubeLayout, setIsGeneratingTubeLayout] = useState(false);
  const [tubeLayoutElapsedSec, setTubeLayoutElapsedSec] = useState(0);
  const [tubeLayoutStatus, setTubeLayoutStatus] = useState('');
  const [isParsingTaskbook, setIsParsingTaskbook] = useState(false);
  const [isTaskbookDragOver, setIsTaskbookDragOver] = useState(false);
  const taskbookInputRef = useRef<HTMLInputElement>(null);

  const isExcelTaskbookFile = (file: File | undefined | null) => {
    if (!file) return false;
    const name = file.name.toLowerCase();
    return name.endsWith('.xlsx') || name.endsWith('.xlsm');
  };

  const pickTaskbookFromDataTransfer = (dt: DataTransfer | null): File | null => {
    if (!dt?.files?.length) return null;
    for (let i = 0; i < dt.files.length; i++) {
      const f = dt.files[i];
      if (isExcelTaskbookFile(f)) return f;
    }
    return null;
  };





  const updateParameterTable = (id: string, field: keyof ParameterTable, value: any) => {
    setParameterTables(parameterTables.map(table => {
      if (table.id !== id) return table;
      if (field === 'coreMaterial') {
        const autoStrength = yieldStrengthFromCoreMaterial(String(value ?? ''));
        return {
          ...table,
          coreMaterial: value,
          ...(autoStrength ? { yieldStrength: autoStrength } : {}),
        };
      }
      return { ...table, [field]: value };
    }));
  };

  const addLengthQuantityRow = (tableId: string) => {
    // 使用函数式更新，确保使用最新的状态
    setParameterTables(prevTables => {
      const updatedTables = prevTables.map(table => 
        table.id === tableId 
          ? { 
              ...table, 
              lengthQuantityTable: [...table.lengthQuantityTable, { length: '', quantity: '' }]
            }
          : table
      );
      
      // 在更新参数表后，立即计算并更新总数量
      let newTotalQuantity = 0;
      updatedTables.forEach(table => {
        table.lengthQuantityTable.forEach(row => {
          const quantity = parseInt(row.quantity) || 0;
          newTotalQuantity += quantity;
        });
      });
      setTotalQuantity(newTotalQuantity);
      
      return updatedTables;
    });
  };

  const removeLengthQuantityRow = (tableId: string, index: number) => {
    // 使用函数式更新，确保使用最新的状态
    setParameterTables(prevTables => {
      const updatedTables = prevTables.map(table => 
        table.id === tableId 
          ? { 
              ...table, 
              lengthQuantityTable: table.lengthQuantityTable.filter((_, i) => i !== index)
            }
          : table
      );
      
      // 在更新参数表后，立即计算并更新总数量
      let newTotalQuantity = 0;
      updatedTables.forEach(table => {
        table.lengthQuantityTable.forEach(row => {
          const quantity = parseInt(row.quantity) || 0;
          newTotalQuantity += quantity;
        });
      });
      setTotalQuantity(newTotalQuantity);
      
      return updatedTables;
    });
  };

  const addParameterTable = () => {
    const newTable: ParameterTable = {
      id: Date.now().toString(),
      designForce: '',
      width: '',
      height: '',
      thickness: '',
      tubeWidth: '',
      tubeThickness: '',
      weld: '',
      coreMaterial: 'Q235B',
      yieldStrength: '294',
      template: '王（丨）',
      lengthQuantityTable: [{ length: '', quantity: '' }]
    };
    // 使用函数式更新，确保使用最新的状态
    setParameterTables(prevTables => {
      const updatedTables = [...prevTables, newTable];
      
      // 在更新参数表后，立即计算并更新总数量
      let newTotalQuantity = 0;
      updatedTables.forEach(table => {
        table.lengthQuantityTable.forEach(row => {
          const quantity = parseInt(row.quantity) || 0;
          newTotalQuantity += quantity;
        });
      });
      setTotalQuantity(newTotalQuantity);
      
      return updatedTables;
    });
  };

  const animateTableEnter = (tableId: string) => {
    setEnterReady(false);
    setEnteringTableId(tableId);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setEnterReady(true);
      });
    });
    if (enterTableTimerRef.current) {
      clearTimeout(enterTableTimerRef.current);
    }
    enterTableTimerRef.current = setTimeout(() => {
      setEnteringTableId(null);
      setEnterReady(false);
      enterTableTimerRef.current = null;
    }, 320);
  };

  const duplicateParameterTable = (id: string) => {
    if (removingTableId || enteringTableId) return;

    const newId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setParameterTables(prevTables => {
      const index = prevTables.findIndex(table => table.id === id);
      if (index < 0) return prevTables;

      const source = prevTables[index];
      const copied: ParameterTable = {
        ...source,
        id: newId,
        lengthQuantityTable: source.lengthQuantityTable.map(row => ({
          length: row.length,
          quantity: row.quantity,
        })),
      };

      const updatedTables = [
        ...prevTables.slice(0, index + 1),
        copied,
        ...prevTables.slice(index + 1),
      ];

      let newTotalQuantity = 0;
      updatedTables.forEach(table => {
        table.lengthQuantityTable.forEach(row => {
          newTotalQuantity += parseInt(row.quantity) || 0;
        });
      });
      setTotalQuantity(newTotalQuantity);

      return updatedTables;
    });

    animateTableEnter(newId);
  };

  const removeParameterTable = (id: string) => {
    if (parameterTables.length <= 1 || removingTableId || enteringTableId) return;

    setRemovingTableId(id);
    if (removeTableTimerRef.current) {
      clearTimeout(removeTableTimerRef.current);
    }
    removeTableTimerRef.current = setTimeout(() => {
      setParameterTables(prevTables => {
        const updatedTables = prevTables.filter(table => table.id !== id);

        let newTotalQuantity = 0;
        updatedTables.forEach(table => {
          table.lengthQuantityTable.forEach(row => {
            newTotalQuantity += parseInt(row.quantity) || 0;
          });
        });
        setTotalQuantity(newTotalQuantity);

        return updatedTables.length > 0
          ? updatedTables
          : prevTables;
      });
      setRemovingTableId(null);
      removeTableTimerRef.current = null;
    }, 320);
  };

  const dragPreviewRef = useRef<HTMLElement | null>(null);

  const highlightMovedTable = (tableId: string) => {
    if (justMovedTimerRef.current) {
      clearTimeout(justMovedTimerRef.current);
    }
    setJustMovedTableId(tableId);
    justMovedTimerRef.current = setTimeout(() => {
      setJustMovedTableId(null);
      justMovedTimerRef.current = null;
    }, 700);
  };

  // 拖拽事件处理函数
  const handleDragStart = (e: React.DragEvent, index: number) => {
    e.dataTransfer.setData('text/plain', index.toString());
    e.dataTransfer.effectAllowed = 'move';
    setDragFromIndex(index);
    setDragToIndex(index);
    
    // 设置自定义拖拽预览，显示整个参数表
    const dragElement = e.currentTarget.closest('.card');
    if (dragElement) {
      const clone = dragElement.cloneNode(true) as HTMLElement;
      clone.style.position = 'absolute';
      clone.style.top = '-10000px';
      clone.style.left = '-10000px';
      clone.style.opacity = '0.92';
      clone.style.width = '320px';
      clone.style.boxShadow = '0 16px 40px rgba(37, 99, 235, 0.35)';
      clone.style.pointerEvents = 'none';
      document.body.appendChild(clone);
      dragPreviewRef.current = clone;
      e.dataTransfer.setDragImage(clone, 40, 24);
    }
  };

  const handleDragEnd = () => {
    setDragFromIndex(null);
    setDragToIndex(null);
    if (dragPreviewRef.current) {
      dragPreviewRef.current.remove();
      dragPreviewRef.current = null;
    }
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const insertIndex = x < rect.width / 2 ? index : index + 1;
    setDragToIndex(insertIndex);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    const container = document.querySelector('[data-param-tables]');
    if (container && !container.contains(e.relatedTarget as Node)) {
      setDragToIndex(null);
    }
  };

  const applyTableReorder = (fromIndex: number, toIndex: number | null, fallbackIndex: number) => {
    let insertIndex = toIndex;
    if (insertIndex === null) {
      insertIndex = fallbackIndex;
    }

    let finalToIndex = insertIndex;
    if (fromIndex < finalToIndex) {
      finalToIndex -= 1;
    }

    finalToIndex = Math.max(0, Math.min(finalToIndex, parameterTables.length - 1));

    if (Number.isNaN(fromIndex) || fromIndex < 0 || fromIndex === finalToIndex) {
      return;
    }

    const newTables = [...parameterTables];
    const [movedTable] = newTables.splice(fromIndex, 1);
    newTables.splice(finalToIndex, 0, movedTable);
    setParameterTables(newTables);
    setDragFromIndex(null);
    setDragToIndex(null);
    highlightMovedTable(movedTable.id);
  };

  const handleDrop = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    const fromIndex = parseInt(e.dataTransfer.getData('text/plain'), 10);
    let toIndex = dragToIndex;

    // 计算正确的插入位置
    if (toIndex === null) {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      toIndex = x < rect.width / 2 ? index : index + 1;
    }

    applyTableReorder(fromIndex, toIndex, index);
  };

  const renderInsertIndicator = () => (
    <div className="relative w-0 shrink-0 self-stretch" aria-hidden>
      <div className="pointer-events-none absolute inset-y-0 left-0 z-20 w-1 -translate-x-1/2 rounded-full bg-brb-blue-500 shadow-[0_0_12px_rgba(37,99,235,0.75)]" />
    </div>
  );

  const updateLengthQuantityRow = (tableId: string, index: number, field: 'length' | 'quantity', value: string) => {
    // 使用函数式更新，确保使用最新的状态
    setParameterTables(prevTables => {
      const updatedTables = prevTables.map(table => 
        table.id === tableId 
          ? { 
              ...table, 
              lengthQuantityTable: table.lengthQuantityTable.map((row, i) => 
                i === index ? { ...row, [field]: value } : row
              )
            }
          : table
      );
      
      // 在更新参数表后，立即计算并更新总数量
      let newTotalQuantity = 0;
      updatedTables.forEach(table => {
        table.lengthQuantityTable.forEach(row => {
          const quantity = parseInt(row.quantity) || 0;
          newTotalQuantity += quantity;
        });
      });
      setTotalQuantity(newTotalQuantity);
      
      return updatedTables;
    });
  };

  const calculateTotalQuantity = () => {
    let total = 0;
    parameterTables.forEach(table => {
      table.lengthQuantityTable.forEach(row => {
        const quantity = parseInt(row.quantity) || 0;
        total += quantity;
      });
    });
    setTotalQuantity(total);
    return total;
  };

  const handleGenerateDrawings = async () => {
    if (!projectName) {
      showToast('请先输入项目名称', 'error');
      return;
    }
    
    const total = calculateTotalQuantity();
    if (total === 0) {
      showToast('请至少输入一个有效的数量', 'error');
      return;
    }
    
    // 验证参数表中的所有数值参数是否有效
    const invalidTables = parameterTables.filter(table => 
      isNaN(parseInt(table.designForce)) || 
      isNaN(parseInt(table.width)) || 
      isNaN(parseInt(table.height)) || 
      isNaN(parseInt(table.thickness)) || 
      isNaN(parseInt(table.tubeWidth)) || 
      isNaN(parseInt(table.tubeThickness)) || 
      isNaN(parseInt(table.weld))
    );
    
    if (invalidTables.length > 0) {
      showToast('请检查所有参数是否为有效的数字', 'error');
      return;
    }
    
    try {
      // 设置加载状态
      setIsGeneratingDrawings(true);
      showToast('正在生成图纸，请稍候...', 'info');
      
      // 验证并处理parameterTables，确保每个表都有有效的template和template_type值
      // 后端的brb_materials.py函数需要template_type参数来区分模板类型
      const validParameterTables = parameterTables.map((table) => {
        const templateValue = table.template || '';
        return {
          ...table,
          template: templateValue, // 保持template字段
          template_type: templateValue // 添加template_type字段，与template值相同
        };
      });

      // 准备请求数据
      const requestData = {
        projectName,
        // 不再发送projectFolder，因为我们不再使用这个字段
        parameterTables: validParameterTables,
        totalQuantity: total
      };
      
      // 调用后端API生成图纸
      // 添加超时设置
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        controller.abort();
      }, 30000); // 30秒超时
      
      try {
        const response = await fetch('/api/brb/design', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestData),
          signal: controller.signal // 添加超时信号
        });
        
        clearTimeout(timeoutId); // 清除超时定时器
        
        if (!response.ok) {
          let errorData;
          try {
            errorData = await response.json();
          } catch (parseError) {
            errorData = { message: '服务器返回错误响应' };
          }
          throw new Error(errorData.message || '生成图纸失败');
        }
        
        // 处理响应
        const contentType = response.headers.get('content-type');
        
        if (contentType && contentType.includes('application/json')) {
          // 如果是JSON响应，表示生成了多个文件或返回了文件路径列表
          const result = await response.json();
          
          // 显示生成的文件路径或文件名
          if (result.result && result.result.length > 0) {
            console.log('生成的文件:', result.result);
            
            // 将生成的文件添加到下载列表
            const newFiles: GeneratedFile[] = result.result.map((item: any, index: number) => {
              const now = Date.now();
              if (item && typeof item === 'object' && item.path) {
                return {
                  id: now.toString() + Math.random().toString(36).substring(2, 9) + index,
                  name: item.name || getBaseName(item.path),
                  path: item.path,
                  type: 'drawing',
                  tableIndex: index
                };
              }

              const rawValue = typeof item === 'string' ? item : '';
              return {
                id: now.toString() + Math.random().toString(36).substring(2, 9) + index,
                name: getBaseName(rawValue),
                path: rawValue || `drawing_${now}_${index}.dxf`,
                type: 'drawing',
                tableIndex: index
              };
            });
            
            setGeneratedFiles(prev => [...prev, ...newFiles]);
            
            // 滚动到文件列表位置
            setTimeout(() => {
              const filesContainer = document.getElementById('generated-files-container');
              if (filesContainer) {
                filesContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
            }, 100);
            
            const fileNames = newFiles.map(file => `• ${file.name}`).join('\n');
            showToast(`图纸生成成功！总数量: ${total}件\n\n生成的文件:\n${fileNames}`, 'success');
          } else {
            showToast(`图纸生成成功！总数量: ${total}件`, 'success');
          }
        } else {
          // 如果不是JSON响应，表示直接返回了文件流（可能是单个DXF文件）
          console.log('直接返回了文件流');
          
          // 获取文件名
          const contentDisposition = response.headers.get('content-disposition');
          let fileName = `${projectName} BRB.dxf`;
          if (contentDisposition) {
            const matches = /filename="([^"]+)"/.exec(contentDisposition);
            if (matches && matches[1]) {
              fileName = matches[1];
            }
          }
          
          // 将生成的文件添加到下载列表
          const newFile: GeneratedFile = {
            id: Date.now().toString() + Math.random().toString(36).substring(2, 9),
            name: fileName,
            path: `drawing_${Date.now()}.dxf`, // 生成一个虚拟路径用于下载标识
            type: 'drawing',
            tableIndex: 0 // 单个文件时，tableIndex默认为0
          };
          
          setGeneratedFiles(prev => [...prev, newFile]);
          
          showToast(`图纸生成成功！总数量: ${total}件\n\n生成的文件:\n• ${newFile.name}`, 'success');
        }
      } catch (error) {
        clearTimeout(timeoutId); // 清除超时定时器
        if ((error as any).name === 'AbortError') {
          throw new Error('API调用超时，请检查网络连接或稍后重试');
        }
        if (error instanceof Error && error.message.includes('Failed to fetch')) {
          throw new Error('无法连接到服务器，请检查网络连接和服务器状态');
        }
        throw error; // 重新抛出其他错误
      }
    } catch (error) {
      console.error('生成图纸错误:', error);
      if (error instanceof Error) {
        console.error('错误类型:', error.name);
        console.error('错误信息:', error.message);
        console.error('错误堆栈:', error.stack);
      }
      showToast(error instanceof Error ? error.message : '生成图纸失败，请检查网络连接或服务器状态', 'error');
    } finally {
      // 无论成功或失败，都重置加载状态
      console.log('重置加载状态');
      setIsGeneratingDrawings(false);
    }
  };

  // 生成材料单功能
  const handleGenerateMaterials = async () => {
    if (!projectName) {
      showToast('请先输入项目名称', 'error');
      return;
    }
    
    const total = calculateTotalQuantity();
    if (total === 0) {
      showToast('请至少输入一个有效的数量', 'error');
      return;
    }
    
    // 验证参数表中的所有数值参数是否有效
    const invalidTables = parameterTables.filter(table => 
      isNaN(parseInt(table.designForce)) || 
      isNaN(parseInt(table.width)) || 
      isNaN(parseInt(table.height)) || 
      isNaN(parseInt(table.thickness)) || 
      isNaN(parseInt(table.tubeWidth)) || 
      isNaN(parseInt(table.tubeThickness)) || 
      isNaN(parseInt(table.weld))
    );
    
    if (invalidTables.length > 0) {
      showToast('请检查所有参数是否为有效的数字', 'error');
      return;
    }
    
    try {
      // 设置加载状态
      setIsGeneratingMaterials(true);
      showToast('正在生成材料单，请稍候...', 'info');
      
      // 调用后端API生成材料单
      console.log('调用后端API生成材料单...');
      const startTime = Date.now();
      
      // 添加超时设置
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        console.error('API调用超时');
        controller.abort();
      }, 30000); // 30秒超时
      
      try {
        // 验证并处理parameterTables，确保每个表都有有效的template和template_type值
        // 后端的brb_materials.py函数需要template_type参数来区分模板类型
        const validParameterTables = parameterTables.map(table => {
          const templateValue = normalizeSectionTemplate(table.template);
          return {
            ...table,
            template: templateValue, // 保持template字段
            template_type: templateValue // 添加template_type字段，与template值相同
          };
        });

        console.log('发送到材料单API的有效参数表:', validParameterTables);
        console.log('每个表的template值:', validParameterTables.map(t => t.template));
        console.log('每个表的template_type值:', validParameterTables.map(t => t.template_type));

        const response = await fetch('/api/brb/materials', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            projectName,
            // 不再传递projectFolder，因为我们不再使用这个字段
            parameterTables: validParameterTables,
            totalQuantity: total
          }),
          signal: controller.signal // 添加超时信号
        });
        
        clearTimeout(timeoutId); // 清除超时定时器
        
        const endTime = Date.now();
        console.log(`API调用完成，耗时: ${endTime - startTime}ms`);
        console.log('响应状态:', response.status, response.statusText);
        
        if (!response.ok) {
          console.error('API响应错误，准备获取错误详情...');
          let errorData;
          try {
            errorData = await response.json();
            console.error('API响应错误详情:', errorData);
          } catch (parseError) {
            console.error('解析错误响应失败:', parseError);
            errorData = { message: '服务器返回错误响应' };
          }
          throw new Error(errorData.message || '生成材料单失败');
        }
        
        console.log('响应正常，准备处理文件...');
        const contentType = response.headers.get('content-type') || '';

        let fileName = `${projectName}_材料单.xlsx`;
        let filePath = `materials_${Date.now()}.xlsx`;
        if (contentType.includes('application/json')) {
          const result = await response.json();
          if (result?.result?.path) {
            fileName = result.result.name || getBaseName(result.result.path);
            filePath = result.result.path;
          }
        }
        
        // 将生成的材料单添加到下载列表
        const materialsFile: GeneratedFile = {
          id: Date.now().toString() + Math.random().toString(36).substring(2, 9),
          name: fileName,
          path: filePath,
          type: 'materials',
          tableIndex: -1 // 材料单对应所有参数表，使用-1表示
        };
        
        setGeneratedFiles(prev => [...prev, materialsFile]);
        
        // 滚动到文件列表位置
        setTimeout(() => {
          const filesContainer = document.getElementById('generated-files-container');
          if (filesContainer) {
            filesContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        }, 100);
        
        showToast(`材料单生成成功！文件: ${materialsFile.name}`, 'success');
      } catch (error) {
        clearTimeout(timeoutId); // 清除超时定时器
        if ((error as any).name === 'AbortError') {
          throw new Error('API调用超时，请检查网络连接或稍后重试');
        }
        if (error instanceof Error && error.message.includes('Failed to fetch')) {
          throw new Error('无法连接到服务器，请检查网络连接和服务器状态');
        }
        throw error; // 重新抛出其他错误
      }
    } catch (error) {
      console.error('生成材料单错误:', error);
      showToast(error instanceof Error ? error.message : '生成材料单失败，请检查网络连接或服务器状态', 'error');
    } finally {
      // 无论成功或失败，都重置加载状态
      setIsGeneratingMaterials(false);
    }
  };



          


  // 导入生产任务书 Excel
  const handleImportTaskbook = async (file: File) => {
    const hasContent =
      !!projectName.trim() ||
      parameterTables.some(
        (table) =>
          table.designForce ||
          table.lengthQuantityTable.some((row) => row.length || row.quantity)
      );
    if (hasContent) {
      const ok = window.confirm('导入任务书将覆盖当前项目名称与参数表（截面尺寸需自行补全），是否继续？');
      if (!ok) return;
    }

    setIsParsingTaskbook(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch('/api/brb/parse-taskbook', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.status !== 'success') {
        throw new Error(data.message || '解析任务书失败');
      }

      const result = data.result || {};
      const tables = Array.isArray(result.parameterTables) ? result.parameterTables : [];
      if (tables.length === 0) {
        throw new Error('任务书中未解析到 BRB 产品');
      }

      setProjectName(result.projectName || '');
      setParameterTables(
        tables.map((table: any, index: number) => ({
          id: table.id || (index === 0 ? '1' : String(Date.now() + index)),
          designForce: String(table.designForce || ''),
          width: table.width || '',
          height: table.height || '',
          thickness: table.thickness || '',
          tubeWidth: table.tubeWidth || '',
          tubeThickness: table.tubeThickness || '',
          weld: table.weld || '',
          coreMaterial: table.coreMaterial || 'Q235B',
          yieldStrength:
            yieldStrengthFromCoreMaterial(table.coreMaterial || '') ||
            table.yieldStrength ||
            '294',
          template: normalizeSectionTemplate(table.template),
          lengthQuantityTable:
            Array.isArray(table.lengthQuantityTable) && table.lengthQuantityTable.length > 0
              ? table.lengthQuantityTable.map((row: any) => ({
                  length: String(row.length || ''),
                  quantity: String(row.quantity || ''),
                }))
              : [{ length: '', quantity: '' }],
        }))
      );
      setTotalQuantity(Number(result.totalQuantity) || 0);
      showToast(data.message || '任务书导入成功', 'success', 6000);
    } catch (error: any) {
      showToast(error?.message || '导入任务书失败', 'error');
    } finally {
      setIsParsingTaskbook(false);
      if (taskbookInputRef.current) {
        taskbookInputRef.current.value = '';
      }
    }
  };

  // 新建项目功能
  const handleNewProject = () => {
    if (parameterTables.some(table => table.lengthQuantityTable.some(row => row.quantity)) || projectName) {
      if (window.confirm('当前项目有未保存的内容，确定要新建项目吗？')) {
        resetProject();
      }
    } else {
      resetProject();
    }
  };

  // 打开项目功能
  const handleOpenProject = () => {
    if (parameterTables.some(table => table.lengthQuantityTable.some(row => row.quantity)) || projectName) {
      if (window.confirm('当前项目有未保存的内容，确定要打开其他项目吗？')) {
        // 创建文件输入元素
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = (e) => {
          const file = (e.target as HTMLInputElement).files?.[0];
          if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
              try {
                const content = event.target?.result as string;
                const data = JSON.parse(content);
                loadProjectData(data);
                showToast('项目打开成功', 'success');
              } catch (error) {
                showToast('项目文件格式错误', 'error');
              }
            };
            reader.readAsText(file);
          }
        };
        input.click();
      }
    } else {
      // 创建文件输入元素
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.json';
      input.onchange = (e) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (event) => {
            try {
              const content = event.target?.result as string;
              const data = JSON.parse(content);
              loadProjectData(data);
              showToast('项目打开成功', 'success');
            } catch (error) {
              showToast('项目文件格式错误', 'error');
            }
          };
          reader.readAsText(file);
        }
      };
      input.click();
    }
  };

  // 保存项目功能
  const handleSaveProject = () => {
    if (!projectName) {
      showToast('请先输入项目名称', 'error');
      return;
    }

    // 验证parameterTables格式，确保所有必要字段都存在
    const validParameterTables = parameterTables.map(table => {
      // 确保所有必要字段都有值
      const validTable = {
        id: table.id || Date.now().toString(),
        designForce: table.designForce || '',
        width: table.width || '',
        height: table.height || '',
        thickness: table.thickness || '',
        tubeWidth: table.tubeWidth || '',
        tubeThickness: table.tubeThickness || '',
        weld: table.weld || '',
        coreMaterial: table.coreMaterial || 'Q235B',
        yieldStrength: table.yieldStrength || '294',
        template: normalizeSectionTemplate(table.template),
        // 确保lengthQuantityTable是有效的数组
        lengthQuantityTable: Array.isArray(table.lengthQuantityTable) ? 
          table.lengthQuantityTable.map(row => ({ 
            length: row.length || '', 
            quantity: row.quantity || '' 
          })) : 
          [{ length: '', quantity: '' }]
      };
      return validTable;
    });

    // 创建标准格式的项目数据
    const projectData = {
      projectName,
      parameterTables: validParameterTables,
      totalQuantity,
      // 添加版本信息，方便未来兼容性处理
      version: '1.0'
    };

    try {
      const dataStr = JSON.stringify(projectData, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = window.URL.createObjectURL(dataBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${projectName}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      showToast('项目保存成功', 'success');
    } catch (error) {
      console.error('保存项目时出错:', error);
      showToast('项目保存失败', 'error');
    }
  };

  // 重置项目
  const resetProject = () => {
    setProjectName('');
    setParameterTables([{
      id: '1',
      designForce: '',
      width: '',
      height: '',
      thickness: '',
      tubeWidth: '',
      tubeThickness: '',
      weld: '',
      coreMaterial: 'Q235B',
      yieldStrength: '294',
      template: '王（丨）',
      lengthQuantityTable: [{ length: '', quantity: '' }]
    }]);
    setTotalQuantity(0);
    
    // 清除localStorage中的数据
    localStorage.removeItem('brb_drawing_projectName');
    localStorage.removeItem('brb_drawing_totalQuantity');
    localStorage.removeItem('brb_drawing_parameterTables');
  };

  // 生成方管排布图
  const generateTubeLayout = async () => {
    if (!projectName || !projectName.trim()) {
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

          const newFiles: GeneratedFile[] = result.result.map((item: any, index: number) => {
            const now = Date.now();
            if (item && typeof item === 'object' && item.path) {
              return {
                id: now.toString() + Math.random().toString(36).substring(2, 9) + index,
                name: item.name || getBaseName(item.path),
                path: item.path,
                type: 'tube_layout',
                tableIndex: index
              };
            }

            const rawValue = typeof item === 'string' ? item : '';
            return {
              id: now.toString() + Math.random().toString(36).substring(2, 9) + index,
              name: getBaseName(rawValue),
              path: rawValue || `tube_layout_${now}_${index}.dxf`,
              type: 'tube_layout',
              tableIndex: index
            };
          });

          setGeneratedFiles(prev => [...prev, ...newFiles]);

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

        const newFile: GeneratedFile = {
          id: Date.now().toString() + Math.random().toString(36).substring(2, 9),
          name: fileName,
          path: `tube_layout_${Date.now()}.dxf`,
          type: 'tube_layout',
          tableIndex: 0
        };

        setGeneratedFiles(prev => [...prev, newFile]);

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

  // 加载项目数据
  const loadProjectData = (data: any) => {
    try {
      console.log('加载的项目数据:', data);
      
      if (!data || typeof data !== 'object') {
        throw new Error('项目数据格式错误，不是有效的对象');
      }
      
      // 处理不同的命名约定（下划线命名法和驼峰命名法）
      const projectName = data.projectName || data.project_name || '';
      const parameterTables = data.parameterTables || data.param_tables || [];
      
      console.log('处理后的项目名称:', projectName);
      console.log('处理后的参数表:', parameterTables);
      
      setProjectName(projectName);
      
      // 确保parameterTables是一个数组
      const tables = Array.isArray(parameterTables) ? parameterTables : [];
      
      // 为每个参数表添加必要的属性，处理可能的不同命名约定
      const processedTables = tables.map((table: any, index: number) => {
        // 确保table是一个对象
        if (!table || typeof table !== 'object') {
          table = {};
        }
        
        // 处理参数表的不同命名约定
        const designForce = table.designForce || table.design_force || '';
        
        // 处理parameters对象中的中文键
        let width = table.width || '';
        let height = table.height || '';
        let thickness = table.thickness || '';
        let tubeWidth = table.tubeWidth || '';
        let tubeThickness = table.tubeThickness || '';
        let weld = table.weld || '';
        let coreMaterial = table.coreMaterial || table.core_material || 'Q235B';
        let template = normalizeSectionTemplate(table.template || table.section_template || table.section);
        
        // 如果存在parameters对象（中文键），则使用其中的值
        if (table.parameters && typeof table.parameters === 'object') {
          width = table.parameters['截面宽度(mm)'] || '';
          height = table.parameters['截面高度(mm)'] || '';
          thickness = table.parameters['板材厚度(mm)'] || '';
          weld = table.parameters['焊缝高度(mm)'] || '';
          tubeWidth = table.parameters['方管宽度(mm)'] || '';
          tubeThickness = table.parameters['方管厚度(mm)'] || '';
          coreMaterial = table.parameters['芯板材料'] || 'Q235B';
          template = table.parameters['选择截面'] || template;
        }
        
        // 处理长度-数量表的不同格式
        const lengthQuantityTable = table.lengthQuantityTable || table.length_quantity_table || table.length_quantity || [];
        
        // 处理长度-数量表的不同命名约定和格式
        let processedLengthQuantity: Array<{ length: string; quantity: string }> = [];
        
        if (Array.isArray(lengthQuantityTable)) {
          if (lengthQuantityTable.length > 0) {
            // 检查是否是二维数组格式 [[length1, quantity1], [length2, quantity2]]
            if (Array.isArray(lengthQuantityTable[0]) && lengthQuantityTable[0].length >= 2) {
              processedLengthQuantity = lengthQuantityTable.map((row: any) => ({
                length: (row[0]?.toString() || '').trim(),
                quantity: (row[1]?.toString() || '').trim()
              }));
            } else {
              // 对象数组格式 [{ length: string; quantity: string }]
              processedLengthQuantity = lengthQuantityTable.map((row: any) => {
                if (row && typeof row === 'object') {
                  return {
                    length: (row.length?.toString() || '').trim(),
                    quantity: (row.quantity?.toString() || '').trim()
                  };
                }
                return { length: '', quantity: '' };
              });
            }
          } else {
            processedLengthQuantity = [{ length: '', quantity: '' }];
          }
        } else {
          processedLengthQuantity = [{ length: '', quantity: '' }];
        }
        
        // 确保返回一个完整的ParameterTable对象
        return {
          id: table.id || table.table_number?.toString() || `table_${index + 1}`,
          designForce: designForce.toString().trim(),
          width: width.toString().trim(),
          height: height.toString().trim(),
          thickness: thickness.toString().trim(),
          tubeWidth: tubeWidth.toString().trim(),
          tubeThickness: tubeThickness.toString().trim(),
          weld: weld.toString().trim(),
          coreMaterial: coreMaterial.trim() || 'Q235B',
          yieldStrength:
            yieldStrengthFromCoreMaterial(coreMaterial) ||
            (table.yieldStrength ? String(table.yieldStrength) : '') ||
            '294',
          template: normalizeSectionTemplate(template),
          lengthQuantityTable: processedLengthQuantity
        };
      });
      
      // 设置参数表
      const tablesToSet = processedTables.length > 0 ? processedTables : [{
        id: '1',
        designForce: '',
        width: '',
        height: '',
        thickness: '',
        tubeWidth: '',
        tubeThickness: '',
        weld: '',
        coreMaterial: 'Q235B',
        yieldStrength: '294',
        template: '王（丨）',
        lengthQuantityTable: [{ length: '', quantity: '' }]
      }];
      
      // 直接计算新的总数量，不依赖状态变量
      let newTotalQuantity = 0;
      tablesToSet.forEach(table => {
        table.lengthQuantityTable.forEach(row => {
          const quantity = parseInt(row.quantity) || 0;
          newTotalQuantity += quantity;
        });
      });
      
      console.log('计算后的总数量:', newTotalQuantity);
      
      // 更新状态
      setParameterTables(tablesToSet);
      setTotalQuantity(newTotalQuantity);
    } catch (error) {
      console.error('加载项目数据时出错:', error);
      showToast('项目文件格式错误，无法加载', 'error');
    }
  }

  return (
    <div
      className="container mx-auto px-4 py-3 space-y-3"
      onDragEnter={(e) => {
        if (dragFromIndex !== null) return;
        if (pickTaskbookFromDataTransfer(e.dataTransfer)) {
          e.preventDefault();
          setIsTaskbookDragOver(true);
        }
      }}
      onDragOver={(e) => {
        if (dragFromIndex !== null) return;
        if (pickTaskbookFromDataTransfer(e.dataTransfer) || [...(e.dataTransfer?.types || [])].includes('Files')) {
          e.preventDefault();
          e.dataTransfer.dropEffect = 'copy';
        }
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) {
          setIsTaskbookDragOver(false);
        }
      }}
      onDrop={(e) => {
        if (dragFromIndex !== null) return;
        const file = pickTaskbookFromDataTransfer(e.dataTransfer);
        if (!file) return;
        e.preventDefault();
        e.stopPropagation();
        setIsTaskbookDragOver(false);
        void handleImportTaskbook(file);
      }}
    >
      {/* 页面标题 */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <Box className="h-6 w-6 text-orange-600" />
          <h1 className="text-xl font-bold text-gray-900">BRB图纸绘制</h1>
        </div>
        <div className="flex space-x-2">
          <button className="btn-secondary flex items-center space-x-1.5 py-1.5 px-3 text-sm"
            onClick={() => handleNewProject()}
          >
            <Plus className="h-3.5 w-3.5" />
            <span>新建项目</span>
          </button>
          <button className="btn-secondary flex items-center space-x-1.5 py-1.5 px-3 text-sm"
            onClick={() => handleOpenProject()}
          >
            <FolderOpen className="h-3.5 w-3.5" />
            <span>打开项目</span>
          </button>
          <button className="btn-secondary flex items-center space-x-1.5 py-1.5 px-3 text-sm"
            onClick={() => handleSaveProject()}
          >
            <Box className="h-3.5 w-3.5" />
            <span>保存项目</span>
          </button>
        </div>
      </div>

      {/* 项目信息区域 */}
      <div className="card px-4 py-2.5">
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="flex-1 min-w-0 flex items-center gap-2">
            <label className="shrink-0 text-base font-semibold text-gray-700 whitespace-nowrap">项目名称</label>
            <input
              type="text"
              className="input-field py-1.5"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="请输入项目名称"
            />
          </div>

          <input
            ref={taskbookInputRef}
            type="file"
            accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                void handleImportTaskbook(file);
              }
            }}
          />
          <div
            role="button"
            tabIndex={0}
            title="拖拽或点击导入生产任务书 Excel"
            className={`md:w-[240px] shrink-0 rounded-lg border-2 border-dashed px-3 py-1.5 transition-colors cursor-pointer ${
              isTaskbookDragOver
                ? 'border-brb-blue-500 bg-blue-50'
                : 'border-gray-300 bg-gray-50 hover:border-brb-blue-400 hover:bg-blue-50/60'
            } ${isParsingTaskbook ? 'opacity-70 pointer-events-none' : ''}`}
            onClick={() => {
              if (!isParsingTaskbook) taskbookInputRef.current?.click();
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                taskbookInputRef.current?.click();
              }
            }}
            onDragEnter={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsTaskbookDragOver(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              e.dataTransfer.dropEffect = 'copy';
              setIsTaskbookDragOver(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsTaskbookDragOver(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsTaskbookDragOver(false);
              const file = pickTaskbookFromDataTransfer(e.dataTransfer);
              if (!file) {
                showToast('请拖入 .xlsx / .xlsm 生产任务书文件', 'error');
                return;
              }
              void handleImportTaskbook(file);
            }}
          >
            <div className="flex items-center space-x-2 text-brb-blue-700 text-sm font-medium">
              <FileSpreadsheet className="h-4 w-4 shrink-0" />
              <span className="truncate">
                {isParsingTaskbook
                  ? '解析任务书中...'
                  : isTaskbookDragOver
                    ? '松开即可导入'
                    : '拖入/选择任务书'}
              </span>
            </div>
          </div>

          <div className="flex items-center shrink-0 gap-3">
            <button
              type="button"
              onClick={addParameterTable}
              className="btn-secondary flex items-center space-x-1.5 py-1.5 px-3 text-sm"
            >
              <Plus className="h-3 w-3" />
              <span>添加参数表</span>
            </button>
            <div className="text-sm font-semibold text-brb-blue-600 whitespace-nowrap">
              BRB总数量: {totalQuantity}件
            </div>
          </div>
        </div>
      </div>

      {/* 参数表区域 */}
      <div className="overflow-x-auto pb-4">
        <div 
          data-param-tables
          className={`flex items-start gap-6 min-w-max transition-all duration-300 ease-in-out ${
            dragFromIndex !== null ? 'py-1' : ''
          }`}
          onDragOver={(e) => {
            // 参数表重排优先；仅在非重排时把 Excel 文件交给页面级导入
            if (dragFromIndex === null) {
              if (pickTaskbookFromDataTransfer(e.dataTransfer) || [...(e.dataTransfer?.types || [])].includes('Files')) {
                return;
              }
            }
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            
            // 计算鼠标在容器中的位置，用于显示插入指示线
            const container = e.currentTarget as HTMLElement;
            const cards = container.querySelectorAll('.card');
            const mouseX = e.clientX;
            
            let closestIndex = parameterTables.length;
            let minDistance = Infinity;
            
            // 遍历所有卡片，找出鼠标最接近的卡片
            cards.forEach((card, index) => {
              const rect = card.getBoundingClientRect();
              const cardCenter = rect.left + rect.width / 2;
              const distance = Math.abs(mouseX - cardCenter);
              
              if (distance < minDistance) {
                minDistance = distance;
                closestIndex = index;
              }
            });
            
            // 根据鼠标位置计算插入位置
            if (cards.length > 0) {
              const closestCard = cards[closestIndex] as HTMLElement;
              const rect = closestCard.getBoundingClientRect();
              const cardCenter = rect.left + rect.width / 2;
              const insertIndex = mouseX < cardCenter ? closestIndex : closestIndex + 1;
              setDragToIndex(insertIndex);
            } else {
              setDragToIndex(0);
            }
          }}
          onDrop={(e) => {
            if (dragFromIndex === null) {
              const file = pickTaskbookFromDataTransfer(e.dataTransfer);
              if (file) {
                e.preventDefault();
                e.stopPropagation();
                setIsTaskbookDragOver(false);
                void handleImportTaskbook(file);
                return;
              }
            }
            e.preventDefault();
            const fromIndex = parseInt(e.dataTransfer.getData('text/plain'), 10);
            applyTableReorder(fromIndex, dragToIndex, parameterTables.length);
          }}
        >
          {/* 渲染参数表和插入点 */}
          {parameterTables.map((table, tableIndex) => {
            const isRemoving = removingTableId === table.id;
            const isEntering = enteringTableId === table.id && !enterReady;
            const isDragging = dragFromIndex === tableIndex;
            const showInsertBefore =
              dragFromIndex !== null &&
              dragToIndex === tableIndex &&
              dragToIndex !== dragFromIndex &&
              dragToIndex !== dragFromIndex + 1;
            const dragShift =
              !isRemoving && !isEntering
                ? getDragLayoutShift(tableIndex, dragFromIndex, dragToIndex)
                : 0;

            return (
            <React.Fragment key={table.id}>
              {/* 在适当位置显示插入点 */}
              {showInsertBefore && renderInsertIndicator()}
              
              {/* 参数表卡片 */}
              <div
                data-table-id={table.id}
                className={`shrink-0 overflow-hidden ${
                  isRemoving
                    ? 'w-0 opacity-0 -translate-x-3 scale-95 pointer-events-none transition-all duration-300 ease-out'
                    : isEntering
                      ? 'w-0 opacity-0 translate-x-3 scale-95 pointer-events-none'
                      : 'w-80 opacity-100 scale-100'
                }`}
                style={
                  !isRemoving && !isEntering
                    ? {
                        transform: `translateX(${dragShift}px)`,
                        transition: 'transform 220ms cubic-bezier(0.22, 1, 0.36, 1), width 300ms ease, opacity 300ms ease',
                      }
                    : undefined
                }
              >
              <div 
                className={`card p-5 w-80 shrink-0 transition-all duration-300 ease-out shadow-md hover:shadow-lg ${
                  isDragging
                    ? 'opacity-20 scale-[0.98] ring-2 ring-dashed ring-brb-blue-300'
                    : justMovedTableId === table.id
                      ? 'ring-2 ring-brb-blue-500 ring-offset-2 shadow-xl shadow-brb-blue-200/60'
                      : ''
                }`}
                style={{ minHeight: '500px' }}
                onDragOver={(e) => handleDragOver(e, tableIndex)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, tableIndex)}
              >
              <div 
                className="flex items-center justify-between mb-4 cursor-move hover:bg-gray-50 p-2 -mx-2 rounded transition-colors"
                draggable="true"
                onDragStart={(e) => handleDragStart(e, tableIndex)}
                onDragEnd={handleDragEnd}
              >
                <h3 className="text-lg font-semibold text-gray-900 hover:text-brb-blue-600 transition-colors">
                  BRB {tableIndex + 1}参数
                </h3>
                <div className="flex items-center space-x-1">
                  <button
                    type="button"
                    title="复制参数表"
                    onClick={(e) => {
                      e.stopPropagation();
                      duplicateParameterTable(table.id);
                    }}
                    onDragStart={(e) => e.stopPropagation()}
                    className="text-brb-blue-600 hover:text-brb-blue-700 p-2 rounded"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  {parameterTables.length > 1 && (
                    <button
                      type="button"
                      title="删除参数表"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeParameterTable(table.id);
                      }}
                      onDragStart={(e) => e.stopPropagation()}
                      className="text-red-600 hover:text-red-700 p-2 rounded"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

            {/* 基本参数 */}
            <div className="space-y-3 mb-5 p-4 rounded-lg">
              {/* 选择截面 */}
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-1/3">选择截面</label>
                <select
                  className="w-2/3 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm"
                  value={normalizeSectionTemplate(table.template)}
                  onChange={(e) => updateParameterTable(table.id, 'template', e.target.value)}
                >
                  {SECTION_TEMPLATE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-3/5">屈服承载力：</label>
                <div className="flex items-center">
                  <input
                    type="number"
                    className="w-4/5 px-4 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                    style={{ MozAppearance: 'textfield' }}
                    onWheel={(e) => {
                    const target = e.target as HTMLInputElement;
                    target.blur();
                  }}
                  onDragStart={(e) => e.stopPropagation()}
                  value={table.designForce}
                  onChange={(e) => updateParameterTable(table.id, 'designForce', e.target.value)}
                  placeholder=""
                  />
                  <span className="ml-2 text-sm text-gray-600">KN</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-2/5">芯板材料：</label>
                <input
                  type="text"
                  className="w-3/5 px-4 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm"
                  onDragStart={(e) => e.stopPropagation()}
                  value={table.coreMaterial}
                  onChange={(e) => updateParameterTable(table.id, 'coreMaterial', e.target.value)}
                  placeholder="Q235B（如：Q235B、Q345B、LY160、LY225）"
                />
              </div>

              {(usesWangSectionDiagram(table.template)) ? (
                <WangSectionParams
                  variant={isShiSectionTemplate(table.template) ? 'shi' : 'wang'}
                  values={{
                    width: table.width,
                    height: table.height,
                    thickness: table.thickness,
                    weld: table.weld,
                    tubeWidth: table.tubeWidth,
                    tubeThickness: table.tubeThickness,
                  }}
                  designForce={table.designForce}
                  yieldStrength={table.yieldStrength || '294'}
                  onYieldStrengthChange={(value) => updateParameterTable(table.id, 'yieldStrength', value)}
                  onChange={(field, value) => updateParameterTable(table.id, field, value)}
                />
              ) : (
                <>
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-3/5">截面宽度：</label>
                <div className="flex items-center">
                  <input
                    type="number"
                    className="w-4/5 px-4 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                    style={{ MozAppearance: 'textfield' }}
                    onWheel={(e) => {
                    const target = e.target as HTMLInputElement;
                    target.blur();
                  }}
                  onDragStart={(e) => e.stopPropagation()}
                  value={table.width}
                  onChange={(e) => updateParameterTable(table.id, 'width', e.target.value)}
                  placeholder=""
                  />
                  <span className="ml-2 text-sm text-gray-600">mm</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-3/5">截面高度：</label>
                <div className="flex items-center">
                  <input
                    type="number"
                    className="w-4/5 px-4 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                    style={{ MozAppearance: 'textfield' }}
                    onWheel={(e) => {
                    const target = e.target as HTMLInputElement;
                    target.blur();
                  }}
                  onDragStart={(e) => e.stopPropagation()}
                  value={table.height}
                  onChange={(e) => updateParameterTable(table.id, 'height', e.target.value)}
                  placeholder=""
                  />
                  <span className="ml-2 text-sm text-gray-600">mm</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-3/5">板材厚度：</label>
                <div className="flex items-center">
                  <input
                    type="number"
                    className="w-4/5 px-4 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                    style={{ MozAppearance: 'textfield' }}
                    onWheel={(e) => {
                    const target = e.target as HTMLInputElement;
                    target.blur();
                  }}
                  onDragStart={(e) => e.stopPropagation()}
                  value={table.thickness}
                  onChange={(e) => updateParameterTable(table.id, 'thickness', e.target.value)}
                  placeholder=""
                  />
                  <span className="ml-2 text-sm text-gray-600">mm</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-3/5">焊缝高度：</label>
                <div className="flex items-center">
                  <input
                    type="number"
                    className="w-4/5 px-4 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                    style={{ MozAppearance: 'textfield' }}
                    onWheel={(e) => {
                    const target = e.target as HTMLInputElement;
                    target.blur();
                  }}
                  onDragStart={(e) => e.stopPropagation()}
                  value={table.weld}
                  onChange={(e) => updateParameterTable(table.id, 'weld', e.target.value)}
                  placeholder=""
                  />
                  <span className="ml-2 text-sm text-gray-600">mm</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-3/5">方管宽度：</label>
                <div className="flex items-center">
                  <input
                    type="number"
                    className="w-4/5 px-4 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                    style={{ MozAppearance: 'textfield' }}
                    onWheel={(e) => {
                    const target = e.target as HTMLInputElement;
                    target.blur();
                  }}
                  onDragStart={(e) => e.stopPropagation()}
                  value={table.tubeWidth}
                  onChange={(e) => updateParameterTable(table.id, 'tubeWidth', e.target.value)}
                  placeholder=""
                  />
                  <span className="ml-2 text-sm text-gray-600">mm</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-3/5">方管厚度：</label>
                <div className="flex items-center">
                  <input
                    type="number"
                    className="w-4/5 px-4 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                    style={{ MozAppearance: 'textfield' }}
                    onWheel={(e) => {
                    const target = e.target as HTMLInputElement;
                    target.blur();
                  }}
                  onDragStart={(e) => e.stopPropagation()}
                  value={table.tubeThickness}
                  onChange={(e) => updateParameterTable(table.id, 'tubeThickness', e.target.value)}
                  placeholder=""
                  />
                  <span className="ml-2 text-sm text-gray-600">mm</span>
                </div>
              </div>
                </>
              )}
            </div>

            {/* 长度-数量表格 */}
            <div className="mb-2">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-gray-700">长度-数量对应表</h4>
                <button
                  onClick={() => addLengthQuantityRow(table.id)}
                  className="flex items-center space-x-1 text-xs px-2 py-1 bg-brb-orange-100 hover:bg-brb-orange-200 text-gray-800 rounded"
                >
                  <Plus className="h-3 w-3" />
                  <span>添加行</span>
                </button>
              </div>
              
              <div id="generated-files-container" className="overflow-x-auto">
                <table className="w-full border-collapse rounded-lg overflow-hidden">
                  <thead>
                    <tr className="bg-brb-blue-100">
                      <th className="px-5 py-2 text-left text-sm font-semibold text-gray-800">
                        长度(mm)
                      </th>
                      <th className="px-4 py-2 text-left text-sm font-semibold text-gray-800">
                        数量(件)
                      </th>
                      <th className="px-2 py-2 text-center text-sm font-semibold text-gray-800 w-20">
                        操作
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.lengthQuantityTable.map((row, rowIndex) => (
                      <tr key={rowIndex} className="hover:bg-gray-50">
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            className="w-full px-3 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                            style={{ MozAppearance: 'textfield' }}
                            onWheel={(e) => {
                              const target = e.target as HTMLInputElement;
                              target.blur();
                            }}
                            onDragStart={(e) => e.stopPropagation()}
                            value={row.length}
                            onChange={(e) => updateLengthQuantityRow(table.id, rowIndex, 'length', e.target.value)}
                            placeholder="长度"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            className="w-full px-3 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm appearance-none [&::-webkit-inner-spin-button]:hidden [&::-webkit-outer-spin-button]:hidden [&::-ms-clear]:hidden"
                            style={{ MozAppearance: 'textfield' }}
                            onWheel={(e) => {
                              const target = e.target as HTMLInputElement;
                              target.blur();
                            }}
                            onDragStart={(e) => e.stopPropagation()}
                            value={row.quantity}
                            onChange={(e) => updateLengthQuantityRow(table.id, rowIndex, 'quantity', e.target.value)}
                            placeholder="数量"
                          />
                        </td>
                        <td className="px-3 py-2 text-center">
                          {table.lengthQuantityTable.length > 1 && (
                            <button
                              onClick={() => removeLengthQuantityRow(table.id, rowIndex)}
                              className="text-red-600 hover:text-red-700 p-1"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            </div>
            </div>
            </React.Fragment>
            );
          })}
          
          {/* 在容器末尾显示插入点（如果需要） */}
          {dragFromIndex !== null &&
           dragToIndex === parameterTables.length &&
           dragToIndex !== dragFromIndex &&
           dragToIndex !== dragFromIndex + 1 &&
           renderInsertIndicator()}
        </div>
      </div>
      
      {/* 生成图纸、材料单和方管排布图按钮 */}
      <div className="flex justify-end space-x-3 mt-4">
        <button 
          className="btn-primary flex items-center space-x-2 disabled:opacity-70 disabled:cursor-not-allowed"
          onClick={handleGenerateDrawings}
          disabled={isGeneratingDrawings}
        >
          <Download className="h-4 w-4" />
          <span>{isGeneratingDrawings ? '生成中...' : '生成图纸'}</span>
        </button>
        <button 
          className="btn-primary flex items-center space-x-2 disabled:opacity-70 disabled:cursor-not-allowed"
          onClick={handleGenerateMaterials}
          disabled={isGeneratingMaterials}
        >
          <Box className="h-4 w-4" />
          <span>{isGeneratingMaterials ? '生成中...' : '生成材料单'}</span>
        </button>
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
      </div>

      {isGeneratingTubeLayout && (
        <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 mt-3">
          <div className="font-medium">方管排布计算进行中 · {tubeLayoutElapsedSec} 秒</div>
          <div className="mt-1 text-blue-800">{tubeLayoutStatus || '正在启动排布计算…'}</div>
          <div className="mt-1 text-xs text-blue-600">大项目深度搜索可能需要 1～3 分钟，计时持续增加即为正常。</div>
        </div>
      )}
      
      {/* 下载列表 */}
      {generatedFiles.length > 0 && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">生成的文件列表</h2>
            <button 
              className="btn-secondary text-sm flex items-center space-x-1"
              onClick={async () => {
                try {
                  // 检查是否有文件可以下载
                  if (generatedFiles.length === 0) {
                    showToast('没有可下载的文件', 'info');
                    return;
                  }
                  
                  const downloadableFiles = generatedFiles
                    .map(file => ({
                      path: file.path || file.name,
                      name: file.name || getBaseName(file.path || ''),
                    }))
                    .filter(f => f.path && !f.path.startsWith('drawing_') && !f.path.startsWith('tube_layout_') && !f.path.startsWith('materials_'));

                  if (downloadableFiles.length === 0) {
                    showToast('当前文件尚未落盘，请先重新生成后再批量下载', 'error');
                    return;
                  }

                  // 批量下载已生成文件，避免再次触发后端生成
                  const response = await fetch('/api/download/batch', {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                      files: downloadableFiles,
                    })
                  });
                  
                  if (!response.ok) {
                    throw new Error('批量下载失败');
                  }
                  
                  // 处理ZIP文件下载
                  const blob = await response.blob();
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${projectName || 'generated_files'}.zip`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  window.URL.revokeObjectURL(url);
                  
                  showToast(`成功下载 ${downloadableFiles.length} 个文件`, 'success');
                } catch (error) {
                  console.error('批量下载出错:', error);
                  showToast('批量下载失败', 'error');
                }
              }}
            >
              <Download className="h-3 w-3" />
              <span>批量下载</span>
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50">
                  <th className="border border-gray-300 px-4 py-2 text-left text-sm font-semibold text-gray-700">文件名称</th>
                  <th className="border border-gray-300 px-4 py-2 text-left text-sm font-semibold text-gray-700">类型</th>
                  <th className="border border-gray-300 px-4 py-2 text-left text-sm font-semibold text-gray-700">操作</th>
                </tr>
              </thead>
              <tbody>
                {generatedFiles.map((file) => (
                  <tr key={file.id} className="hover:bg-gray-50" data-file-id={file.id}>
                    <td className="border border-gray-300 px-4 py-2 text-sm text-gray-900">
                      {file.name}
                    </td>
                    <td className="border border-gray-300 px-4 py-2 text-sm text-gray-600">
                      {file.type === 'drawing' ? '图纸' : file.type === 'tube_layout' ? '方管排布图' : '材料单'}
                    </td>
                    <td className="border border-gray-300 px-4 py-2 flex space-x-2">
                      <button 
                        className="btn-primary text-sm flex items-center space-x-1"
                        onClick={async () => {
                          try {
                            let response;
                            
                            // 根据文件类型调用不同的API端点
                            if (file.type === 'materials') {
                              // 材料单下载直接读取已生成文件，避免重复调用后端生成流程
                              const downloadTarget = file.path || file.name;
                              const downloadUrl = `/api/download/file?path=${encodeURIComponent(downloadTarget)}`;
                              response = await fetch(downloadUrl, {
                                method: 'GET',
                                headers: {
                                  'Content-Type': 'application/json',
                                }
                              });
                            } else if (file.type === 'tube_layout') {
                              // 方管排布图下载直接读取已生成文件，避免重复调用后端生成流程
                              const downloadTarget = file.path || file.name;
                              const downloadUrl = `/api/download/file?path=${encodeURIComponent(downloadTarget)}`;
                              response = await fetch(downloadUrl, {
                                method: 'GET',
                                headers: {
                                  'Content-Type': 'application/json',
                                }
                              });
                            } else {
                              // 图纸下载直接读取已生成文件，避免重复调用后端图纸生成流程
                              const downloadTarget = file.path || file.name;
                              const downloadUrl = `/api/download/file?path=${encodeURIComponent(downloadTarget)}`;
                              response = await fetch(downloadUrl, {
                                method: 'GET',
                                headers: {
                                  'Content-Type': 'application/json',
                                }
                              });
                            }
                            
                            if (!response.ok) {
                              throw new Error('文件下载失败');
                            }
                            
                            // 处理文件下载
                            const blob = await response.blob();
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = file.name;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            window.URL.revokeObjectURL(url);
                            
                            showToast(`文件 ${file.name} 下载成功`, 'success');
                          } catch (error) {
                            console.error('下载文件出错:', error);
                            showToast(`文件 ${file.name} 下载失败`, 'error');
                          }
                        }}
                      >
                        <Download className="h-3 w-3" />
                        <span>下载</span>
                      </button>
                      <button 
                        className="btn-danger text-sm flex items-center space-x-1"
                        onClick={async () => {
                          try {
                            // 对于使用虚拟路径的文件，不调用后端删除
                            const isVirtualPath = file.path.startsWith('drawing_') || file.path.startsWith('tube_layout_') || file.path.startsWith('materials_');
                            if (!isVirtualPath) {
                              // 对于实际保存到磁盘的图纸，调用后端API删除文件
                              const response = await fetch('/api/download/delete', {
                                method: 'POST',
                                headers: {
                                  'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({ filePath: file.path })
                              });
                              
                              if (!response.ok) {
                                throw new Error('文件删除失败');
                              }
                            }
                            
                            // 更新前端文件列表
                            setGeneratedFiles(prev => prev.filter(f => f.id !== file.id));
                            showToast(`文件 ${file.name} 删除成功`, 'success');
                          } catch (error) {
                            console.error('删除文件出错:', error);
                            showToast(`文件 ${file.name} 删除失败`, 'error');
                          }
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                        <span>删除</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default BrbDrawing;