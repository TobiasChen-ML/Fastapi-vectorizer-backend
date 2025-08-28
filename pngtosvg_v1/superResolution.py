from waifu2x_ncnn_py import Waifu2x
from PIL import Image
import numpy as np
import cv2

def waifu2x(image,waifu2x):

    
    image_rgb = image[:,:,:3]

    image_a = image[:,:,3]

    image = cv2.resize(image,dsize=None,fx=2,fy=2)
    
    image_rgb = waifu2x.process_cv2(image_rgb)
    image_a = cv2.resize(image_a,dsize=None,fx=2,fy=2, interpolation=cv2.INTER_LINEAR)
    image[:,:,:3] = image_rgb
    image[:,:,3] = image_a
    return image


def waifu2x_single(image):

    waifu2x = Waifu2x(gpuid=-1, scale=2, noise=0)
    
    image = waifu2x.process_cv2(image)

    return image