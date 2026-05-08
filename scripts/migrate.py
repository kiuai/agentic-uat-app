from alembic.config import Config
from alembic import command

c = Config("alembic.ini")
command.upgrade(c, "head")
print("migrations ok")
