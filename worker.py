"""
Celery 任务：耗时图片处理
启动命令：
celery -A tasks worker --loglevel=info --pool=prefork
"""
import uuid
from vec import bitmap_to_bezier
from celery import Celery
import requests

# ----------------- 连接 Redis -----------------
celery_app = Celery(
    "tasks",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0",
)

@celery_app.task(bind=True, name="tasks.process_image")
def process_image(self, task_package: str) -> dict:
    self.update_state(state="PROCESSING")  # 非必需，方便前端轮询
    # 解析任务包
    pic_url = task_package.get("pic_url")
    openid = task_package.get("openid")
    domain_name = task_package.get("domain_name")
    svg_content = bitmap_to_bezier(pic_url)

    # 保存结果
    out_name = f"static/{str(uuid.uuid4())}.svg"
    with open(out_name, "w") as f:
        f.write(svg_content)

    # 回调结果给用户
    response = requests.post(
        "http://127.0.0.1:6999/vec_notify/",
        json={"task_id": self.request.id, "result":{"url": f"{domain_name}/{out_name}"}, "openid": openid}, 
        timeout=30
    )

    self.update_state(state="SUCCESS")  # 非必需，方便前端轮询
    return {"openid": openid ,"url": f"{domain_name}/{out_name}"}