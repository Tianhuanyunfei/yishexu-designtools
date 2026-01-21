import React, { useState, useEffect } from 'react';
import { Box, FolderOpen, Download, Plus, Trash2 } from 'lucide-react';
import { useToast } from '../components/Toast';

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

const BrbDrawing: React.FC = () => {
  // 从localStorage加载初始状态
  const loadInitialState = () => {
    try {
      const savedProjectName = localStorage.getItem('brb_drawing_projectName') || '';
      const savedTotalQuantity = parseInt(localStorage.getItem('brb_drawing_totalQuantity') || '0', 10);
      const savedParameterTables = localStorage.getItem('brb_drawing_parameterTables');
      
      const initialParameterTables = savedParameterTables ? 
        JSON.parse(savedParameterTables) as ParameterTable[] :
        [{
          id: '1',
          designForce: '',
          width: '',
          height: '',
          thickness: '',
          tubeWidth: '',
          tubeThickness: '',
          weld: '',
          coreMaterial: 'Q235B',
          template: '王一',
          lengthQuantityTable: [{ length: '', quantity: '' }]
        }];
      
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
          template: '王一',
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
  const [dragFromIndex, setDragFromIndex] = useState<number | null>(null);
  const [dragToIndex, setDragToIndex] = useState<number | null>(null);
  // 添加加载状态
  const [isGeneratingDrawings, setIsGeneratingDrawings] = useState(false);
  const [isGeneratingMaterials, setIsGeneratingMaterials] = useState(false);
  const [isGeneratingTubeLayout, setIsGeneratingTubeLayout] = useState(false);





  const updateParameterTable = (id: string, field: keyof ParameterTable, value: any) => {
    setParameterTables(parameterTables.map(table => 
      table.id === id ? { ...table, [field]: value } : table
    ));
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
      template: '王一',
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

  const removeParameterTable = (id: string) => {
    if (parameterTables.length > 1) {
      // 使用函数式更新，确保使用最新的状态
      setParameterTables(prevTables => {
        const updatedTables = prevTables.filter(table => table.id !== id);
        
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
    }
  };

  // 拖拽事件处理函数
  const handleDragStart = (e: React.DragEvent, index: number) => {
    e.dataTransfer.setData('text/plain', index.toString());
    setDragFromIndex(index);
    setDragToIndex(null);
    
    // 设置自定义拖拽预览，显示整个参数表
    const dragElement = e.currentTarget.closest('.card');
    if (dragElement) {
      // 创建一个克隆元素作为拖拽预览
      const clone = dragElement.cloneNode(true) as HTMLElement;
      // 设置克隆元素的样式
      clone.style.position = 'absolute';
      clone.style.top = '-10000px';
      clone.style.left = '-10000px';
      clone.style.opacity = '0.8';
      clone.style.width = '320px'; // 确保宽度与原卡片一致
      // 添加到DOM
      document.body.appendChild(clone);
      // 设置拖拽预览
      e.dataTransfer.setDragImage(clone, 10, 10);
      // 在拖拽结束后移除克隆元素
      setTimeout(() => {
        document.body.removeChild(clone);
      }, 0);
    }
  };

  const handleDragEnd = (e: React.DragEvent) => {
    setDragFromIndex(null);
    setDragToIndex(null);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const insertIndex = x < rect.width / 2 ? index : index + 1;
    setDragToIndex(insertIndex);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    const container = document.querySelector('.flex.space-x-6.min-w-max');
    if (container && !container.contains(e.relatedTarget as Node)) {
      setDragToIndex(null);
    }
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
    
    // 调整位置逻辑：如果从前面的位置拖拽到后面的位置，需要减去1
    let finalToIndex = toIndex;
    if (fromIndex < finalToIndex) {
      finalToIndex -= 1;
    }
    
    // 确保位置在有效范围内
    finalToIndex = Math.max(0, Math.min(finalToIndex, parameterTables.length));
    
    if (fromIndex !== finalToIndex) {
      const newTables = [...parameterTables];
      const [movedTable] = newTables.splice(fromIndex, 1);
      newTables.splice(finalToIndex, 0, movedTable);
      setParameterTables(newTables);
    }
    setDragFromIndex(null);
    setDragToIndex(null);
  };

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
            const newFiles: GeneratedFile[] = result.result.map((fileName: string, index: number) => ({
              id: Date.now().toString() + Math.random().toString(36).substring(2, 9) + index,
              name: fileName,
              path: `drawing_${Date.now()}_${index}.dxf`, // 生成一个虚拟路径用于下载标识
              type: 'drawing',
              tableIndex: index // 记录该文件对应的参数表索引
            }));
            
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
          const templateValue = table.template || '王一';
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
        
        // 获取文件名
        const contentDisposition = response.headers.get('content-disposition');
        let fileName = `${projectName}_材料单.xlsx`;
        if (contentDisposition) {
          const matches = /filename="([^"]+)"/.exec(contentDisposition);
          if (matches && matches[1]) {
            fileName = matches[1];
          }
        }
        
        // 将生成的材料单添加到下载列表
        const materialsFile: GeneratedFile = {
          id: Date.now().toString() + Math.random().toString(36).substring(2, 9),
          name: fileName,
          path: `materials_${Date.now()}.xlsx`, // 生成一个虚拟路径用于下载标识
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
        template: table.template || '王一',
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
      template: '王一',
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
            path: fileName,
            type: 'tube_layout',
            tableIndex: index
          }));

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
        let template = table.template || table.section_template || table.section || '王一';
        
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
          template: template.trim() || '王一',
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
        template: '王一',
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
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Box className="h-8 w-8 text-orange-600" />
          <h1 className="text-2xl font-bold text-gray-900">BRB图纸绘制</h1>
        </div>
        <div className="flex space-x-3">
          <button className="btn-secondary flex items-center space-x-2"
            onClick={() => handleNewProject()}
          >
            <Plus className="h-4 w-4" />
            <span>新建项目</span>
          </button>
          <button className="btn-secondary flex items-center space-x-2"
            onClick={() => handleOpenProject()}
          >
            <FolderOpen className="h-4 w-4" />
            <span>打开项目</span>
          </button>
          <button className="btn-secondary flex items-center space-x-2"
            onClick={() => handleSaveProject()}
          >
            <Box className="h-4 w-4" />
            <span>保存项目</span>
          </button>
        </div>
      </div>

      {/* 项目信息区域 */}
      <div className="card p-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex-1">
            <label className="form-label text-xl">项目名称</label>
            <input
              type="text"
              className="input-field"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="请输入项目名称"
            />
          </div>
          <div className="flex items-center justify-center min-w-[150px]">
            <div className="text-lg font-semibold text-brb-blue-600">
              BRB总数量: {totalQuantity}件
            </div>
          </div>
        </div>
      </div>

      {/* 参数表区域 */}
      {/* 添加参数表按钮（移到参数表上方） */}
      <div className="mb-4">
        <button
          onClick={addParameterTable}
          className="btn-secondary flex items-center justify-center space-x-2 py-2 px-4 text-sm"
        >
          <Plus className="h-3 w-3" />
          <span>添加参数表</span>
        </button>
      </div>
      
      <div className="overflow-x-auto pb-4">
        <div 
          className="flex space-x-6 min-w-max transition-all duration-300 ease-in-out"
          onDragOver={(e) => {
            e.preventDefault();
            
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
            e.preventDefault();
            const fromIndex = parseInt(e.dataTransfer.getData('text/plain'), 10);
            let toIndex = dragToIndex;
            
            if (toIndex === null) {
              toIndex = parameterTables.length;
            }
            
            // 调整位置：如果从前面拖拽到后面，需要减去1
            let finalToIndex = toIndex;
            if (fromIndex < finalToIndex) {
              finalToIndex -= 1;
            }
            
            if (fromIndex !== finalToIndex) {
              const newTables = [...parameterTables];
              const [movedTable] = newTables.splice(fromIndex, 1);
              newTables.splice(finalToIndex, 0, movedTable);
              setParameterTables(newTables);
            }
            setDragFromIndex(null);
            setDragToIndex(null);
          }}
        >
          {/* 渲染参数表和插入点 */}
          {parameterTables.map((table, tableIndex) => (
            <React.Fragment key={table.id}>
              {/* 在适当位置显示插入点 */}
              {dragToIndex !== null && 
               dragToIndex === tableIndex && 
               dragFromIndex !== tableIndex && (
                <div 
                  className="w-2 bg-brb-blue-500 rounded-full transition-all duration-300 ease-in-out"
                  style={{ height: '100%', marginRight: '16px' }}
                />
              )}
              
              {/* 参数表卡片 */}
              <div 
                className="card p-5 w-80 shrink-0 transition-all duration-300 ease-in-out shadow-md hover:shadow-lg"
                style={{ opacity: dragFromIndex === tableIndex ? 0.5 : 1, minHeight: '500px' }}
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
                {parameterTables.length > 1 && (
                  <button
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

            {/* 基本参数 */}
            <div className="space-y-3 mb-5 p-4 rounded-lg">
              {/* 选择截面 */}
              <div className="flex items-center justify-between">
                <label className="block text-base font-semibold text-gray-800 w-1/3">选择截面</label>
                <select
                  className="w-2/3 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brb-blue-500 focus:border-transparent transition-all duration-200 text-sm"
                  value={table.template}
                  onChange={(e) => updateParameterTable(table.id, 'template', e.target.value)}
                >
                  <option value="王一">王一</option>
                  <option value="王工">王工</option>
                  <option value="十一">十一</option>
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
            </React.Fragment>
          ))}
          
          {/* 在容器末尾显示插入点（如果需要） */}
          {dragToIndex !== null && 
           dragToIndex === parameterTables.length && (
            <div 
              className="w-2 bg-brb-blue-500 rounded-full transition-all duration-300 ease-in-out"
              style={{ height: '100%', marginLeft: '16px' }}
            />
          )}
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
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          <span>{isGeneratingTubeLayout ? '生成中...' : '生成方管排布图'}</span>
        </button>
      </div>
      
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
                  
                  // 验证并处理parameterTables，确保每个表都有有效的template和template_type值
                  // 后端的brb_materials.py函数需要template_type参数来区分模板类型
                  const validParameterTables = parameterTables.map(table => {
                    const templateValue = table.template || '王一';
                    return {
                      ...table,
                      template: templateValue, // 保持template字段
                      template_type: templateValue // 添加template_type字段，与template值相同
                    };
                  });

                  // 调用新的批量下载API，支持所有生成的文件
                  const response = await fetch('/api/brb/batch-download', {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                      projectName,
                      parameterTables: validParameterTables,
                      totalQuantity,
                      fileTypes: generatedFiles.map(file => file.type),
                      tableIndices: generatedFiles.map(file => file.tableIndex)
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
                  
                  showToast(`成功下载 ${generatedFiles.length} 个文件`, 'success');
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
                              // 对于材料单，重新调用生成API获取文件
                              // 验证并处理parameterTables，确保每个表都有有效的template和template_type值
                              const validParameterTables = parameterTables.map(table => {
                                const templateValue = table.template || '王一';
                                return {
                                  ...table,
                                  template: templateValue, // 保持template字段
                                  template_type: templateValue // 添加template_type字段，与template值相同
                                };
                              });
                              
                              response = await fetch('/api/brb/materials', {
                                method: 'POST',
                                headers: {
                                  'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                  projectName,
                                  parameterTables: validParameterTables,
                                  totalQuantity: totalQuantity
                                })
                              });
                            } else if (file.type === 'tube_layout') {
                              // 对于方管排布图，使用文件下载API
                              const downloadUrl = `/api/download/file?path=${encodeURIComponent(file.name)}`;
                              response = await fetch(downloadUrl, {
                                method: 'GET',
                                headers: {
                                  'Content-Type': 'application/json',
                                }
                              });
                              
                              // 如果API返回JSON，说明需要重新生成文件
                              if (response.headers.get('content-type')?.includes('application/json')) {
                                const errorData = await response.json();
                                if (errorData.status === 'error') {
                                  // 重新调用生成API获取文件
                                  // 验证并处理parameterTables，确保每个表都有有效的template和template_type值
                                  const validParameterTables = parameterTables.map(table => {
                                    const templateValue = table.template || '王一';
                                    return {
                                      ...table,
                                      template: templateValue, // 保持template字段
                                      template_type: templateValue // 添加template_type字段，与template值相同
                                    };
                                  });
                                  
                                  response = await fetch('/api/brb/tube-layout', {
                                    method: 'POST',
                                    headers: {
                                      'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({
                                      projectName,
                                      parameterTables: validParameterTables,
                                      totalQuantity: totalQuantity
                                    })
                                  });
                                }
                              }
                            } else {
                              // 对于图纸，只发送该文件对应的参数表
                              const tableIndex = file.tableIndex !== undefined ? file.tableIndex : 0;
                              
                              // 验证并处理parameterTables，确保每个表都有有效的template和template_type值
                              const validSingleParameterTable = [parameterTables[tableIndex]].map(table => {
                                const templateValue = table.template || '王一';
                                return {
                                  ...table,
                                  template: templateValue, // 保持template字段
                                  template_type: templateValue // 添加template_type字段，与template值相同
                                };
                              });
                              
                              // 计算该参数表的总数量
                              let singleTotalQuantity = 0;
                              validSingleParameterTable[0].lengthQuantityTable.forEach(row => {
                                const quantity = parseInt(row.quantity) || 0;
                                singleTotalQuantity += quantity;
                              });
                              
                              // 调用专门的API获取单个图纸文件流
                              response = await fetch('/api/brb/drawing-download', {
                                method: 'POST',
                                headers: {
                                  'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                  projectName,
                                  parameterTable: validSingleParameterTable[0],
                                  totalQuantity: singleTotalQuantity
                                })
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
                            // 对于材料单、使用虚拟路径的图纸和方管排布图，我们不需要调用后端API来删除文件
                            if (file.type !== 'materials' && !file.path.startsWith('drawing_') && !file.path.startsWith('tube_layout_')) {
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