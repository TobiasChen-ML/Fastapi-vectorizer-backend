from PIL import Image,ImageChops,ImageEnhance,ImageFilter
import cv2.mat_wrapper
import copy
from shapely.geometry import Polygon
import cv2
import numpy as np
from superResolution import waifu2x,waifu2x_single
import random
from getPathPoints import *
from colorUtils import *
from imgFenceMap import *
from removeBg import *
import os
# 对比度强度
contrast_factor = 3
# 颜色围栏和原图合并的权重，可以调整   
alpha = 0.3 

# 路径颜色字典
path_color = dict()
# 转弯细节参数

def mergeImage(array1,array2):
    array1 = np.array(array1)  
    array2 = np.array(array2)  

    result_array = alpha * array1 + (1 - alpha) * array2
    result_array = np.clip(result_array, 0, 255).astype(np.uint8)  

    # 将结果数组转换回图像  
    image = Image.fromarray(result_array) 

    return image

def fill_color(binary_image):
    # 查找轮廓（包括内部轮廓）  
    contours, hierarchy = cv2.findContours(binary_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)  
    
    # 创建一个与输入图像大小相同的彩色图像  
    h, w = binary_image.shape  
    color_image = np.zeros((h, w), dtype=np.uint8)  
    
    # 定义一个颜色列表（可以根据需要调整长度）  
     
    
    # 填充每个连通区域  
    for contour_idx, contour in enumerate(contours):  
        # 创建一个与输入图像大小相同的掩码图像  
        mask = np.zeros_like(binary_image, dtype=np.uint8)  
        
        # 填充轮廓内部为白色  
        cv2.drawContours(mask, [contour], -1, (255), thickness=cv2.FILLED)  
        
        # 获取该区域的颜色  
        color =  random.randint(30,240)
        
        # 在彩色图像中填充该区域（只考虑掩码为白色的部分）  
        color_image[mask == 255] = color  
    
    # 显示结果  
    return color_image


def path2points(all_path):
    # 所有path转成point
    restpath_dict = dict()
    for restp in all_path:
        polygon_vertices = getsvgrectfunc(restp,n=20)
        restpath_dict[restp]=Polygon(polygon_vertices) 
    return restpath_dict

def resize_image_to_shortest_edge(image, target_shortest_edge=1024):  

      
    # 获取图像的宽度和高度  
    height, width = image.shape[:2]  
      
    # 计算最短边并确定缩放比例  
    if height < width:  
        scale_factor = target_shortest_edge / height  
        new_width = int(width * scale_factor)  
        new_height = target_shortest_edge  
    else:  
        scale_factor = target_shortest_edge / width  
        new_width = target_shortest_edge  
        new_height = int(height * scale_factor)  
      
    # 调整图像大小  
    resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)  
      
    return resized_image 


def png2svg(imgaddr:str = None,outpath:str="./test.svg"):
    turdsize = 2

    if imgaddr  == None:
        print("image is None. Upload again.")
        return

    # read image, 转 4 通道
    image = cv2.imread(imgaddr,-1)

    origin_image = copy.deepcopy(image)
    origin_width = image.shape[1]
    origin_height = image.shape[2]
    if len(image.shape) == 2:
        image = cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
    
    is_background = 0
    bg_color = "#000"
    if image.shape[2] == 3:
        b, g, r = image[0,0]
        bg_color = RGB_to_Hex([r,g,b])
        image = cv2.cvtColor(image,cv2.COLOR_BGR2BGRA)
        is_background = 1 
    if image.shape[2] == 4 and not np.any(image[:,:,-1] == 0):
        b, g, r, a = image[0,0]
        bg_color = RGB_to_Hex([r,g,b])
        image = cv2.cvtColor(image,cv2.COLOR_BGR2BGRA)
        is_background = 1 


    # image = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)) 
    # image =  quantize_image(image, bins=10)
    # image =  cv2.cvtColor(np.asarray(image),cv2.COLOR_RGBA2BGRA)


 
    while max(image.shape[0],image.shape[1]) < 1200:
        image = waifu2x(image)
        # fenceMapExtend = waifu2x_single(fenceMapExtend)
        # turdsize = 4

    
    
    ret, thresholded_image = cv2.threshold(cv2.cvtColor(image,cv2.COLOR_BGRA2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)  

    # 获取图片的所有颜色
    # image = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)) 
    # image =  quantize_image(image, bins=8)
    # image =  cv2.cvtColor(np.asarray(image),cv2.COLOR_RGBA2BGRA)

    allcolors = getColor(image)
    

    image_cv2copy = copy.deepcopy(Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)))

    # fenceMapExtend = fenceMap(cv2.convertScaleAbs(image, alpha=1.5, beta=0))["fence"] 
# 
    fenceMapExtend = fenceMap(image)["fence"] 

    fenceMapExtend = cv2.morphologyEx(fenceMapExtend, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    # fill_color(fenceMapExtend)
    # cv2.imshow('t',fenceMapExtend)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # CV2 转 PIL
    image = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)) 
    
  
    width = image.size[0]
    height = image.size[1]

    # # 存一个拷贝
    image_copy = copy.deepcopy(image_cv2copy)
    
    # 调整对比度
    enhancer = ImageEnhance.Contrast(image)  
    image = enhancer.enhance(contrast_factor)

    # 转灰度图
    image = image.convert('L')

    # 颜色围栏和图片合并
    image = mergeImage(image,fenceMapExtend)

    image = ImageChops.invert(image)
    
    # 获取全部路径，去除第一个背景。

    all_path = getAllPath(image,turdsize,0.5)[1:]

    # import random
    # with open(f"test2.svg", "w") as fp:
    #     fp.write(
    #         f'''<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{image.width}" height="{image.height}" viewBox="0 0 {image.width} {image.height}">''')
    #     parts = []
    #     for curve in all_path:
    #         color = random.randint(000,999)
    #         fp.write(f'<path stroke="none" fill="#{color}" fill-rule="evenodd" d="{curve}"/>')
    #         all_path = all_path[1:]
    #     fp.write("</svg>")

    all_path_copy = all_path.copy()

    # 所有路径转成点
    allPathPoints = path2points(all_path)
    
  


    # 获取所有路径的颜色
    while all_path:
        # 取第一个路径
        pickpath = all_path[0]
        # 获取第一个path的n个内点
        
        inside_points = pathInnerPoints(pickpath,n=25)

        # 排除选中的path
        restpath_dict2 =  {k: v for k, v in allPathPoints.items() if k != pickpath}  
        
        real_inside_points = remove_rest_points(inside_points,restpath_dict2)
        
        if real_inside_points != []:
            all_path=all_path[1:]
            color_hex = pick_color(image_copy,real_inside_points)
            path_color[pickpath]=color_hex
        else:
            all_path=all_path[1:]
            if inside_points == []:
                path_color[pickpath]=0
            else:
                if len(image_copy.mode) == 3:
                    path_color[pickpath] = pick_color(image_copy,inside_points)
                if len(image_copy.mode) == 4:
                    a_num = 0
                    colors = []
                    for point in inside_points:
                        x,y = point
                        (r,g,b,a)= image_copy.getpixel((x,y))
                        if a == 0:
                            a_num += 1
                        else:
                            colors.append(RGB_to_Hex([r,g,b]))
                    if a_num / len(inside_points) > 0.6:
                        path_color[pickpath] = 0
                    else:
                        color_hex = max(colors,key=colors.count)
                        is_color_ok,color_hex = compareColors(allcolors,color_hex,delta=30)
                        path_color[pickpath] = color_hex
                    
    #########################################################


    mymask = []
    mypath = []

    # 把color为0的path和正常的path分开。
    for parts in all_path_copy:
        color = path_color[parts]
        if color == 0:
            mymask.append(parts)
        else:
            mypath.append(parts)

    svgs = ['''<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width2} {height2}">'''.format(width=width,height=height,width2=width,height2=height)]
    svgs += ['''<g transform="scale({})">'''.format(1)]

    # 把背景先塞进去
    if is_background == 1:
        svgs += ['''<rect x="0" y="0" width="{width}" height="{height}" fill="{bg_color}"></rect>'''.format(width = width,height = height,bg_color = bg_color)]

    # 判断所有mask，哪个在path内部，在的部分组成一个mask，专门让path一个用。
    if len(mymask)>0:
        maskcounter = 0
        maskmask = dict()
        for part in mypath:
            masklist = []
            color = path_color[part]
            for mask in mymask:
                # 判断mask在path内
                if check_path_inside(mask,part,rate=0.6):
                    masklist.append(mask)
            
            svgs.append(f'<path vector-effect="non-scaling-stroke" stroke="none" fill="{color}" fill-rule="evenodd" d="{part}" mask="url(#PIXELOPEN-PNGTOSVG{maskcounter})" />'.format(color=str(color)))
            maskmask["PIXELOPEN-PNGTOSVG{maskcounter}".format(maskcounter=maskcounter)] = masklist
            maskcounter += 1

        for maskid,maskpath in maskmask.items():
            if len(maskpath) > 0:
                svgs.append(f'''<mask id="{maskid}"><rect x="0" y="0" width="{width}" height="{height}" fill="white" />'''.format(width=width,height=height))
                for maskp in maskpath:
                    svgs.append(f'<path vector-effect="non-scaling-stroke" stroke="none" fill="black" fill-rule="evenodd" d="{maskp}" />'.format(maskp=maskp))
                svgs.append('</mask>')


    else:
        
        for parts in all_path_copy:
            color = path_color[parts]
            if color == 0:
                pass
            else:
                svgs.append(f'<path vector-effect="non-scaling-stroke" stroke="none" fill="{color}" fill-rule="evenodd" d="{parts}" />'.format(color=str(color)))

    svgs.append('</g></svg>')

    with open(outpath,'w') as f:
        f.write("\n".join(svgs))

    


def split_list(lst, n):
    k, m = divmod(len(lst), n)
    return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

def png2svg2(addrr):
    from tqdm import tqdm
    tz = 0
    counter = 0
    import time
    for addr in tqdm(addrr):
        t1 = time.time()
        png2svg(addr,addr.replace(".png",".svg"))
        tz+=time.time()-t1
        counter+=1
        print("average:",tz/counter)

if __name__ == "__main__":
    


    # imgaddr = r"52175.png"
    # outpath = imgaddr.replace(".png",".svg")
    # png2svg(imgaddr,outpath)

    # import glob
    # address = glob.glob(r"E:\logo_data\logo2\*.png")
    # t = 0
    # import time
    # counterr = 0
    # mmse = 0
    # ssimm = 0
    # for imgaddr in address:
    #     t1 = time.time()
    #     outpath = imgaddr.replace(".png",".svg")
    #     mse,ssim = png2svg(imgaddr,outpath)
    #     t += time.time() - t1
    #     counterr +=1
    #     mmse += mse
    #     ssimm += ssimm
    #     print("average:",t/counterr,"mse:",mse/counterr,"ssim:",ssim/counterr)




    import glob
    from multiprocessing import Process

    imgaddrlist = glob.glob(r'./*.png')
    my_new_list = split_list(imgaddrlist, 4)
    process_list = []
    for i in range(4):  #开启5个子进程执行fun1函数
        p = Process(target=png2svg2,args=(my_new_list[i],)) #实例化进程对象
        p.start()
        process_list.append(p)

    for i in process_list:
        p.join()

    print('结束测试') 










 
    #  mymask = []
    # maskcounter = 0

    # svgs = ['''<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width2} {height2}">'''.format(width=width,height=height,width2=width,height2=height)]

    # for parts in all_path2:
    
    #     color = path_color[parts]
    #     if color == 0:
    #         mymask.append(f'<path stroke="none" fill="black" fill-rule="evenodd" d="{parts}" />')
    #     else:
    #         svgs.append(f'<path stroke="none" fill="{color}" fill-rule="evenodd" d="{parts}" mask="url(#myMask{maskcounter})" />'.format(color=str(color)))
    
    
    # svgs.append(f'''<mask id="myMask{maskcounter}"><rect x="0" y="0" width="{width}" height="{height}" fill="white" />'''.format(width=width,height=height))
    # svgs += mymask
    # svgs.append('</mask>')
    # svgs.append('</svg>')

    # t2 = time.time()
    # t += t2-t1
    
    # print("个数:",counter,"平均耗时为：",t/counter)
    # counter +=1
    # with open(imgaddr.replace(".png",".svg"),'w') as f:
    #     f.write("".join(svgs))