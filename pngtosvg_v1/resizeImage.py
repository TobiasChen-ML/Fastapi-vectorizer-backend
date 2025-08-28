import numpy as np
# from waifu2x_ncnn_py import Waifu2x
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


def resizeMyLogo(image,cropper,waifu2x_init):
    crops_list = cropper.crop(image, save=False)
    main_image = np.zeros((1000,1000))
    if "main-text" in list(crops_list.keys()):
        main_image = crops_list["main-text"]
    elif 'text-combination' in list(crops_list.keys()):
        if min(crops_list["text-combination"].shape[0],crops_list["text-combination"].shape[1]) < min(main_image.shape[0],main_image.shape[1]):
            main_image = crops_list["text-combination"]
    elif 'aux-text' in list(crops_list.keys()):
        if min(crops_list["aux-text"].shape[0],crops_list["aux-text"].shape[1]) < min(main_image.shape[0],main_image.shape[1]):
            main_image = crops_list["aux-text"]

    if max(main_image.shape[0],main_image.shape[1])<1500:
        for _ in range(int(np.ceil(np.sqrt(np.ceil(1500/max(main_image.shape[0],main_image.shape[1])))))):
            # image = waifu2x(image,waifu2x_init)
            cv2.resize(image,dsize=None,fx=2,fy=2)


    while min(image.shape[0],image.shape[1])<1000:
        cv2.resize(image,dsize=None,fx=2,fy=2)
        # image = waifu2x(image,waifu2x_init)
    
    return image