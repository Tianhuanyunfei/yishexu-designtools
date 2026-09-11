import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  Box, 
  Zap, 
  FileText, 
  FileSpreadsheet, 
  Table,
  Calculator,
  Shield,
  Settings,
  ChevronDown
} from 'lucide-react';

// 版本更新记录接口
interface VersionUpdate {
  version: string;
  date: string;
  changes: string[];
}

const Dashboard: React.FC = () => {
  // 分类折叠状态管理
  const [collapsedCategories, setCollapsedCategories] = React.useState<{ [key: string]: boolean }>({});
  
  // 更新内容模态框显示状态
  const [showUpdateModal, setShowUpdateModal] = React.useState(false);
  
  // 权限检查相关状态
  const [toast, setToast] = useState<{ show: boolean; message: string; type: 'success' | 'error' }>({
    show: false,
    message: '',
    type: 'success',
  });
  
  // 使用认证上下文
  const { checkPermission } = useAuth();
  const navigate = useNavigate();
  
  // 检查权限并导航
  const handleFunctionClick = async (link: string, permission: string) => {
    const hasPerm = await checkPermission(permission);
    if (hasPerm) {
      navigate(link);
    } else {
      setToast({
        show: true,
        message: '您没有权限使用此功能，请联系管理员',
        type: 'error',
      });
    }
  };
  
  // 版本更新记录
  const versionUpdates: VersionUpdate[] = [
    {
      version: "3.4.0",
      date: "2026-08-25",
      changes: [
        "强化BRB方管排布算法",
        "优化BRB绘图界面与用户的交互"
      ]
    },
    {
      version: "3.3.0",
      date: "2026-05-19",
      changes: [
        "重构和强化方管排布算法"
      ]
    },
    {
      version: "3.2.0",
      date: "2026-03-12",
      changes: [
        "VFD频率计算器单位切换功能优化",
        "增加文件系统浏览系统",
        "增加文档编辑功能"
      ]
    },
    {
      version: "3.1.5",
      date: "2026-03-06",
      changes: [
        "优化BRB结构核算功能和计算逻辑",
        "Fcr2 改为套筒屈服力",
        "总屈曲强度增加混凝土的作用力",
        "材料型号改为下拉菜单，预设Q235、LY225、LY160、其他",
        "优化公式说明的变量表示"
      ]
    },
    {
      version: "3.1.4",
      date: "2026-03-04",
      changes: [
        "优化方管排布算法，提升排布效率",
        "改进方管排布图视觉效果",
      ]
    },
    {
      version: "3.1.3",
      date: "2026-01-29",
      changes: [
        "增加用户注册和登录功能",
        "添加权限管理系统，所有用户默认无权限",
        "允许2个字符的用户名",
        "实现密码修改功能",
        "用户数据存储在外部位置，避免更新时覆盖",
        "优化用户界面提示信息位置"
      ]
    },
    {
      version: "3.1.2",
      date: "2026-01-29",
      changes: [
        "整理日志系统，统一功能模块日志记录",
        "移除不再使用的日志文件，优化日志管理",
        "修复日志文件乱码问题，确保中文字符正常显示"
      ]
    },
    {
      version: "3.1.1",
      date: "2026-01-29",
      changes: [
        "修复方管排布图生成逻辑，解决内存流处理错误",
        "移除方管排布图文件名中的时间戳，优化批量下载体验"
      ]
    },
    {
      version: "3.1.0",
      date: "2026-01-21",
      changes: [
        "增加BRB方管自动排布功能"
      ]
    },
    {
      version: "3.0.3",
      date: "2026-01-19",
      changes: [
        "修改BRB挡板宽度，当方管为200时，挡板宽度为215",
        "修复BRB材料单中当截面为十字时，灌浆重量公式取值错误问题",
        "优化线型信息的读取写入功能，使其能正确处理图纸实际线型",
        "增加带密码验证的开发者工具功能"
      ]
    },
    {
      version: "3.0.2",
      date: "2026-01-15",
      changes: [
        "优化侧边栏显示，默认状态改为折叠",
        "添加顶部标题栏导航到主页功能"
      ]
    },
    {
      version: "3.0.1",
      date: "2026-01-15",
      changes: [
        "修复侧边栏与折叠按钮阴影显示问题",
        "BRB结构核算导出文件由csv改为excel",
        "修复BRB参数表无法拖动到指定位置bug"
      ]
    }
  ];
  
  // 切换分类折叠；id 可能是数字或字符串，统一按字符串存取
  const toggleCategory = (categoryId: string | number) => {
    const key = String(categoryId);
    setCollapsedCategories(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };
  
  const categories = [
    {
      id: 'drawing',
      name: '图纸绘制',
      functions: [
        {
          id: 'brb-drawing',
          title: 'BRB图纸绘制',
          description: '参数化生成BRB阻尼器图纸',
          icon: Box,
          color: 'bg-orange-500',
          link: '/brb-drawing',
          permission: 'brb.drawing'
        }
      ]
    },
    {
      id: 6,
      name: '设计计算',
      functions: [
        {
          id: 7,
          title: 'VFD频率计算',
          description: '计算黏滞阻尼器的周期频率相关参数',
          icon: Calculator,
          color: 'bg-blue-500',
          link: '/vfd-period-frequency',
          permission: 'vfd.calculate'
        },
        {
          id: 8,
          title: 'BRB结构核算',
          description: '核算屈曲约束支撑（BRB）屈服力及稳定性',
          icon: Shield,
          color: 'bg-green-500',
          link: '/brb-stability',
          permission: 'brb.calculate'
        }
      ]
    },
    {
      id: 'file-system',
      name: '文件系统',
      functions: [
        {
          id: 'test-files',
          title: '试验文件',
          description: '管理和查看试验文件',
          icon: FileText,
          color: 'bg-orange-500',
          link: '/test-files',
          permission: 'file.test'
        }
      ]
    },
    {
      id: 3,
      name: '数据处理',
      functions: [
        {
          id: 3,
          title: 'DXF转CSV',
          description: '将DXF文件转换为CSV格式',
          icon: FileText,
          color: 'bg-purple-500',
          link: '/dxf-to-csv',
          permission: 'convert.dxf_to_csv'
        },
        {
          id: 4,
          title: 'CSV转DXF',
          description: '将CSV文件转换为DXF格式',
          icon: FileSpreadsheet,
          color: 'bg-indigo-500',
          link: '/csv-to-dxf',
          permission: 'convert.csv_to_dxf'
        },
        {
          id: 5,
          title: 'CSV编辑器',
          description: '在线编辑CSV文件数据',
          icon: Table,
          color: 'bg-blue-500',
          link: '/csv-editor',
          permission: 'edit.csv'
        },
        {
          id: 'excel-editor',
          title: 'Excel编辑器',
          description: '在线编辑Excel文件数据',
          icon: FileSpreadsheet,
          color: 'bg-green-500',
          link: '/excel-data-editor',
          permission: 'edit.excel'
        }
      ]
    },
    {
      id: 5,
      name: '开发中',
      functions: [
        {
          id: 'brb-connector-drawing',
          title: 'BRB连接件绘制',
          description: '参数化生成BRB连接件图纸',
          icon: Box,
          color: 'bg-blue-500',
          link: '/brb-connector-drawing',
          permission: 'brb.connector.drawing'
        },
        {
          id: 2,
          title: '粘滞产品设计',
          description: '粘滞阻尼器参数化设计',
          icon: Zap,
          color: 'bg-green-500',
          link: '/vfd-designer',
          permission: 'vfd.designer'
        }
      ]
    },
    {
      id: 4,
      name: '系统设置',
      functions: [
        {
          id: 6,
          title: '系统设置',
          description: '配置系统参数和偏好设置',
          icon: Settings,
          color: 'bg-purple-500',
          link: '/settings',
          permission: 'system.settings'
        }
      ]
    }
  ];

  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      {/* 页面标题 */}
      <div className="max-w-7xl mx-auto mb-12 relative">
        <h1 className="text-3xl font-bold text-gray-900">阻尼器设计工具集</h1>
        <div className="mt-2 flex items-center justify-between">
          <p className="text-lg text-gray-600">专业的阻尼器辅助设计平台</p>
          <div className="flex items-center space-x-2">
            <div className="bg-brb-blue-100 text-brb-blue-800 px-3 py-1 rounded-full text-sm font-medium">
              版本 {versionUpdates[0].version}
            </div>
            {/* 更新内容按钮 */}
            <button
              onClick={() => setShowUpdateModal(!showUpdateModal)}
              className="bg-brb-blue-500 text-white px-3 py-1 rounded-full text-sm font-medium hover:bg-brb-blue-600 transition-colors duration-150 flex items-center space-x-1"
            >
              <span>更新内容</span>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </button>
          </div>
        </div>
        
        {/* 更新内容悬浮框 */}
        {showUpdateModal && (
          <div className="absolute top-full right-0 mt-2 w-80 bg-white shadow-lg rounded-lg border border-gray-200 z-50 p-4">
            <div className="flex justify-between items-start mb-3">
              <h3 className="text-lg font-semibold text-gray-900">版本更新内容</h3>
              <button
                onClick={() => setShowUpdateModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {/* 所有版本更新记录 */}
            <div className="space-y-6 max-h-96 overflow-y-auto pr-2">
              {versionUpdates.map((update, index) => (
                <div key={index} className="border-b border-gray-100 pb-3 last:border-b-0 last:pb-0">
                  <div className="flex justify-between items-center mb-2">
                    <h4 className="font-medium text-brb-blue-600">{update.version}</h4>
                    <span className="text-xs text-gray-500">{update.date}</span>
                  </div>
                  <div className="space-y-1 text-sm text-gray-700">
                    {update.changes.map((change, changeIndex) => (
                      <div key={changeIndex} className="flex items-start space-x-2">
                        <span className="text-brb-blue-500 font-medium">•</span>
                        <span>{change}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 分类功能区域 */}
      <div className="max-w-7xl mx-auto space-y-12">
        {categories.map((category) => {
          const isCollapsed = Boolean(collapsedCategories[String(category.id)]);
          return (
          <div key={category.id} className="space-y-6">
            {/* 分类标题 */}
            <div className="flex items-center space-x-3">
              <div className="text-xl font-bold text-gray-900">{category.name}</div>
              <button 
                type="button"
                className="flex items-center justify-center w-10 h-10 bg-brb-blue-100 hover:bg-brb-blue-200 text-brb-blue-600 hover:text-brb-blue-800 transition-all duration-300 rounded-full"
                onClick={() => toggleCategory(category.id)}
                aria-expanded={!isCollapsed}
              >
                <ChevronDown className={`h-6 w-6 transition-transform duration-300 ${isCollapsed ? '-rotate-90' : ''}`} />
              </button>
            </div>

            {/* 功能方块 */}
            <div 
              className={`grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 overflow-hidden transition-all duration-300 ease-in-out ${isCollapsed ? 'max-h-0 opacity-0' : 'max-h-96 opacity-100'}`}
            >
              {category.functions.map((func) => (
                <button
                  key={func.id}
                  onClick={() => handleFunctionClick(func.link, func.permission)}
                  className="group relative overflow-hidden bg-white border border-gray-200 rounded-xl hover:shadow-xl transition-all duration-300 hover:-translate-y-1 w-full text-left"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-50 to-purple-50 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                  <div className="relative p-6">
                    <div className="flex flex-col items-center text-center">
                      <div className={`p-4 rounded-xl ${func.color} text-white shadow-lg group-hover:scale-110 transition-transform duration-300 mb-4`}>
                        <func.icon className="h-8 w-8" />
                      </div>
                      <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors duration-300 mb-2">
                        {func.title}
                      </h3>
                      <p className="text-sm text-gray-500">{func.description}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
          );
        })}
      </div>

      {toast.show && (
        <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
          <div className={`bg-${toast.type === 'success' ? 'green' : 'red'}-500 text-white px-4 py-2 rounded-md shadow-lg flex items-center space-x-2`}>
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={toast.type === 'success' ? "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" : "M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"} />
            </svg>
            <span>{toast.message}</span>
            <button
              onClick={() => setToast({ ...toast, show: false })}
              className="ml-2 text-white hover:opacity-80"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;