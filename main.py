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
from wechat_pay.wechat_pay import WechatPayAPI
from util import *
from worker import process_image
import httpx
from fastapi import Request, HTTPException
import logging
from models import init_db
# main.py 顶部
# 2. 创建 Redis 连接池（全局复用）
from pydantic import BaseModel
import redis.asyncio as redis


from wechat_pay.pay import *
from menu import create_menu,delete_menu
from fastapi.responses import RedirectResponse
from llm import get_response
from datetime import datetime, timezone, timedelta
init_db()


app = FastAPI()

WECHAT_TOKEN = os.getenv("WECHAT_TOKEN")
APP_ID = os.getenv("WECHAT_APP_ID")
APP_SECRET = os.getenv("WECHAT_APP_SECRET")
FREE_CREDIT = int(os.getenv("FREE_CREDIT"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),   # 写文件
        logging.StreamHandler()          # 继续打终端
    ]
)

from redis import asyncio as aioredis
from fastapi_cache import FastAPICache


# prometheus + grafana monitor
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
http_request_duration = Histogram(
    "http_request_duration_seconds", "HTTP latency", ["method", "endpoint"]
)

# ② 中间件：统一记录请求量 & 延迟
@app.middleware("http")
async def add_prometheus_metrics(request, call_next):
    start = time.time()
    method = request.method
    path = request.url.path
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as e:
        status = 500
        raise e
    finally:
        http_requests_total.labels(method=method, endpoint=path, status=status).inc()
        http_request_duration.labels(method=method, endpoint=path).observe(time.time() - start)
    return response

# ③ 暴露 Prometheus 格式指标
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

KEY_DATE = 'free_date'
KEY_COUNT = 'counter'
r: Optional[aioredis.Redis] = None
tz = timezone(timedelta(hours=8)) 
from fastapi_cache.backends.redis import RedisBackend
@app.on_event("startup")
async def startup_event():
    await delete_menu()
    await create_menu()
    global r
    r = aioredis.from_url("redis://127.0.0.1:6379", db=0)   
    FastAPICache.init(RedisBackend(r), prefix="fc")
    await r.set(KEY_DATE, datetime.now(tz).strftime('%Y-%m-%d'))
    await r.set(KEY_COUNT, 1)

async def get_counter():
    """
    返回今天已用的 counter，如果跨天则自动清零。
    返回值：当前 counter
    """
    TODAY = datetime.now(tz).strftime('%Y-%m-%d')
    # 取出上次记录的日期
    last_date = await r.get(KEY_DATE)
    print('last_date:', last_date)
    print('TODAY:', TODAY)
    last_date = last_date.decode() if last_date else None
    if last_date == TODAY:
        # 同一天，直接自增并返回
        new_val = await r.incr(KEY_COUNT)   # 这里确实自增
        print('incr 返回值:', new_val, 'Redis 真实值:', await r.get(KEY_COUNT))
        return new_val
    else:
        # 跨天了：事务性更新
        async with r.pipeline(transaction=True) as pipe:
            await pipe.set(KEY_DATE, TODAY)
            await pipe.set(KEY_COUNT, 1)
            await pipe.execute()
        return 1

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
                reply_content = f"👋 欢迎使用【小矢·位图转矢量工具】！\n发送一张位图，我会帮你快速转成可无限放大的矢量图（SVG格式），适合印刷、设计和展示。\n🎁 新用户赠送 5 积分（每转 1 张图消耗 1 积分），现在就可以试试啦！。"
            else:
                # 如果是很久之前关注的用户，则送积分，否则不送
                cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                if user_create_time.replace(tzinfo=timezone.utc) < cutoff:
                    add_points(from_user, 5)
                    reply_content = f"欢迎回来，发送一张位图，我会帮你快速转成可无限放大的矢量图（SVG格式），适合印刷、设计和展示。\n老用户赠送5积分，您剩余{get_points(from_user)}积分。"
                else:
                    reply_content = f"欢迎回来，发送一张位图，我会帮你快速转成可无限放大的矢量图（SVG格式），适合印刷、设计和展示。\n您剩余{get_points(from_user)}积分。"
        elif event == "unsubscribe":
            print("用户取消关注")
            reply_content = f"再见！要记住我哦！你还会回来的吧？\n"
        # elif event == "VIEW": # 点击到充值页面
        #     return RedirectResponse("https://vectorizer.cn/pay?code={from_user}", status_code=302)
    elif msg_type == "image":  # 图片
        user_create_time = get_creat_time(from_user)
        if not user_create_time:  # 关注很久但第一次用
            create_or_set_points(from_user, 5)
            reply_content = f"欢迎使用位图转矢量工具，发送一张位图，我会帮你快速转成可无限放大的矢量图（SVG格式），适合印刷、设计和展示。\n🎁 转1张图消耗1积分，老用户赠送您5积分，您剩余{get_points(from_user)}积分。"
        
        media_id = root.findtext("MediaId") 
        token = await get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/media/get?access_token={token}&media_id={media_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            # 微信返回头里会带文件名：Content-Disposition: attachment; filename="xxx.jpg"
            filename = resp.headers.get("Content-Disposition", "").split("filename=")[-1].strip('"')
            if not filename:
                filename = f"{media_id}.png"

            local_path = r"static/"+filename
            with open(local_path, "wb") as f:
                f.write(resp.content)
        pic_url  =  os.getenv('DOMAIN_NAME') + "/"+local_path
        print(pic_url)
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
            cc = await get_counter()

            if cc > FREE_CREDIT: # 当日免费积分用完
                add_points(from_user, -1)
                reply_content = f"今天免费额度已用完。0/{FREE_CREDIT}张。\n"
            else:
                reply_content = f"今天免费额度剩余{FREE_CREDIT-cc}/{FREE_CREDIT}张。\n"
            task = process_image.delay(task_package)   

            reply_content += f"✅ 已收到图片，小矢正在为你处理矢量化…（大约需要 10 秒钟）\n👉 您剩余{get_points(from_user)}积分。"
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
from fastapi_cache.decorator import cache
@cache(expire=7000, namespace="wechat_access_token")
async def get_access_token() -> str:
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

@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def send_message(openid: str, result: dict, content="矢量化完成！请复制到浏览器打开并右键保存："):
    token = await get_access_token()
    url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
    body = {
        "touser": openid,
        "msgtype": "text",
        "text": {
            "content": content + f"\n{result.get('url')}"
        }
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        return {"openid": openid, "resp": r.json()}

is_send = []
@app.post('/vec_notify/')
async def vec_notify(request: Request):
    payload = await request.json()
    openid  = payload.get("openid")
    result  = payload.get("result", {})
    await send_message(openid,result)
    global is_send
    if openid not in is_send:
        await send_message(openid,{"url":""},"为了给你推荐更合适的文件格式或尺寸，小矢想了解下：\n你打算把这张矢量图用在哪些场景？\n（例如：印刷海报 / PPT / 网站图标 / App 界面 / 其他）")
        is_send.append(openid)
        if len(is_send) > 50:
            is_send = []
    return fastapi.Response(status_code=200)


@app.post('/add_points/')
async def add_points_api(request: Request):
    payload = await request.json()
    openid  = payload.get("openid")
    add_points(openid, delta=1)
    return {'status':1}


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
    logging.info(f"用户 {openid} 下单 {amount} 元，需要 {credits} 积分")
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
            logging.info('收到支付回调,',xml_data)
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
                
                if amount == 19.99:        
                    add_points(openid, delta=100)
                    logging.info(f"用户 {openid} 充值 {amount} 元, 增加100积分")
                elif amount == 49.99:
                    add_points(openid, delta=1000)
                    logging.info(f"用户 {openid} 充值 {amount} 元, 增加1000积分")
                # 1. 拿 token
                token = await get_access_token()

                # 2. 发客服文本给用户
                url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
                body = {
                    "touser": openid,
                    "msgtype": "text",
                    "text": {"content": f"充值成功，您剩余{get_points(openid)}积分。"}
                }

                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.post(url, json=body)
                #对报文进行应答
 
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

@app.get("/api/order/all")
def get_payment():
    # 获取所有payment
    return list_all_payments()

@app.get("/api/add_point/{userid}/{points}")
async def add_points2(userid: str = Path(..., description="订单号"),points: str = Path(..., description="订单号")):
    add_points(userid,int(points))
    return JSONResponse({"p":get_points(user_id=userid)},status_code=200)

@app.get('/api/get_points/{userid}')
async def add_points3(userid: str = Path(..., description="订单号")):
    p = get_points(user_id=userid)
    return JSONResponse({"p":p},status_code=200)

@app.post('/check/payment')
async def check_payment_1_minute():
    # all_payments = list_all_payments()
    # if all_payments[-1].status == "Success":
    #     paytime = all_payments[-1].created_at
    #     target = datetime.fromisoformat(paytime)   # 解析带 T 的 ISO 格式
    #     now = datetime.now()                       # 本地时间；若要 UTC 用 datetime.utcnow()
    #     if abs(now - target) <= timedelta(minutes=2):
    #         if all_payments[-1]["amount"] == "9.99":
    #             add_points(all_payments[-1].user_id,20)
    #         else:
    #             add_points(all_payments[-1].user_id,100)

    return True

@app.get("/logs_all/", response_class=PlainTextResponse)
def show_logs(lines: int = 200):
    """
    lines: 返回最后多少行，默认 200 行
    """
    LOG_FILE = "app.log"
    if not os.path.exists(LOG_FILE):
        return "日志文件不存在，稍等或先产生一些日志。"

    # 用 tail 的思想读最后 N 行，防止大文件一次性读爆内存
    from collections import deque
    with open(LOG_FILE, "rb") as f:
        # 倒序读，最多取 lines 行
        last_lines = deque(f, maxlen=lines)
    # bytes -> str
    last_lines = [line.decode(errors="ignore") for line in last_lines]
    return "".join(last_lines)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8999)