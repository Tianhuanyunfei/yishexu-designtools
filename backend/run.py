# 应用入口
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(
        debug=app.config.get('DEBUG', True),
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 8000)
    )
