from flask_migrate import Migrate

# render_as_batch=False：本项目以 MySQL 为准（CI/生产跑真实 MySQL），用原生 ALTER/CREATE INDEX，
# 不走 SQLite 风格的 batch 重建表，迁移 DDL 更干净、可预期。
migrate = Migrate(render_as_batch=False)
