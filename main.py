import fastapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
import time
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Request, Query
import os
import hashlib
from dotenv import load_dotenv

from util import *
from worker import process_image
import httpx
from fastapi import Request, HTTPException
from models import init_db
# main.py 顶部
import asyncio
from menu import create_menu
from datetime import datetime, timezone
init_db()


load_dotenv()
app = FastAPI()

WECHAT_TOKEN = os.getenv("WECHAT_TOKEN")
APP_ID = os.getenv("WECHAT_APP_ID")
APP_SECRET = os.getenv("WECHAT_APP_SECRET")

@app.on_event("startup")
async def startup_event():
    await create_menu()

# 处理微信服务器验证（GET）
@app.get("/wx-server/msg/")
async def wechat_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    """
    微信服务器首次验证接口
    """
    tmp_str = "".join(sorted([WECHAT_TOKEN, timestamp, nonce]))
    hash_str = hashlib.sha1(tmp_str.encode()).hexdigest()
    if hash_str == signature:
        return int(echostr)
    return "fail"


@app.post('/wx-server/msg/')
async def get_wx_message(request: Request):
    """
    接收微信服务器推送的消息
    """
    xml_data = await request.body()
    root = ET.fromstring(xml_data)

    # 解析 XML
    to_user = root.find("ToUserName").text
    from_user = root.find("FromUserName").text
    msg_type = root.find("MsgType").text
    create_time  = int(root.findtext("CreateTime"))
    print(f"收到来自 {from_user} 的 {msg_type} 消息，时间戳：{create_time}")
    if msg_type == "text":  # 文字
        content = root.find("Content").text
        reply_content = f"你说了：{content}"


    elif msg_type == "event":  # 关注
        event = root.findtext("Event")
        if event == "subscribe":
            print("用户关注")
            # 注册用户，或更新用户信息
            user_info = get_points(from_user)
            if not user_info:
                create_or_set_points(from_user, 5)
                reply_content = f"欢迎使用位图转矢量工具，请把图片发给我，我会帮你转矢量！\n转1张图消耗1积分，赠送您5积分，您剩余{get_points(from_user)}积分。"
            else:
                # 如果是很久之前关注的用户，则送积分，否则不送
                if (datetime.now(timezone.utc) - user_info.updated_at).days > 30:
                    add_points(from_user, 5)
                    reply_content = f"欢迎回来，\n老用户赠送5积分，您剩余{get_points(from_user)}积分。"
                else:
                    reply_content = f"欢迎回来，\n您剩余{get_points(from_user)}积分。"
        elif event == "unsubscribe":
            print("用户取消关注")
            reply_content = f"再见！要记住我哦！你还会回来的吧？\n"
    elif msg_type == "image":  # 图片
        pic_url  = root.findtext("PicUrl")      # 图片 CDN 地址（有效期 3 天）
        # 组织任务包
        task_package = {
            "pic_url": pic_url,
            "openid": from_user,
            "domain_name": os.getenv("DOMAIN_NAME")
        }
        task = process_image.delay(task_package)   

        reply_content = f"收到图片！小矢正在为你插队转矢量化中，请稍后...\n"
    else:
        reply_content = "暂不支持此类型消息"

    # 构造返回 XML
    reply_xml = f"""
    <xml>
        <ToUserName><![CDATA[{from_user}]]></ToUserName>
        <FromUserName><![CDATA[{to_user}]]></FromUserName>
        <CreateTime>{int(time.time())}</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[{reply_content}]]></Content>
    </xml>
    """
    return fastapi.Response(content=reply_xml, media_type="application/xml")


import httpx
from aiocache import cached, Cache
from aiocache.serializers import JsonSerializer
@cached(
    ttl=7000,                     # 官方 7200s，提前 200s 刷新
    cache=Cache.REDIS,
    key="wechat_access_token",
    serializer=JsonSerializer(),
    endpoint="127.0.0.1", port=6379, db=0
)
async def get_access_token() -> str:
    """
    如果 Redis 里没有或已过期，则真正去微信服务器拿
    """
    url = (
        "https://api.weixin.qq.com/cgi-bin/token"
        f"?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        data = resp.json()
    if "access_token" not in data:
        raise HTTPException(status_code=502, detail=data)
    return data["access_token"]

@app.post('/vec_notify/')
async def vec_notify(request: Request):
    """
    接收矢量化结果
    期望 JSON:
    {
      "task_id": "...",
      "openid": "...",
      "result": {"url":"https://..."}
    }
    """
    payload = await request.json()
    openid  = payload.get("openid")
    result  = payload.get("result", {})

    # 1. 拿 token
    token = await get_access_token()

    # 2. 发客服文本给用户
    url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
    body = {
        "touser": openid,
        "msgtype": "text",
        "text": {"content": f"矢量化完成！下载地址：{result.get('url')}"}
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=body)
    return {"status": "ok", "wx_resp": r.json()}


 

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8999)