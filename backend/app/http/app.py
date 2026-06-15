"""Flask 入口。FLASK_APP=app.http.app 即可被 flask CLI 识别。
celery worker 入口：`celery -A app.http.app.celery worker`
"""
import dotenv
from flask_login import LoginManager
from flask_migrate import Migrate

from config import Config
from internal.middleware import Middleware
from internal.router import Router
from internal.server import Http
from pkg.sqlalchemy import SQLAlchemy

from .module import injector

# 1. 加载 .env
dotenv.load_dotenv()

# 2. 构建配置
conf = Config()

# 3. 装配 Http
app = Http(
    __name__,
    conf=conf,
    db=injector.get(SQLAlchemy),
    migrate=injector.get(Migrate),
    login_manager=injector.get(LoginManager),
    middleware=injector.get(Middleware),
    router=injector.get(Router),
)

# 4. 暴露 celery 让 worker 拿到（Phase 4 注册任务后才有可消费任务）
celery = app.extensions["celery"]


@app.cli.command("seed-bootstrap-account")
def seed_bootstrap_account():
    """幂等地按 BOOTSTRAP_ACCOUNT_EMAIL/PASSWORD 创建初始账号；未配置或已存在则跳过。"""
    from internal.service import AccountService

    email = app.config.get("BOOTSTRAP_ACCOUNT_EMAIL")
    password = app.config.get("BOOTSTRAP_ACCOUNT_PASSWORD")
    if not email or not password:
        print("[seed] BOOTSTRAP_ACCOUNT_EMAIL/PASSWORD 未配置，跳过")
        return
    account_service = injector.get(AccountService)
    if account_service.get_by_email(email):
        print(f"[seed] 账号已存在，跳过：{email}")
        return
    account_service.create_account(email=email, password=password, name="admin")
    print(f"[seed] 已创建初始账号：{email}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
