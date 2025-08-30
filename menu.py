# menu.py
import httpx, json
from util import get_access_token

MENU = {
    "button": [
        {
            "type": "view",
            "name": "立即购买",
            "url": "https://vectorizer.cn/pay/"        # 你的 H5 购买页
        }
    ]
}

async def create_menu():
    token = get_access_token()
    url = f"https://api.weixin.qq.com/cgi-bin/menu/create?access_token={token}"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=MENU)
    print("创建菜单返回：", r.text)  # 打印返回结果