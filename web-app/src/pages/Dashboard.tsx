import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Box, 
  Zap, 
  FileText, 
  FileSpreadsheet, 
  Table,
  Calculator,
  Shield,
  Settings,
  ChevronDown, 
  ChevronRight
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
  
  // 版本更新记录
  const versionUpdates: VersionUpdate[] = [
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
  
  // 切换分类的折叠状态
  const toggleCategory = (categoryId: number) => {
    setCollapsedCategories(prev => ({
      ...prev,
      [categoryId]: !prev[categoryId]
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
          link: '/brb-drawing'
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
          link: '/vfd-period-frequency'
        },
        {
          id: 8,
          title: 'BRB结构核算',
          description: '核算屈曲约束支撑（BRB）屈服力及稳定性',
          icon: Shield,
          color: 'bg-green-500',
          link: '/brb-stability'
        }
      ]
    },
    {
      id: 2,
      name: '文件转换',
      functions: [
        {
          id: 3,
          title: 'DXF转CSV',
          description: '将DXF文件转换为CSV格式',
          icon: FileText,
          color: 'bg-purple-500',
          link: '/dxf-to-csv'
        },
        {
          id: 4,
          title: 'CSV转DXF',
          description: '将CSV文件转换为DXF格式',
          icon: FileSpreadsheet,
          color: 'bg-indigo-500',
          link: '/csv-to-dxf'
        }
      ]
    },
    {
      id: 3,
      name: '数据处理',
      functions: [
        {
          id: 5,
          title: 'CSV编辑器',
          description: '在线编辑CSV文件数据',
          icon: Table,
          color: 'bg-blue-500',
          link: '/csv-editor'
        }
      ]
    },
    {
      id: 5,
      name: '开发中',
      functions: [
        {
          id: 1,
          title: 'BRB产品设计',
          description: '屈曲约束支撑参数化设计，包含屈服力及稳定性的核算',
          icon: Box,
          color: 'bg-orange-500',
          link: '/brb-designer'
        },
        {
          id: 2,
          title: '粘滞产品设计',
          description: '粘滞阻尼器参数化设计',
          icon: Zap,
          color: 'bg-green-500',
          link: '/vfd-designer'
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
          link: '/settings'
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
        {categories.map((category) => (
          <div key={category.id} className="space-y-6">
            {/* 分类标题 */}
            <div className="flex items-center space-x-3">
              <div className="text-xl font-bold text-gray-900">{category.name}</div>
              <button 
                className="flex items-center justify-center w-10 h-10 bg-brb-blue-100 hover:bg-brb-blue-200 text-brb-blue-600 hover:text-brb-blue-800 transition-all duration-300 rounded-full"
                onClick={() => toggleCategory(Number(category.id))}
              >
                {collapsedCategories[category.id] ? <ChevronRight className="h-6 w-6 font-bold" /> : <ChevronDown className="h-6 w-6 font-bold" />}
              </button>
            </div>

            {/* 功能方块 */}
            <div 
              className={`grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 overflow-hidden transition-all duration-300 ease-in-out ${collapsedCategories[category.id] ? 'max-h-0 opacity-0' : 'max-h-96 opacity-100'}`}
            >
              {category.functions.map((func) => (
                <Link
                  key={func.id}
                  to={func.link}
                  className="group relative overflow-hidden bg-white border border-gray-200 rounded-xl hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
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
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Dashboard;