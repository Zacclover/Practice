import re
import unittest
from pathlib import Path


INDEX_PATH = Path(__file__).resolve().parents[1] / "index.html"


class NativeImageLoadingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_PATH.read_text(encoding="utf-8")

    def test_generated_evidence_images_use_native_lazy_loading_and_async_decoding(self):
        """大量证据图片应由浏览器在接近视口时加载，且不阻塞主线程解码。"""
        evidence_tile_image = re.search(
            r'<img\s+src="\$\{escapeHtml\(image\)\}"\s+alt="证据图片"[^>]*>',
            self.source,
        )
        self.assertIsNotNone(evidence_tile_image)
        assert evidence_tile_image is not None
        image_tag = evidence_tile_image.group(0)
        self.assertIn('loading="lazy"', image_tag)
        self.assertIn('decoding="async"', image_tag)

    def test_detail_and_linked_evidence_images_keep_the_same_native_loading_contract(self):
        """详情和关联证据列表应沿用卡片的非阻塞图片加载策略。"""
        self.assertRegex(
            self.source,
            r'class="detail-image"\s+src="\$\{escapeHtml\(image\)\}"\s+alt="证据图片 \$\{index \+ 1\}"\s+loading="lazy"\s+decoding="async"',
        )
        self.assertRegex(
            self.source,
            r'alt="关联证据缩略图"\s+loading="lazy"\s+decoding="async"',
        )

    def test_eager_introductory_image_is_not_changed(self):
        """首屏系统引导图保持即时加载，避免改变首次使用流程。"""
        introduction_image = re.search(
            r'<img\s+id="systemIntroductionImage"[^>]+>', self.source,
            re.S,
        )
        self.assertIsNotNone(introduction_image)
        assert introduction_image is not None
        self.assertNotIn('loading="lazy"', introduction_image.group(0))


if __name__ == '__main__':
    unittest.main()
