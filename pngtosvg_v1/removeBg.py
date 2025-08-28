import numpy as np

import cv2.mat_wrapper


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