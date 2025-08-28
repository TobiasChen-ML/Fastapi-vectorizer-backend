from .colorUtils import *
from .getPathPoints import *

def getPathColor(all_path,image_copy):
    path_color = dict()
    while all_path:
        pickpath = all_path[0]
        inside_points = pathInnerPoints(pickpath,n=50)

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
                    if a < 127:
                        a_num += 1
                    else:
                        colors.append(RGB_to_Hex([r,g,b]))
                if a_num / len(inside_points) > 0.5:
                    path_color[pickpath] = 0
                else:
                    color_hex = max(colors,key=colors.count)           
                    path_color[pickpath] = color_hex
    return path_color


def splitMaskPath(all_path_copy,path_color):
    mymask,mypath = [],[]
    # 把color为0的path和正常的path分开。
    for parts in all_path_copy:
        color = path_color[parts]
        if color == 0:
            mymask.append(parts)
        else:
            mypath.append(parts)

    return mymask,mypath

def writesvg(is_background,bg_color,mymask,mypath,path_color,width,height,all_path_copy):
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
                svgs.append(f'<path vector-effect="non-scaling-stroke" stroke="none"  fill="{color}" fill-rule="evenodd" d="{parts}" />'.format(color=str(color)))

    svgs.append('</g></svg>')

    return svgs