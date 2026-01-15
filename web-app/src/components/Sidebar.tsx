import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  Home, 
  LayoutDashboard, 
  Box, 
  Zap, 
  FileText, 
  FileSpreadsheet,
  Table,
  Calculator,
  Settings,
  HelpCircle,
  Shield,
  ChevronDown, 
  ChevronRight
} from 'lucide-react';

interface SidebarProps {
  visible: boolean;
}

const Sidebar: React.FC<SidebarProps> = ({ visible }) => {
  const location = useLocation();
  
  // 为每个分类添加折叠状态管理，默认都展开
  const [collapsedCategories, setCollapsedCategories] = React.useState<{ [key: string]: boolean }>({});
  
  // 切换分类的折叠状态
  const toggleCategory = (categoryIndex: string) => {
    setCollapsedCategories(prev => ({
      ...prev,
      [categoryIndex]: !prev[categoryIndex]
    }));
  };

  const menuItems = [
    {
      category: '主导航',
      items: [
        {
          name: '主页',
          path: '/',
          icon: Home,
          color: 'text-blue-600'
        }
      ]
    },
    {
      category: '图纸设计',
      items: [
        {
          name: 'BRB图纸设计',
          path: '/brb-drawing',
          icon: Box,
          color: 'text-orange-600'
        }
      ]
    },
    {
        category: '设计计算',
        items: [
          {
            name: 'VFD频率计算',
            path: '/vfd-period-frequency',
            icon: Calculator,
            color: 'text-blue-600'
          },
          {
            name: 'BRB稳定性核算',
            path: '/brb-stability',
            icon: Shield,
            color: 'text-green-600'
          }
        ]
      },
    {
      category: '文件转换',
      items: [
        {
          name: 'DXF转CSV',
          path: '/dxf-to-csv',
          icon: FileText,
          color: 'text-purple-600'
        },
        {
          name: 'CSV转DXF',
          path: '/csv-to-dxf',
          icon: FileSpreadsheet,
          color: 'text-indigo-600'
        }
      ]
    },
    {
      category: '数据处理',
      items: [
        {
          name: '编辑CSV文件',
          path: '/csv-editor',
          icon: Table,
          color: 'text-gray-600'
        }
      ]
    },
    {
      category: '开发中',
      items: [
        {
          name: 'BRB产品设计',
          path: '/brb-designer',
          icon: Box,
          color: 'text-orange-600'
        },
        {
          name: '粘滞产品设计',
          path: '/vfd-designer',
          icon: Zap,
          color: 'text-green-600'
        }
      ]
    },
    {
      category: '系统设置',
      items: [
        {
          name: '系统设置',
          path: '/settings',
          icon: Settings,
          color: 'text-purple-600'
        }
      ]
    },
    {
      category: '其他',
      items: [
        {
          name: '帮助文档',
          path: '/help',
          icon: HelpCircle,
          color: 'text-gray-600'
        }
      ]
    }
  ];

  return (
    <aside 
      className={`fixed left-0 top-16 h-screen w-64 bg-white shadow-brb-lg border-r border-gray-200 z-40 transition-all duration-300 ease-in-out transform ${visible ? 'translate-x-0 opacity-100' : '-translate-x-full opacity-0 pointer-events-none'}`}
    >
      <nav className="p-4">
        <div className="space-y-4">
          {menuItems.map((menuCategory, categoryIndex) => {
            return (
              <div key={categoryIndex}>
                {/* 分类标题（可点击，带折叠/展开图标） */}
                <button
                  className="flex items-center justify-between w-full px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider hover:text-gray-700 hover:bg-gray-50 rounded-lg transition-colors duration-150"
                  onClick={() => toggleCategory(categoryIndex.toString())}
                >
                  <span>{menuCategory.category}</span>
                  {collapsedCategories[categoryIndex.toString()] ? (
                    <ChevronRight className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </button>
                {/* 分类下的菜单项 */}
                <div 
                  className={`space-y-1 overflow-hidden transition-all duration-300 ease-in-out ${collapsedCategories[categoryIndex.toString()] ? 'max-h-0 opacity-0' : 'max-h-96 opacity-100'}`}
                >
                  {menuCategory.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.path;
                    
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${isActive
                        ? 'bg-brb-blue-50 text-brb-blue-700 border-r-4 border-brb-blue-600'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}
                      `}
                      >
                        <Icon className={`h-5 w-5 ${isActive ? 'text-brb-blue-600' : item.color}`} />
                        <span className="font-medium">{item.name}</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
          

        </div>
      </nav>
    </aside>
  );
};

export default Sidebar;