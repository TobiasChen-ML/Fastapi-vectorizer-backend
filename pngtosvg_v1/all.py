from PIL import Image,ImageChops,ImageEnhance,ImageFilter
import cv2.mat_wrapper
from potrace import Bitmap, POTRACE_TURNPOLICY_MINORITY
import copy
import glob
import time
from multiprocessing import  Process
import random
from shapely.geometry import Polygon, Point ,MultiPolygon
import cv2
import svgpathtools as svg  
import numpy as np
from scipy import stats
from svg.path import parse_path
from typing import Iterable
import math
import typing



def calculate_path_bbox(svg_path_data):
    path = parse_path(svg_path_data)
    min_x = float('inf')
    min_y = float('inf')
    max_x = float('-inf')
    max_y = float('-inf')
    for segment in path:
        if segment.start.real < min_x:
            min_x = segment.start.real
        if segment.start.imag < min_y:
            min_y = segment.start.imag
        if segment.start.real > max_x:
            max_x = segment.start.real
        if segment.start.imag > max_y:
            max_y = segment.start.imag

        if hasattr(segment, 'end'):
            if segment.end.real < min_x:
                min_x = segment.end.real
            if segment.end.imag < min_y:
                min_y = segment.end.imag
            if segment.end.real > max_x:
                max_x = segment.end.real
            if segment.end.imag > max_y:
                max_y = segment.end.imag
    width = max_x - min_x
    height = max_y - min_y
    
    return min_x,min_y,max_x,max_y

def getsvgrectfunc(path, n=20):  
    polygon_vertices = []
    # 解析 SVG 路径  
    pp = svg.parse_path(path)  
      
    # 生成等间距的点  
    points = [pp.point(pos) for pos in np.linspace(0, 1, n)]  

    # 初始化新的 SVG 路径字符串  
    new_path_str = ["M"]  # 开始移动命令  
      
    # 遍历点并添加到路径字符串中  
    for i, point in enumerate(points):  
        x, y = point.real, point.imag  
        # 对于第一个点之后的每个点，添加 'L' 命令（如果不是第一个点）  
        if i > 0:  
            new_path_str.append("L")  
        # 添加坐标  
        new_path_str.append(f"{x} {y}")  

        polygon_vertices.append((point.real, point.imag ))
    # 添加 'z' 命令以关闭路径  
    new_path_str.append("z")  
      
    # 将列表转换为字符串并打印  
    new_path_str = " ".join(new_path_str)  
    return polygon_vertices

def check_path_inside(path1,path2,rata=0.8):
    # 判断path1 是否在path2 内

    # 生成path1的点 
    n=50
    path1_polygon_vertices = []
    # 解析 path1 路径  
    pp = svg.parse_path(path1)  
    path1_points = [pp.point(pos) for pos in np.linspace(0, 1, n)] 
    for i, point in enumerate(path1_points):  
        x, y = point.real, point.imag  
        path1_polygon_vertices.append((point.real, point.imag ))

    # 解析 path2 路径  
    path2_polygon_vertices = []
    pp = svg.parse_path(path2)  
    path2_points = [pp.point(pos) for pos in np.linspace(0, 1, n)] 
    for i, point in enumerate(path2_points):  
        x, y = point.real, point.imag  
        path2_polygon_vertices.append((point.real, point.imag ))


    path1_path2_inside_point = []
    polygon = Polygon(path2_polygon_vertices) 
    # 遍历点并添加到路径字符串中  
    for i, point in enumerate(path1_points):  
        x, y = point.real, point.imag  
        point_to_test = Point(x, y)
        is_inside = polygon.contains(point_to_test)  
        if is_inside:
            path1_path2_inside_point.append([x,y])

    if len(path1_path2_inside_point)/ len(path1_points)>rata:
        return True
    else:
        return False


def check_is_inside2(svg_path_data):

    # 生成等间距的点  
    n=50
    inside_points = []
    polygon_vertices = []
    # 解析 SVG 路径  
    pp = svg.parse_path(svg_path_data)  

    points = [pp.point(pos) for pos in np.linspace(0, 1, n)] 
    for i, point in enumerate(points):  
        x, y = point.real, point.imag  
        polygon_vertices.append((point.real, point.imag ))


    polygon = Polygon(polygon_vertices) 
    # 遍历点并添加到路径字符串中  
    for i, point in enumerate(points):  
        x, y = point.real, point.imag  
        # 取上下左右的整数点 是否inside

        for counterx in [k for k in range(-3,3)]:
            for countery in [k for k in range(-3,3)]:
                point_to_test = Point(x+counterx, y+countery)  
                is_inside = polygon.contains(point_to_test)  
                if is_inside:
                    inside_points.append([x+counterx, y+countery])
    return inside_points


def RGB_to_Hex(rgb):
    strs = '#'
    for i in rgb:
        num = int(i) 
        strs += str(hex(num))[-2:].replace('x', '0').upper()
 
    return strs


def pick_color(image,points):
    # color = "#fff"
    colors = []
    for point in points:
        x,y = point
        if len(image.mode) == 3:
            (r,g,b) = image.getpixel((x,y))
  
        if len(image.mode) == 4:
            (r,g,b,a)= image.getpixel((x,y))
            if a == 0:
                continue
        color_hex = RGB_to_Hex([r,g,b])

        # print("点的颜色",x,y,color_hex)
        colors.append(color_hex)

    if colors == []:
        color = 0
    else:
        color = max(colors,key=colors.count)

    # from collections import Counter  
    # counter = Counter(colors)
    # for value, count in counter.items():  
    #     print(f"颜色 {value} 出现了 {count} 次") 
    return color

def remove_rest_points(point_list,path_list):
    remain_points = []
    delete_points = []
    for point in point_list:
        x,y=point
        is_unique = 0
        for path,polygon  in path_list.items():
            point_to_test = Point(x, y)  
            is_inside = polygon.contains(point_to_test)  
            if is_inside:
                delete_points.append(point)
                is_unique = 1
                break

        if is_unique == 0:
            remain_points.append(point)
    return remain_points

def getAllPath(image):
    # 转换svg
    bm = Bitmap(image, blacklevel=0.5)
    # bm.invert()
    plist = bm.trace(
        turdsize=2,
        turnpolicy=POTRACE_TURNPOLICY_MINORITY,
        alphamax=1,
        opticurve=False,
        opttolerance=0.2,
    )

    # 先把所有的path都统计起来
    all_path = []
    for curve in plist:
        parts = []
        fs = curve.start_point
        parts.append(f"M{fs.x},{fs.y}")
        for segment in curve.segments:
            if segment.is_corner:
                a = segment.c
                b = segment.end_point
                parts.append(f"L{a.x},{a.y}L{b.x},{b.y}")
            else:
                a = segment.c1
                b = segment.c2
                c = segment.end_point
                parts.append(f"C{a.x},{a.y} {b.x},{b.y} {c.x},{c.y}")
        parts.append("z")
        all_path.append("".join(parts))
    
    return all_path


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

def segmentBackground(image: np.ndarray, is_all_in_one: bool,
                      kmeans_K: int = 6, kmeans_max_iter: int = 10, kmeans_epsilon: float = 0.1, kmeans_attempts: int = 3,
                      border_thickness: int = 5, border_buffer: int = 1, min_object_size: int = 3) -> np.ndarray:

    if image is None:
        print('空图片!')
        return None

    if 3 == image.ndim and 4 == image.shape[-1]:
        print('已有透明通道!')
        return None

    if min(image.shape[:2]) < 3*border_thickness:
        print('图像过小!')
        return None

    image_height, image_width, image_channels = (
        image.shape if 3 == image.ndim else image.shape + (1,))
    kmeans_flags = cv2.KMEANS_RANDOM_CENTERS
    kmeans_criteria = (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS,
                       kmeans_max_iter, kmeans_epsilon)
    _, label_map, color_centers = cv2.kmeans(
        image.reshape([-1, image_channels]).astype(np.float32),
        kmeans_K, None, kmeans_criteria, kmeans_attempts, kmeans_flags)
    label_map = label_map.reshape([image_height, image_width])

    WHITE_COLOR_THRESH = 240
    white_valids = np.all(color_centers > WHITE_COLOR_THRESH, 1)
    white_labels = np.arange(kmeans_K)[white_valids]
    # numpy.vectorize 太慢了，怀疑没并行
    # white_varify = np.vectorize(lambda x: x in white_labels)

    label_bars = [label_map[:border_thickness, :-border_thickness],
                  label_map[-border_thickness:, border_thickness:],
                  label_map[border_thickness:, :border_thickness],
                  label_map[:-border_thickness, -border_thickness:]]

    is_white_background = False
    background_mask = None
    white_include_number = 0
    min_object_size += (min_object_size+1) % 2
    open_kernel = np.ones([min_object_size, min_object_size])
    for label_bar in label_bars:
        # numpy.vectorize 太慢了，怀疑没并行
        # background_mask = white_varify(label_bar).astype(np.uint8)
        background_mask = np.full_like(label_bar, False, bool)
        for white_label in white_labels:
            background_mask |= label_bar == white_label
        background_mask = background_mask.astype(np.uint8)
        if np.any(cv2.morphologyEx(background_mask, cv2.MORPH_OPEN, open_kernel)):
            white_include_number += 1
        if 2 < white_include_number:
            is_white_background = True
            break

    if is_white_background:
        # numpy.vectorize 太慢了，怀疑没并行
        # background_mask = white_varify(label_map).astype(np.uint8)
        background_mask = np.full_like(label_map, False, bool)
        for white_label in white_labels:
            background_mask |= label_map == white_label
    else:
        background_ID = np.argmax(np.bincount(
            np.concatenate([label_bar.reshape(-1) for label_bar in label_bars])))
        background_mask = label_map == background_ID

    if is_all_in_one:
        return 0 < cv2.dilate(background_mask.astype(np.uint8), np.ones((3, 3), dtype=np.uint8))
        return background_mask

    region_count, region_label, region_stats, region_centroids = cv2.connectedComponentsWithStats(
        background_mask.astype(np.uint8))
    if region_count < 2:
        print('区域过少!')
        return None

    XYXYs = [(box[0], box[1], box[0]+box[2], box[1]+box[3])
             for box in region_stats[1:, :-1]]
    limit = (border_buffer, border_buffer, image_width -
             border_buffer, image_height-border_buffer)

    def border_varify(
        x): return x[0] <= limit[0] or x[1] <= limit[1] or limit[2] <= x[2] or limit[3] <= x[3]
    region_indices = np.arange(1, region_count)[
        list(map(border_varify, XYXYs))]
    # numpy.vectorize 太慢了，怀疑没并行
    # background_filter = np.vectorize(lambda x: x in region_indices)
    # filtered_background_mask = background_filter(region_label)
    filtered_background_mask = np.full_like(region_label, False, bool)
    for region_index in region_indices:
        filtered_background_mask |= region_label == region_index

    return 0 < cv2.dilate(filtered_background_mask.astype(np.uint8), np.ones((3, 3), dtype=np.uint8))
    return filtered_background_mask

def removebackground(img: np.ndarray):
    
    if img.ndim == 3 and img.shape[2] == 4 and np.min(img[:,:,3]) < 128:
        return np.concatenate([img[:,:,:3], np.where(img[:,:,3:] < 128, 0, 255).astype(img.dtype)], axis=2)
    
    content = img[:,:,:3]
    filtered_background_mask = segmentBackground(image=content, is_all_in_one=True)
    alpha = np.where(filtered_background_mask, 0, 255).astype(img.dtype)

    image = np.zeros((content.shape[0], content.shape[1], 4), dtype=np.uint8)
    image[:, :, 0:3] = content
    image[:, :, -1] = alpha

    return image


def drawPalette(colors: np.ndarray, size_mul: int = 1):
    
    size_mul = int(size_mul)
    size_mul = 1 if size_mul < 1 else size_mul
    global_size = 600*size_mul
    if len(colors) <= 4:
        rows = 2
    elif len(colors) <= 9:
        rows = 3
    elif len(colors) <= 16:
        rows = 4
    else:
        rows = 5
    cols = rows
    size = global_size // rows
    palette = np.full(
        (rows*size, cols*size, colors.shape[-1]), fill_value=180, dtype=np.uint8)
    for ind in range(rows+cols):
        cv2.line(palette, (ind*size, 0), (0, ind*size), [80]*3, 2)
    for ind in range(rows+cols):
        cv2.line(palette, ((ind-rows)*size, 0),
                 (ind*size, rows*size), [80]*3, 2)
    for row in range(rows):
        for col in range(cols):
            index = row*cols+col
            if index < len(colors):
                palette[row*size:(row+1)*size, col *
                        size:(col+1)*size] = colors[index]
    for col in range(cols+1):
        cv2.line(palette, (col*size, 0), (col*size, rows*size), [255]*3, 1)
    for row in range(rows+1):
        cv2.line(palette, (0, row*size), (cols*size, row*size), [255]*3, 1)
    return palette


def mergeColor(colors: np.ndarray, numbers: np.ndarray, distance_thresh: float = 20.0, max_iter: int = 2):
 
    max_iter -= 1
    colors_h = np.expand_dims(colors, axis=0)
    colors_v = np.expand_dims(colors, axis=1)
    distances = np.linalg.norm(colors_v-colors_h, axis=2)
    equal_mask = np.less_equal(distances, distance_thresh)
    one_to_N = [set(np.where(ids)[0]) for ids in equal_mask]
    dealt = np.zeros_like(numbers, dtype=bool)
    clusters_indices = []
    for index in range(len(dealt)):
        if dealt[index]:
            continue
        dealt[index] = True
        total_set = one_to_N[index]
        done_set = set([index])
        wait_set = total_set - done_set
        while len(wait_set):
            new_index = list(wait_set)[0]
            dealt[new_index] = True
            total_set.update(one_to_N[new_index])
            done_set.add(new_index)
            # wait_set.remove(new_index)
            wait_set = total_set - done_set
        clusters_indices.append(np.array(list(total_set)))
    new_numbers = np.array([np.sum(numbers[indices])
                           for indices in clusters_indices])
    new_colors = np.array([np.sum(colors[indices]*np.expand_dims(numbers[indices], axis=1), axis=0) /
                           new_numbers[index] for index, indices in enumerate(clusters_indices)])
    if 0 < max_iter:
        return mergeColor(new_colors, new_numbers, distance_thresh, max_iter)
    return new_colors, new_numbers


def pickColor(
    image: np.ndarray,
    degenerate_order: typing.Literal[2, 4, 8, 16] = 8,
    edge_threshold: int | float | None = None,
    edge_diffuse_width: typing.Literal[3, 5] | None = 3,
    kmeans_max_iter: int = 10,
    kmeans_eps: float = 0.1,
    kmeans_attempts: int = 3,
    color_dist_thresh: float = 20.0,
    merge_max_iter: int = 2,
    *,
    drop_white: bool = True,
    sort_base_num: bool = True,
    return_palette: bool = False,
):
    input_image = image
    ret_dict = {}

    if image is None or 0 == image.size:
        return ret_dict

    if image.dtype != np.uint8:
        return ret_dict

    if image.ndim < 2 or 3 < image.ndim:
        return ret_dict

    if image.ndim == 2:
        image = image.reshape(image.shape+(1,))

    alpha_u8 = None
    alpha_fg = None
    if 4 == image.shape[-1]:
        alpha_u8 = image[:, :, 3]
        image = image[:, :, :3]
        alpha_fg = 127 < alpha_u8

    lut = np.array(
        [i//degenerate_order*degenerate_order for i in range(256)], dtype=np.uint8)
    degenerated = cv2.LUT(image, lut)
    # cv2.namedWindow('degenerated', cv2.WINDOW_KEEPRATIO)
    # cv2.imshow('degenerated', degenerated)

    if edge_threshold is None:
        edge_threshold = 256/degenerate_order
    edge = cv2.Canny(degenerated, edge_threshold, edge_threshold)
    # cv2.namedWindow('edge', cv2.WINDOW_KEEPRATIO)
    # cv2.imshow('edge', edge)

    diffused_edge = edge
    if edge_diffuse_width:
        diffused_edge = cv2.dilate(edge, cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (edge_diffuse_width,)*2))
    # cv2.namedWindow('diffused_edge', cv2.WINDOW_KEEPRATIO)
    # cv2.imshow('diffused_edge', diffused_edge)
    flat_region = diffused_edge < 128

    if alpha_fg is None:
        flat_fg_region = flat_region
    else:
        flat_fg_region = np.logical_and(alpha_fg, flat_region)
    if not flat_fg_region.any():
        flat_fg_region = np.full_like(
            flat_fg_region, fill_value=True, dtype=bool)
    # cv2.namedWindow('flat_fg_region', cv2.WINDOW_KEEPRATIO)
    # cv2.imshow('flat_fg_region', flat_fg_region.astype(np.uint8)*255)
    masked_low_order = degenerated[flat_fg_region]

    nBits = int(round(math.log(degenerate_order, 2)))
    set_in_1 = np.zeros(len(masked_low_order), dtype=np.uint32)
    for ch in range(masked_low_order.shape[-1]):
        set_in_1 += masked_low_order[:,
                                     ch].astype(np.uint32)//degenerate_order << ch*nBits

    the_1color, the_inv_ind, the_count = np.unique(
        set_in_1, return_inverse=True, return_counts=True)
    # print(the_1color)
    # print(the_inv_ind)
    # print(the_count)
    pick_1mask = np.zeros_like(the_count, dtype=bool)
    rank_threshold = np.array(sorted(list(set([
        len(str(image.shape[0])),
        len(str(image.shape[1])),
        len(str(sum(image.shape[:2]))),
    ])))[::-1])
    the_ranks = np.array([len(str(int(count))) for count in the_count])
    for rank_thresh in rank_threshold:
        pick_1mask = np.greater_equal(the_ranks, rank_thresh)
        if pick_1mask.any():
            break
    if not pick_1mask.any():
        pick_1mask = np.greater(the_count, np.mean(the_count))
    if not pick_1mask.any():
        pick_1mask[np.argmax(the_count)] = True
    pick_1color = the_1color[pick_1mask]
    pick_count = the_count[pick_1mask]
    # print(pick_1color)
    # print(pick_count)
    pick_inv_mask = np.zeros_like(the_inv_ind, dtype=bool)
    for ind in np.where(pick_1mask)[0]:
        pick_inv_mask |= np.equal(the_inv_ind, ind)
    # print(pick_inv_mask.all(), pick_inv_mask.any())
    # print(len(set_in_1) == len(pick_inv_mask))

    _, label_m, colors_in_raw = cv2.kmeans(
        image[flat_fg_region][pick_inv_mask].astype(np.float32),
        K=len(pick_1color),
        bestLabels=None,
        criteria=(cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS,
                  kmeans_max_iter, kmeans_eps),
        attempts=kmeans_attempts,
        flags=cv2.KMEANS_RANDOM_CENTERS)
    # print(label_m.max())
    # print(colors_in_raw.shape)
    numbers = np.array([np.sum(np.equal(label_m, label_id))
                       for label_id in range(len(colors_in_raw))])

    colors_new, numbers_new = mergeColor(
        colors_in_raw, numbers, distance_thresh=color_dist_thresh, max_iter=merge_max_iter)
    if drop_white:
        no_white_mask = np.any(np.less(colors_new, 240), axis=1)
        colors_new = colors_new[no_white_mask]
        numbers_new = numbers_new[no_white_mask]
    if sort_base_num:
        descend_indices = np.argsort(numbers_new)[::-1]
        colors_new = colors_new[descend_indices]
        numbers_new = numbers_new[descend_indices]

    ret_dict.update({
        'colors': colors_new,
        'numbers': numbers_new
    })

    if return_palette:
        palette = drawPalette(colors_new)
        ret_dict.update({
            'palette': palette
        })

    return ret_dict

def getColor(image):
    colors_bgr = pickColor(image)["colors"]
    all_colors = list()
    for i in range(0, colors_bgr.shape[0]):
        color = colors_bgr[i].tolist()
        color[0], color[2] = color[2], color[0]
        all_colors.append(RGB_to_Hex(color))

    return all_colors

def rgb2hsv(r, g, b):

    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx-mn
    if mx == mn:
        h = 0
    elif mx == r:
        h = (60 * ((g-b)/df) + 360) % 360
    elif mx == g:
        h = (60 * ((b-r)/df) + 120) % 360
    elif mx == b:
        h = (60 * ((r-g)/df) + 240) % 360
    if mx == 0:
        s = 0
    else:
        s = df/mx
    v = mx
    return h, s, v

def hex2bgr(hex:str="#ff7722"):

    if len(hex[1:]) == 3:
        hex = "#" + hex[1] + hex[1] + hex[2] +hex[2] + hex[3]+ hex[3]

    r = int(hex[1:3], 16)
    g = int(hex[3:5], 16)
    b = int(hex[5:7], 16)

    return r,g,b


def compareColors(allcolors,singlecolor):
    r,g,b = hex2bgr(singlecolor)
    h,s,v = rgb2hsv(r,g,b)
    for color in allcolors:
        R, G, B = hex2bgr(color)
        H, S, V = rgb2hsv(R, G, B)
        if abs(h-H) < 30:
            return True
    return False
    
def png2svg(imgaddrs):
    ccc = 0
    tt = 0
    for imgaddr in imgaddrs:
        t1 = time.time()
        image = cv2.imread(imgaddr,-1)



        if image.shape[2] == 3:
            # if max(image.shape[0],image.shape[1]) < 800:
            #     sr_model = super_resolution_predict(SR_MODEL_4x)
            #     image = sr_model.forward(image[:,:,:3])
            image = removebackground(image)

        # 获取颜色，如果遇到点的颜色和这些颜色的H差值太大，直接设为0
        allcolors = getColor(image)


        extend = fenceMap(image)["fence"]

        extend = cv2.morphologyEx(extend, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

        image = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)) 
        image.filter(ImageFilter.SHARPEN)

        image2 = copy.deepcopy(image)

        # # 创建Contrast对象  
        enhancer = ImageEnhance.Contrast(image)  
        
        # 调整对比度（1.0表示原始对比度）  
        contrast_factor = 3 
        image = enhancer.enhance(contrast_factor)

        image = image.convert('L')

        width = image.size[0]
        height = image.size[1]


        # 将图像转换为numpy数组以便进行像素操作  
        array1 = np.array(image)  
        array2 = np.array(extend)  
        
        
        alpha = 0.3  # 权重，可以调整  
        result_array = alpha * array1 + (1 - alpha) * array2


        result_array = np.clip(result_array, 0, 255).astype(np.uint8)  

        # 将结果数组转换回图像  
        image = Image.fromarray(result_array) 
        

        image = ImageChops.invert(image)
        
        # 获取全部路径
        all_path = getAllPath(image)[1:]
        all_path2 = all_path.copy()
        # 路径：颜色
        path_color = dict()

        # 全部路径转polygen多边形
        restpath_dict = dict()
        for restp in all_path:
            polygon_vertices = getsvgrectfunc(restp)
            restpath_dict[restp]=Polygon(polygon_vertices) 
        
        # 循环获取颜色
        point_color = dict()
        while all_path:
        
            # 取第一个路径
            pickpath = all_path[0]
            
            # 剩下的路径
            restpath = all_path[1:]
        
            # 获取第一个path的所有内点
            inside_points = check_is_inside2(pickpath)
            # print(inside_points)
            # 这些内点要排除 不在其他path上，要unique的内点
            
            # 排除选中的path，让其他path 去比较
            restpath_dict2 =  {k: v for k, v in restpath_dict.items() if k != pickpath}  
            
            real_inside_points = remove_rest_points(inside_points,restpath_dict2)
            
            if real_inside_points != []:
                all_path=all_path[1:]
                color_hex = pick_color(image2,real_inside_points)
                path_color[pickpath]=color_hex
            else:
                all_path=all_path[1:]
                if inside_points == []:
                    path_color[pickpath]=0
                else:
                    x,y = inside_points[0]
                    if len(image2.mode) == 3:
                        (r,g,b) = image2.getpixel((x,y))
                        color_hex = RGB_to_Hex([r,g,b])
                        path_color[pickpath] = color_hex
                    if len(image2.mode) == 4:
                        (r,g,b,a)= image2.getpixel((x,y))
                        if a == 0:
                            path_color[pickpath]=0
                        else:
                            color_hex = RGB_to_Hex([r,g,b])
                            if not compareColors(allcolors,color_hex):
                                path_color[pickpath]=0
                            else:
                                path_color[pickpath] = color_hex




        mymask = []
        mypath = []
        
        # 把color为0的path和正常的path分开。
        for parts in all_path2:
            color = path_color[parts]
            if color == 0:
                mymask.append(parts)
            else:
                mypath.append(parts)
        
        # 判断所有mask，哪个在path内部，在的部分组成一个mask，专门让path一个用。
        if len(mymask)>0:
            maskcounter = 0
            svgs = ['''<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width2} {height2}">'''.format(width=width,height=height,width2=width,height2=height)]
            maskmask = dict()
            for part in mypath:
                masklist = []
                color = path_color[part]
                for mask in mymask:
                    # 判断mask在path内
                    if check_path_inside(mask,part,rata=0.6):
                        masklist.append(mask)
                
                svgs.append(f'<path stroke="none" fill="{color}" fill-rule="evenodd" d="{part}" mask="url(#myMask{maskcounter})" />'.format(color=str(color)))
                maskmask["myMask{maskcounter}".format(maskcounter=maskcounter)] = masklist
                maskcounter += 1

            for maskid,maskpath in maskmask.items():
                if len(maskpath) >0:
                    svgs.append(f'''<mask id="{maskid}"><rect x="0" y="0" width="{width}" height="{height}" fill="white" />'''.format(width=width,height=height))
                    for maskp in maskpath:
                        svgs.append(f'<path stroke="none" fill="black" fill-rule="evenodd" d="{maskp}" />'.format(maskp=maskp))
                    svgs.append('</mask>')

            svgs.append('</svg>')

            with open(imgaddr.replace(".png",".svg"),'w') as f:
                f.write("".join(svgs))
        else:
            
            svgs = ['''<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width2} {height2}">'''.format(width=width,height=height,width2=width,height2=height)]
        
            for parts in all_path2:
                color = path_color[parts]
                if color == 0:
                    pass
                else:
                    svgs.append(f'<path stroke="none" fill="{color}" fill-rule="evenodd" d="{parts}" />'.format(color=str(color)))
            
            svgs.append('</svg>')

            with open(imgaddr.replace(".png",".svg"),'w') as f:
                f.write("".join(svgs))
        
        t2 = time.time()
        tt += t2-t1
        ccc+=1
        print('平均耗时:',tt/ccc)
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

def split_list(lst, n):
    k, m = divmod(len(lst), n)
    return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]


if __name__ == "__main__":

    # t = 0
    # counter = 1
    # imgaddr = r"e:\LogoDatasets\circle\circle_15.png"
    imgaddrlist = glob.glob(r'E:\LogoDatasets\logo测试集透明\logo测试集透明\*.png')
    my_new_list = split_list(imgaddrlist, 12)
    process_list = []
    for i in range(10):  #开启5个子进程执行fun1函数
        p = Process(target=png2svg,args=(my_new_list[i],)) #实例化进程对象
        p.start()
        process_list.append(p)

    for i in process_list:
        p.join()

    print('结束测试')
