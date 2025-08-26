import fastapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
import time
import xml.etree.ElementTree as ET
app = fastapi.FastAPI()

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

    # 示例：文本消息
    if msg_type == "text":
        content = root.find("Content").text
        reply_content = f"你说了：{content}"
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
    return reply_xml