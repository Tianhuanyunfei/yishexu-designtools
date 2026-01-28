import React, { useLocation } from 'react';
import { Navigate } from 'react-router-dom';

interface PermissionWrapperProps {
  children: React.ReactNode;
  requiredPermission?: string;
  userRole?: string;
  userPermissions?: string[];
}

export default function PermissionWrapper({
  children,
  requiredPermission,
  userRole,
  userPermissions = []
}: PermissionWrapperProps) {
  const location = useLocation();

  if (requiredPermission) {
    const isAdmin = userRole === 'admin';
    const hasPermission = isAdmin || (userPermissions && userPermissions.includes(requiredPermission));
    
    if (!hasPermission) {
      return (
        <div className="flex flex-col items-center justify-center h-64">
          <div className="bg-red-100 border border-red-400 text-red-700 px-8 py-6 rounded-lg shadow-md">
            <h2 className="text-xl font-bold mb-2">无权限访问</h2>
            <p className="mb-4">您没有权限访问此功能，请联系管理员开通权限。</p>
            <p className="text-sm text-gray-600">当前页面: {location.pathname}</p>
          </div>
          <a href="/" className="mt-4 text-blue-600 hover:text-blue-800 underline">
            返回主页
          </a>
        </div>
      );
    }
  }

  return <>{children}</>;
}
