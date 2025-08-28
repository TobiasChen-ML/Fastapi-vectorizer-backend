import cv2.mat_wrapper
import cv2
import numpy as np
from scipy import stats
from typing import Iterable

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