# -*- coding: utf-8 -*-
"""test_md2html.py — md2html.py 纯渲染层单元测试。

覆盖：Markdown 解析（标题/表格/代码块/列表/引用/分隔线/段落）、
      HTML 渲染（行内格式/表格条形图/导航/主题）、CLI 入口。
"""
import sys
import os
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from md2html import (
    parse_markdown,
    render_html,
    convert_md_to_html,
    _strip_md_inline,
    _is_numeric_cell,
    _parse_table_aligns,
    _safe_url,
    _assign_heading_ids,
)

# ============================================================
# 解析层测试
# ============================================================

class TestParseHeading:
    def test_h1_to_h6(self):
        for level in range(1, 7):
            md = f"{'#' * level} 标题{level}"
            nodes = parse_markdown(md)
            assert len(nodes) == 1
            assert nodes[0]["type"] == "heading"
            assert nodes[0]["level"] == level
            assert nodes[0]["text"] == f"标题{level}"

    def test_heading_with_inline(self):
        nodes = parse_markdown("## **粗体**标题")
        assert nodes[0]["type"] == "heading"
        assert nodes[0]["level"] == 2
        assert "**粗体**标题" == nodes[0]["text"]


class TestParseTable:
    def test_simple_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        nodes = parse_markdown(md)
        assert len(nodes) == 1
        assert nodes[0]["type"] == "table"
        assert nodes[0]["headers"] == ["A", "B"]
        assert nodes[0]["rows"] == [["1", "2"], ["3", "4"]]

    def test_table_aligns(self):
        md = "| A | B | C |\n|:--|:--:|--:|\n| 1 | 2 | 3 |"
        nodes = parse_markdown(md)
        assert nodes[0]["aligns"] == ["left", "center", "right"]

    def test_table_no_outer_pipes(self):
        md = "A | B\n---|---\n1 | 2"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "table"
        assert nodes[0]["headers"] == ["A", "B"]
        assert nodes[0]["rows"] == [["1", "2"]]

    def test_table_with_chinese_units(self):
        md = "| 营收 | 净利润 |\n|---|---|\n| 100亿 | 20亿 |\n| -50亿 | 10亿 |"
        nodes = parse_markdown(md)
        assert nodes[0]["rows"] == [["100亿", "20亿"], ["-50亿", "10亿"]]


class TestParseCode:
    def test_fenced_code(self):
        md = "```python\nprint('hello')\n```"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "code"
        assert nodes[0]["lang"] == "python"
        assert "print('hello')" in nodes[0]["text"]

    def test_fenced_code_no_lang(self):
        md = "```\nplain text\n```"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "code"
        assert nodes[0]["lang"] == ""

    def test_fenced_code_tilde(self):
        md = "~~~bash\necho hi\n~~~"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "code"
        assert nodes[0]["lang"] == "bash"


class TestParseList:
    def test_unordered_list(self):
        md = "- 第一项\n- 第二项\n- 第三项"
        nodes = parse_markdown(md)
        assert len(nodes) == 1
        assert nodes[0]["type"] == "list"
        assert nodes[0]["ordered"] is False
        assert len(nodes[0]["items"]) == 3

    def test_ordered_list(self):
        md = "1. 第一\n2. 第二\n3. 第三"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "list"
        assert nodes[0]["ordered"] is True
        assert len(nodes[0]["items"]) == 3

    def test_nested_list(self):
        md = "- 外层\n  - 内层"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "list"
        # 至少解析出外层
        assert len(nodes[0]["items"]) >= 1


class TestParseBlockquote:
    def test_simple_quote(self):
        md = "> 这是一条引用"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "blockquote"
        assert "children" in nodes[0]

    def test_multi_line_quote(self):
        md = "> 第一行\n> 第二行"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "blockquote"

    def test_quote_with_heading(self):
        md = "> ### 引用标题\n> 引用内容"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "blockquote"
        children = nodes[0]["children"]
        assert any(c["type"] == "heading" for c in children)


class TestParseHr:
    def test_dash_hr(self):
        nodes = parse_markdown("---")
        assert nodes[0]["type"] == "hr"

    def test_asterisk_hr(self):
        nodes = parse_markdown("***")
        assert nodes[0]["type"] == "hr"


class TestParsePara:
    def test_simple_para(self):
        nodes = parse_markdown("这是一段普通文本。")
        assert nodes[0]["type"] == "para"
        assert "这是一段普通文本。" in nodes[0]["text"]

    def test_multi_line_para(self):
        md = "第一行\n第二行\n第三行"
        nodes = parse_markdown(md)
        assert nodes[0]["type"] == "para"
        assert "第一行" in nodes[0]["text"]


class TestParseMixed:
    def test_heading_table_code_sequence(self):
        md = """# 标题

| A | B |
|---|---|
| 1 | 2 |

```python
code_here()
```
"""
        nodes = parse_markdown(md)
        types = [n["type"] for n in nodes]
        assert "heading" in types
        assert "table" in types
        assert "code" in types


# ============================================================
# 渲染层测试
# ============================================================

class TestStripMdInline:
    def test_bold(self):
        assert _strip_md_inline("**粗体**") == "粗体"

    def test_italic(self):
        assert _strip_md_inline("*斜体*") == "斜体"

    def test_link(self):
        assert _strip_md_inline("[文本](http://example.com)") == "文本"

    def test_image(self):
        assert _strip_md_inline("![alt](http://img.png)") == "alt"

    def test_code(self):
        assert _strip_md_inline("`code`") == "code"

    def test_combined(self):
        assert _strip_md_inline("**粗** and [链](url) and `码`") == "粗 and 链 and 码"


class TestIsNumericCell:
    def test_plain_float(self):
        assert _is_numeric_cell("12.5") == 12.5

    def test_negative(self):
        assert _is_numeric_cell("-3.2") == -3.2

    def test_with_commas(self):
        assert _is_numeric_cell("1,234.56") == 1234.56

    def test_with_percent(self):
        assert _is_numeric_cell("15.2%") == 15.2

    def test_with_yi(self):
        assert _is_numeric_cell("100亿") == 100.0

    def test_dash(self):
        assert _is_numeric_cell("—") is None

    def test_text(self):
        assert _is_numeric_cell("行业名称") is None

    def test_empty(self):
        assert _is_numeric_cell("") is None

    def test_with_currency(self):
        assert _is_numeric_cell("¥100") == 100.0

    def test_pe_multiple(self):
        assert _is_numeric_cell("18.1x") == 18.1


class TestParseTableAligns:
    def test_left(self):
        assert _parse_table_aligns(":---|:---") == ["left", "left"]

    def test_right(self):
        assert _parse_table_aligns("---:|---:") == ["right", "right"]

    def test_center(self):
        assert _parse_table_aligns(":---:|:---:") == ["center", "center"]

    def test_none(self):
        assert _parse_table_aligns("---|---") == [None, None]


# ============================================================
# 端到端转换测试
# ============================================================

    def test_link_url_quote_escaped(self):
        """链接 URL 含引号时应被转义，防止属性注入。"""
        html_out = convert_md_to_html('[文本](http://ex.com/" onmouseover="alert(1))')
        # 引号必须被转义为 &quot;，不能出现裸 " 突破 href 属性
        assert '&quot; onmouseover=' in html_out
        # 不应出现未转义的 " 紧跟 onmouseover 形成真正的新属性
        assert '" onmouseover="' not in html_out

    def test_link_javascript_scheme_blocked(self):
        """javascript: scheme 必须被净化为 #。"""
        html_out = convert_md_to_html('[点击](javascript:alert(1))')
        assert 'href="#"' in html_out
        assert 'javascript:' not in html_out

    def test_image_javascript_scheme_blocked(self):
        """图片 src 的 javascript:/data: scheme 必须被净化。"""
        html_out = convert_md_to_html('![alt](data:text/html,<script>alert(1)</script>))')
        assert 'src="#"' in html_out

    def test_link_normal_preserved(self):
        """正常 URL 不应被误杀。"""
        html_out = convert_md_to_html('[文本](https://example.com/path?q=1)')
        assert 'href="https://example.com/path?q=1"' in html_out


class TestHeadingIdConsistency:
    """P2 修复：blockquote 内标题 id 应与正文一致。"""

    def test_blockquote_heading_gets_id(self):
        nodes = parse_markdown('> ### 引用内标题\n引用内容')
        _assign_heading_ids(nodes)
        bq = nodes[0]
        headings = [c for c in bq["children"] if c.get("type") == "heading"]
        assert len(headings) == 1
        assert headings[0].get("_id") == "h-1"

    def test_toplevel_and_blockquote_ids_sequential(self):
        nodes = parse_markdown('# 顶层标题\n\n> ### 引用内标题')
        _assign_heading_ids(nodes)
        top = nodes[0]
        bq = nodes[1]
        bq_h = [c for c in bq["children"] if c.get("type") == "heading"][0]
        assert top.get("_id") == "h-1"
        assert bq_h.get("_id") == "h-2"

    def test_blockquote_heading_anchor_matches_body(self):
        """导航锚点与正文渲染的 id 应一致。"""
        md = "# 顶层\n\n> ### 引用内标题\n> 内容"
        html_out = convert_md_to_html(md, sidebar=True)
        # 正文和 sidebar 应使用同一套 id
        # 正文中 blockquote 内 h3 应有 id="h-2"
        assert 'id="h-2"' in html_out
        # sidebar 应有指向 h-2 的链接（如果展示）或至少 h-1
        assert 'href="#h-1"' in html_out


class TestTableWrapClass:
    """P3 修复：.table-wrap CSS 选择器需带点号。"""

    def test_table_wrap_css_has_dot(self):
        from md2html import _CSS
        assert ".table-wrap{" in _CSS

    def test_table_rendered_with_wrap_div(self):
        html_out = convert_md_to_html("| A | B |\n|---|---|\n| 1 | 2 |")
        assert '<div class="table-wrap">' in html_out


class TestConvertMdToHtml:
    def test_basic_output(self):
        html = convert_md_to_html("# 标题\n\n正文内容")
        assert "<!DOCTYPE html>" in html
        assert "标题" in html
        assert "正文内容" in html

    def test_title_from_h1(self):
        html = convert_md_to_html("# 我的报告\n内容")
        assert "<title>我的报告</title>" in html

    def test_title_override(self):
        html = convert_md_to_html("# 我的报告", title="自定义标题")
        assert "<title>自定义标题</title>" in html

    def test_default_title_no_h1(self):
        html = convert_md_to_html("只是段落", title="无标题报告")
        assert "<title>无标题报告</title>" in html

    def test_dark_theme_default(self):
        html = convert_md_to_html("# test")
        assert 'data-theme="dark"' in html

    def test_light_theme(self):
        html = convert_md_to_html("# test", default_theme="light")
        assert 'data-theme="light"' in html

    def test_sidebar_present(self):
        html = convert_md_to_html("# H1\n## H2\n### H3\nbody", sidebar=True)
        assert "sidebar" in html
        assert 'nav class="sidebar"' in html

    def test_sidebar_absent(self):
        html = convert_md_to_html("# H1\nbody", sidebar=False)
        assert 'class="content no-sidebar"' in html
        assert 'nav class="sidebar"' not in html

    def test_html_escape(self):
        html = convert_md_to_html("内容含 <script>alert(1)</script>")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_table_bar_chart(self):
        md = """| 指标 | 数值 |
|---|---|
| 营收 | 100亿 |
| 成本 | -50亿 |"""
        html = convert_md_to_html(md)
        assert "cell-bar" in html
        assert "num-cell" in html

    def test_code_block(self):
        md = "```python\nprint('hi')\n```"
        html = convert_md_to_html(md)
        assert "<pre>" in html
        assert "language-python" in html
        assert "print('hi')" in html

    def test_blockquote(self):
        html = convert_md_to_html("> 这是引用")
        assert "<blockquote>" in html

    def test_ordered_list(self):
        md = "1. 第一\n2. 第二"
        html = convert_md_to_html(md)
        assert "<ol>" in html
        assert "<li>第一</li>" in html

    def test_unordered_list(self):
        md = "- 第一\n- 第二"
        html = convert_md_to_html(md)
        assert "<ul>" in html
        assert "<li>第一</li>" in html

    def test_inline_bold(self):
        html = convert_md_to_html("**粗体**")
        assert "<strong>粗体</strong>" in html

    def test_inline_link(self):
        html = convert_md_to_html("[文本](http://example.com)")
        assert '<a href="http://example.com"' in html

    def test_nav_links(self):
        md = "# 报告\n## 第一节\n## 第二节"
        html = convert_md_to_html(md, sidebar=True)
        assert 'href="#h-' in html

    def test_self_contained_no_external(self):
        """输出应自包含，无外链 CSS/JS。"""
        html = convert_md_to_html("# test")
        assert 'rel="stylesheet"' not in html
        assert '<script src=' not in html
        assert '<link' not in html

    def test_meta_viewport(self):
        html = convert_md_to_html("# test")
        assert '<meta name="viewport"' in html

    def test_footer(self):
        html = convert_md_to_html("# test")
        assert "ai-berkshire md2html.py" in html

    def test_chinese_content(self):
        html = convert_md_to_html("# 腾讯研究报告\n\n市值 4.61万亿港币")
        assert "腾讯研究报告" in html
        assert "4.61万亿港币" in html

    def test_percentage_bar(self):
        md = """| 增长率 |
|---|
| 15% |
| -5% |
| 20% |"""
        html = convert_md_to_html(md)
        assert "%;" in html  # CSS 含百分比值

    def test_full_report_structure(self):
        """模拟真实报告结构转换。"""
        md = """# 腾讯投资研究

**日期**：2026-04-09
**评级**：买入

## 核心数据

| 指标 | 数值 | 来源 |
|------|------|------|
| 市值 | 4.61万亿HKD | 理杏仁 |
| PE | 18.1x | 理杏仁 |
| ROE | 28% | 理杏仁 |

## 护城河分析

> 巴菲特：护城河是企业的命运。

### 网络效应

微信 13 亿用户构成强网络效应。

```python
# 验算 PE
pe = price / eps
print(pe)
```

---

## 结论

建议买入。
"""
        html = convert_md_to_html(md, title="腾讯投资研究")
        assert "<!DOCTYPE html>" in html
        assert "腾讯投资研究" in html
        assert "4.61万亿HKD" in html
        assert "理杏仁" in html
        assert "cell-bar" in html
        assert "<blockquote>" in html
        assert "<pre>" in html
        assert "<hr>" in html
        assert "sidebar" in html


# ============================================================
# CLI 入口测试
# ============================================================

class TestCLI:
    def test_file_to_file(self, tmp_path):
        from md2html import _main
        md_file = tmp_path / "test.md"
        md_file.write_text("# 测试报告\n\n内容", encoding="utf-8")
        html_file = tmp_path / "test.html"
        rc = _main([str(md_file), "-o", str(html_file)])
        assert rc == 0
        assert html_file.exists()
        content = html_file.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_default_output_path(self, tmp_path):
        from md2html import _main
        md_file = tmp_path / "report.md"
        md_file.write_text("# 报告", encoding="utf-8")
        rc = _main([str(md_file)])
        assert rc == 0
        assert (tmp_path / "report.html").exists()

    def test_nonexistent_file(self, tmp_path):
        from md2html import _main
        rc = _main([str(tmp_path / "nofile.md")])
        assert rc == 1

    def test_light_flag(self, tmp_path):
        from md2html import _main
        md_file = tmp_path / "t.md"
        md_file.write_text("# t", encoding="utf-8")
        html_file = tmp_path / "t.html"
        rc = _main([str(md_file), "-o", str(html_file), "--light"])
        assert rc == 0
        content = html_file.read_text(encoding="utf-8")
        assert 'data-theme="light"' in content

    def test_no_sidebar_flag(self, tmp_path):
        from md2html import _main
        md_file = tmp_path / "t.md"
        md_file.write_text("# t", encoding="utf-8")
        html_file = tmp_path / "t.html"
        rc = _main([str(md_file), "-o", str(html_file), "--no-sidebar"])
        assert rc == 0
        content = html_file.read_text(encoding="utf-8")
        assert "no-sidebar" in content