#!/usr/bin/env python3
"""Serialize the current Codex LLM's complete review of the 862 keyword proposals."""
import json
from pathlib import Path
import re

from common import config, save_json

c = config()
out = Path(c["task_root"]) / "analysis/labels"
rows = json.loads((out / "keyword_proposals.json").read_text())
# These are the semantic decisions made after reading all four complete batches.
# Freezing them allows exact replays without an external LLM service.
add = {}
remove = {}
notes = {}


def edit(indices, plus="", minus="", note=""):
    for i in indices:
        add.setdefault(i, set()).update(plus)
        remove.setdefault(i, set()).update(minus)
        if note:
            notes.setdefault(i, []).append(note)


# Human category synonyms and accessory/attire predicates missed by the first pass.
for row in rows:
    text = row["sentence"]
    if re.search(r"\b(folks|humans?|human beings|individuals?|persons?|someone|females?|males?|feminine|gentlemen|guys|ladies|womenfolk|fairer sex|female gender|female|male|walkers?)\b", text):
        edit([row["index"]], "A", note="补齐人类类别同义词；不把普通复数自动归为 H。")
    if re.search(r"\b(shirts?|tees?|tops?|coats?|jacket|pants|trousers|jeans|denim|skirts?|bag|handbag|backpack|tote)\b", text):
        edit([row["index"]], "A", note="服装/随身配件属于外观；穿衣/持包措辞不单列为外部空间关系。")
    if "direction" in text or "opposite paths" in text or "opposite way" in text:
        # A direction-only descriptor of traffic is a motion-direction predicate,
        # whereas the explicitly described back-to-camera posture is appearance/orientation.
        if "camera" not in text:
            edit([row["index"]], "E", note="交通同向/逆向的省略表达仍含运动方向约束。")

edit([15,197,256,268,327,328,329,336,349,390,414,420,442,789], "E",
     note="补齐 abandoned/braking/rapid/relocating/slowing/upright/strolling 等动作或静止状态。")
edit([206,277], "C", note="self-centered car / the ones we have 指自车。")
edit([266,267,345,375,376,387,391], "D", note="exceed speed/outpace/speedier/quicker 是比较型同义表达。")
edit([206,228,266,267,274,275,276,277,278,279,345,372,375,376,379,386,387,389,391,397,404], "E",
     note="速度比较同时含运动属性；rapid/swift 只有绝对速度、不标 D。")
edit([160,189,194,421], "C", note="we/you 为自车视角指代；不是无参照物的绝对空间描述。")
edit([281,286,498,565,572,605,626], "C", note="与自行车伴随关系需要另一物体；不是服装属性。")
edit([353], "E", note="leading ours 表示领行的相对运动；不等价于更快，不标 D。")
edit([582], minus="C", note="own a t-shirt 中 own 是拥有服装，不是自车 own。")

# Absolute B is not a duplicate tag for an exclusively anchored relative position.
edit([46,140,142,210,211,354,355,358,363,365,367,368,393,395,408,421], minus="B",
     note="in front/ahead of 明示参照物，仅 C；该句没有独立绝对方位约束。")
edit([149,161], "C", note="before ours 是相对自车的前方。")
edit([278], minus="B", note="speed ahead 是速度动作，不是绝对前方位置。")
edit([153,217,293,489], minus="B", note="left behind 是遗留/停车语义，不当作 left-side。")
edit([533], "B", note="rightward 含绝对运动方向。")
edit([606], minus="B", note="walkers left behind 的空间意图不清，保留 A/E 并交给人工审计。")
edit([21], note="语法受损：opposite of black；保留明确 A/E，不凭空补出另一参照车。")
edit([17,27,68,78,81,145,165,183,212,216,270,338,377,378,399,431,534,535,536,537],
     note="were left 一类回译有歧义；结合显式 left 仍保留 B，人工审计可修正；不利用预测结果调标签。")

overrides = {}
for row in rows:
    i = row["index"]
    labels = sorted((set(row["keyword_labels"]) | add.get(i, set())) - remove.get(i, set()))
    if labels != row["keyword_labels"] or i in notes:
        overrides[row["name"]] = {"labels": labels, "note": " ".join(notes.get(i, []))}
    if "C" in labels:
        note = ("C_scene：自行车伴随。" if any(x in row["sentence"] for x in ("bicycle", "bike"))
                else "C_viewpoint：相对自车/相机；与可见场景物体关系分开解释。")
        overrides.setdefault(row["name"], {"labels": labels, "note": ""})["note"] += " " + note

save_json(out / "llm_review.json", {
    "seed": c["seed"], "reviewer": "current Codex LLM in this task",
    "method": "Read every expression in four complete ordered batches; semantic labels frozen before seeing category errors.",
    "reviewed_names": [r["name"] for r in rows], "overrides": overrides,
    "category_definitions": {
        "A": "Appearance/class including vehicle or human class, gender, attire and accessories; base category nouns count.",
        "B": "Absolute image/road position or direction, without requiring a named reference object.",
        "C": "Explicit reference to ego/camera or another object; accompanying bicycle counts; attire/handbags treated as accessories.",
        "D": "Comparison/ranking including speed synonyms; absolute rapid/swift alone is E, not D.",
        "E": "Motion, direction of traffic, standing, parking and braking; wearing/holding accessories alone is A.",
        "F": "Annotation only: positive membership changes between consecutive visible observations of the same GT ID; record gaps.",
        "G": "Annotation only: the expression has zero positive GT object-frames over the whole video.",
        "H": "Explicit count or group; ordinary plural class nouns alone do not count."},
    "limitations": "No human accuracy claim until label_audit.csv is reviewed; ambiguous machine paraphrases retained with notes."})
print(json.dumps({"reviewed": len(rows), "overrides": len(overrides)}, indent=2))
