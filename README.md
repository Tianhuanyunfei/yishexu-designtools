# yishexu-designtools 项目

yishexu-designtools 是一个用于CAD文件转换和设计工具的项目，包含后端API服务和前端网页应用。

## 项目结构

```
├── backend/               # 后端API服务
│   ├── app/              # 应用核心模块
│   │   ├── routes/       # 路由模块
│   │   ├── services/     # 业务逻辑模块
│   │   ├── utils/        # 工具函数
│   │   └── __init__.py   # 应用初始化
│   ├── config/           # 配置文件
│   ├── design/           # 设计相关功能模块
│   ├── uploads/          # 上传文件目录
│   ├── app.py            # 原始应用文件（已拆分）
│   ├── requirements.txt  # 依赖列表
│   ├── run.py            # 应用入口
│   └── .env              # 环境变量
├── web-app/              # 前端网页应用
│   ├── src/              # 源代码
│   ├── dist/             # 构建输出
│   ├── package.json      # 前端依赖
│   └── vite.config.ts    # Vite配置
└── README.md             # 项目说明文档
```

## 功能特性

### 后端API
- **健康检查**：API服务状态检查
- **BRB设计**：防屈曲支撑设计和图纸生成
- **VFD设计**：粘滞阻尼器设计和图纸生成
- **文件转换**：DXF与CSV文件之间的转换
- **CSV编辑**：CSV文件的解析和保存
- **文件下载**：单个文件和批量文件下载

### 前端应用
- 直观的用户界面
- 多种设计工具集成
- 文件上传和下载功能
- 实时预览和编辑

## 快速开始

### 后端服务

1. 进入后端目录：
```bash
cd backend
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 运行应用：
```bash
python run.py
```

### 前端应用

1. 进入前端目录：
```bash
cd web-app
```

2. 安装依赖：
```bash
npm install
```

3. 开发模式运行：
```bash
npm run dev
```

4. 构建生产版本：
```bash
npm run build
```

## 技术栈

- **后端**：Python, Flask, Flask-CORS, python-dotenv
- **前端**：React, TypeScript, TailwindCSS, Vite
- **依赖管理**：pip, npm

## 环境变量

后端服务使用以下环境变量（在.env文件中配置）：

- `DEVELOPER_PASSWORD`：开发者密码

## 注意事项

1. 确保Python版本为3.7及以上
2. 确保Node.js版本为14及以上
3. 首次运行时会自动创建uploads目录

## 许可证

MIT License
