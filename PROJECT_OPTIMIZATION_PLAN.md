# 项目目录结构优化方案

## 1. 项目概述
当前项目是一个包含前端和后端的Web应用，主要功能包括设计工具和数据转换功能。前端使用React + TypeScript + Vite，后端使用Python Flask。

## 2. 当前结构分析

### 2.1 优点
- 已分离前后端代码（backend/ 和 web-app/）
- 前端使用现代技术栈（React + TypeScript + Vite）
- 后端核心功能已实现

### 2.2 存在的问题
- `backend/app.py` 文件过大（31KB），所有功能集中在一个文件
- `backend/requirements.txt` 内容不完整（仅15字节）
- 缺少项目级别的标准文件（README.md、LICENSE等）
- 目录结构可以更规范化，便于维护和扩展

## 3. 优化方案

### 3.1 项目根目录结构
```
yishexu-designtools/
├── backend/            # Python后端代码
│   ├── app/            # 应用核心代码
│   │   ├── __init__.py
│   │   ├── routes/     # 路由模块
│   │   ├── services/   # 业务逻辑
│   │   └── utils/      # 工具函数
│   ├── design/         # 设计相关模块
│   ├── config/         # 配置文件
│   ├── data/           # 数据文件（迁移到backend根目录）
│   ├── requirements.txt
│   └── run.py          # 应用入口
├── web-app/            # 前端代码
│   ├── src/            # 源代码
│   │   ├── components/ # 组件
│   │   ├── pages/      # 页面
│   │   ├── hooks/      # 自定义Hook
│   │   ├── services/   # API服务
│   │   ├── utils/      # 工具函数
│   │   └── types/      # TypeScript类型定义
│   ├── public/         # 静态资源
│   └── config/         # 配置文件
├── .gitignore          # Git忽略文件
├── README.md           # 项目说明文档
├── LICENSE             # 许可证
└── start_servers.ps1   # 启动脚本
```

### 3.2 后端优化
1. **拆分app.py**：将单个大文件拆分为多个模块
   - 路由模块（routes/）：处理API请求
   - 服务模块（services/）：实现业务逻辑
   - 工具模块（utils/）：通用工具函数
   - 配置模块（config/）：应用配置

2. **更新requirements.txt**：添加必要的依赖
   - Flask
   - Flask-CORS
   - 其他必要的Python库

3. **数据目录迁移**：将design/data/迁移到backend/data/

### 3.3 前端优化
1. **完善目录结构**：
   - 添加public/目录：存放静态资源
   - 添加types/目录：TypeScript类型定义
   - 添加hooks/目录：自定义React Hook
   - 添加services/目录：API服务封装

2. **配置文件整理**：确保所有配置文件正确配置

### 3.4 项目级别文件
1. **README.md**：项目说明文档
2. **LICENSE**：许可证文件
3. **.gitignore**：确保正确忽略node_modules、__pycache__等目录

## 4. 实施步骤

1. **重构backend目录结构**
2. **更新requirements.txt**
3. **完善web-app目录结构**
4. **修改代码中的路径引用**
5. **添加项目级别的标准文件**
6. **测试项目是否能正常运行**

## 5. 预期效果
- 代码结构更清晰，便于维护和扩展
- 依赖管理更完善
- 项目更符合现代Web应用的最佳实践
- 提高开发效率和代码质量