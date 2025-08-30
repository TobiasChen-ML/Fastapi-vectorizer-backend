from __future__ import annotations
from sqlmodel import SQLModel, Field, Session, create_engine, select
from decimal import Decimal
from datetime import datetime,timezone
from typing import Optional

# 支付记录表
class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str                           # 用户标识（外键思路）
    amount: Decimal = Field(decimal_places=2, max_digits=10)
    currency: str = Field(default="CNY", max_length=3)
    status: str = Field(default="pending", max_length=20)  # pending / success / failed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# 用户积分/余额表
class Points(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    points: int = Field(default=0, ge=0)     # 积分
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

DATABASE_URL = "sqlite:///pay_points.db"
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)