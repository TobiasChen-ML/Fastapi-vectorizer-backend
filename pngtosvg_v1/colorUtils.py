
import cv2.mat_wrapper
import cv2
import numpy as np
import math
import typing
from PIL import Image

h_degree = {
    "red":[337.5,360],
    "red2":[-0.1,22.5],
    "orange":[22.5,52.5],
    "yellow":[52.5,67.5],
    "green": [67.5, 97.5],
    "green3": [97.5, 127.5],
    "green2": [127.5, 157.5],
    "tsing":[157.5,187.5],
    "skyblue":[187.5,202.5],
    "blue2":[202.5,232.5],
    "blue":[232.5,262.5],
    "purple":[262.5,307.5],
    "purple-red":[307.5,337.5]
}




def RGB_to_Hex(rgb):
    strs = '#'
    for i in rgb:
        num = int(i) 
        strs += str(hex(num))[-2:].replace('x', '0').upper()
 
    return strs


def quantize_color(r, g, b, bins=8):  
    # 将每个颜色通道的值量化到bins个等级中  
    return (  
        (r // (256 // bins)) * (256 // bins),  
        (g // (256 // bins)) * (256 // bins),  
        (b // (256 // bins)) * (256 // bins)  
    )  
  
def quantize_image(image, bins=8):  

    # image = Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA))
    # 创建一个新的图像来存储量化后的颜色  
    quantized_image = Image.new("RGB", image.size)  
      
    # 遍历图像的每个像素  
    for y in range(image.height):  
        for x in range(image.width):  
            # 获取当前像素的RGB值  
            r, g, b,a = image.getpixel((x, y))  
              
            # 量化颜色  
            qr, qg, qb = quantize_color(r, g, b, bins)  
              
            # 设置量化后的颜色到新的图像中  
            quantized_image.putpixel((x, y), (qr, qg, qb,a))  
      
    return quantized_image


def pick_color(image,points):
    # color = "#fff"
    colors = []
    for point in points:
        try:
            x,y = point
            if len(image.mode) == 3:
                (r,g,b) = image.getpixel((x,y))
    
            if len(image.mode) == 4:
                (r,g,b,a)= image.getpixel((x,y))
                if a < 127:
                    continue
            color_hex = RGB_to_Hex([r,g,b])
            colors.append(color_hex)
        except:
            pass
    if colors == []:
        color = 0
    else:
        color = max(colors,key=colors.count)


    return color










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
    drop_white: bool = False,
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


def is_same_h(h1,h2):
    for k,v in h_degree.items():
        if h1>v[0] and h1<v[1] and h2>v[0] and h2<v[1]:
            return True
    return False

def compareColors_v2(allcolors,singlecolor,delta=30):
    r,g,b = hex2bgr(singlecolor)
    h,s,v = rgb2hsv(r,g,b)

    delta_h = []
    color_h = []
    for color in allcolors:
        R, G, B = hex2bgr(color)
        H, S, V = rgb2hsv(R, G, B)

        if abs(h-H) < delta:
            delta_h.append(abs(h-H))
            color_h.append(color)
        if (360 - abs(h-H)) < delta:
            delta_h.append(360 - abs(h-H))
            color_h.append(color)
    if delta_h == []:
        return False,0
    if s < 20 and v > 255 - 20 and "#FFFFFF" in allcolors:
        return True,"#FFFFFF"
    color_hex = color_h[delta_h.index(min(delta_h))]
    return True,color_hex

def compareColors(allcolors,singlecolor,delta=30):
    r,g,b = hex2bgr(singlecolor)
    h,s,v = rgb2hsv(r,g,b)
    for color in allcolors:
        R, G, B = hex2bgr(color)
        H, S, V = rgb2hsv(R, G, B)
        if abs(h-H) < delta or (360 - abs(h-H)) < delta:
            return True,singlecolor
    if s < 30 and v > 255 - 30 and "#FFFFFF" in allcolors:
        return True,"#FFFFFF"
        
    return False,0