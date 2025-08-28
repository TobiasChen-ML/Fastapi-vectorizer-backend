from fastapi import FastAPI, Request
import uvicorn
from pydantic import BaseModel
import requests
import vtracer
from PIL import Image
import cv2
import numpy as np
# from waifu2x_ncnn_py import Waifu2x
from .imgFenceMap import *
from .getPathPoints import *
from .colorUtils import *
from .svgController import *
import copy
import uuid
from .resizeImage import resizeMyLogo
from .cropper import LogoCropper
import json
app = FastAPI()

cropper = LogoCropper(device='cpu')
# waifu2x_init = Waifu2x(gpuid=-1, scale=2, noise=3)
DOMAIN_NAME = 'https://pixelopen.com/'
def getlogo(logo_url):
    
    image_np = np.frombuffer(requests.get(logo_url, timeout=30).content, dtype=np.uint8)
    logo = cv2.imdecode(image_np, cv2.IMREAD_UNCHANGED)
    if logo.dtype != np.uint8:
        logo = cv2.normalize(logo, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    return logo

def change_channel(image):
    if len(image.shape) == 2:
        image = cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
    
    is_background = 0
    bg_color = "#000"
    if image.shape[2] == 3:
        b, g, r = image[0,0]
        bg_color = RGB_to_Hex([r,g,b])
        image = cv2.cvtColor(image,cv2.COLOR_BGR2BGRA)
        is_background = 1 
    elif image.shape[2] == 4 and not np.any(image[:,:,-1] == 0):
        b, g, r, a = image[0,0]
        bg_color = RGB_to_Hex([r,g,b])
        image = cv2.cvtColor(image,cv2.COLOR_BGR2BGRA)
        is_background = 1 
    else:
        image = cv2.copyMakeBorder(image,10,10,10,10,cv2.BORDER_CONSTANT,value=(0,0,0,0))
    return is_background,bg_color,image  

def png2svg_vtracer(image):
    img = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)) 
    pixels: list[tuple[int, int, int, int]] = list(img.getdata())
    svg_str: str = vtracer.convert_pixels_to_svg(pixels,size=(img.size[0],img.size[1]))

    return svg_str

def png2svg_pixelopen(image):
    origin_width = image.shape[1]
    origin_height = image.shape[0]
    is_background,bg_color,image = change_channel(image)
    # 放大图片
    resizeMyLogo(image,cropper,waifu2x_init=None)

    # 获取颜色围栏
    fenceMapExtend = fenceMap(image)["fence"]

    image_cv2copy = copy.deepcopy(Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)))
    
    if max(image.shape[0],image.shape[1])<1600:
        fenceMapExtend = cv2.morphologyEx(fenceMapExtend, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

    # CV2 转 PIL
    image = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)) 
    
  
    width = image.size[0]
    height = image.size[1]

    # # 存一个拷贝
    image_copy = copy.deepcopy(image_cv2copy)
    
    all_path = getAllPath(fenceMapExtend,1,2,0.5)[1:]

    all_path_copy = all_path.copy()

    # 整理颜色
    path_color = getPathColor(all_path,image_copy)

    # 把前景背景分开
    mymask,mypath = splitMaskPath(all_path_copy,path_color)

    svg_content = writesvg(is_background,bg_color,mymask,mypath,path_color,width,height,all_path_copy)
    svg_content = "\n".join(svg_content)
    return svg_content

##########################################################################################
def is_token(token):
    return True


class Item(BaseModel):
    logo_url: str 
    token: str = '1'
    filetype: str = 'content'

@app.post('/pngtosvg/')
def png2svg_main(item:Item):
    
    # 验证token
    if not is_token(item.token):
        return {
            "code":"400",
            "msg":'token is invaild'
        }
    
    
    logo_url = item.logo_url
    
    image = getlogo(logo_url)

    if min(image.shape[0],image.shape[1])>800:
        svg_content = png2svg_vtracer(image).replace('<!-- Generator: visioncortex VTracer 0.6.4 -->','')
    else:
        svg_content = png2svg_pixelopen(image)
    
    if item.filetype == 'file_url':
        outputpath = '{}.svg'.format(uuid.uuid4())
        with open(outputpath,'w') as f:
            f.write(svg_content)
        return {
            'code':'200',
            'msg':'convert svg success!',
            'data': DOMAIN_NAME + outputpath
        }
    
    if item.filetype == 'content':
        return {
            'code':'200',
            'msg':'convert svg success!',
            'data':svg_content
        }

def png2svg(logo_url):
  
    image = getlogo(logo_url)  
    if min(image.shape[0],image.shape[1])>800:

        svg_content = png2svg_vtracer(image).replace('<!-- Generator: visioncortex VTracer 0.6.4 -->','')
    else:
        try:
            response = requests.get('https://ai.pixelopen.com/hello/',timeout=5)
            print(response.text)
            if response.text == "true":
                url = "https://ai.pixelopen.com/pngtosvg/"
                print('runing:',url)
                payload = json.dumps({
                "logo_url": logo_url
                })
                headers = {
                'Content-Type': 'application/json'
                }
                response = requests.request("POST", url, headers=headers, data=payload,timeout=5000)

                svg_content = json.loads(response.text)
  
                return svg_content["data"]
            else:
                svg_content = png2svg_pixelopen(image)
        except requests.exceptions.Timeout:
            svg_content = png2svg_pixelopen(image)
    


    return svg_content


def removebg_func(logo_url):
   

    response = requests.get('https://ai.pixelopen.com/hello/',timeout=5)
    print(response.text)
    if response.text == "true":
        url = "https://ai.pixelopen.com/removebg/"
        print('runing:',url)
        payload = json.dumps({
        "logo_url": logo_url
        })
        headers = {
        'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload,timeout=3000)

        svg_content = json.loads(response.text)
     
        return svg_content["data"]


    return svg_content
def upscale_func(logo_url,times):


    response = requests.get('https://ai.pixelopen.com/hello/',timeout=5)
    print(response.text)
    if response.text == "true":
        url = "https://ai.pixelopen.com/upscale/"
        print('runing:',url)
        payload = json.dumps({
        "logo_url": logo_url,
        "times":times
        })
        headers = {
        'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload,timeout=3000)

        svg_content = json.loads(response.text)
     
        return svg_content["data"]


    

    return svg_content

def whitelogo_func(logo_url):
   

    response = requests.get('https://ai.pixelopen.com/hello/',timeout=5)
    print(response.text)
    if response.text == "true":
        url = "https://ai.pixelopen.com/whiteImage/"
        print('runing:',url)
        payload = json.dumps({
        "logo_url": logo_url
        })
        headers = {
        'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload,timeout=3000)

        svg_content = json.loads(response.text)
 
        return svg_content["data"]


    


    return svg_content

def outline_func(logo_url):
    # image = getlogo(logo_url)

    response = requests.get('https://ai.pixelopen.com/hello/',timeout=5)
    print(response.text)
    if response.text == "true":
        url = "https://ai.pixelopen.com/outline/"
        print('runing:',url)
        payload = json.dumps({
        "logo_url": logo_url
        })
        headers = {
        'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload,timeout=3000)

        svg_content = json.loads(response.text)

        return svg_content["data"]


    return svg_content

def sam_func(logo_url,input_point_list,input_label_list):


    response = requests.get('https://ai.pixelopen.com/hello/',timeout=5)
    print(response.text)
    if response.text == "true":
        url = "https://ai.pixelopen.com/sam/"
        print('runing:',url)
        payload = json.dumps({
        "logo_url": logo_url,
        "input_point_list":input_point_list,
        "input_label_list":input_label_list
        })
        headers = {
        'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload,timeout=3000)
       
        svg_content = json.loads(response.text)
        
        return svg_content

    return svg_content
# if __name__ == "__main__":
#     uvicorn.run('main:app', host='0.0.0.0', port=7999, reload=True, workers=1)