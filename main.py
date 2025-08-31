import os
from dotenv import load_dotenv
load_dotenv()
from fastapi.responses import PlainTextResponse,JSONResponse
import fastapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
import time
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Request, Query,Path
import os
import hashlib
from wechat_pay import WechatPayAPI
from util import *
from worker import process_image
import httpx
from fastapi import Request, HTTPException
from models import init_db
# main.py 顶部
# 2. 创建 Redis 连接池（全局复用）
from pydantic import BaseModel
import redis.asyncio as redis
r = redis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)

from pay import *
from menu import create_menu,delete_menu
from fastapi.responses import RedirectResponse
from llm import get_response
from datetime import datetime, timezone, timedelta
init_db()


app = FastAPI()

WECHAT_TOKEN = os.getenv("WECHAT_TOKEN")
APP_ID = os.getenv("WECHAT_APP_ID")
APP_SECRET = os.getenv("WECHAT_APP_SECRET")







@app.on_event("startup")
async def startup_event():
    await delete_menu()
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
    reply_content = ""
    # 解析 XML
    to_user = root.find("ToUserName").text
    from_user = root.find("FromUserName").text
    msg_type = root.find("MsgType").text
    create_time  = int(root.findtext("CreateTime"))
    if msg_type == "text":  # 文字
        content = root.find("Content").text
        reply_content = get_response(content)

    elif msg_type == "event":  # 关注
        event = root.findtext("Event")
        print(event)
        if event == "subscribe":
            print("用户关注")
            # 注册用户，或更新用户信息
            user_create_time = get_creat_time(from_user)
            if not user_create_time:
                create_or_set_points(from_user, 5)
                reply_content = f"欢迎使用位图转矢量工具，请把图片发给我，我会帮你转矢量！\n转1张图消耗1积分，赠送您5积分，您剩余{get_points(from_user)}积分。"
            else:
                # 如果是很久之前关注的用户，则送积分，否则不送
                cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                if user_create_time.replace(tzinfo=timezone.utc) < cutoff:
                    add_points(from_user, 5)
                    reply_content = f"欢迎回来，\n老用户赠送5积分，您剩余{get_points(from_user)}积分。"
                else:
                    reply_content = f"欢迎回来，\n您剩余{get_points(from_user)}积分。"
        elif event == "unsubscribe":
            print("用户取消关注")
            reply_content = f"再见！要记住我哦！你还会回来的吧？\n"
        # elif event == "VIEW": # 点击到充值页面
        #     return RedirectResponse("https://vectorizer.cn/pay?code={from_user}", status_code=302)
    elif msg_type == "image":  # 图片
        user_create_time = get_creat_time(from_user)
        if not user_create_time:  # 关注很久但第一次用
            create_or_set_points(from_user, 5)
            reply_content = f"欢迎使用位图转矢量工具，请把图片发给我，我会帮你转矢量！\n转1张图消耗1积分，老用户赠送您5积分，您剩余{get_points(from_user)}积分。"

        pic_url  = root.findtext("PicUrl")      # 图片 CDN 地址（有效期 3 天）
        # 组织任务包
        task_package = {
            "pic_url": pic_url,
            "openid": from_user,
            "domain_name": os.getenv("DOMAIN_NAME")
        }
        # 如果积分不够，则不处理
        if get_points(from_user) < 1:
            reply_content = f"您的积分不足，请充值后再试。\n"
        else:
            # 扣1积分
            add_points(from_user, -1)
            task = process_image.delay(task_package)   

            reply_content += f"收到图片！小矢正在为你转矢量化中，请稍后...\n目前，您剩余{get_points(from_user)}积分。"
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
from tenacity import retry, stop_after_attempt, wait_fixed
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
    # 存到redis里  
    return data["access_token"]


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def send_message(openid: str, result:dict) -> None:

    
    token = r.get('wx_access_token')
    if not token:
        token = await get_access_token()
        r.set('wx_access_token',token,ex=7200)
    """
    发送微信客服消息
    """
    # 2. 发客服文本给用户
    url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
    body = {
        "touser": openid,
        "msgtype": "text",
        "text": {"content": f"矢量化完成！请复制到浏览器打开并右键保存：\n{result.get('url')}"}
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=body)
        if r["error_code"]== 40001:
            # 微信 access_token 过期，重新获取
            token = await get_access_token()
            raise Exception("access_token expired")
        else:
            r.set('wx_access_token',token,ex=7200)
    return True

@app.post('/vec_notify/')
async def vec_notify(request: Request):
    payload = await request.json()
    openid  = payload.get("openid")
    result  = payload.get("result", {})
    return await send_message(openid,result)
    

@app.post('/get_openid/')
async def get_openid(request: Request):
    """
    获取用户 openid
    """

    # 假设用 FastAPI / Flask / Django 拿到 ?code=XXXX
    payload = await request.json()
    code  = payload.get("code")
    url = (
        "https://api.weixin.qq.com/sns/oauth2/access_token"
        f"?appid={APP_ID}&secret={APP_SECRET}&code={code}&grant_type=authorization_code"
    )

    r = httpx.get(url, timeout=10)
    data = r.json()
    openid = data["openid"] 
    return {"openid": openid}

@app.post('/api/order/make/')
async def make_order(request: Request):
    """
    接收用户下单请求
    """
    payload = await request.json()
    openid  = payload.get("openid")
    amount  = payload.get("amount")
    credits = payload.get("credits")

    print(f"用户 {openid} 下单 {amount} 元，需要 {credits} 积分")
    if credits == -1:
        # 包月
        s = build_order(openid,amount)
    else:
        # 按量付费
        s = build_order(openid,amount)

        return fastapi.Response(s)
@app.post('/wechat/notify/')
async def wechat_notify(request:Request):
    """微信支付结果通知"""
    if request.method == 'POST':
        try:
            # 获取微信支付回调数据
            xml_data = await request.body()
            print('收到支付回调,',xml_data)
            wechat_pay = WechatPayAPI()
            
            # 验证签名
            if not wechat_pay.verify_payment(xml_data):
                return fastapi.Response('<xml><return_code><![CDATA[FAIL]]></return_code></xml>')
            
            # 解析XML数据
            data = wechat_pay.parse_xml(xml_data)
            
            if data.get('return_code') == 'SUCCESS' and data.get('result_code') == 'SUCCESS':
                # 更新订单状态
                update_payment_by_order_id(order_id=data.get('out_trade_no'), status="Success")
                openid  = data.get('openid')
                # 新增积分
                info = get_payment(order_id=data.get('out_trade_no'))
                amount = float(info.amount)
                if amount == 0.01:        
                    add_points(openid, delta=20)
                elif amount == 19.99:
                    add_points(openid, delta=100)
                # # 1. 拿 token
                # token = await get_access_token()

                # # 2. 发客服文本给用户
                # url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
                # body = {
                #     "touser": openid,
                #     "msgtype": "text",
                #     "text": {"content": f"充值成功，您剩余{get_points(openid)}积分。"}
                # }

                # async with httpx.AsyncClient(timeout=10) as client:
                #     r = await client.post(url, json=body)
                # 对报文进行应答
                # return fastapi.Response(status_code=200)
                return PlainTextResponse(
                    content="<xml><return_code><![CDATA[SUCCESS]]></return_code><return_msg><![CDATA[OK]]></return_msg></xml>",
                    media_type="text/xml"
                )

            return fastapi.Response(status_code=403)
            
        except Exception as e:
            return fastapi.Response(status_code=403)
    
    return fastapi.Response(status_code=403)

@app.get("/api/order/status/{orderNo}/")
async def get_order_status(orderNo: str = Path(..., description="订单号")):
    """
    根据 orderNo 查询订单状态
    """
    try:
        order = get_payment(order_id=orderNo)
        print(order.status)
        if order.status == 'Success':
            return JSONResponse({
                'status': "paid"
            },status_code=200)
        else:
            return JSONResponse({
                'status': order.status
            },status_code=200)
    except:
        return JSONResponse({
        }, status_code=404) 


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8999)