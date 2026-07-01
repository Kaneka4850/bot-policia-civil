from sqlalchemy.orm import Session
from services.membro_service import Prisao 
from services.membro_service import Membro
from services.membro_service import Advertencia

# 🔹 Membro
def criar_membro(db: Session, dados: dict) -> Membro:
    membro = Membro(**dados)
    db.add(membro)
    db.commit()
    db.refresh(membro)
    return membro

# 🔹 Prisão
def registrar_prisao(db: Session, dados: dict) -> Prisao:
    prisao = Prisao(**dados)
    db.add(prisao)
    db.commit()
    db.refresh(prisao)
    return prisao

# 🔹 Advertência
def aplicar_advertencia(db: Session, dados: dict) -> Advertencia:
    advertencia = Advertencia(**dados)
    db.add(advertencia)
    db.commit()
    db.refresh(advertencia)
    return advertencia
