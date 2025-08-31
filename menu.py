# menu.py
import httpx, json
from util import get_access_token
import os
from dotenv import load_dotenv
load_dotenv()
appid = os.getenv("WECHAT_APP_ID")
MENU = {
    "button": [
        {
            "type": "view",
            "name": "充值积分",
            "url": f"https://open.weixin.qq.com/connect/oauth2/authorize?appid={appid}&redirect_uri=https%3A%2F%2Fvectorizer.cn%2Fpay%2F&response_type=code&scope=snsapi_base&state=123#wechat_redirect"        
        }
    ]
}

async def create_menu():
    token = get_access_token()
    url = f"https://api.weixin.qq.com/cgi-bin/menu/create?access_token={token}"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=MENU)
    print("创建菜单返回：", r.text)  

async def delete_menu():
    token = get_access_token()
    url = f"https://api.weixin.qq.com/cgi-bin/menu/delete?access_token={token}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
    print("删除菜单返回：", r.text)