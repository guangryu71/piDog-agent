"""
测试checker模块的功能
"""
import unittest
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.checker.dynamic_injection import get_checker_md


class TestCheckerFunctionality(unittest.TestCase):
    """测试checker模块的功能"""

    def test_get_checker_md_returns_content(self):
        """测试get_checker_md函数能正确返回内容"""
        content = get_checker_md()
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0, "checker.md内容不应为空")

    def test_get_checker_md_contains_expected_keywords(self):
        """测试checker.md包含预期的关键字"""
        content = get_checker_md()
        expected_keywords = ["工作检查专家", "if_have_error_and_re-execute", "JSON", "suggestion"]
        for keyword in expected_keywords:
            self.assertIn(keyword, content, f"checker.md应包含关键字: {keyword}")

    def test_get_checker_md_file_exists(self):
        """测试checker.md文件确实存在"""
        from agents.checker.dynamic_injection import get_checker_md
        # 这个测试会间接验证文件存在性，因为get_checker_md会抛出异常如果文件不存在
        try:
            content = get_checker_md()
            self.assertTrue(True, "文件存在且可读取")  # 如果没抛出异常，说明文件存在
        except FileNotFoundError:
            self.fail("checker.md文件不存在")


if __name__ == '__main__':
    print("开始测试checker模块功能...")
    unittest.main()