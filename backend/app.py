"""
应用启动入口（兼容 `python app.py` / Docker 等）。

业务路由与工厂函数在 `app` 包内：`app.create_app` → `app.routes.routes`。
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        debug=app.config.get("DEBUG", True),
        host=app.config.get("HOST", "0.0.0.0"),
        port=app.config.get("PORT", 8000),
    )
