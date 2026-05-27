from sqlalchemy import create_engine, Column, String, Enum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
import uuid
import enum

class AssetType(enum.Enum):
    solar   = "solar"
    battery = "battery"
    ev      = "ev"
    wind    = "wind"

class AssetStatus(enum.Enum):
    active      = "active"
    inactive    = "inactive"
    fault       = "fault"
    maintenance = "maintenance"

class Base(DeclarativeBase):
    pass

class Users(Base):
    __tablename__   = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username        = Column(String(100), nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    assets = relationship("Assets", back_populates="user")

    def __repr__(self):
        return f"<User ID={self.id} name={self.username} created at={self.created_at}>"

class Assets(Base):
    __tablename__   = "assets"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            = Column(String(200), nullable=False)
    asset_type      = Column(Enum(AssetType), nullable=False)
    status          = Column(Enum(AssetStatus), nullable=False, default=AssetStatus.active)
    owner_id        = Column(UUID(as_uuid=True), ForeignKey(column="users.id"), nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="assets")

    def __repr__(self):
        return f"<Asset id={self.id} name={self.name} type={self.asset_type}>"
    

if __name__ == "__main__":
    print(AssetType.solar.value)                # solar
    print(AssetStatus.fault.value)     