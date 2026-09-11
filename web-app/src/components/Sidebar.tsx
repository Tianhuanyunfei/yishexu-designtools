import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
import { useAuth } from '../context/AuthContext';

interface SidebarProps {
  visible: boolean;
  toggleSidebar: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ visible, toggleSidebar }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { checkPermission } = useAuth();
  
  // 为每个分类添加折叠状态管理，默认都展开
  const [collapsedCategories, setCollapsedCategories] = React.useState<{ [key: string]: boolean }>({});
  const [toast, setToast] = React.useState<{ show: boolean; message: string; type: 'success' | 'error' }>({
    show: false,
    message: '',
    type: 'success',
  });
  
  // 切换分类的折叠状态
  const toggleCategory = (categoryIndex: string) => {
    setCollapsedCategories(prev => ({
      ...prev,
      [categoryIndex]: !prev[categoryIndex]
    }));
  };
  
  // 检查权限并导航
  const handleMenuItemClick = async (path: string, permission?: string) => {
    // 主页不需要权限检查
    if (path === '/') {
      navigate(path);
      return;
    }
    
    // 其他页面需要检查权限
    if (permission) {
      const hasPerm = await checkPermission(permission);
      if (hasPerm) {
        navigate(path);
      } else {
        setToast({
          show: true,
          message: '您没有权限使用此功能，请联系管理员',
          type: 'error',
        });
      }
    } else {
      // 如果没有指定权限，默认不允许访问
      setToast({
        show: true,
        message: '您没有权限使用此功能，请联系管理员',
        type: 'error',
      });
    }
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
          permission: ''
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
          permission: 'brb.drawing'
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
            permission: 'vfd.calculate'
          },
          {
            name: 'BRB结构核算',
            path: '/brb-stability',
            icon: Shield,
            color: 'text-green-600',
            permission: 'brb.calculate'
          }
        ]
      },
    {
      category: '文件系统',
      items: [
        {
          name: '试验文件',
          path: '/test-files',
          icon: FileText,
          color: 'text-orange-600',
          permission: 'file.test'
        }
      ]
    },
    {
      category: '数据处理',
      items: [
        {
          name: 'DXF转CSV',
          path: '/dxf-to-csv',
          icon: FileText,
          color: 'text-purple-600',
          permission: 'convert.dxf_to_csv'
        },
        {
          name: 'CSV转DXF',
          path: '/csv-to-dxf',
          icon: FileSpreadsheet,
          color: 'text-indigo-600',
          permission: 'convert.csv_to_dxf'
        },
        {
          name: '编辑CSV文件',
          path: '/csv-editor',
          icon: Table,
          color: 'text-gray-600',
          permission: 'edit.csv'
        },
        {
          name: '编辑Excel文件',
          path: '/excel-data-editor',
          icon: FileSpreadsheet,
          color: 'text-green-600',
          permission: 'edit.excel'
        }
      ]
    },
    {
      category: '开发中',
      items: [
        {
          name: 'BRB连接件绘制',
          path: '/brb-connector-drawing',
          icon: Box,
          color: 'text-blue-600',
          permission: 'brb.connector.drawing'
        },
        {
          name: '粘滞产品设计',
          path: '/vfd-designer',
          icon: Zap,
          color: 'text-green-600',
          permission: 'vfd.designer'
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
          permission: 'system.settings'
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
          permission: ''
        }
      ]
    }
  ];

  return (
    <>
      <aside 
        className={`fixed left-0 top-12 h-[calc(100vh-3rem)] w-64 bg-white shadow-brb-lg border-r border-gray-200 z-40 transition-all duration-300 ease-in-out transform ${visible ? 'translate-x-0 opacity-100' : '-translate-x-full opacity-0 pointer-events-none'}`}
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
                        <button
                          key={item.path}
                          onClick={() => handleMenuItemClick(item.path, item.permission)}
                          className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${isActive
                          ? 'bg-brb-blue-50 text-brb-blue-700 border-r-4 border-brb-blue-600'
                          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}
                        `}
                        >
                          <Icon className={`h-5 w-5 ${isActive ? 'text-brb-blue-600' : item.color}`} />
                          <span className="font-medium">{item.name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
            

          </div>
        </nav>
      </aside>
      
      {/* Toast消息 */}
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
    </>
  );
};

export default Sidebar;