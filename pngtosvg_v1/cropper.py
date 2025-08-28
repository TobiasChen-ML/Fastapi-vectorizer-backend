import cv2
import numpy as np
from PIL import Image
import math
import torch
import torchvision.transforms.functional as F


def get_padding(img, des_h, des_w, margin=5):
    """
    img: PIL img
    des_h, des_w : int
    margin: int
    """
    # get padding size for padding and resize transform, the destination w and h are inputs
    w, h = img.size[0], img.size[1]
    scale = min(float(des_h-2*margin)/h, float(des_w-2*margin)/w)
    pad_h, pad_w = math.ceil((des_h-scale*h)/(2*scale)), math.ceil((des_w-scale*w)/(2*scale))
    return pad_h, pad_w


def pad_and_resize(img, des_h, des_w, margin=5):
    """
    img: PIL img
    des_h, des_w : int
    margin: int
    """
    w, h = img.size[0], img.size[1]
    pad_h, pad_w = get_padding(img, des_h, des_w, margin)
    img = F.pad(img,padding=[pad_w,pad_h],fill=150)
    mid_w, mid_h = img.size[0], img.size[1]
    img = F.resize(img,[des_h,des_w])
    h_scale, w_scale = float(des_h)/mid_h, float(des_w)/mid_w
    return img, (h_scale,w_scale),(pad_h,pad_w),(w,h)


def transform_to_origin(xyxy, mid_scale, paddings,ori_size):
    """
    xyxy: torch tensor shape (N,4)
    mid_scale: tuple(int, int)
    paddings: tuple(int, int)
    ori_size: tuple(int, int)
    """
    h_scale, w_scale = mid_scale
    pad_h, pad_w = paddings
    w,h = ori_size
    x1, y1, x2, y2 = xyxy[:,0:1], xyxy[:, 1:2],xyxy[:, 2:3],xyxy[:,3:4]
    x1, y1, x2, y2 = x1/w_scale-pad_w, y1/h_scale-pad_h, x2/w_scale-pad_w, y2/h_scale-pad_h
    x1, y1, x2, y2 = x1.clamp(0,w), y1.clamp(0,h), x2.clamp(0,w), y2.clamp(0,h)
    new_xyxy = torch.concat([x1,y1,x2,y2],dim=-1)
    return new_xyxy


# custom pad and torch resize transformation
class PadAndResize(object):
    def __init__(self, output_size, margin=5):
        assert isinstance(output_size, int)
        self.output_size = output_size
        self.margin = margin

    def __call__(self, image):
        output_img,_,_,_ = pad_and_resize(image,self.output_size,self.output_size,self.margin)
        return output_img


def bboxes_iou(bboxes_a, bboxes_b, xyxy=True, giou=False):
    """
    Args:
        bboxes_a: tensor, shape [N,4]
        bboxes_b: tensor, shape [M,4]
        xyxy: bool, true if bboxes are in xyxy format,
              flase if bboxes are in xywh format
    Return:
        pairwise iou: tensor, shape [N,M]
    """
    if bboxes_a.shape[1] != 4 or bboxes_b.shape[1] != 4:
        raise IndexError

    if xyxy:
        tl = torch.max(bboxes_a[:, None, :2], bboxes_b[None, :, :2])  # [N,M,2]
        br = torch.min(bboxes_a[:, None, 2:], bboxes_b[None, :, 2:])  # [N,M,2]
        area_a = torch.prod(bboxes_a[:, 2:] - bboxes_a[:, :2], 1)  # [N]
        area_b = torch.prod(bboxes_b[:, 2:] - bboxes_b[:, :2], 1)  # [M]
        if giou:
            enclosed_tl = torch.min(bboxes_a[:, None, :2], bboxes_b[None, :, :2])  # [N,M,2]
            enclosed_br = torch.max(bboxes_a[:, None, 2:], bboxes_b[None, :, 2:])
    else:
        tl = torch.max(bboxes_a[:, None, :2], bboxes_b[None, :, :2])
        br = torch.min(
            bboxes_a[:, None, :2] + bboxes_a[:, None, 2:],
            bboxes_b[None, :, :2] + bboxes_b[None, :, 2:]
        )
        area_a = torch.prod(bboxes_a[:, 2:], 1)  # [N]
        area_b = torch.prod(bboxes_b[:, 2:], 1)  # [M]
        if giou:
            enclosed_tl = torch.min(bboxes_a[:, None, :2], bboxes_b[None, :, :2])
            enclosed_br = torch.max(
                bboxes_a[:, None, :2] + bboxes_a[:, None, 2:],
                bboxes_b[None, :, :2] + bboxes_b[None, :, 2:]
            )  # [N,M,2]


    is_overlapped = (tl < br).type(tl.dtype).prod(dim=2)  # [N,M]
    area_overlap = torch.prod(br-tl, 2) * is_overlapped  # [N,M]
    union = area_a[:, None] + area_b[None, :] - area_overlap
    ious = area_overlap/union
    if giou:
        enclosed_wh = (enclosed_br-enclosed_tl).clamp(min=0)
        enclosed_area = torch.maximum(torch.tensor([1e-6]).to(enclosed_wh.device),
                                      enclosed_wh[:,:,0] * enclosed_wh[:,:,1])
        gious = ious - (enclosed_area-union)/enclosed_area
        return 1 - gious
    else:
        return ious


def bboxes_overlap(bboxes_a, bboxes_b, xyxy=True):
    """
    Args:
        bboxes_a: tensor, shape [N,4]
        bboxes_b: tensor, shape [M,4]
        xyxy: bool, true if bboxes are in xyxy format,
              flase if bboxes are in xywh format
    Return:
        pairwise overlap_ratio: tensor, shape [N,M]
    """
    if bboxes_a.shape[1] != 4 or bboxes_b.shape[1] != 4:
        raise IndexError

    if xyxy:
        tl = torch.max(bboxes_a[:, None, :2], bboxes_b[None, :, :2])  # [N,M,2]
        br = torch.min(bboxes_a[:, None, 2:], bboxes_b[None, :, 2:])  # [N,M,2]
        area_a = torch.prod(bboxes_a[:, 2:] - bboxes_a[:, :2], 1)  # [N]
        area_b = torch.prod(bboxes_b[:, 2:] - bboxes_b[:, :2], 1)  # [M]

    else:
        tl = torch.max(bboxes_a[:, None, :2], bboxes_b[None, :, :2])
        br = torch.min(
            bboxes_a[:, None, :2] + bboxes_a[:, None, 2:],
            bboxes_b[None, :, :2] + bboxes_b[None, :, 2:]
        )
        area_a = torch.prod(bboxes_a[:, 2:], 1)  # [N]
        area_b = torch.prod(bboxes_b[:, 2:], 1)  # [M]


    is_overlapped = (tl < br).type(tl.dtype).prod(dim=2)  # [N,M]
    area_overlap = torch.prod(br-tl, 2) * is_overlapped  # [N,M]
    min_area = torch.minimum(area_a[:, None],area_b[None, :])
    overlap_ratio = area_overlap/min_area

    return overlap_ratio

def bboxes_intersection_baseMin(bboxes_a, bboxes_b):
    
    if bboxes_a.shape[1] != 4 or bboxes_b.shape[1] != 4:
        raise IndexError

    tl = torch.max(bboxes_a[:, None, :2], bboxes_b[None, :, :2])  # [N,M,2]
    br = torch.min(bboxes_a[:, None, 2:], bboxes_b[None, :, 2:])  # [N,M,2]
    area_a = torch.prod(bboxes_a[:, 2:] - bboxes_a[:, :2], 1)  # [N]
    area_b = torch.prod(bboxes_b[:, 2:] - bboxes_b[:, :2], 1)  # [M]

    is_overlapped = (tl < br).type(tl.dtype).prod(dim=2)  # [N,M]
    area_overlap = torch.prod(br-tl, 2) * is_overlapped  # [N,M]
    min_area = torch.minimum(area_a[:, None], area_b[None, :])  # [N,M]
    overlap_ratio = area_overlap/min_area

    return overlap_ratio, area_overlap


def segmentBackground(image: np.ndarray, is_all_in_one: bool,
                      kmeans_K: int = 12, kmeans_max_iter: int = 10, kmeans_epsilon: float = 0.1, kmeans_attempts: int = 3,
                      border_thickness: int = 5, border_buffer: int = 1, min_object_size: int = 3) -> np.ndarray:

    if image is None or image.size == 0:
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
        background_mask = np.full_like(label_map, False, bool)
        for white_label in white_labels:
            background_mask |= label_map == white_label
    else:
        background_ID = np.argmax(np.bincount(
            np.concatenate([label_bar.reshape(-1) for label_bar in label_bars])))
        background_mask = label_map == background_ID

    if is_all_in_one:
        return background_mask

    region_count, region_label, region_stats, region_centroids = cv2.connectedComponentsWithStats(
        background_mask.astype(np.uint8))
    if region_count < 2:
        print('区域过少!')
        return background_mask

    XYXYs = [(box[0], box[1], box[0]+box[2], box[1]+box[3])
             for box in region_stats[1:, :-1]]
    limit = (border_buffer, border_buffer, image_width -
             border_buffer, image_height-border_buffer)

    def border_varify(
        x): return x[0] <= limit[0] or x[1] <= limit[1] or limit[2] <= x[2] or limit[3] <= x[3]
    region_indices = np.arange(1, region_count)[
        list(map(border_varify, XYXYs))]
    filtered_background_mask = np.full_like(region_label, False, bool)
    for region_index in region_indices:
        filtered_background_mask |= region_label == region_index

    return filtered_background_mask


def objectBoxes(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if image is None or 0 == image.size:
        return None, None

    if image.ndim != 2:
        return None, None

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(image)
    stats = stats[1:]
    if len(stats) == 0:
        return None, None

    xywh = stats[:, :4].copy()
    xyxy = xywh.copy()
    xyxy[:, 2] += xyxy[:, 0]
    xyxy[:, 3] += xyxy[:, 1]
    return xyxy, xywh


def filterBoxes(exist_xywh: list, xyxys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    exist_xyxy = np.array(exist_xywh).reshape((1, 4))
    exist_xyxy[:, 2] += exist_xyxy[:, 0]
    exist_xyxy[:, 3] += exist_xyxy[:, 1]
    areas = (xyxys[:, 2] - xyxys[:, 0]) * (xyxys[:, 3] - xyxys[:, 1])
    ratio, area = bboxes_intersection_baseMin(
        torch.tensor(exist_xyxy), torch.tensor(xyxys))
    area = area[0].numpy()
    ratio = area / areas
    xyxy = xyxys[ratio < 0.5]
    xywh = xyxy.copy()
    xywh[:, 2] -= xywh[:, 0]
    xywh[:, 3] -= xywh[:, 1]
    return xyxy, xywh


def clusterBoxes(xyxys: np.ndarray, outs: list[np.ndarray] = None) -> list:
    xyxys = xyxys.copy()
    whs = xyxys[:, :2].copy()
    whs = xyxys[:, 2:] - whs
    med = np.median(whs, axis=0)
    haf = (med / 2).astype(np.int32)
    xyxys[:, :2] -= haf
    xyxys[:, 2:] += haf
    ratio, area = bboxes_intersection_baseMin(
        torch.tensor(xyxys), torch.tensor(xyxys))
    area = area.numpy()
    mask = area > 0
    ready = np.full(len(xyxys), False, dtype=bool)
    clus = dict[int, list[int]]()
    for ind in range(len(xyxys)):
        if ready[ind]:
            continue
        ready[ind] = True
        clus[ind] = [ind,]
        a_que = []
        idxs = list(np.where(mask[ind, :])[0])
        for idx in idxs:
            if ready[idx]:
                continue
            a_que.append(idx)
        while len(a_que):
            sub = a_que.pop()
            if ready[sub]:
                continue
            idxs = list(np.where(mask[sub, :])[0])
            for idx in idxs:
                if ready[idx]:
                    continue
                a_que.append(idx)
            ready[sub] = True
            clus[ind].append(sub)
    new_xyxys = []
    for clu in clus.values():
        a_clu = xyxys[clu]
        new_xyxys.append(np.concatenate(
            [a_clu[:, :2].min(axis=0)+haf, a_clu[:, 2:].max(axis=0)-haf]))
    new_xyxys = np.stack(new_xyxys, axis=0)
    new_xywhs = new_xyxys.copy()
    new_xywhs[:, 2] -= new_xywhs[:, 0]
    new_xywhs[:, 3] -= new_xywhs[:, 1]
    if isinstance(outs, list):
        outs.clear()
        outs.append(np.array(new_xyxys))
        outs.append(np.array(new_xywhs))
    xywhs = sorted(new_xywhs, reverse=True, key=lambda x: x[2]*x[3])
    return list(xywhs[0])

from ultralytics.engine.results import Results
from ultralytics import YOLO

MODEL = YOLO('./algorithm/pngtosvg_v1/yolov8n-+3000-start_over100.pt')

SCORE_THR = 0.5
SAVE_NAMES = {
        0: 'aux-text',
        1: 'main-image',
        2: 'main-text',
        3: 'text-combination',
    }

class LogoCropper:
    def __init__(self, score_thr=SCORE_THR, model=MODEL, save_names=SAVE_NAMES, device='cpu'):
        self.model = model
        self.score_thr = score_thr
        self.save_names = save_names
        self.device = device

    def _crop_one_img(self, in_img: np.ndarray, crops_coordinate: dict = None):
        if in_img.ndim < 3 or 1 == in_img.shape[-1]:
            in_img = cv2.cvtColor(in_img, cv2.COLOR_GRAY2BGR)
        if in_img.dtype != np.uint8:
            in_img = cv2.normalize(in_img, None, 0, 255,
                                   cv2.NORM_MINMAX, cv2.CV_8U)
        cvt = cv2.cvtColor(in_img[:, :, :3], cv2.COLOR_BGR2RGB)
        image = Image.fromarray(cvt)
        # pad and resize image
        input_img, mid_scale, paddings, ori_size = pad_and_resize(image, des_h=480, des_w=896, margin=20)
        # predict
        # t1 = time.time()
        results: list[Results] = self.model.predict(input_img, conf=self.score_thr, device=self.device, imgsz=(896, 480),)
        # print('predict crop:{}s'.format(time.time()-t1))
        # extract results
        names = results[0].names
        cls = results[0].boxes.cls.cpu()  # tensor (x,)
        # scores = results[0].boxes.conf.cpu()  # tensor (x,)
        xyxy = results[0].boxes.xyxy.cpu()  # tensor (x,4)
        # compute area
        areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])  # tensor (x,)
        mask = torch.full_like(areas, True, dtype=torch.bool)
        # supress small bboxes that is > 0.5 overlapped with bigger bboxes
        # overlap_ratio = bboxes_overlap(xyxy, xyxy, xyxy=True)




        # 交集去除

        # # 主图的交集比例大于0.5的去除，其他的大于0.2时去除
        # overlap_ratio, area_overlap = bboxes_intersection_baseMin(xyxy, xyxy)
        # overlap_idx = torch.where(overlap_ratio > 0.2)
        # for idx_a, idx_b in zip(*overlap_idx):
        #     if idx_a != idx_b:
        #         if areas[idx_b] <= areas[idx_a] and ('text-combination' == names[int(cls[idx_a])]):
        #             if 'main-image' == names[int(cls[idx_b])]:
        #                 if 0.5 < area_overlap[idx_a, idx_b] / areas[idx_b]:
        #                     mask[idx_b] = False
        #             else:
        #                 mask[idx_b] = False
        #         elif areas[idx_a] < areas[idx_b] and ('text-combination' == names[int(cls[idx_b])]):
        #             if 'main-image' == names[int(cls[idx_a])]:
        #                 if 0.5 < area_overlap[idx_a, idx_b] / areas[idx_a]:
        #                     mask[idx_a] = False
        #             else:
        #                 mask[idx_a] = False

        # cls = cls[mask]
        # # scores = scores[mask]
        # xyxy = xyxy[mask]
        # areas = areas[mask]








        # transform images to original size
        new_xyxy = transform_to_origin(xyxy, mid_scale, paddings, ori_size)
        num_bbox = cls.shape[0]
        crops = dict[str, np.ndarray]()
        crops_rectangles = dict[str, np.ndarray]()
        if in_img.shape[2] == 4:
            img_with_bg = in_img
        else:
            bg = segmentBackground(
                in_img, False, kmeans_K=6, kmeans_max_iter=10, kmeans_epsilon=1.0, kmeans_attempts=10)
            alpha = ((~bg).astype(np.uint8)*255).reshape(bg.shape+(1,))
            img_with_bg = np.concatenate([in_img, alpha], axis=-1)
        # tt2 = time.time()
        for i in range(num_bbox):
            [x1, y1, x2, y2] = new_xyxy[i].to(torch.int).tolist()
            x, y, w, h = x1, y1, x2 - x1, y2 - y1
            rgba = img_with_bg[y1:y2, x1:x2].copy()
            # rgba = in_img[y1:y2, x1:x2].copy()
            # kmeans remove background
            # if rgba.shape[2] == 3:
            #     fore, _, mask = kmeans_rmbg(rgba)
            #     # rgba = np.concatenate([fore, mask[:, :, None]], axis=-1)
            #     rgba = np.concatenate([rgba, mask[:, :, None]], axis=-1)

            keys = names[int(cls[i])]
            if keys in crops:
                img_old = crops[keys]
                rect_area = img_old.shape[0]*img_old.shape[1]
                if rect_area < w*h:
                    crops[keys]=rgba
                    crops_rectangles[keys] = [x, y, w, h]
                    # if isinstance(crops_coordinate, dict):
                    #     crops_coordinate[keys]=[x, y, w, h]
            else:
                crops[keys]=rgba
                crops_rectangles[keys] = [x, y, w, h]
                # if isinstance(crops_coordinate, dict):
                #     crops_coordinate[keys]=[x, y, w, h]
        # print('after:{}s'.format(time.time()-tt2))

        has_main_image = 'main-image' in crops
        has_text_group = 'text-combination' in crops
        has_main_text = 'main-text' in crops
        has_text = has_text_group or has_main_text
        if has_main_image and has_text:
            if isinstance(crops_coordinate, dict):
                crops_coordinate.update(crops_rectangles)
            return crops

        objs_xyxy, objs_xywh = objectBoxes(img_with_bg[:, :, 3])
        outs_of_cluster = None  # []
        if has_main_image:
            # print('有主图')
            objs_xyxy, objs_xywh = filterBoxes(
                crops_rectangles['main-image'], objs_xyxy)
            if len(objs_xyxy):
                x, y, w, h = clusterBoxes(objs_xyxy, outs_of_cluster)
                if outs_of_cluster is not None:
                    objs_xyxy, objs_xywh = outs_of_cluster
                crops['text-combination'] = img_with_bg[y:y+h, x:x+w].copy()
                crops_rectangles['text-combination'] = [x, y, w, h]
        if has_text:
            if has_text_group:
                # print('有文字组')
                objs_xyxy, objs_xywh = filterBoxes(
                    crops_rectangles['text-combination'], objs_xyxy)
            else:
                # print('有主文')
                objs_xyxy, objs_xywh = filterBoxes(
                    crops_rectangles['main-text'], objs_xyxy)
            if len(objs_xyxy):
                x, y, w, h = clusterBoxes(objs_xyxy, outs_of_cluster)
                if outs_of_cluster is not None:
                    objs_xyxy, objs_xywh = outs_of_cluster
                crops['main-image'] = img_with_bg[y:y+h, x:x+w].copy()
                crops_rectangles['main-image'] = [x, y, w, h]
        # img_to_show = img_with_bg.copy()
        # for rec in objs_xywh:
        #     cv2.rectangle(img_to_show, list(rec), (154, 235, 23), 1)
        # cv2.namedWindow('img-to-show', cv2.WINDOW_KEEPRATIO)
        # cv2.imshow('img-to-show', img_to_show)

        if isinstance(crops_coordinate, dict):
            crops_coordinate.update(crops_rectangles)
        return crops

    def crop(self, source, save=False, crops_coordinate: dict = None):
        """
        source could either be a directory of images or a specific image's path
        """
        # print(crops_coordinate)
        return self._crop_one_img(source, crops_coordinate)