import requests
import os
import json
def get_access_token():
    """
    获取微信公众号 access_token
    """
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": os.getenv("WECHAT_APP_ID"),
        "secret": os.getenv("WECHAT_APP_SECRET")
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data.get("access_token")

def send_wechat_msg(openid, result_str,TOKEN):
    """
    发送微信公众号消息
    """
    url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={TOKEN}"
    data = {
        "touser": openid,
        "msgtype": "text",
        "text": {"content": result_str}
    }
    r = requests.post(url, json=data, timeout=5)
    print(r.json())   # {'errcode':0,'errmsg':'ok'}
    return r.json()


from sqlmodel import Session, select
from models import Points, engine
from typing import Optional
from sqlmodel import Session
from models import Payment, engine
from decimal import Decimal
from typing import List, Optional

def create_payment(user_id: str, amount: Decimal, currency="CNY", status="pending") -> Payment:
    with Session(engine) as s:
        p = Payment(user_id=user_id, amount=amount, currency=currency, status=status)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p

def get_payment(pay_id: int) -> Optional[Payment]:
    with Session(engine) as s:
        return s.get(Payment, pay_id)

def list_payments(user_id: str) -> List[Payment]:
    with Session(engine) as s:
        return s.exec(select(Payment).where(Payment.user_id == user_id)).all()

def update_payment(pay_id: int, **kwargs) -> Optional[Payment]:
    with Session(engine) as s:
        p = s.get(Payment, pay_id)
        if not p:
            return None
        for k, v in kwargs.items():
            setattr(p, k, v)
        s.commit()
        s.refresh(p)
        return p

def delete_payment(pay_id: int) -> bool:
    with Session(engine) as s:
        p = s.get(Payment, pay_id)
        if p:
            s.delete(p)
            s.commit()
            return True
        return False
    ##################################

def create_or_set_points(user_id: str, points: int) -> Points:
    with Session(engine) as s:
        rec = s.get(Points, user_id)
        if rec:
            rec.points = points
        else:
            rec = Points(user_id=user_id, points=points)
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return rec
    
def get_creat_time(user_id: str) -> Optional[int]:
    with Session(engine) as s:
        rec = s.get(Points, user_id)
        return rec.updated_at if rec else None
    
def get_points(user_id: str) -> Optional[int]:
    with Session(engine) as s:
        rec = s.get(Points, user_id)
        return rec.points if rec else None

def add_points(user_id: str, delta: int) -> int:
    """返回最新积分"""
    with Session(engine) as s:
        rec = s.get(Points, user_id) or Points(user_id=user_id, points=0)
        rec.points += delta
        s.add(rec)
        s.commit()
        return rec.points

def reset_points(user_id: str) -> bool:
    with Session(engine) as s:
        rec = s.get(Points, user_id)
        if rec:
            rec.points = 0
            s.add(rec)
            s.commit()
            return True
        return False