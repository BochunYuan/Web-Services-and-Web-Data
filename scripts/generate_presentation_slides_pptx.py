#!/usr/bin/env python3
"""
Generate a PowerPoint deck for the coursework submission.

The PDF slide deck is already generated from code in
`generate_presentation_slides_pdf.py`. This companion script reuses the same
vector slide model and writes a minimal Office Open XML `.pptx` package using
only the Python standard library, which keeps the deck reproducible in the
coursework environment.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "presentation_slides.pptx"
sys.path.insert(0, str(ROOT))

from scripts.generate_presentation_slides_pdf import SLIDE_H, SLIDE_W, build_deck

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcmitype": "http://purl.org/dc/dcmitype/",
    "dcterms": "http://purl.org/dc/terms/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "vt": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_TYPES = {
    "app": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties",
    "core": "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
    "layout": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout",
    "master": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
    "office_document": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
    "slide": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
    "theme": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme",
}

for prefix, uri in NS.items():
    register_namespace(prefix, uri)

EMU_PER_UNIT = 12_700
SLIDE_CX = int(SLIDE_W * EMU_PER_UNIT)
SLIDE_CY = int(SLIDE_H * EMU_PER_UNIT)


def qn(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


def rel_qn(tag: str) -> str:
    return f"{{{REL_NS}}}{tag}"


def xml_bytes(element: Element) -> bytes:
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + tostring(
        element,
        encoding="utf-8",
        short_empty_elements=False,
    )


def emu(value: float) -> int:
    return int(round(value * EMU_PER_UNIT))


def slide_top_from_bottom(y: float, height: float = 0.0) -> int:
    return emu(SLIDE_H - y - height)


def hex_color(rgb: tuple[float, float, float]) -> str:
    return "".join(f"{max(0, min(255, round(channel * 255))):02X}" for channel in rgb)


def add_color(parent: Element, rgb: tuple[float, float, float], tag: str = "solidFill") -> None:
    fill = SubElement(parent, qn("a", tag))
    SubElement(fill, qn("a", "srgbClr"), {"val": hex_color(rgb)})


def add_line_style(parent: Element, rgb: tuple[float, float, float] | None, width: float = 1.0) -> None:
    line = SubElement(parent, qn("a", "ln"), {"w": str(max(12_700, emu(width)))})
    if rgb is None:
        SubElement(line, qn("a", "noFill"))
    else:
        add_color(line, rgb)


def add_group_root(sp_tree: Element) -> None:
    nv_grp = SubElement(sp_tree, qn("p", "nvGrpSpPr"))
    SubElement(nv_grp, qn("p", "cNvPr"), {"id": "1", "name": ""})
    SubElement(nv_grp, qn("p", "cNvGrpSpPr"))
    SubElement(nv_grp, qn("p", "nvPr"))

    grp_sp_pr = SubElement(sp_tree, qn("p", "grpSpPr"))
    xfrm = SubElement(grp_sp_pr, qn("a", "xfrm"))
    SubElement(xfrm, qn("a", "off"), {"x": "0", "y": "0"})
    SubElement(xfrm, qn("a", "ext"), {"cx": "0", "cy": "0"})
    SubElement(xfrm, qn("a", "chOff"), {"x": "0", "y": "0"})
    SubElement(xfrm, qn("a", "chExt"), {"cx": "0", "cy": "0"})


def add_rect_shape(sp_tree: Element, shape_id: int, rect: object) -> int:
    shape = SubElement(sp_tree, qn("p", "sp"))
    nv_sp_pr = SubElement(shape, qn("p", "nvSpPr"))
    SubElement(nv_sp_pr, qn("p", "cNvPr"), {"id": str(shape_id), "name": f"Rectangle {shape_id}"})
    SubElement(nv_sp_pr, qn("p", "cNvSpPr"))
    SubElement(nv_sp_pr, qn("p", "nvPr"))

    sp_pr = SubElement(shape, qn("p", "spPr"))
    xfrm = SubElement(sp_pr, qn("a", "xfrm"))
    SubElement(xfrm, qn("a", "off"), {"x": str(emu(rect.x)), "y": str(slide_top_from_bottom(rect.y, rect.h))})
    SubElement(xfrm, qn("a", "ext"), {"cx": str(emu(rect.w)), "cy": str(emu(rect.h))})
    prst = SubElement(sp_pr, qn("a", "prstGeom"), {"prst": "rect"})
    SubElement(prst, qn("a", "avLst"))
    add_color(sp_pr, rect.fill)
    add_line_style(sp_pr, rect.stroke, rect.lw)

    return shape_id + 1


def font_family(font_code: str) -> str:
    return "Courier New" if font_code in {"F3", "F4"} else "Arial"


def add_text_shape(sp_tree: Element, shape_id: int, text: object) -> int:
    font_size = max(9, int(round(text.size * 100)))
    approx_width = max(36.0, min(SLIDE_W - text.x - 4, len(text.text) * max(text.size * 0.68, 7.5)))
    approx_height = max(18.0, text.size * 1.45)

    shape = SubElement(sp_tree, qn("p", "sp"))
    nv_sp_pr = SubElement(shape, qn("p", "nvSpPr"))
    SubElement(nv_sp_pr, qn("p", "cNvPr"), {"id": str(shape_id), "name": f"TextBox {shape_id}"})
    SubElement(nv_sp_pr, qn("p", "cNvSpPr"), {"txBox": "1"})
    SubElement(nv_sp_pr, qn("p", "nvPr"))

    sp_pr = SubElement(shape, qn("p", "spPr"))
    xfrm = SubElement(sp_pr, qn("a", "xfrm"))
    SubElement(
        xfrm,
        qn("a", "off"),
        {"x": str(emu(text.x)), "y": str(slide_top_from_bottom(text.y, approx_height * 0.85))},
    )
    SubElement(xfrm, qn("a", "ext"), {"cx": str(emu(approx_width)), "cy": str(emu(approx_height))})
    prst = SubElement(sp_pr, qn("a", "prstGeom"), {"prst": "rect"})
    SubElement(prst, qn("a", "avLst"))
    SubElement(sp_pr, qn("a", "noFill"))
    add_line_style(sp_pr, None)

    tx_body = SubElement(shape, qn("p", "txBody"))
    body_pr = SubElement(
        tx_body,
        qn("a", "bodyPr"),
        {
            "wrap": "none",
            "lIns": "0",
            "tIns": "0",
            "rIns": "0",
            "bIns": "0",
            "anchor": "t",
        },
    )
    SubElement(body_pr, qn("a", "spAutoFit"))
    SubElement(tx_body, qn("a", "lstStyle"))
    paragraph = SubElement(tx_body, qn("a", "p"))
    SubElement(paragraph, qn("a", "pPr"), {"algn": "l"})
    run = SubElement(paragraph, qn("a", "r"))
    r_pr = SubElement(
        run,
        qn("a", "rPr"),
        {
            "lang": "en-US",
            "sz": str(font_size),
            "b": "1" if text.font in {"F2", "F4"} else "0",
            "dirty": "0",
        },
    )
    add_color(r_pr, text.color)
    family = font_family(text.font)
    SubElement(r_pr, qn("a", "latin"), {"typeface": family})
    SubElement(r_pr, qn("a", "cs"), {"typeface": family})
    SubElement(run, qn("a", "t")).text = text.text
    end_pr = SubElement(paragraph, qn("a", "endParaRPr"), {"lang": "en-US", "sz": str(font_size), "dirty": "0"})
    SubElement(end_pr, qn("a", "latin"), {"typeface": family})
    SubElement(end_pr, qn("a", "cs"), {"typeface": family})

    return shape_id + 1


def add_line_shape(sp_tree: Element, shape_id: int, line: object) -> int:
    left = min(line.x1, line.x2)
    width = max(abs(line.x2 - line.x1), 0.8)
    height = max(abs(line.y2 - line.y1), 0.8)
    top = slide_top_from_bottom(min(line.y1, line.y2), height)

    connector = SubElement(sp_tree, qn("p", "cxnSp"))
    nv_cxn = SubElement(connector, qn("p", "nvCxnSpPr"))
    SubElement(nv_cxn, qn("p", "cNvPr"), {"id": str(shape_id), "name": f"Connector {shape_id}"})
    SubElement(nv_cxn, qn("p", "cNvCxnSpPr"))
    SubElement(nv_cxn, qn("p", "nvPr"))

    sp_pr = SubElement(connector, qn("p", "spPr"))
    xfrm_attrib: dict[str, str] = {}
    if line.x2 < line.x1:
        xfrm_attrib["flipH"] = "1"
    if line.y2 > line.y1:
        xfrm_attrib["flipV"] = "1"
    xfrm = SubElement(sp_pr, qn("a", "xfrm"), xfrm_attrib)
    SubElement(xfrm, qn("a", "off"), {"x": str(emu(left)), "y": str(top)})
    SubElement(xfrm, qn("a", "ext"), {"cx": str(emu(width)), "cy": str(emu(height))})
    prst = SubElement(sp_pr, qn("a", "prstGeom"), {"prst": "straightConnector1"})
    SubElement(prst, qn("a", "avLst"))
    add_line_style(sp_pr, line.color, line.lw)

    return shape_id + 1


def build_slide_xml(slide_index: int, slide: object) -> bytes:
    sld = Element(qn("p", "sld"))
    c_sld = SubElement(sld, qn("p", "cSld"), {"name": f"Slide {slide_index}"})
    sp_tree = SubElement(c_sld, qn("p", "spTree"))
    add_group_root(sp_tree)

    shape_id = 2
    for rect in slide.rects:
        shape_id = add_rect_shape(sp_tree, shape_id, rect)
    for line in slide.lines:
        shape_id = add_line_shape(sp_tree, shape_id, line)
    for text in slide.texts:
        shape_id = add_text_shape(sp_tree, shape_id, text)

    clr_map = SubElement(sld, qn("p", "clrMapOvr"))
    SubElement(clr_map, qn("a", "masterClrMapping"))
    return xml_bytes(sld)


def build_slide_rels() -> bytes:
    relationships = Element(rel_qn("Relationships"))
    SubElement(
        relationships,
        rel_qn("Relationship"),
        {"Id": "rId1", "Type": REL_TYPES["layout"], "Target": "../slideLayouts/slideLayout1.xml"},
    )
    return xml_bytes(relationships)


def build_presentation_xml(slide_count: int) -> bytes:
    presentation = Element(qn("p", "presentation"))

    master_ids = SubElement(presentation, qn("p", "sldMasterIdLst"))
    SubElement(master_ids, qn("p", "sldMasterId"), {"id": "2147483648", qn("r", "id"): "rId1"})

    slide_ids = SubElement(presentation, qn("p", "sldIdLst"))
    for index in range(slide_count):
        SubElement(slide_ids, qn("p", "sldId"), {"id": str(256 + index), qn("r", "id"): f"rId{index + 2}"})

    SubElement(presentation, qn("p", "sldSz"), {"cx": str(SLIDE_CX), "cy": str(SLIDE_CY)})
    SubElement(presentation, qn("p", "notesSz"), {"cx": "6858000", "cy": "9144000"})
    SubElement(presentation, qn("p", "defaultTextStyle"))

    return xml_bytes(presentation)


def build_presentation_rels(slide_count: int) -> bytes:
    relationships = Element(rel_qn("Relationships"))
    SubElement(
        relationships,
        rel_qn("Relationship"),
        {"Id": "rId1", "Type": REL_TYPES["master"], "Target": "slideMasters/slideMaster1.xml"},
    )
    for index in range(slide_count):
        SubElement(
            relationships,
            rel_qn("Relationship"),
            {"Id": f"rId{index + 2}", "Type": REL_TYPES["slide"], "Target": f"slides/slide{index + 1}.xml"},
        )
    return xml_bytes(relationships)


def build_slide_master_xml() -> bytes:
    master = Element(qn("p", "sldMaster"))
    c_sld = SubElement(master, qn("p", "cSld"), {"name": "F1 Analytics Master"})
    sp_tree = SubElement(c_sld, qn("p", "spTree"))
    add_group_root(sp_tree)

    layout_ids = SubElement(master, qn("p", "sldLayoutIdLst"))
    SubElement(layout_ids, qn("p", "sldLayoutId"), {"id": "1", qn("r", "id"): "rId1"})
    SubElement(
        master,
        qn("p", "clrMap"),
        {
            "bg1": "lt1",
            "tx1": "dk1",
            "bg2": "lt2",
            "tx2": "dk2",
            "accent1": "accent1",
            "accent2": "accent2",
            "accent3": "accent3",
            "accent4": "accent4",
            "accent5": "accent5",
            "accent6": "accent6",
            "hlink": "hlink",
            "folHlink": "folHlink",
        },
    )
    tx_styles = SubElement(master, qn("p", "txStyles"))
    SubElement(tx_styles, qn("p", "titleStyle"))
    SubElement(tx_styles, qn("p", "bodyStyle"))
    SubElement(tx_styles, qn("p", "otherStyle"))
    return xml_bytes(master)


def build_slide_master_rels() -> bytes:
    relationships = Element(rel_qn("Relationships"))
    SubElement(
        relationships,
        rel_qn("Relationship"),
        {"Id": "rId1", "Type": REL_TYPES["layout"], "Target": "../slideLayouts/slideLayout1.xml"},
    )
    SubElement(
        relationships,
        rel_qn("Relationship"),
        {"Id": "rId2", "Type": REL_TYPES["theme"], "Target": "../theme/theme1.xml"},
    )
    return xml_bytes(relationships)


def build_slide_layout_xml() -> bytes:
    layout = Element(qn("p", "sldLayout"), {"type": "blank", "preserve": "1"})
    c_sld = SubElement(layout, qn("p", "cSld"), {"name": "Blank"})
    sp_tree = SubElement(c_sld, qn("p", "spTree"))
    add_group_root(sp_tree)
    clr_map = SubElement(layout, qn("p", "clrMapOvr"))
    SubElement(clr_map, qn("a", "masterClrMapping"))
    return xml_bytes(layout)


def build_slide_layout_rels() -> bytes:
    relationships = Element(rel_qn("Relationships"))
    SubElement(
        relationships,
        rel_qn("Relationship"),
        {"Id": "rId1", "Type": REL_TYPES["master"], "Target": "../slideMasters/slideMaster1.xml"},
    )
    return xml_bytes(relationships)


def build_theme_xml() -> bytes:
    theme = Element(qn("a", "theme"), {"name": "F1 Analytics Theme"})
    elements = SubElement(theme, qn("a", "themeElements"))

    clr_scheme = SubElement(elements, qn("a", "clrScheme"), {"name": "F1 Analytics"})
    for name, value in [
        ("dk1", "0B0F14"),
        ("lt1", "FFFFFF"),
        ("dk2", "111827"),
        ("lt2", "F3F4F6"),
        ("accent1", "E10600"),
        ("accent2", "0EA5E9"),
        ("accent3", "22C55E"),
        ("accent4", "F59E0B"),
        ("accent5", "6366F1"),
        ("accent6", "A855F7"),
        ("hlink", "2563EB"),
        ("folHlink", "9333EA"),
    ]:
        container = SubElement(clr_scheme, qn("a", name))
        SubElement(container, qn("a", "srgbClr"), {"val": value})

    font_scheme = SubElement(elements, qn("a", "fontScheme"), {"name": "F1 Analytics"})
    for block in ("majorFont", "minorFont"):
        fonts = SubElement(font_scheme, qn("a", block))
        SubElement(fonts, qn("a", "latin"), {"typeface": "Arial"})
        SubElement(fonts, qn("a", "ea"), {"typeface": "Arial"})
        SubElement(fonts, qn("a", "cs"), {"typeface": "Arial"})

    fmt_scheme = SubElement(elements, qn("a", "fmtScheme"), {"name": "F1 Analytics"})
    fill_styles = SubElement(fmt_scheme, qn("a", "fillStyleLst"))
    for color in ("FFFFFF", "111827", "E10600"):
        solid = SubElement(fill_styles, qn("a", "solidFill"))
        SubElement(solid, qn("a", "srgbClr"), {"val": color})

    line_styles = SubElement(fmt_scheme, qn("a", "lnStyleLst"))
    for width, color in [("9525", "0B0F14"), ("25400", "E10600"), ("38100", "0EA5E9")]:
        line = SubElement(line_styles, qn("a", "ln"), {"w": width, "cap": "flat", "cmpd": "sng", "algn": "ctr"})
        solid = SubElement(line, qn("a", "solidFill"))
        SubElement(solid, qn("a", "srgbClr"), {"val": color})
        SubElement(line, qn("a", "prstDash"), {"val": "solid"})

    effect_styles = SubElement(fmt_scheme, qn("a", "effectStyleLst"))
    for _ in range(3):
        effect = SubElement(effect_styles, qn("a", "effectStyle"))
        SubElement(effect, qn("a", "effectLst"))

    bg_fill_styles = SubElement(fmt_scheme, qn("a", "bgFillStyleLst"))
    for color in ("FFFFFF", "0B0F14", "1F2937"):
        solid = SubElement(bg_fill_styles, qn("a", "solidFill"))
        SubElement(solid, qn("a", "srgbClr"), {"val": color})

    return xml_bytes(theme)


def build_root_rels() -> bytes:
    relationships = Element(rel_qn("Relationships"))
    SubElement(
        relationships,
        rel_qn("Relationship"),
        {"Id": "rId1", "Type": REL_TYPES["office_document"], "Target": "ppt/presentation.xml"},
    )
    SubElement(
        relationships,
        rel_qn("Relationship"),
        {"Id": "rId2", "Type": REL_TYPES["core"], "Target": "docProps/core.xml"},
    )
    SubElement(
        relationships,
        rel_qn("Relationship"),
        {"Id": "rId3", "Type": REL_TYPES["app"], "Target": "docProps/app.xml"},
    )
    return xml_bytes(relationships)


def build_content_types(slide_count: int) -> bytes:
    types = Element(
        "Types",
        {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"},
    )
    SubElement(types, "Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    SubElement(types, "Default", {"Extension": "xml", "ContentType": "application/xml"})
    SubElement(
        types,
        "Override",
        {
            "PartName": "/ppt/presentation.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        },
    )
    SubElement(
        types,
        "Override",
        {
            "PartName": "/ppt/slideMasters/slideMaster1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml",
        },
    )
    SubElement(
        types,
        "Override",
        {
            "PartName": "/ppt/slideLayouts/slideLayout1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml",
        },
    )
    SubElement(
        types,
        "Override",
        {
            "PartName": "/ppt/theme/theme1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.theme+xml",
        },
    )
    for index in range(slide_count):
        SubElement(
            types,
            "Override",
            {
                "PartName": f"/ppt/slides/slide{index + 1}.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
            },
        )
    SubElement(
        types,
        "Override",
        {
            "PartName": "/docProps/core.xml",
            "ContentType": "application/vnd.openxmlformats-package.core-properties+xml",
        },
    )
    SubElement(
        types,
        "Override",
        {
            "PartName": "/docProps/app.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.extended-properties+xml",
        },
    )
    return xml_bytes(types)


def build_core_properties() -> bytes:
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    core = Element(qn("cp", "coreProperties"))
    SubElement(core, qn("dc", "title")).text = "F1 Analytics API Presentation Slides"
    SubElement(core, qn("dc", "subject")).text = "XJCO3011 Coursework 1 submission slides"
    SubElement(core, qn("dc", "creator")).text = "Bochun Yuan"
    SubElement(core, qn("cp", "keywords")).text = "F1 Analytics API, coursework, presentation"
    SubElement(core, qn("dc", "description")).text = "Submission-ready PowerPoint deck generated from the repository slide model."
    SubElement(core, qn("cp", "lastModifiedBy")).text = "Codex"
    created = SubElement(core, qn("dcterms", "created"), {qn("xsi", "type"): "dcterms:W3CDTF"})
    created.text = timestamp
    modified = SubElement(core, qn("dcterms", "modified"), {qn("xsi", "type"): "dcterms:W3CDTF"})
    modified.text = timestamp
    return xml_bytes(core)


def build_app_properties(slide_count: int) -> bytes:
    props = Element(qn("ep", "Properties"))
    SubElement(props, qn("ep", "Application")).text = "Microsoft PowerPoint"
    SubElement(props, qn("ep", "PresentationFormat")).text = "On-screen Show (16:9)"
    SubElement(props, qn("ep", "Slides")).text = str(slide_count)
    SubElement(props, qn("ep", "Notes")).text = "0"
    SubElement(props, qn("ep", "HiddenSlides")).text = "0"
    SubElement(props, qn("ep", "MMClips")).text = "0"
    SubElement(props, qn("ep", "ScaleCrop")).text = "false"

    heading_pairs = SubElement(props, qn("ep", "HeadingPairs"))
    heading_vector = SubElement(heading_pairs, qn("vt", "vector"), {"size": "2", "baseType": "variant"})
    variant_one = SubElement(heading_vector, qn("vt", "variant"))
    SubElement(variant_one, qn("vt", "lpstr")).text = "Slides"
    variant_two = SubElement(heading_vector, qn("vt", "variant"))
    SubElement(variant_two, qn("vt", "i4")).text = str(slide_count)

    titles = SubElement(props, qn("ep", "TitlesOfParts"))
    title_vector = SubElement(titles, qn("vt", "vector"), {"size": str(slide_count), "baseType": "lpstr"})
    for index in range(slide_count):
        SubElement(title_vector, qn("vt", "lpstr")).text = f"Slide {index + 1}"

    SubElement(props, qn("ep", "Company"))
    SubElement(props, qn("ep", "LinksUpToDate")).text = "false"
    SubElement(props, qn("ep", "SharedDoc")).text = "false"
    SubElement(props, qn("ep", "HyperlinksChanged")).text = "false"
    SubElement(props, qn("ep", "AppVersion")).text = "16.0000"
    return xml_bytes(props)


def build_package() -> None:
    deck = build_deck()
    slide_count = len(deck.slides)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT_PATH, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", build_content_types(slide_count))
        archive.writestr("_rels/.rels", build_root_rels())
        archive.writestr("docProps/core.xml", build_core_properties())
        archive.writestr("docProps/app.xml", build_app_properties(slide_count))
        archive.writestr("ppt/presentation.xml", build_presentation_xml(slide_count))
        archive.writestr("ppt/_rels/presentation.xml.rels", build_presentation_rels(slide_count))
        archive.writestr("ppt/slideMasters/slideMaster1.xml", build_slide_master_xml())
        archive.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", build_slide_master_rels())
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", build_slide_layout_xml())
        archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", build_slide_layout_rels())
        archive.writestr("ppt/theme/theme1.xml", build_theme_xml())

        for index, slide in enumerate(deck.slides, start=1):
            archive.writestr(f"ppt/slides/slide{index}.xml", build_slide_xml(index, slide))
            archive.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", build_slide_rels())


def main() -> None:
    build_package()
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
