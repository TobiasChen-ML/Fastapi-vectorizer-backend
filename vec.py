import cv2
import numpy as np
import requests
import os
from PIL import Image
import vtracer
def png2svg_vtracer(image):
    img = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)) 
    pixels: list[tuple[int, int, int, int]] = list(img.getdata())
    svg_str: str = vtracer.convert_pixels_to_svg(pixels,size=(img.size[0],img.size[1]))

    return svg_str

def resize_max(image:np.array, max_size: int = 2048):
    height, width = image.shape[:2]
    
    # 计算缩放比例
    if max(height, width) > max_size:
        if height > width:
            scale = max_size / height
        else:
            scale = max_size / width
    else:
        return image
    
    # 缩放图片
    resized_img = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    
    return resized_img

def getlogo(logo_url):
    
    image_np = np.frombuffer(requests.get(logo_url, timeout=30).content, dtype=np.uint8)
    logo = cv2.imdecode(image_np, cv2.IMREAD_UNCHANGED)
    if logo.dtype != np.uint8:
        logo = cv2.normalize(logo, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    return logo

def bitmap_to_bezier(logo_url): 
 
    image = getlogo(logo_url) 
    image = resize_max(image, max_size=2048)
    svg_content = png2svg_vtracer(image).replace('<!-- Generator: visioncortex VTracer 0.6.4 -->','') 
    return svg_content