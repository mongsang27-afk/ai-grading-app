# -*- coding: utf-8 -*-
"""
채점 엔진.

판정은 항상 아래 순서로 진행한다. 순서를 바꾸면 오검출이 생긴다.
  0) 안전 표현 마스킹  ('집중'을 '집'으로 잡는 일 방지)
  1) 금칙어            (지문에서 부정된 선택지 등)
  2) 교차 오염          (다른 개념의 특성을 끌어다 씀)
  3) 결론 방향          (조건이 요구한 결론과 반대인가)
  4) 필수군 충족
  5) 부분 인정
"""

import re
from rules import METHOD_ALIASES, METHOD_MARKERS, ALL_METHODS

PASS, PARTIAL, FAIL, REVIEW = "통과", "부분", "오답", "검토"


# ---------------------------------------------------------------- 전처리

def nospace(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"[\s·ㆍ]+", "", t)
    t = t.replace("（", "(").replace("）", ")")
    return t


def apply_mask(text: str, safe_list) -> str:
    out = text
    for i, s in enumerate(safe_list):
        s = nospace(s)
        if s:
            out = out.replace(s, f"§{i}§")
    return out


def hit_any(text: str, patterns):
    return [p for p in patterns if nospace(p) in text]


# ---------------------------------------------------------------- 문항 1

def grade_blank(rule: dict, answer: str) -> dict:
    raw = (answer or "").strip()
    t = nospace(raw)
    ev = []          # 판정 근거
    if not t:
        return {"score": 0.0, "max": rule["max_score"], "verdict": FAIL,
                "evidence": ["미작성"], "model": rule["model"], "note": rule["note"]}

    masked = apply_mask(t, rule["safe"])

    # 1) 금칙어
    for pat, reason in rule["forbidden"]:
        if nospace(pat) in masked:
            return {"score": 0.0, "max": rule["max_score"], "verdict": FAIL,
                    "evidence": [f"금칙 표현 ‘{pat}’ → {reason}"],
                    "model": rule["model"], "note": rule["note"]}

    # 2) 교차 오염 (오개념 방지)
    for pat, reason in rule["crossover"]:
        if nospace(pat) in masked:
            return {"score": 0.0, "max": rule["max_score"], "verdict": FAIL,
                    "evidence": [f"다른 개념의 특성 ‘{pat}’ 유입 → {reason}"],
                    "model": rule["model"], "note": rule["note"]}

    # 3) 결론 방향
    d = rule.get("direction")
    if d:
        for pat, reason in d.get("wrong", []):
            if nospace(pat) in masked:
                return {"score": 0.0, "max": rule["max_score"], "verdict": FAIL,
                        "evidence": [f"결론 방향 오류: ‘{pat}’ → {reason}",
                                     f"요구되는 결론: {d['name']}"],
                        "model": rule["model"], "note": rule["note"]}
        ev.append(f"결론 방향 확인: {d['name']} — 반대 표현 없음")

    # 4) 필수군
    missing, core_missing = [], False
    for g in rule["groups"]:
        hits = hit_any(masked, g["any"])
        tag = "핵심" if g.get("core") else "필수"
        if hits:
            ev.append(f"{tag} [{g['name']}] 충족 — {', '.join(hits[:3])}")
        else:
            missing.append(g["name"])
            if g.get("core"):
                core_missing = True
            ev.append(f"{tag} [{g['name']}] 미충족")

    if core_missing:
        return {"score": 0.0, "max": rule["max_score"], "verdict": FAIL, "evidence": ev,
                "model": rule["model"], "note": rule["note"]}

    # 5) 부분 인정
    bonus = 0.0
    for p in rule["partial"]:
        hits = hit_any(masked, p["any"])
        if hits:
            ev.append(f"부가 [{p['name']}] 포함 — {', '.join(hits[:2])}")
        else:
            bonus -= p["score"]
            ev.append(f"부가 [{p['name']}] 누락 → −{p['score']}점")

    mx = rule["max_score"]
    if missing:
        # 필수군 일부만 충족되면 부분 인정, 전부 미충족이면 오답
        filled = len(rule["groups"]) - len(missing)
        if filled == 0:
            return {"score": 0.0, "max": mx, "verdict": FAIL, "evidence": ev,
                    "model": rule["model"], "note": rule["note"]}
        score = round(mx * filled / len(rule["groups"]) / 2, 2)
        return {"score": score, "max": mx, "verdict": PARTIAL, "evidence": ev,
                "model": rule["model"], "note": rule["note"]}

    score = max(0.0, round(mx + bonus, 2))
    verdict = PASS if abs(score - mx) < 1e-9 else PARTIAL
    return {"score": score, "max": mx, "verdict": verdict, "evidence": ev,
            "model": rule["model"], "note": rule["note"]}


def grade_q1(setdef: dict, answers: dict) -> dict:
    results = [grade_blank(r, answers.get(r["id"], "")) for r in setdef["q1"]]
    return {
        "items": [dict(r, id=b["id"], label=b["label"])
                  for b, r in zip(setdef["q1"], results)],
        "score": round(sum(r["score"] for r in results), 2),
        "max": round(sum(r["max"] for r in results), 2),
    }


# ---------------------------------------------------------------- 문항 2

LABEL_RE = re.compile(r"[(\[]([^)\]]{1,12})[)\]]")


def extract_label(raw: str):
    """문장에서 괄호 안 설명 방법 명칭을 뽑는다. 위치는 문말이 아니어도 인정."""
    for cand in LABEL_RE.findall(raw or ""):
        key = nospace(cand)
        if key in METHOD_ALIASES:
            return METHOD_ALIASES[key], cand.strip()
        # '비유' 등 목록 밖 명칭도 잡아 둔다
        if key and re.fullmatch(r"[가-힣]{2,6}", cand.strip()):
            return None, cand.strip()
    return None, None


def detect_methods(raw: str, setdef: dict):
    """문장 구조에서 설명 방법의 특성을 읽어 낸다."""
    t = nospace(raw)
    found = {}
    for m, marks in METHOD_MARKERS.items():
        hits = hit_any(t, marks)
        if hits:
            found[m] = hits

    # 구조 조건으로 걸러 내기
    ents = setdef["entities"]
    a = bool(hit_any(t, ents["A"]["any"]))
    b = bool(hit_any(t, ents["B"]["any"]))

    if "비교와 대조" in found and not (a and b):
        found.pop("비교와 대조")
    if "분류와 구분" in found and not (a and b):
        # 하위 항목 둘이 드러나지 않으면 분류로 보지 않음
        if not hit_any(t, ["두가지", "둘로", "종류로"]):
            found.pop("분류와 구분")
    if "정의" in found and not hit_any(t, ["란", "이란", "라고"]):
        found.pop("정의")
    return found


def grade_sentence(setdef: dict, raw: str, idx: int, allow_unlabeled=True) -> dict:
    q2 = setdef["q2"]
    t = nospace(raw)
    ev, flags = [], []
    content, label_pt = 1.0, 1.0

    if not t:
        return {"idx": idx, "method": None, "raw_label": None, "score": 0.0, "max": 2.0,
                "verdict": FAIL, "evidence": ["미작성"], "flags": []}

    label, raw_label = extract_label(raw)
    structural = detect_methods(raw, setdef)

    # (1) 명칭 판정
    if label:
        ev.append(f"명칭 표기: {label}")
        if label in q2["blocked"]:
            content = 0.0
            label_pt = 0.0
            ev.append(f"이 지문에서 사용 불가한 방법 — {q2['blocked'][label]}")
        elif label not in structural:
            label_pt = 0.0
            ev.append(f"명칭과 문장 구조 불일치 — ‘{label}’의 특성이 문장에 드러나지 않음"
                      f"{' (검출된 특성: ' + ', '.join(structural) + ')' if structural else ''}")
        else:
            ev.append(f"‘{label}’의 특성 확인 — {', '.join(structural[label][:3])}")
    elif raw_label:
        label_pt = 0.0
        ev.append(f"목록 밖 명칭 ‘{raw_label}’ → 명칭 점수 0")
        if structural:
            inferred = sorted(structural, key=lambda m: -len(structural[m]))[0]
            label = inferred
            ev.append(f"문장 구조상 ‘{inferred}’에 해당 → 내용 점수는 유지")
    else:
        # 명칭 미표기: 의미가 담기면 인정
        if structural and allow_unlabeled:
            inferred = sorted(structural, key=lambda m: -len(structural[m]))[0]
            label = inferred
            if len(structural) > 1:
                flags.append(f"방법 후보가 여럿({', '.join(structural)}) — 교사 확인 필요")
            ev.append(f"명칭 미표기이나 ‘{inferred}’의 의미가 문장에 담김 → 인정")
            label_pt = 0.5
            ev.append("괄호 표기 조건 미이행 → 명칭 점수 절반")
        else:
            label_pt = 0.0
            ev.append("명칭 미표기 + 방법의 특성도 드러나지 않음")

    # (2) 내용 판정 — 지문 어휘 사용 여부
    vocab_hits = hit_any(t, setdef["vocab"])
    if vocab_hits:
        ev.append(f"지문 어휘 사용 — {', '.join(vocab_hits[:4])}")
    else:
        content = 0.0
        ev.append("지문 어휘가 확인되지 않음 → 지문 외 지식 사용 의심")
        flags.append("지문 외 지식 여부 육안 확인 필요")

    # (3) 결론 방향
    conc = q2.get("conclusion")
    if conc:
        masked = apply_mask(t, conc.get("safe", []))
        for pat, reason in conc["wrong"]:
            if nospace(pat) in masked:
                content = 0.0
                ev.append(f"결론 방향 오류: ‘{pat}’ → {reason}")
                break
        else:
            ev.append(f"결론 방향 확인: {conc['name']}")

    score = round(content + label_pt, 2)
    verdict = PASS if score >= 2.0 else (FAIL if score == 0 else PARTIAL)
    if flags:
        verdict = REVIEW if verdict != FAIL else FAIL
    return {"idx": idx, "method": label, "raw_label": raw_label,
            "score": score, "max": 2.0, "verdict": verdict,
            "evidence": ev, "flags": flags}


def grade_q2(setdef: dict, s1: str, s2: str, allow_unlabeled=True) -> dict:
    r1 = grade_sentence(setdef, s1, 1, allow_unlabeled)
    r2 = grade_sentence(setdef, s2, 2, allow_unlabeled)
    penalty, notes = 0.0, []
    if r1["method"] and r1["method"] == r2["method"]:
        penalty = 1.0
        notes.append(f"두 문장이 같은 방법(‘{r1['method']}’) → 뒤 문장 명칭 점수 1점 감점")
    total = max(0.0, round(r1["score"] + r2["score"] - penalty, 2))
    return {"items": [r1, r2], "penalty": penalty, "notes": notes,
            "score": total, "max": 4.0}


# ---------------------------------------------------------------- 문항 3

def prefilter_q3(spec: dict, plan: str, effect: str) -> dict:
    """자동 채점이 아니라 1차 필터. 필수 요소 누락분만 표시한다."""
    pt, et = nospace(plan), nospace(effect)
    ev = []

    for pat, reason in spec["reject"]:
        if nospace(pat) in pt:
            ev.append(("오답 후보", f"연출에 ‘{pat}’ → {reason}"))

    for g in spec["plan"]:
        hits = hit_any(pt, g["any"])
        ev.append(("충족" if hits else "누락", f"연출 [{g['name']}]"
                   + (f" — {', '.join(hits[:2])}" if hits else "")))

    for g in spec["link"]:
        hits = hit_any(et, g["any"])
        ev.append(("충족" if hits else "누락", f"효과 [{g['name']}]"
                   + (f" — {', '.join(hits[:2])}" if hits else "")))

    if pt and et and pt == et:
        ev.append(("오답 후보", "연출과 효과 서술이 동일함"))

    missing = sum(1 for k, _ in ev if k == "누락")
    reject = sum(1 for k, _ in ev if k == "오답 후보")
    if reject:
        hint = "재검토 필요"
    elif missing == 0:
        hint = "요건 충족"
    else:
        hint = f"{missing}개 항목 누락"
    return {"evidence": ev, "hint": hint,
            "model_plan": spec["model_plan"], "model_effect": spec["model_effect"]}
