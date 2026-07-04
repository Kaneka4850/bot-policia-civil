from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

# 1. Aqui você mudou o nome do arquivo para 'database-fbi.db'
DATABASE_URL = "sqlite:///database-fbi.db" 

# 2. O motor que faz a conexão
engine = create_engine(DATABASE_URL, echo=False)

# 3. A Base que seus modelos (Membro, Prisao) usam
Base = declarative_base()

# 🚀 O COMANDO QUE CRIA O ARQUIVO FÍSICO:
def init_db():
    # Importe seus modelos aqui para o SQLAlchemy saber o que criar
    # from database.models import Membro, Prisao, Advertencia, Ticket
    Base.metadata.create_all(bind=engine)
    print("✅ Arquivo 'database-fbi.db' e tabelas criados com sucesso!")

if __name__ == "__main__":
    init_db()