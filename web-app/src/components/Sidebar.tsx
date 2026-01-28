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
  ChevronRight,
  ChevronLeft
} from 'lucide-react';

interface SidebarProps {
  visible: boolean;
  toggleSidebar: () => void;
  userRole?: string;
  userPermissions?: string[];
}

const Sidebar: React.FC<SidebarProps> = ({ visible, toggleSidebar, userRole = 'user', userPermissions = [] }) => {
  const location = useLocation();
  
  const [collapsedCategories, setCollapsedCategories] = React.useState<{ [key: string]: boolean }>({});
  
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
          color: 'text-blue-600',
          permission: null
        }
      ]
    },
    {
      category: '图纸绘制',
      items: [
        {
          name: 'BRB图纸绘制',
          path: '/brb-drawing',
          icon: Box,
          color: 'text-orange-600',
          permission: 'brb_drawing'
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
            color: 'text-blue-600',
            permission: 'vfd_period'
          },
          {
            name: 'BRB结构核算',
            path: '/brb-stability',
            icon: Shield,
            color: 'text-green-600',
            permission: 'brb_stability'
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
          color: 'text-purple-600',
          permission: 'dxf_csv'
        },
        {
          name: 'CSV转DXF',
          path: '/csv-to-dxf',
          icon: FileSpreadsheet,
          color: 'text-indigo-600',
          permission: 'csv_dxf'
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
          color: 'text-gray-600',
          permission: 'csv_editor'
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
          color: 'text-orange-600',
          permission: 'brb_designer'
        },
        {
          name: '粘滞产品设计',
          path: '/vfd-designer',
          icon: Zap,
          color: 'text-green-600',
          permission: 'vfd_designer'
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
          color: 'text-purple-600',
          permission: 'settings'
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
          color: 'text-gray-600',
          permission: null
        }
      ]
    }
  ];

  const hasPermission = (permission: string | null): boolean => {
    if (!permission) return true;
    if (userRole === 'admin') return true;
    return userPermissions.includes(permission);
  };

  const filterMenuItems = () => {
    return menuItems.map(category => ({
      ...category,
      items: category.items.filter(item => hasPermission(item.permission))
    })).filter(category => category.items.length > 0);
  };

  const filteredMenuItems = filterMenuItems();

  return (
    <aside 
      className={`fixed left-0 top-16 h-screen w-64 bg-white shadow-brb-lg border-r border-gray-200 z-40 transition-all duration-300 ease-in-out transform ${visible ? 'translate-x-0 opacity-100' : '-translate-x-full opacity-0 pointer-events-none'}`}
    >
      <nav className="p-4">
        <div className="space-y-4">
          {filteredMenuItems.map((menuCategory, categoryIndex) => {
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