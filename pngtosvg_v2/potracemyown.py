import svgpathtools as svg  
from scipy.interpolate import splprep, splev
import cv2
import numpy as np
from shapely.geometry import Polygon, Point ,MultiPoint
import itertools
from concurrent.futures import ThreadPoolExecutor
# from waifu2x_ncnn_py import Waifu2x

import numpy as np
from scipy.optimize import minimize
import requests
from algorithm.pngtosvg_v2.superResolution import super_resolution_predict
SR_MODEL = r"algorithm/pngtosvg_v2/0925-x4_rep_epoch151_x4.pth"
sr_model = super_resolution_predict(SR_MODEL)
import cv2.mat_wrapper
from scipy import stats
from typing import Iterable
from PIL import Image
import vtracer
'''
ubuntu的waifu2x
apt install pocl-opencl-icd ocl-icd-opencl-dev python-dev opencl-headers
source cl-waifu2x/bin/activate
pip install pyopencl pyopencl[pocl] numpy scipy pillow
    
Install cl-waifu2x
git clone https://github.com/marcan/cl-waifu2x.git
    
???
export PYOPENCL_CTX='0'
c
    
 sudo apt install pocl-opencl-icd
[pip]conda install pocl
'''

METHOD = 'L'

# waifu2x_init = Waifu2x(gpuid=0, scale=2, noise=3)
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





def calcMajorInThickBorder(image: np.ndarray, margin: int = 5, calc_mean: str = "mode", calc_std: str = "no"):
    
    if image is None or 0 == image.size:
        return None, None

    if image.shape[0] < margin or image.shape[1] < margin:
        return None, None

    bars = [
        image[:margin, :],
        image[-margin:, :],
        image[:, :margin],
        image[:, -margin:],
    ]
    shape = image.shape if 3 == image.ndim else image.shape + (1,)
    lines = [bar.reshape((-1, shape[-1])) for bar in bars]
    one_bar = np.concatenate(lines, axis=0)

    mean_value = None
    if "mean" == calc_mean:
        mean_value = np.mean(one_bar, axis=0)
    elif "median" == calc_mean:
        mean_value = np.median(one_bar, axis=0)
    else:
        if image.dtype in (np.int8, np.uint8, np.int16, np.uint16, np.int32, np.uint32, np.int64, np.uint64) \
                and (image.ndim == 2 or 1 == shape[-1]):
            mean_value = stats.mode(one_bar, axis=None, keepdims=False).mode
        else:
            print("mode 仅支持单通道整型像素图像，将改用 median。")
            mean_value = np.median(one_bar, axis=0)

    std_value = None
    if "std" == calc_std:
        std_value = np.std(one_bar, axis=0)
    elif "max" == calc_std:
        std_value = np.max(one_bar, axis=0)
    elif "min" == calc_std:
        std_value = np.min(one_bar, axis=0)

    return mean_value, std_value


def fenceMap(image: np.ndarray, *, return_extend: str = None, powers: Iterable = [2]):
    """构建围栏图。

    参数:
        - image (np.ndarray): 图片。
        - return_extend (str, optional): 返回额外的结果图，可选【binary、label、label-with-fence】，默认无。
        - powers (Iterable, optional): 额外的颜色变换，幂指数。默认 2.

    返回:
        dict: 'fence'围栏图，'binary'多重二值图，'label'标签图
    """
    if image is None or 0 == image.size:
        return None

    if image.ndim < 2 or 3 < image.ndim:
        return None

    if image.dtype != np.uint8:
        return None

    if image.ndim == 2:
        image = image.reshape(image.shape+(1,))

    if powers:
        tweaks = [image]
        for power in powers:
            pow_vals = [power, 1/power]
            for pow_val in pow_vals:
                lut = np.linspace(0, 1, 256)
                np.power(lut, pow_val, out=lut)
                np.multiply(lut, 255, out=lut)
                lut = lut.astype(np.uint8)
                if 4 == image.shape[-1]:
                    tweaks.append(cv2.LUT(image[:, :, :3], lut))
                else:
                    tweaks.append(cv2.LUT(image, lut))
        image = np.concatenate(tweaks, axis=2)

    contours = []
    binaries = []
    for ch in range(image.shape[-1]):
        bin = np.greater(image[:, :, ch], 127).astype(np.uint8)
        np.multiply(bin, 255, out=bin)
        val = calcMajorInThickBorder(bin)[0]
        if 0 < val:
            np.bitwise_not(bin, out=bin)
        cont = cv2.findContours(bin, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0]
        if len(cont) == 0:
            cv2.threshold(image[:, :, ch], 127, 255,
                          cv2.THRESH_BINARY+cv2.THRESH_OTSU, dst=bin)
            val = calcMajorInThickBorder(bin)[0]
            if 0 < val:
                np.bitwise_not(bin, out=bin)
            cont = cv2.findContours(
                bin, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0]
        contours.extend(cont)
        if return_extend:
            binaries.append(bin)
    if len(contours) == 0:
        extend = {'fence': np.zeros(image.shape[:2], dtype=np.uint8)}
        if return_extend:
            return_extend = return_extend.lower()
            if 'binary' in return_extend:
                extend['binary'] = np.stack(binaries, axis=2)
            if 'label' in return_extend:
                extend['label'] = np.zeros_like(
                    extend['fence'], dtype=np.uint8)

    fence = np.zeros(image.shape[:2], dtype=np.uint8)
    some = np.concatenate(contours, axis=0).squeeze(axis=1)
    fence[(some[:, 1], some[:, 0])] = 255

    extend = {'fence': fence}
    if return_extend:
        return_extend = return_extend.lower()
        if 'binary' in return_extend:
            extend['binary'] = np.stack(binaries, axis=2)
        if 'label' in return_extend:
            dtype = np.uint32
            label = np.zeros_like(fence, dtype=dtype)
            temp1 = np.zeros_like(label, dtype=dtype)
            temp2 = np.zeros_like(label, dtype=dtype)
            for index in range(len(binaries)):
                np.greater(binaries[index], 127, out=temp1)
                np.multiply(temp1, 2**index, out=temp2)
                label += temp2
            if 'label-with-fence' in return_extend or 'label with fence' in return_extend:
                label[0 < fence] = np.iinfo(dtype).max
            extend['label'] = label

    return extend




def calculate_angle(p1, p2, p3):
    # 计算三点之间的角度
    v1 = np.array(p1) - np.array(p2)
    v2 = np.array(p3) - np.array(p2)
    
    # 计算两个向量的点积
    dot_product = np.dot(v1, v2)
    
    # 计算两个向量的模长
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    # 计算角度（单位：弧度）
    cos_theta = dot_product / (norm_v1 * norm_v2)
    angle = np.arccos(np.clip(cos_theta, -1.0, 1.0))
    
    # 将弧度转换为角度
    angle = np.degrees(angle)
    
    return angle

def find_corner_points(contour, distance_threshold=3, angle_threshold=10):
    """
    找到轮廓的拐点，排除了小距离和小角度变化的误判。
    
    参数：
    - contour: 轮廓点集。
    - distance_threshold: 用于判断是否为直线段的距离阈值。
    - angle_threshold: 拐点的角度变化阈值。
    
    返回：
    - corner_points: 拐点坐标。
    """
    corner_points = []
    
    for i in range(1, len(contour) - 1):
        p1 = contour[i - 1][0]
        p2 = contour[i][0]
        p3 = contour[i + 1][0]
        
        # 计算相邻点之间的欧氏距离
        dist1 = np.linalg.norm(np.array(p1) - np.array(p2))
        dist2 = np.linalg.norm(np.array(p2) - np.array(p3))
        
        # 如果两个相邻点之间的距离小于阈值，则认为它们在同一条直线段上，跳过角度计算
        if dist1 < distance_threshold and dist2 < distance_threshold:
            continue
        
        # 计算角度
        angle = calculate_angle(p1, p2, p3)
        
        # 如果角度大于阈值，认为是拐点
        if angle > angle_threshold:
            corner_points.append(p2)
    
    return corner_points

# 贝塞尔曲线公式（三次贝塞尔曲线）
def bezier(t, P0, P1, P2, P3):
    return (
        (1 - t)**3 * P0 +
        3 * (1 - t)**2 * t * P1 +
        3 * (1 - t) * t**2 * P2 +
        t**3 * P3
    )

# 误差函数，用于优化控制点
def bezier_fit_error(control_points, points, t_values):
    P0, P1, P2, P3 = control_points.reshape(4, 2)
    bez_points = np.array([bezier(t, P0, P1, P2, P3) for t in t_values])
    return np.sum(np.linalg.norm(points - bez_points, axis=1)**2)

# 分段拟合函数
def fit_polygon_segments(polygon, num_segments):
    num_points = len(polygon)
    segment_length = num_points // num_segments
    bezier_curves = []

    for i in range(num_segments):
        # 获取当前段的点
        start_idx = i * segment_length
        end_idx = (i + 1) * segment_length if i < num_segments - 1 else num_points
        segment = polygon[start_idx:end_idx]

        # 参数化 t 值
        t_values = np.linspace(0, 1, len(segment))

        # 初始控制点猜测
        P0, P3 = segment[0], segment[-1]
        P1 = P0 + (P3 - P0) * 0.3  # 初步猜测
        P2 = P0 + (P3 - P0) * 0.7  # 初步猜测
        init_control_points = np.array([P0, P1, P2, P3])

        # 优化控制点
        result = minimize(
            bezier_fit_error,
            init_control_points.flatten(),
            args=(segment, t_values),
            method='L-BFGS-B'
        )

        # 保存优化后的控制点
        optimized_control_points = result.x.reshape(4, 2)
        bezier_curves.append(optimized_control_points)

    return bezier_curves


def bezier_fit_error_segment(polygon, control_points):
    # 计算贝塞尔曲线拟合的误差
    t_values = np.linspace(0, 1, len(polygon))
    bez_points = np.array([bezier(t, *control_points) for t in t_values])
    return np.max(np.linalg.norm(polygon - bez_points, axis=1))  # 最大误差

def determine_segments_by_error(polygon, error_threshold=0.5, max_segments=10):
    num_segments = 1
    while num_segments <= max_segments:
        # 分段
        segment_length = len(polygon) // num_segments
        total_error = 0
        
        for i in range(num_segments):
            start_idx = i * segment_length
            end_idx = (i + 1) * segment_length if i < num_segments - 1 else len(polygon)
            segment = polygon[start_idx:end_idx]
            
            # 初始控制点猜测
            P0, P3 = segment[0], segment[-1]
            P1 = P0 + (P3 - P0) * 0.3
            P2 = P0 + (P3 - P0) * 0.7
            init_control_points = np.array([P0, P1, P2, P3])
            
            # 计算误差
            total_error += bezier_fit_error_segment(segment, init_control_points)
        
        # 检查总误差是否满足阈值
        if total_error / num_segments <= error_threshold:
            break
        
        num_segments += 1  # 增加分段数量
    
    return num_segments



def waifu2x(image,waifu2x):

    
    image_rgb = image[:,:,:3]

    image_a = image[:,:,3]

    image = cv2.resize(image,dsize=None,fx=2,fy=2)
    
    image_rgb = waifu2x.process_cv2(image_rgb)
    image_a = cv2.resize(image_a,dsize=None,fx=2,fy=2, interpolation=cv2.INTER_LINEAR)
    image[:,:,:3] = image_rgb
    image[:,:,3] = image_a
    return image

def preprocess_image(image):
    # 加载图像
    
    image = shift_demo(image)
   
    fenceMapExtend = fenceMap(image)["fence"]

    if max(image.shape[0],image.shape[1])<1000:
        fenceMapExtend = cv2.morphologyEx(fenceMapExtend, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

    return fenceMapExtend,image

def waifu2x(image,waifu2x):
    image_rgb = image[:,:,:3]
    image_a = image[:,:,3]
    image = cv2.resize(image,dsize=None,fx=2,fy=2)

    image_rgb = waifu2x.process_cv2(image_rgb)
    image_a = cv2.resize(image_a,dsize=None,fx=2,fy=2, interpolation=cv2.INTER_LINEAR)
    image[:,:,:3] = image_rgb
    image[:,:,3] = image_a
    return image

def RGB_to_Hex(rgb):
    strs = '#'
    for i in rgb:
        num = int(i) 
        strs += str(hex(num))[-2:].replace('x', '0').upper()
    return strs


def fit_bezier_curve(points):
    """
    拟合三阶贝塞尔曲线的控制点。
    points: 要拟合的点集 (Nx2 numpy array)
    返回值: [P0, P1, P2, P3] 的控制点坐标
    """
    # 起点和终点
    if METHOD == 'C':
        P0 = points[0]
        P3 = points[-1]
        P1 = points[1]
        P2 = points[2]
        return P0, P1, P2, P3
    if METHOD == 'Q':
        P0 = points[0]
        P1 = points[1]
        P2 = points[-1]
        return P0, P1, P2
    if METHOD == 'L':
        P0 = points[0]
        P1 = points[1]
        return P0,P1
    
def is_contained(boxA, boxB):
    minxA, minyA, maxxA, maxyA = boxA
    minxB, minyB, maxxB, maxyB = boxB
    
    return (minxA <= minxB and
            minyA <= minyB and
            maxxA >= maxxB and
            maxyA >= maxyB)

def check_containment(poly1, poly2):
    poly1 = poly1["smooth_polygon"]
    poly2 = poly2["smooth_polygon"]

    poly1_area = poly1.area
    poly2_area = poly2.area

    # 先判断面积，小的在大的里
    if poly1_area >= poly2_area:
        if poly1.contains(poly2):
            return 1
        else:
            return False
    else:
        if poly2.contains(poly1):
            return 2
        else:
            return False


def cal_middle_point(point1,point2):
    return ((point2[0]+point1[0])/2,(point2[1]+point1[1])/2)

def smooth_contour(contour):
    
    
    contours = [tuple(contour[0])]
    corner_points = find_corner_points(contours[0])

    for i in range(len(contour)-1):
        if contour[i] in corner_points:
            contours.append(contour[i])
        contours.append(cal_middle_point(contour[i+1],contour[i]))
    contours.append(tuple(contour[-1]))
    return contours
def png2svg_vtracer(image):
    img = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)) 
    pixels: list[tuple[int, int, int, int]] = list(img.getdata())
    svg_str: str = vtracer.convert_pixels_to_svg(pixels,size=(img.size[0],img.size[1]))

    return svg_str

def extract_contours(contours,image):
   
    # 提取轮廓
    # contours, hierarchy = cv2.findContours(binary_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    all_polygons = []
    # 找到所有父轮廓
    for idx, contour in enumerate(contours):
           
        all_polygon = {}
        if len(contour) < 3:
            continue
        contour_polygon = Polygon(contour.squeeze().tolist())
        if contour_polygon.area < 5:
            continue
        simply_polygon = contour_polygon.simplify(0.3, preserve_topology=True)

        all_polygon = {
            "id":idx,
            "polygon":contour_polygon,
            "contour":contour,
            "smooth_polygon":simply_polygon,
            "inside_polygon":[]
        } 
       
        all_polygon.update(fit_contour_with_bezier(simply_polygon.exterior.coords,image,simply_polygon))
        all_polygons.append(all_polygon)

    # 创建多边形组合
    combinations = list(itertools.combinations(all_polygons, 2))

    # 线程池并行处理函数
    
    def process_combine_polygon(combine_polygon):
        response = check_containment(combine_polygon[0], combine_polygon[1])
        result = None

        if response == False:
            result = None
        else:
            if response == 1:
                combine_polygon[0]["inside_polygon"].append(combine_polygon[1]['path'])
                result = (combine_polygon[0]["id"], combine_polygon[1]["id"], "poly1 contains poly2")
            if response == 2:
                combine_polygon[1]["inside_polygon"].append(combine_polygon[0]['path'])
                result = (combine_polygon[1]["id"], combine_polygon[0]["id"], "poly2 contains poly1")
        
        return result
    
 
    with ThreadPoolExecutor() as executor:
        results = executor.map(process_combine_polygon, combinations)

    return all_polygons


    
def build_path(path,color,opacity,maskid):
    d = f"M {path[0][0][0]} {path[0][0][1]}"
    for p in path:
        if METHOD == 'C':
            P0, P1, P2, P3 = p
            d += f"C {P1[0]} {P1[1]}, {P2[0]} {P2[1]}, {P3[0]} {P3[1]}"
        if METHOD == 'Q':
            P0, P1, P2 = p
            d += f"Q {P1[0]} {P1[1]}, {P2[0]} {P2[1]}"
        if METHOD == 'L':
            P0,P1 = p
            d += f"L {P1[0]} {P1[1]}"
    d += "z"
    return f'<path  stroke="none" fill-rule="evenodd" d="{d}" fill="{color}" opacity="{opacity}" mask="url(#PIXELOPEN-PNGTOSVG{maskid})"/>\n'


def build_mask(maskid,width,height,maskpath):
    
    m = ""
    m += f'''<mask id="PIXELOPEN-PNGTOSVG{maskid}"><rect x="0" y="0" width="{width}" height="{height}" fill="white" />'''
    for path in maskpath:
        
        d = f"M {path[0][0][0]} {path[0][0][1]}"
        for p in path:
            if METHOD == 'C':
                P0, P1, P2, P3 = p
                d += f"C {P1[0]} {P1[1]}, {P2[0]} {P2[1]}, {P3[0]} {P3[1]}"
            if METHOD == 'Q':
                P0, P1, P2 = p
                d += f"Q {P1[0]} {P1[1]}, {P2[0]} {P2[1]}"
            if METHOD == 'L':
                P0,P1 = p
                d += f"L {P1[0]} {P1[1]}"
        d += "z"
        m += f'<path vector-effect="non-scaling-stroke" stroke="none" fill="black" fill-rule="evenodd" d="{d}" />'
    m+='</mask>'
    return m


def splitMaskPath(all_polygons):
    
    mymask,mypath = [],[]
    # 把color为0的path和正常的path分开。
    for polygon in all_polygons:
        opacity = polygon["opacity"]
        if opacity == 0:
            mymask.append(polygon)
        else:
            mypath.append(polygon)

    return mymask,mypath

def bezier_to_svg(image,all_polygons,is_background,bg_color,output_file):
    """
    将贝塞尔曲线转换为 SVG 文件。
    image 要的是宽高
    all_polygons是所有的轮廓信息
    output_file 是输出文件位置
    """
    maskcounter = 0
    with open(output_file, 'w') as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {} {}" width="{}" height="{}">\n'.format(image.shape[1],image.shape[0],image.shape[1],image.shape[0]))
        # 把背景先塞进去
        if is_background == 1:
            f.write(f'''<rect x="0" y="0" width="{image.shape[1]}" height="{image.shape[0]}" fill="{bg_color}"></rect>''')

        maskcounter = 0
        maskmask = dict()
        for path in all_polygons:
            color = path["color"]
            part = path["path"]
            masklist = path['inside_polygon']
            opacity = path['opacity']
            f.write(build_path(part,color,opacity,maskcounter))
            maskmask[maskcounter] = masklist
            maskcounter += 1

        for maskid,maskpath in maskmask.items():
            if len(maskpath) > 0:
                f.write(build_mask(maskid,image.shape[1],image.shape[0],maskpath))

        f.write('</svg>')

def bezier_to_svgstr(image,all_polygons,is_background,bg_color):
    """
    将贝塞尔曲线转换为 SVG 文件。
    image 要的是宽高
    all_polygons是所有的轮廓信息
    output_file 是输出文件位置
    """
    maskcounter = 0
    response = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {} {}" width="{}" height="{}">\n'.format(image.shape[1],image.shape[0],image.shape[1],image.shape[0])
        
    maskcounter = 0
    maskmask = dict()
    for path in all_polygons:
        color = path["color"]
        part = path["path"]
        masklist = path['inside_polygon']
        opacity = path['opacity']
        response += build_path(part,color,opacity,maskcounter)
        maskmask[maskcounter] = masklist
        maskcounter += 1

    for maskid,maskpath in maskmask.items():
        if len(maskpath) > 0:
            response += build_mask(maskid,image.shape[1],image.shape[0],maskpath)

    response += '</svg>'

    maskcounter = 0
    
    response ='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {} {}" width="{}" height="{}">\n'.format(image.shape[1],image.shape[0],image.shape[1],image.shape[0])
    # 把背景先塞进去
    if is_background == 1:
        response +=f'''<rect x="0" y="0" width="{image.shape[1]}" height="{image.shape[0]}" fill="{bg_color}"></rect>'''

    maskcounter = 0
    maskmask = dict()
    for path in all_polygons:
        color = path["color"]
        part = path["path"]
        masklist = path['inside_polygon']
        opacity = path['opacity']
        response +=build_path(part,color,opacity,maskcounter)
        maskmask[maskcounter] = masklist
        maskcounter += 1

    for maskid,maskpath in maskmask.items():
        if len(maskpath) > 0:
            response +=build_mask(maskid,image.shape[1],image.shape[0],maskpath)

    response +='</svg>'
    return response

def shift_demo(image):   #均值迁移
    image_rgb = image[:,:,:3]

    image_a = image[:,:,3]
    image_rgb = cv2.pyrMeanShiftFiltering(image_rgb, 10, 50)
    image[:,:,:3] = image_rgb

    binary_alpha = np.where(image_a < 127, 0, 255).astype(np.uint8)
    image[:,:,3] = binary_alpha

    return image


def fit_contour_with_bezier(contour,image,polygon,krange=3):
    """
    将轮廓拟合为多段贝塞尔曲线。
    contour: 轮廓点 (Nx2 numpy array)
    segment_length: 每段使用的点数
    返回值: 贝塞尔曲线控制点列表 [(P1,P2,P3,P4),(P1,P2,P3,P4),..]
    """
    # contour = smooth_contour(contour)
    if METHOD == 'C':
        segment_length=3
    if METHOD == 'Q':
        segment_length=2
    if METHOD == 'L':
        segment_length=2
    
    num_points = len(contour)
    colors = []
    opacity = []
    grouped_points = []
    # 遍历轮廓点，每次取三个点（注意不要超出边界）
    for i in range(0, num_points - (segment_length-1)):  # 减2是因为我们需要三个点，所以最后一个可能的起始索引是 num_points - 3
        # 获取当前三个点
        group = contour[i:i+segment_length]
        if METHOD == 'C':
            P0, P1, P2, P3 = fit_bezier_curve(group)
            grouped_points.append((P0, P1, P2, P3))
        if METHOD == 'Q':
            P0, P1, P2 = fit_bezier_curve(group)
            grouped_points.append((P0, P1, P2))
        if METHOD == 'L':
            P0, P1 = fit_bezier_curve(group)
            grouped_points.append((P0, P1))
        
        # 取上下左右的整数点 是否inside
    
    colors = []
    opacity = []
    
    (x,y) = grouped_points[0][0]
    x,y = int(x),int(y)
    b, g, r, a = image[y,x]
    bg_color = RGB_to_Hex([r,g,b])
    colors.append(bg_color)
    opacity.append(a/255)

    offsets = np.arange(-krange, krange)  # 生成偏移量范围
    x_offsets, y_offsets = np.meshgrid(offsets, offsets)  # 创建二维网格

    # 扁平化坐标点
    points = np.vstack([x + x_offsets.ravel(), y + y_offsets.ravel()]).T  # 获取所有需要检查的点的坐标

    # 使用 shapely 的 MultiPoint 一次性检查所有点是否在多边形内
    multipoint = MultiPoint([Point(px, py) for px, py in points])  # 创建 MultiPoint 对象
    is_inside = np.array([point.within(polygon) for point in multipoint.geoms])  # 判断每个点是否在多边形内

    # 获取所有在多边形内的点坐标
    inside_points = points[is_inside]

    # 获取对应的颜色和透明度

    for px, py in inside_points:
        b, g, r, a = image[int(py), int(px)]  # 图像坐标的索引需要整数
        bg_color = RGB_to_Hex([r, g, b])
        colors.append(bg_color)
        opacity.append(a / 255)  # 转换为 0-1 范围的透明度值

            # for counterx in [k for k in range(-1*krange,krange)]:
            #     for countery in [k for k in range(-1*krange,krange)]:
            #         point_to_test = Point(x+counterx, y+countery)  
            #         is_inside = point_to_test.within(polygon)  
            #         if is_inside:
            #             b, g, r, a = image[y+countery,x+counterx]
            #             bg_color = RGB_to_Hex([r,g,b])
            #             colors.append(bg_color)
            #             opacity.append(a/255)
    
    color_hex = max(colors,key=colors.count)    
    opacity_1 = max(opacity,key=opacity.count)   
    
    return {"path":grouped_points,"color":color_hex,"opacity":opacity_1}

   
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
    

def upscale2x(image):
    image_rgb = image[:,:,:3]
    
    image_rgb = sr_model.forward(image[:,:,:3])

    image = cv2.resize(image,dsize=None,fx=4,fy=4, interpolation=cv2.INTER_LINEAR)

    image[:,:,:3] = image_rgb
    return image

def getlogo(logo_url):
    
    image_np = np.frombuffer(requests.get(logo_url, timeout=30).content, dtype=np.uint8)
    logo = cv2.imdecode(image_np, cv2.IMREAD_UNCHANGED)
    if logo.dtype != np.uint8:
        logo = cv2.normalize(logo, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    return logo

def bitmap_to_bezier(logo_url):
    # t1 = time.time()
    # image = cv2.imread(image_path, -1)
    image = getlogo(logo_url)  
    is_background,bg_color,image = change_channel(image)
    image = resize_max(image, max_size=2048)
    while min(image.shape[0],image.shape[1]) < 300:
        image = upscale2x(image)
    binary,image = preprocess_image(image)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) > 1000:
        svg_content = png2svg_vtracer(image).replace('<!-- Generator: visioncortex VTracer 0.6.4 -->','') 
        return svg_content
    
    all_polygons = extract_contours(contours,image)
    return bezier_to_svgstr(binary,all_polygons,is_background,bg_color)
     
    # t2 = time.time()
    # print(f'该图片转换耗时:{t2-t1}')
# bitmap_to_bezier(r"e:\logo_data\logo2\0.png","output.svg")
# import tracemalloc

# # 开始跟踪内存
# tracemalloc.start()

# # 示例调用



# import os
# import glob
# import time
# images = glob.glob(r'E:\logo_data\logo2\*.png')
# # counter = 1 
# tt = time.time()
# for j in images:
#     bitmap_to_bezier(j,j.replace('png','svg'))

#     # print((time.time()-t1)/counter)
#     # counter+=1
# print(f'average time:{(time.time()-tt)/100}s')
    # # 获取内存使用情况
    # current, peak = tracemalloc.get_traced_memory()
    # print(f"Current memory usage: {current / 1024:.2f} KB")
    # print(f"Peak memory usage: {peak / 1024:.2f} KB")

# 停止跟踪
# tracemalloc.stop()