import React, { useState, useEffect } from 'react';
import { Shield, CheckCircle, AlertTriangle, Download, Plus, Trash2, ChevronsLeftRight } from 'lucide-react';
import { useToast } from '../components/Toast';

// 单行参数接口
interface BrbParamRow {
  rowId: string; // 行ID
  energySection: string; // 耗能面
  endSection: string; // 端面
  yieldForce: string; // 屈服力(kN)
  length: string; // 支撑长度(mm)
  coreWidth: string; // 芯板宽度(mm)
  coreHeight: string; // 芯板高度(mm)
  coreThickness: string; // 芯板厚度(mm)
  tubeWidth: string; // 套筒宽度(mm)
  tubeHeight: string; // 套筒高度(mm)
  tubeThickness: string; // 套筒厚度(mm)
  materialModel: string; // 材料型号
  elasticModulus: string; // 弹性模量(GPa)
  yieldStrength: string; // 屈服强度(MPa)
}

// 参数集接口
interface BrbStabilityParams {
  id: string; // 参数集ID
  rows: BrbParamRow[]; // 参数行数组
  concreteStrength: string; // 填充混凝土强度(MPa) - 全局参数
}

interface StabilityResult {
  id: string;
  slendernessRatio: number; // 长细比
  coreArea: number; // 芯板截面积(mm²)
  coreIy: number; // 芯板Iy(mm⁴)
  coreIz: number; // 芯板Iz(mm⁴)
  tubeArea: number; // 套筒截面积(mm²)
  tubeIy: number; // 套筒Iy(mm⁴)
  tubeIz: number; // 套筒Iz(mm⁴)
  fcr1: number; // Fcr1(kN)
  fcr2: number; // Fcr2(kN)
  fcr: number; // Fcr(kN)
  fcrFyRatio: number; // Fcr/Fy
  bucklingStrength: number; // 屈曲强度(kN)
  isStable: boolean; // 是否稳定
  safetyMargin: number; // 安全余量
  theoreticalFy: number; // 理论屈服力(kN)
  deviation: number; // 偏差(kN)
  deviationPercentage: number; // 偏差百分比(%)
}

const BrbStabilityChecker: React.FC = () => {
  // 从localStorage加载初始状态
  const loadInitialState = () => {
    try {
      const savedParamsList = localStorage.getItem('brbStabilityParamsList');
      if (savedParamsList) {
        // 解析保存的参数列表
        const savedList = JSON.parse(savedParamsList);
        // 转换旧数据格式，处理model字段
        const paramsList = savedList.map((paramSet: any) => {
          const updatedRows = paramSet.rows.map((row: any) => {
            // 如果行中有model字段，将其转换为energySection和endSection
            if (row.model) {
              let energySection = '';
              let endSection = '';
              
              // 根据model值确定耗能面和端面
              if (row.model === '王工') {
                energySection = '工';
                endSection = '王';
              } else if (row.model === '十一') {
                energySection = '丨';
                endSection = '十';
              }
              
              // 创建新行，移除model字段，添加energySection和endSection
              const { model, ...rest } = row;
              return {
                ...rest,
                energySection,
                endSection
              };
            }
            // 如果已经是新格式，直接返回
            return row;
          });
          
          return {
            ...paramSet,
            rows: updatedRows
          };
        }) as BrbStabilityParams[];
        
        return { 
          paramsList, 
          currentRowIndex: 0
        };
      } else {
        // 初始化为包含一个默认参数集和一行默认参数的列表
        const defaultParamRow: BrbParamRow = {
          rowId: '1',
          energySection: '工',
          endSection: '王',
          yieldForce: '',
          length: '',
          coreWidth: '',
          coreHeight: '',
          coreThickness: '',
          tubeWidth: '',
          tubeHeight: '',
          tubeThickness: '',
          materialModel: 'Q235',
          elasticModulus: '206',
          yieldStrength: '294'
        };
        
        const defaultParam: BrbStabilityParams = {
          id: '1',
          rows: [defaultParamRow],
          concreteStrength: '30'
        };
        
        return { 
          paramsList: [defaultParam], 
          currentRowIndex: 0
        };
      }
    } catch (error) {
      console.error('加载初始状态失败:', error);
      // 加载失败时返回默认状态
      const defaultParamRow: BrbParamRow = {
        rowId: '1',
        energySection: '工',
        endSection: '王',
        yieldForce: '',
        length: '',
        coreWidth: '',
        coreHeight: '',
        coreThickness: '',
        tubeWidth: '',
        tubeHeight: '',
        tubeThickness: '',
        materialModel: 'Q235',
        elasticModulus: '206',
        yieldStrength: '294'
      };
      
      const defaultParam: BrbStabilityParams = {
        id: '1',
        rows: [defaultParamRow],
        concreteStrength: '30'
      };
      
      return { 
        paramsList: [defaultParam], 
        currentRowIndex: 0
      };
    }
  };
  
  const initialState = loadInitialState();
  
  const [paramsList, setParamsList] = useState<BrbStabilityParams[]>(initialState.paramsList);
  const [currentRowIndex, setCurrentRowIndex] = useState<number>(initialState.currentRowIndex);
  const [results, setResults] = useState<Record<string, Record<string, StabilityResult>>>({}); // 使用参数集ID和行ID作为键存储结果
  const { showToast } = useToast();
  const [isCalculating, setIsCalculating] = useState(false);

  // 获取当前参数集（固定使用第一个参数集）
  const currentParamSet = paramsList[0];
  
  // 获取当前行参数
  const currentRow = currentParamSet?.rows[currentRowIndex];
  
  // 获取所有行参数
  const rows = currentParamSet?.rows || [];

  // 监听状态变化并保存到localStorage
  useEffect(() => {
    localStorage.setItem('brbStabilityParamsList', JSON.stringify(paramsList));
  }, [paramsList]);

  // 更新参数
  const updateParam = (rowId: string, field: keyof BrbParamRow, value: string) => {
    setParamsList(prev => {
      const newList = [...prev];
      const paramSet = { ...newList[0] };
      const updatedRows = paramSet.rows.map(row => {
        if (row.rowId === rowId) {
          // 如果更新的是材料型号，且值为Q235，则自动设置屈服强度为294
          if (field === 'materialModel' && value === 'Q235') {
            return { ...row, [field]: value, yieldStrength: '294' };
          }
          return { ...row, [field]: value };
        }
        return row;
      });
      paramSet.rows = updatedRows;
      newList[0] = paramSet;
      return newList;
    });
  };

  // 更新全局参数（如混凝土强度）
  const updateGlobalParam = (field: keyof BrbStabilityParams, value: string) => {
    setParamsList(prev => {
      const newList = [...prev];
      newList[0] = { ...newList[0], [field]: value };
      return newList;
    });
  };

  // 添加新行参数
  const addNewRow = () => {
    setParamsList(prev => {
      // 创建paramsList的深拷贝
      const newList = [...prev];
      const paramSet = { 
        ...newList[0],
        rows: [...newList[0].rows] // 深拷贝rows数组
      };
      
      // 生成新的行ID
      const maxRowId = Math.max(...paramSet.rows.map(r => parseInt(r.rowId)), 0);
      const newRowId = (maxRowId + 1).toString();
      
      // 创建新行（基于当前行）
      const currentRow = paramSet.rows[currentRowIndex] || paramSet.rows[0];
      const newRow: BrbParamRow = {
        ...currentRow,
        rowId: newRowId
      };
      
      // 使用新的数组，避免修改原始数组
      paramSet.rows = [...paramSet.rows, newRow];
      newList[0] = paramSet;
      return newList;
    });
    
    // 切换到新添加的行
    setCurrentRowIndex(prev => prev + 1);
    
    showToast('已添加新参数行', 'success');
  };

  // 删除指定行
  const deleteRow = (rowId: string) => {
    if (rows.length <= 1) {
      showToast('至少需要保留一行参数', 'error');
      return;
    }
    
    const rowIndexToDelete = rows.findIndex(row => row.rowId === rowId);
    if (rowIndexToDelete === -1) return;
    
    setParamsList(prev => {
      const newList = [...prev];
      const paramSet = { 
        ...newList[0],
        rows: [...newList[0].rows].filter(row => row.rowId !== rowId)
      };
      newList[0] = paramSet;
      return newList;
    });
    
    // 更新当前行索引
    if (currentRowIndex === rowIndexToDelete) {
      setCurrentRowIndex(prev => Math.min(prev, rows.length - 2));
    } else if (currentRowIndex > rowIndexToDelete) {
      setCurrentRowIndex(prev => prev - 1);
    }
    
    // 同时删除对应的结果
    setResults(prev => {
      const newResults = { ...prev };
      const paramSetResults = { ...newResults[currentParamSet.id] };
      if (paramSetResults) {
        delete paramSetResults[rowId];
        newResults[currentParamSet.id] = paramSetResults;
      }
      return newResults;
    });
    
    showToast('已删除参数行', 'success');
  };

  // 删除当前行（保留旧函数以兼容现有按钮）
  const deleteCurrentRow = () => {
    if (rows.length <= 1) {
      showToast('至少需要保留一行参数', 'error');
      return;
    }
    
    const rowToDelete = rows[currentRowIndex];
    if (rowToDelete) {
      deleteRow(rowToDelete.rowId);
    }
  };

  // 全部清空（保留一行默认参数）
  const clearAllRows = () => {
    // 创建默认行
    const defaultParamRow: BrbParamRow = {
      rowId: '1',
      energySection: '工',
      endSection: '王',
      yieldForce: '',
      length: '',
      coreWidth: '',
      coreHeight: '',
      coreThickness: '',
      tubeWidth: '',
      tubeHeight: '',
      tubeThickness: '',
      materialModel: 'Q235',
      elasticModulus: '206',
      yieldStrength: '294'
    };
    
    // 更新参数列表
    const updatedParamsList = [...paramsList];
    updatedParamsList[0] = {
      ...updatedParamsList[0],
      rows: [defaultParamRow]
    };
    
    setParamsList(updatedParamsList);
    
    // 重置当前行索引
    setCurrentRowIndex(0);
    
    // 清空结果
    const updatedResults = { ...results };
    delete updatedResults[currentParamSet.id];
    setResults(updatedResults);
    
    showToast('已清空所有参数行，保留一行默认参数', 'success');
  };

  // 监听参数变化，自动重新计算
  useEffect(() => {
    calculateStability();
  }, [paramsList]);

  // 监听结果变化，更新状态
  useEffect(() => {
    // 当结果更新时，不需要额外操作
  }, [results]);

  // 计算单个BRB行参数的稳定性
  const calculateRowStability = (rowId: string, rowParams: BrbParamRow): StabilityResult | null => {
    // 默认参数值映射表
    const defaultParams: Record<string, string> = {
      yieldForce: '5500',
      length: '2700',
      coreWidth: '200',
      coreHeight: '200',
      coreThickness: '35',
      tubeWidth: '250',
      tubeHeight: '250',
      tubeThickness: '4',
      elasticModulus: '206',
      yieldStrength: '294',
      materialModel: 'Q235'
    };

    try {
      // 转换为数值，使用默认值填充空字段
      const Fy = parseFloat(rowParams.yieldForce || defaultParams.yieldForce); // 屈服力(kN)
      const b = parseFloat(rowParams.coreWidth || defaultParams.coreWidth); // 芯板宽度(mm)
      const h = parseFloat(rowParams.coreHeight || defaultParams.coreHeight); // 芯板高度(mm)
      const t = parseFloat(rowParams.coreThickness || defaultParams.coreThickness); // 芯板厚度(mm)
      const f_y = parseFloat(rowParams.yieldStrength || defaultParams.yieldStrength); // 屈服强度(MPa)
      const E = parseFloat(rowParams.elasticModulus || defaultParams.elasticModulus) * 1000; // 弹性模量(MPa)
      const L = parseFloat(rowParams.length || defaultParams.length); // 支撑长度(mm)
      const B = parseFloat(rowParams.tubeWidth || defaultParams.tubeWidth); // 套筒宽度(mm)
      const H = parseFloat(rowParams.tubeHeight || defaultParams.tubeHeight); // 套筒高度(mm)
      const T = parseFloat(rowParams.tubeThickness || defaultParams.tubeThickness); // 套筒厚度(mm)

      // 计算芯板截面积(mm²)，根据截面类型使用不同公式
      let coreArea: number;
      if (rowParams.energySection === '工') {
        // 工字钢截面公式：2×翼缘面积 + 腹板面积
        coreArea = 2 * (b * t) + (h - 2 * t) * t;
      } else {
        // 丨字形截面公式：高度×厚度
        coreArea = h * t;
      }

      // 计算芯板惯性矩Iy和Iz(mm⁴)，根据截面类型使用不同公式
      let coreIy: number;
      let coreIz: number;
      
      if (rowParams.energySection === '工') {
        // 工字钢截面惯性矩计算公式
        const webHeight = h - 2 * t; // 腹板高度
        const webThickness = t; // 腹板厚度
        const flangeWidth = b; // 翼缘宽度
        const flangeThickness = t; // 翼缘厚度
        
        // Iz（绕z轴，弱轴） - 对应腹板方向（原Iy公式）
        coreIz = 
          (webHeight * Math.pow(webThickness, 3)) / 12 + // 腹板惯性矩
          2 * (flangeThickness * Math.pow(flangeWidth, 3)) / 12; // 翼缘惯性矩
        
        // Iy（绕y轴，强轴） - 对应翼缘方向（原Iz公式）
        coreIy = 
          (webThickness * Math.pow(webHeight, 3)) / 12 + // 腹板惯性矩
          2 * ((flangeWidth * Math.pow(flangeThickness, 3)) / 12 + // 翼缘自身惯性矩
          (flangeWidth * flangeThickness) * Math.pow((webHeight / 2 + flangeThickness / 2), 2)); // 翼缘平移惯性矩
      } else {
        // 丨字形截面惯性矩计算公式
        // Iz（绕z轴，弱轴）（原Iy公式）
        coreIz = (h * Math.pow(t, 3)) / 12;
        
        // Iy（绕y轴，强轴）（原Iz公式）
        coreIy = (t * Math.pow(h, 3)) / 12;
      }

      // 计算理论屈服力(kN) = 芯板截面积(mm²) * 屈服强度(MPa) / 1000
      const theoreticalFy = (coreArea * f_y) / 1000;
      
      // 计算套筒截面积(mm²) - 矩形空心截面
      const tubeArea = (B * H) - ((B - 2 * T) * (H - 2 * T));

      // 计算套筒惯性矩Iy和Iz(mm⁴) - 矩形空心截面
      const tubeIy = (H * Math.pow(B, 3)) / 12 - ((H - 2 * T) * Math.pow(B - 2 * T, 3)) / 12;
      const tubeIz = (B * Math.pow(H, 3)) / 12 - ((B - 2 * T) * Math.pow(H - 2 * T, 3)) / 12;

      // 计算长细比
      const i = Math.sqrt(coreIz / coreArea); // 回转半径
      const slendernessRatio = L / i;

      // 计算约束系数
      const k = 1.0; // 约束系数
      const PI = 3.14; // 取π为3.14

      // 计算Fcr1 - 欧拉临界力(kN) - 使用欧拉公式
      const fcr1 = (k * Math.pow(PI, 2) * E * coreIz) / (Math.pow(L, 2)) / 1000;

      // 计算Fcr2 - 套筒的欧拉临界力(kN) - 使用欧拉公式
      const fcr2 = (k * Math.pow(PI, 2) * E * tubeIz) / (Math.pow(L, 2)) / 1000;

      // 计算Fcr - 总屈曲强度(kN)
      const fcr = fcr1 + fcr2;

      // 计算Fcr/Fy比值，使用理论屈服力
      const fcrFyRatio = fcr / theoreticalFy;

      // 计算屈曲强度
      const bucklingStrength = fcr;

      // 安全余量(%)，使用理论屈服力，增加安全余量到1.2
      const safetyMargin = ((bucklingStrength / (theoreticalFy * 1.2)) - 1) * 100;

      // 判断是否稳定，Fcr/Fy ≥ 1.2 时为稳定（包含0.2的安全余量）
      const isStable = fcrFyRatio >= 1.2;
      
      // 计算偏差(kN) = 理论屈服力 - 输入屈服力
      const deviation = theoreticalFy - Fy;
      
      // 计算偏差百分比(%) = (偏差 / 输入屈服力) * 100
      const deviationPercentage = Fy !== 0 ? (deviation / Fy) * 100 : 0;

      // 创建结果对象
      const result: StabilityResult = {
        id: rowId,
        slendernessRatio: parseFloat(slendernessRatio.toFixed(2)),
        coreArea: parseFloat(coreArea.toFixed(0)),
        coreIy: parseFloat(coreIy.toFixed(0)),
        coreIz: parseFloat(coreIz.toFixed(0)),
        tubeArea: parseFloat(tubeArea.toFixed(0)),
        tubeIy: parseFloat(tubeIy.toFixed(0)),
        tubeIz: parseFloat(tubeIz.toFixed(0)),
        fcr1: parseFloat(fcr1.toFixed(0)),
        fcr2: parseFloat(fcr2.toFixed(0)),
        fcr: parseFloat(fcr.toFixed(0)),
        fcrFyRatio: parseFloat(fcrFyRatio.toFixed(2)),
        bucklingStrength: parseFloat(bucklingStrength.toFixed(2)),
        isStable,
        safetyMargin: parseFloat(safetyMargin.toFixed(2)),
        theoreticalFy: parseFloat(theoreticalFy.toFixed(0)),
        deviation: parseFloat(deviation.toFixed(0)),
        deviationPercentage: parseFloat(deviationPercentage.toFixed(2))
      };

      return result;
    } catch (error) {
      console.error(`计算行 ${rowId} 的BRB稳定性失败:`, error);
      return null;
    }
  };

  // 计算BRB稳定性
  const calculateStability = () => {
    setIsCalculating(true);

    try {
      // 计算所有行的稳定性
      const newResults = { ...results };
      const paramSetResults = newResults[currentParamSet.id] || {};
      
      // 遍历所有行参数
      rows.forEach(row => {
        const rowResult = calculateRowStability(row.rowId, row);
        if (rowResult) {
          paramSetResults[row.rowId] = rowResult;
        }
      });
      
      newResults[currentParamSet.id] = paramSetResults;
      setResults(newResults);

      showToast('稳定性核算完成', 'success');
    } catch (error) {
      console.error('计算失败:', error);
      showToast('计算失败，请检查输入参数', 'error');
    } finally {
      setIsCalculating(false);
    }
  };

  // 导出结果
  const exportResults = () => {
    const paramSetResults = results[currentParamSet.id];
    if (!paramSetResults || Object.keys(paramSetResults).length === 0) {
      showToast('没有可导出的结果', 'info');
      return;
    }

    // 创建更完整的导出数据结构
    const header = [
      '序号', '截面选择', '屈服力(kN)', '支撑长度(mm)', '芯板宽度(mm)', '芯板高度(mm)', '芯板厚度(mm)',
      '套筒宽度(mm)', '套筒高度(mm)', '套筒厚度(mm)',
      '材料型号', '弹性模量(GPa)', '屈服强度(MPa)',
      '芯板截面积(mm²)', '芯板Iy(mm⁴)', '芯板Iz(mm⁴)',
      '套筒截面积(mm²)', '套筒Iy(mm⁴)', '套筒Iz(mm⁴)',
      '长细比', 'Fcr1(kN)', 'Fcr2(kN)', 'Fcr(kN)', 'Fcr/Fy', '是否稳定', '安全余量(%)'
    ];

    // 数据行
    const rowsWithResults = rows.map((row, rowIndex) => {
      const result = paramSetResults[row.rowId];
      if (!result) return null;
      
      return [
        rowIndex + 1,
        `${row.energySection}${row.endSection}`,
        row.yieldForce,
        row.length,
        row.coreWidth,
        row.coreHeight,
        row.coreThickness,
        row.tubeWidth,
        row.tubeHeight,
        row.tubeThickness,
        row.materialModel,
        row.elasticModulus,
        row.yieldStrength,
        result.coreArea.toFixed(0),
        result.coreIy.toFixed(0),
        result.coreIz.toFixed(0),
        result.tubeArea.toFixed(0),
        result.tubeIy.toFixed(0),
        result.tubeIz.toFixed(0),
        result.slendernessRatio.toFixed(2),
        result.fcr1.toFixed(0),
        result.fcr2.toFixed(0),
        result.fcr.toFixed(0),
        result.fcrFyRatio.toFixed(2),
        result.isStable ? '是' : '否',
        result.safetyMargin.toFixed(2)
      ];
    }).filter(row => row !== null);

    // 创建CSV内容
    const csvContent = [
      header.join(','),
      ...rowsWithResults.map(row => row!.join(','))
    ].join('\n');

    // 创建Blob并下载
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `BRB稳定性核算结果_${new Date().toISOString().slice(0, 10)}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast('结果导出成功', 'success');
  };

  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* 页面标题 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            <Shield className="inline-block mr-3" />
            BRB稳定性核算
          </h1>
          <p className="mt-2 text-lg text-gray-600">
            用于计算屈曲约束支撑(BRB)的稳定性参数
          </p>
        </div>

        {/* 上下布局容器 */}
        <div className="grid grid-cols-1 gap-6 mb-10">
          {/* 上边：参数输入区域 */}
          <div className="bg-white rounded-lg shadow-md p-4">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-800 mb-2 sm:mb-0">输入参数</h2>
              
              {/* 参数管理控件 */}
              <div className="flex items-center space-x-2">
                {/* 添加按钮 */}
                <button
                  onClick={addNewRow}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-1 px-2 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-300 flex items-center text-xs"
                >
                  <Plus size={14} className="mr-1" />
                  添加行
                </button>
                
                {/* 全部清空按钮 */}
                <button
                  onClick={clearAllRows}
                  className="bg-red-600 hover:bg-red-700 text-white font-semibold py-1 px-2 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-all duration-300 flex items-center text-xs"
                >
                  <Trash2 size={14} className="mr-1" />
                  全部清空
                </button>
              </div>
            </div>
            
            {/* 输入参数表格 - 更紧凑的Excel风格 */}
            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-300">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" rowSpan={2} style={{ width: '50px' }}>序号</th>
                    {/* BRB型号 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={2}>BRB型号</th>
                    
                    {/* 截面大类 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={2}>截面</th>
                    
                    {/* 端面尺寸 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={3}>端面尺寸</th>
                    
                    {/* 套筒尺寸 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={3}>套筒尺寸</th>
                    
                    {/* 材料参数 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={3}>材料参数</th>
                    {/* 操作 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" rowSpan={2} style={{ width: '60px' }}>操作</th>
                  </tr>
                  <tr>
                    {/* BRB型号 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '80px' }}>屈服力</th>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '80px' }}>长度</th>
                    
                    {/* 截面小类 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '100px' }}>耗能面</th>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '100px' }}>端面</th>
                    
                    {/* 端面尺寸 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '70px' }}>宽</th>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '70px' }}>高</th>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '70px' }}>板厚</th>
                    
                    {/* 套筒尺寸 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '70px' }}>宽</th>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '70px' }}>高</th>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '50px' }}>壁厚</th>
                    
                    {/* 材料参数 */}
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '80px' }}>型号</th>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '70px' }}>E</th>
                    <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" style={{ width: '70px' }}>强度</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, rowIndex) => (
                    <tr key={row.rowId}>
                      <td className="px-2 py-1 border-b border-r border-gray-300 bg-gray-50 text-center text-xs">{rowIndex + 1}</td>
                      {/* BRB型号 */}
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.yieldForce}
                          onChange={(e) => updateParam(row.rowId, 'yieldForce', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="5500"
                        />
                      </td>
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.length}
                          onChange={(e) => updateParam(row.rowId, 'length', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="2700"
                        />
                      </td>
                      
                      <td className="px-2 py-1 border-b border-r border-gray-300 relative">
                        <select
                          value={row.energySection}
                          onChange={(e) => {
                            const newValue = e.target.value;
                            // 当选择耗能面时，自动设置端面
                            let endSectionValue = row.endSection;
                            if (newValue === '工') {
                              endSectionValue = '王';
                            } else if (newValue === '丨') {
                              endSectionValue = '十';
                            }
                            
                            // 使用updateParam函数更新energySection，它会自动触发calculateStability
                            updateParam(row.rowId, 'energySection', newValue);
                            // 使用updateParam函数更新endSection，它会自动触发calculateStability
                            // 由于React的批处理机制，这两次更新会合并，只触发一次重新渲染
                            updateParam(row.rowId, 'endSection', endSectionValue);
                          }}
                          className="w-full px-2 py-1 border border-gray-300 text-xs focus:outline-none appearance-none text-center pr-6 rounded-sm"
                          style={{ backgroundImage: 'url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 fill=%22none%22 viewBox=%220 0 16 16%22%3E%3Cpath stroke=%22%236b7280%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 stroke-width=%221.5%22 d=%22m4 6 4 4 4-4%22/%3E%3C/svg%3E")', backgroundPosition: 'right 0.3rem center', backgroundRepeat: 'no-repeat', backgroundSize: '1em 1em' }}
                        >
                          <option value="工">工</option>
                          <option value="丨">丨</option>
                        </select>
                      </td>
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="text"
                          value={row.endSection}
                          onChange={(e) => updateParam(row.rowId, 'endSection', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none text-center"
                          placeholder=""
                          readOnly
                        />
                      </td>
                      
                      {/* 端面尺寸 */}
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.coreWidth}
                          onChange={(e) => updateParam(row.rowId, 'coreWidth', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="200"
                        />
                      </td>
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.coreHeight}
                          onChange={(e) => updateParam(row.rowId, 'coreHeight', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="200"
                        />
                      </td>
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.coreThickness}
                          onChange={(e) => updateParam(row.rowId, 'coreThickness', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="35"
                        />
                      </td>
                      
                      {/* 套筒尺寸 */}
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.tubeWidth}
                          onChange={(e) => updateParam(row.rowId, 'tubeWidth', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="250"
                        />
                      </td>
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.tubeHeight}
                          onChange={(e) => updateParam(row.rowId, 'tubeHeight', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="250"
                        />
                      </td>
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.tubeThickness}
                          onChange={(e) => updateParam(row.rowId, 'tubeThickness', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="4"
                        />
                      </td>
                      
                      {/* 材料参数 */}
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="text"
                          value={row.materialModel}
                          onChange={(e) => updateParam(row.rowId, 'materialModel', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none text-center"
                          placeholder=""
                        />
                      </td>
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.elasticModulus}
                          onChange={(e) => updateParam(row.rowId, 'elasticModulus', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="206"
                        />
                      </td>
                      <td className="px-2 py-1 border-b border-r border-gray-300">
                        <input
                          type="number"
                          value={row.yieldStrength}
                          onChange={(e) => updateParam(row.rowId, 'yieldStrength', e.target.value)}
                          className="w-full px-2 py-1 border-0 text-xs focus:outline-none appearance-none text-center"
                          placeholder="294"
                        />
                      </td>
                      {/* 操作列 */}
                      <td className="px-2 py-1 border-b border-r border-gray-300 text-center">
                        <button
                          onClick={() => deleteRow(row.rowId)}
                          className="bg-red-500 hover:bg-red-600 text-white p-1 rounded-md transition-all duration-300 flex items-center justify-center"
                        >
                          <Trash2 size={12} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>


          </div>

          {/* 下边：结果显示区域 */}
          <div className="bg-white rounded-lg shadow-md p-4">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-lg font-semibold text-gray-800">核算结果</h2>
              <div className="flex space-x-2">
                <button
                  onClick={calculateStability}
                  disabled={isCalculating}
                  className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-md flex items-center text-xs"
                >
                  {isCalculating ? (
                    <span>核算中...</span>
                  ) : (
                    <>
                      <ChevronsLeftRight className="mr-1 h-3 w-3" />
                      刷新结果
                    </>
                  )}
                </button>
                {results[currentParamSet.id] && Object.keys(results[currentParamSet.id]).length > 0 && (
                  <button
                    onClick={exportResults}
                    className="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded-md flex items-center text-xs"
                  >
                    <Download className="mr-1 h-3 w-3" />
                    导出结果
                  </button>
                )}
              </div>
            </div>

            {results[currentParamSet.id] && Object.keys(results[currentParamSet.id]).length > 0 ? (
              <div className="space-y-3">
                {/* 结果表格 - 更紧凑的Excel风格 */}
                <div className="overflow-x-auto">
                  <table className="min-w-full border border-gray-300">
                    <thead className="bg-gray-100">
                      <tr>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">序号</th>
                        {/* 芯材截面参数 */}
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={3}>芯材截面参数</th>
                        
                        {/* 套筒结构参数 */}
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={3}>套筒结构参数</th>
                        
                        {/* 芯材屈服力核算 */}
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={2}>芯材屈服力核算</th>
                        
                        {/* 稳定性核算 */}
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800" colSpan={5}>稳定性核算</th>
                      </tr>
                      <tr>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800"></th>
                        {/* 芯材截面参数 */}
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">截面积</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Iy</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Iz</th>
                        
                        {/* 套筒结构参数 */}
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">截面积</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Iy</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Iz</th>
                        
                        {/* 芯材屈服力核算 */}
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Fy(理论)</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">偏差</th>
                        
                        {/* 稳定性核算 */}
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Fcr1</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Fcr2</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Fcr</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">Fcr/Fy</th>
                        <th className="px-2 py-1 border-b border-r border-gray-300 bg-gray-100 font-medium text-xs text-gray-800">是否稳定</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, rowIndex) => {
                        const result = results[currentParamSet.id][row.rowId];
                        if (!result) return null;
                        
                        return (
                          <tr key={row.rowId}>
                            <td className="px-2 py-1 border-b border-r border-gray-300 bg-gray-50 text-center text-xs">{rowIndex + 1}</td>
                            {/* 芯材截面参数 */}
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.coreArea}</td>
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.coreIy.toExponential(2)}</td>
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.coreIz.toExponential(2)}</td>
                            
                            {/* 套筒结构参数 */}
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.tubeArea}</td>
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.tubeIy.toExponential(2)}</td>
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.tubeIz.toExponential(2)}</td>
                            
                            {/* 芯材屈服力核算 */}
                            <td className={`px-2 py-1 border-b border-r border-gray-300 text-xs text-center ${Math.abs(result.deviationPercentage) <= 5 ? 'bg-green-100' : Math.abs(result.deviationPercentage) <= 10 ? 'bg-orange-100' : 'bg-red-100'}`}>{result.theoreticalFy}</td>
                            <td className={`px-2 py-1 border-b border-r border-gray-300 text-xs text-center ${Math.abs(result.deviationPercentage) <= 5 ? 'bg-green-100' : Math.abs(result.deviationPercentage) <= 10 ? 'bg-orange-100' : 'bg-red-100'}`}>{result.deviationPercentage}%</td>
                            
                            {/* 稳定性核算 */}
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.fcr1}</td>
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.fcr2}</td>
                            <td className="px-2 py-1 border-b border-r border-gray-300 text-xs text-center">{result.fcr}</td>
                            <td className={`px-2 py-1 border-b border-r border-gray-300 text-xs text-center ${result.fcrFyRatio >= 1.2 ? 'bg-green-100' : result.fcrFyRatio >= 1.0 ? 'bg-orange-100' : 'bg-red-100'}`}>{result.fcrFyRatio.toFixed(2)}</td>
                            <td className={`px-2 py-1 border-b border-r border-gray-300 text-xs text-center ${result.fcrFyRatio >= 1.2 ? 'bg-green-100 text-green-800' : result.fcrFyRatio >= 1.0 ? 'bg-orange-100 text-orange-800' : 'bg-red-100 text-red-800'}`}>
                              {result.isStable ? '是' : '否'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="bg-blue-50 p-3 rounded-md grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h3 className="text-xs font-medium text-blue-900 mb-1">计算说明</h3>
                    <ul className="text-xs text-blue-800 space-y-1">
                      <li>• 稳定性核心指标：Fcr/Fy 比值</li>
                      <li>• Fcr/Fy ≥ 1.2 时，支撑稳定</li>
                      <li>• Fcr/Fy &lt; 1.2 时，支撑不稳定</li>
                      <li>• 稳定判据中包含0.2的安全余量</li>
                      <li>• Q235的屈服强度取值为1.25倍，即294 MPa</li>
                    </ul>
                    
                    <h3 className="text-xs font-medium text-blue-900 mt-3 mb-1">单位说明</h3>
                    <ul className="text-xs text-blue-800 space-y-1">
                      <li>• 长度单位：毫米 (mm)</li>
                      <li>• 面积单位：平方毫米 (mm²)</li>
                      <li>• 惯性矩单位：毫米的四次方 (mm⁴)</li>
                      <li>• 力的单位：千牛 (kN)</li>
                      <li>• 强度单位：兆帕 (MPa)</li>
                      <li>• 弹性模量单位：吉帕 (GPa)</li>
                    </ul>
                  </div>
                  
                  <div>
                    <h3 className="text-xs font-medium text-blue-900 mb-1">公式说明</h3>
                    <ul className="text-xs text-blue-800 space-y-1">
                      <li>• 芯板截面积计算：</li>
                      <li>  - 工字形截面：2×(宽×板厚) + (高-2×板厚)×板厚</li>
                      <li>  - 丨字形截面：高度×厚度</li>
                      <li>• 惯性矩计算：</li>
                      <li>  - 工字形截面：分别计算腹板和翼缘的惯性矩并叠加</li>
                      <li>  - 丨字形截面：使用矩形截面惯性矩公式</li>
                      <li>• 欧拉临界力计算公式：Fcr = (k×π²×E×I)/(L²)/1000 (kN)</li>
                      <li>  - Fcr1 = 芯板的欧拉临界力</li>
                      <li>  - Fcr2 = 套筒的欧拉临界力</li>
                      <li>  - Fcr = Fcr1 + Fcr2 (总屈曲强度)</li>
                      <li>• 约束系数 k = 1.0（k为支撑的有效长度系数，根据支撑的约束条件确定，此处取1.0）</li>
                      <li>• π 取 3.14</li>
                    </ul>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 bg-gray-50 rounded-md">
                <Shield className="h-12 w-12 text-gray-400 mb-4" />
                <p className="text-gray-600 text-center">
                  请输入参数并点击"开始核算"按钮
                </p>
                <p className="text-sm text-gray-500 mt-2 text-center">
                  系统将自动计算BRB的稳定性参数
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BrbStabilityChecker;
