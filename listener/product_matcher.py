import time
from pathlib import Path

import numpy as np
from PIL import Image


class ProductImageMatcher:
    """
    产品图片库映射器。

    在 product_images 目录中放入以产品名称命名的图片即可，
    例如：product_images/iPhone15.png、product_images/机械键盘.jpg。
    未匹配成功的截图会保存到 unknown_products 目录，方便扩充图片库。
    """

    SUPPORTED_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
    }

    def __init__(
        self,
        library_dir=None,
        unknown_dir=None,
        distance_threshold=10
    ):
        if library_dir is None:
            library_dir = (
                Path(__file__).resolve().parent
                / "product_images"
            )

        if unknown_dir is None:
            unknown_dir = (
                Path(__file__).resolve().parent
                / "unknown_products"
            )

        self.library_dir = Path(library_dir)
        self.unknown_dir = Path(unknown_dir)
        self.distance_threshold = distance_threshold

        # 图片库缓存：{产品名: 感知哈希}
        self._library = None

        # 图片库文件指纹，用于检测运行中新增的图片
        self._fingerprint = None

    # ==========================================================
    # 图片库
    # ==========================================================

    def refresh(self):
        """重新扫描 product_images 图片库。"""

        library = {}

        if self.library_dir.exists():

            for path in sorted(
                self.library_dir.iterdir()
            ):

                if (
                    path.suffix.lower()
                    not in self.SUPPORTED_EXTENSIONS
                ):
                    continue

                try:

                    with Image.open(path) as image:

                        library[path.stem] = {
                            "full": self._features(image),
                            "square": self._features(
                                self._square_crop(image)
                            ),
                        }

                except Exception as exc:

                    print(
                        f"[产品图片] 无法读取 "
                        f"{path.name}：{exc}"
                    )

        self._library = library
        self._fingerprint = self._library_fingerprint()

        print(
            f"[产品图片] 图片库已加载："
            f"{len(library)} 张"
        )

        return library

    def ensure_loaded(self):

        if (
            self._library is None
            or self._fingerprint != self._library_fingerprint()
        ):

            self.refresh()

    def _library_fingerprint(self):
        """返回图片库的文件列表指纹。"""

        if not self.library_dir.exists():

            return None

        fingerprint = []

        for path in sorted(
            self.library_dir.iterdir()
        ):

            if (
                path.suffix.lower()
                not in self.SUPPORTED_EXTENSIONS
            ):

                continue

            try:

                fingerprint.append(
                    (
                        path.name,
                        path.stat().st_mtime_ns
                    )
                )

            except OSError:

                continue

        return tuple(fingerprint)

    @staticmethod
    def _features(image):
        """计算一张图片的全部匹配特征。"""

        return {
            "dhash": ProductImageMatcher._dhash(image),
            "ahash": ProductImageMatcher._ahash(image),
            "hist": ProductImageMatcher._color_histogram(image),
        }

    @staticmethod
    def _square_crop(image):
        """取图片居中的正方形区域。"""

        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2

        return image.crop(
            (
                left,
                top,
                left + side,
                top + side
            )
        )

    # ==========================================================
    # 哈希计算
    # ==========================================================

    @staticmethod
    def _dhash(image, hash_size=8):
        """
        计算 dHash 感知哈希。

        dHash 对亮度变化不敏感，
        适合对比同一产品的不同截图。
        """

        gray = (
            image
            .convert("L")
            .resize(
                (hash_size + 1, hash_size),
                Image.LANCZOS
            )
        )

        array = np.asarray(
            gray,
            dtype=np.int16
        )

        bits = (
            array[:, 1:] > array[:, :-1]
        )

        return bits.flatten()

    @staticmethod
    def _ahash(image, hash_size=8):
        """
        平均哈希。

        比较每个像素与整图平均亮度的关系，
        对同一产品但分辨率不同的图片更宽容。
        """

        gray = (
            image
            .convert("L")
            .resize(
                (hash_size, hash_size),
                Image.LANCZOS
            )
        )

        array = np.asarray(
            gray,
            dtype=np.int16
        )

        return (
            array > array.mean()
        ).flatten()

    @staticmethod
    def _color_histogram(image, bins=32):
        """
        颜色直方图。

        用 HSV 色相统计主要颜色分布，
        同一产品的不同角度/裁剪通常颜色仍相近。
        """

        hsv = (
            image
            .convert("HSV")
            .resize(
                (64, 64),
                Image.LANCZOS
            )
        )

        array = np.asarray(
            hsv,
            dtype=np.int16
        )

        hue = array[..., 0]
        weight = array[..., 1] / 255.0

        hist, _ = np.histogram(
            hue,
            bins=bins,
            range=(0, 255),
            weights=weight
        )

        total = hist.sum()

        if total <= 0:

            return np.zeros(
                bins,
                dtype=np.float64
            )

        return hist / total

    # ==========================================================
    # 匹配
    # ==========================================================

    def match(self, image):
        """
        返回 (产品名称, 汉明距离)。

        没有匹配时返回 (None, 最近距离)。
        """

        self.ensure_loaded()

        if not self._library:

            print(
                "[产品图片] 图片库为空，"
                "请先在 product_images 目录放入产品图片"
            )

            return None, None

        gray_array = np.asarray(
            image.convert("L"),
            dtype=np.int16
        )

        if gray_array.std() < 5:

            print(
                "[产品图片] 截图内容过于单一，"
                "可能是空截图，跳过匹配"
            )

            return None, None

        query_dhash = self._dhash(image)
        query_ahash = self._ahash(image)
        query_hist = self._color_histogram(image)

        dhash_limit = max(
            16,
            self.distance_threshold * 2
        )

        ahash_limit = max(
            12,
            self.distance_threshold + 6
        )

        accepted = []
        best_distance = None

        for name, record in (
            self._library.items()
        ):

            best_score = None
            score_dhash = None
            best_dhash = None
            best_ahash = None
            best_hist = 0.0

            for variant in record.values():

                dhash_distance = int(
                    np.count_nonzero(
                        query_dhash != variant["dhash"]
                    )
                )

                ahash_distance = int(
                    np.count_nonzero(
                        query_ahash != variant["ahash"]
                    )
                )

                histogram_similarity = float(
                    np.sum(
                        np.minimum(
                            query_hist,
                            variant["hist"]
                        )
                    )
                )

                # 综合评分：哈希距离越小、颜色越接近越好
                score = (
                    dhash_distance * 0.5
                    + ahash_distance * 0.3
                    + (1.0 - histogram_similarity) * 20.0
                )

                if (
                    best_score is None
                    or score < best_score
                ):

                    best_score = score
                    score_dhash = dhash_distance

                if (
                    best_dhash is None
                    or dhash_distance < best_dhash
                ):

                    best_dhash = dhash_distance

                if (
                    best_ahash is None
                    or ahash_distance < best_ahash
                ):

                    best_ahash = ahash_distance

                if histogram_similarity > best_hist:

                    best_hist = histogram_similarity

            if (
                best_distance is None
                or best_dhash < best_distance
            ):

                best_distance = best_dhash

            # 任一指标接近都认为可能是同一产品，
            # 避免只因为截图包含边角就被判失败
            if (
                best_dhash <= dhash_limit
                or best_ahash <= ahash_limit
                or best_hist >= 0.75
            ):

                accepted.append(
                    (
                        best_score,
                        name,
                        score_dhash
                    )
                )

        if accepted:

            accepted.sort(
                key=lambda item: item[0]
            )

            return accepted[0][1], accepted[0][2]

        return None, best_distance

    # ==========================================================
    # 保存未匹配图片
    # ==========================================================

    def save_unknown(self, image, username, suffix=""):
        """保存未匹配截图，方便之后扩充图片库。"""

        self.unknown_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        safe_username = "".join(
            char
            for char in username
            if char.isalnum()
            or char in "-_"
        ).strip() or "unknown"

        suffix_part = (
            f"_{suffix}"
            if suffix
            else ""
        )

        path = (
            self.unknown_dir
            / (
                f"{safe_username}"
                f"{suffix_part}_"
                f"{int(time.time())}.png"
            )
        )

        image.save(
            path,
            "PNG"
        )

        print(
            f"[产品图片] 未匹配成功，"
            f"截图已保存到：{path}"
        )

        return path
