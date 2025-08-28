from potrace import Bitmap, POTRACE_TURNPOLICY_MINORITY
from shapely.geometry import Point
import cv2
import svgpathtools as svg  
import numpy as np
from shapely.geometry import Polygon, Point 

def check_path_inside(path1,path2,rate=0.8):
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
 
    if len(path1_path2_inside_point) / len(path1_points) > rate:
        return True
    else:
        return False

def pathInnerPoints(svg_path_data,n,krange = 3):
 
    # 生成等间距的点  
    
    inside_points = []
    polygon_vertices = []
    # 解析 SVG 路径  
    pp = svg.parse_path(svg_path_data)  

    points = [pp.point(pos) for pos in np.linspace(0, 1, n)] 

    # area = polygon_area([(p.real, p.imag) for p in points ])  
    # if area < 50:
    #     points = [pp.point(pos) for pos in np.linspace(0, 1, 20)]
    # else:
    #     points = [pp.point(pos) for pos in np.linspace(0, 1, n)] 

    for i, point in enumerate(points):  
        x, y = point.real, point.imag  
        polygon_vertices.append((point.real, point.imag ))


    polygon = Polygon(polygon_vertices) 
    # print(polygon.area,polygon.length)
    if krange > 0:
        compactness = polygon.area / (polygon.length ** 2) * 4 * 3.14159
        if compactness < 0.5:
            krange = 2
        if compactness < 0.3:
            krange = 1
        if compactness < 0.2:
            krange = 0
    # 遍历点并添加到路径字符串中  
    for i, point in enumerate(points):  
        x, y = point.real, point.imag  
        # 取上下左右的整数点 是否inside
        for counterx in [k for k in range(-1*krange,krange)]:
            for countery in [k for k in range(-1*krange,krange)]:
                point_to_test = Point(x+counterx, y+countery)  
                is_inside = point_to_test.within(polygon)  
                # is_inside = polygon.contains(point_to_test) 
                if is_inside:
                    inside_points.append([x+counterx, y+countery])
        inside_points.append([x,y])
    return inside_points

def getAllPath(image,turnpolicy=1,turdsize=2,blacklevel=0.5):
    # 转换svg
    bm = Bitmap(image, blacklevel=blacklevel)
    
    # bm.invert()
    plist = bm.trace(
        turdsize=turdsize,
        turnpolicy=turnpolicy,
        alphamax=0,
        opticurve=True,
        opttolerance=0.1,
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


def remove_rest_points(point_list,path_list):
    remain_points = []
    delete_points = []
    for point in point_list:
        x,y=point
        is_unique = 0
        for path,polygon  in path_list.items():
            point_to_test = Point(x, y)  
            # is_inside = polygon.contains(point_to_test)  
            is_inside = point_to_test.within(polygon)
            if is_inside:
                delete_points.append(point)
                is_unique = 1
                break

        if is_unique == 0:
            remain_points.append(point)
    return remain_points

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

def polygon_area(vertices) -> float:  
    """计算多边形面积"""  
    n = len(vertices)  
    area = 0.0  
    for i in range(n):  
        x1, y1 = vertices[i]  
        x2, y2 = vertices[(i + 1) % n]  
        area += x1 * y2 - y1 * x2  
    return abs(area) / 2.0 