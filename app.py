# -*- coding: utf-8 -*-
"""서·논술형 채점 도구 — 2회고사 대비"""

import io
import pandas as pd
import streamlit as st

from rules import SETS, SET_ORDER, ALL_METHODS
from grader import grade_q1, grade_q2, prefilter_q3, PASS, PARTIAL, FAIL, REVIEW

st.set_page_config(page_title="서·논술형 채점", page_icon="✎", layout="wide")

COLOR = {PASS: "#0F6E5C", PARTIAL: "#A9762A", FAIL: "#9C3B32", REVIEW: "#5B4B8A"}

st.markdown("""
<style>
  .stApp { background: #F6F6F3; }
  h1, h2, h3 { letter-spacing: -0.01em; color: #1F2933; }
  .verdict { display:inline-block; padding:1px 9px; border-radius:3px;
             color:#fff; font-size:0.78rem; font-weight:600; }
  .evline { font-size:0.86rem; color:#3E4C59; padding:1px 0 1px 12px;
            border-left:2px solid #DCDCD6; margin-left:2px; }
  .evbad  { border-left-color:#9C3B32; }
  .card { background:#fff; border:1px solid #E3E3DD; border-radius:5px;
          padding:14px 16px; margin-bottom:10px; }
  .qlabel { font-weight:600; color:#1F2933; }
  .score { float:right; font-variant-numeric:tabular-nums; color:#52606D; }
</style>
""", unsafe_allow_html=True)


def badge(v):
    return f'<span class="verdict" style="background:{COLOR[v]}">{v}</span>'


def render_evidence(lines, bad_keys=("오답", "금칙", "미충족", "불일치", "오류", "유입", "누락", "의심")):
    for e in lines:
        cls = "evline evbad" if any(k in e for k in bad_keys) else "evline"
        st.markdown(f'<div class="{cls}">{e}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- 사이드바

with st.sidebar:
    st.markdown("### 서·논술형 채점")
    set_key = st.radio("지문 세트", SET_ORDER,
                       format_func=lambda k: SETS[k]["title"], label_visibility="collapsed")
    S = SETS[set_key]
    st.divider()
    mode = st.radio("모드", ["개별 채점", "일괄 채점", "채점 기준"])
    st.divider()
    allow_unlabeled = st.checkbox("명칭 미표기도 의미로 인정", value=True,
                                  help="문장에 방법의 특성이 드러나면 괄호 표기가 없어도 내용 점수를 인정합니다. "
                                       "괄호 표기 조건 미이행분은 명칭 점수 절반만 감점합니다.")
    st.caption("문항 3은 자동 채점 대상이 아닙니다. 필수 요소 누락만 1차로 걸러 냅니다.")

st.title(S["title"])
st.caption(S["topic"])

# ================================================================ 개별 채점

if mode == "개별 채점":
    name = st.text_input("학생 이름 또는 번호", "")
    t1, t2, t3 = st.tabs(["문항 1 · 표 빈칸", "문항 2 · 설명 방법", "문항 3 · 영상 연출"])

    # -------------------------------------------------- 문항 1
    with t1:
        cols = st.columns(len(S["q1"]))
        ans = {}
        for c, b in zip(cols, S["q1"]):
            with c:
                ans[b["id"]] = st.text_area(b["label"], key=f"q1{b['id']}", height=90)

        if st.button("문항 1 채점", type="primary"):
            r = grade_q1(S, ans)
            st.markdown(f"#### 합계 {r['score']} / {r['max']}점")
            for it in r["items"]:
                st.markdown(
                    f'<div class="card"><span class="qlabel">{it["label"]}</span> '
                    f'{badge(it["verdict"])}<span class="score">{it["score"]} / {it["max"]}</span></div>',
                    unsafe_allow_html=True)
                render_evidence(it["evidence"])
                with st.expander("모범 답안 · 적용 기준"):
                    for m in it["model"]:
                        st.write(f"· {m}")
                    if it["note"]:
                        st.caption(it["note"])

    # -------------------------------------------------- 문항 2
    with t2:
        st.caption(f"첫 문장: {S['q2']['lead']}")
        s1 = st.text_area("(1)", key="q2s1", height=80)
        s2 = st.text_area("(2)", key="q2s2", height=80)

        if st.button("문항 2 채점", type="primary"):
            r = grade_q2(S, s1, s2, allow_unlabeled)
            st.markdown(f"#### 합계 {r['score']} / {r['max']}점")
            for it in r["items"]:
                head = it["method"] or it["raw_label"] or "방법 미확인"
                st.markdown(
                    f'<div class="card"><span class="qlabel">({it["idx"]}) {head}</span> '
                    f'{badge(it["verdict"])}<span class="score">{it["score"]} / {it["max"]}</span></div>',
                    unsafe_allow_html=True)
                render_evidence(it["evidence"])
                for f in it["flags"]:
                    st.warning(f, icon="⚠")
            for n in r["notes"]:
                st.error(n, icon="✕")

        st.divider()
        st.markdown("##### 선택지별 모범 답안")
        rows = []
        for m in ALL_METHODS:
            status, text = S["q2"]["models"][m]
            rows.append({"설명 방법": m, "사용": status, "모범 답안 / 사유": text})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        if S["q2"].get("extra_note"):
            st.info(S["q2"]["extra_note"], icon="ℹ")

    # -------------------------------------------------- 문항 3
    with t3:
        st.caption(f"장면 1: {S['q3']['scene1']}")
        for tag, key in (("Ⓐ 시각 요소", "A"), ("Ⓑ 청각 요소", "B")):
            st.markdown(f"##### {tag}")
            c1, c2 = st.columns(2)
            plan = c1.text_area("연출 계획", key=f"q3{key}p", height=100)
            eff = c2.text_area("효과", key=f"q3{key}e", height=100)
            if plan or eff:
                p = prefilter_q3(S["q3"][key], plan, eff)
                st.markdown(f"**1차 확인: {p['hint']}**")
                for k, v in p["evidence"]:
                    cls = "evline evbad" if k != "충족" else "evline"
                    st.markdown(f'<div class="{cls}">[{k}] {v}</div>', unsafe_allow_html=True)
                st.radio("최종 판정", ["연출 1점", "연결 1점", "효과 1점"],
                         key=f"q3{key}m", horizontal=True, index=None,
                         label_visibility="collapsed")
                with st.expander("모범 답안"):
                    st.write(f"**연출** {p['model_plan']}")
                    st.write(f"**효과** {p['model_effect']}")
            st.divider()

# ================================================================ 일괄 채점

elif mode == "일괄 채점":
    st.markdown("CSV 열 이름: `이름, ㄱ, ㄴ, ㄷ, 문2_1, 문2_2`  (문항 2 열은 없어도 됩니다)")
    up = st.file_uploader("답안 CSV", type=["csv"])

    tmpl = pd.DataFrame([{"이름": "1번", "ㄱ": "", "ㄴ": "", "ㄷ": "", "문2_1": "", "문2_2": ""}])
    st.download_button("빈 서식 내려받기", tmpl.to_csv(index=False).encode("utf-8-sig"),
                       "답안_서식.csv", "text/csv")

    if up:
        df = pd.read_csv(up).fillna("")
        out = []
        for _, row in df.iterrows():
            rec = {"이름": row.get("이름", "")}
            r1 = grade_q1(S, {b["id"]: str(row.get(b["id"], "")) for b in S["q1"]})
            for it in r1["items"]:
                rec[f"{it['id']}_점수"] = it["score"]
                rec[f"{it['id']}_판정"] = it["verdict"]
                rec[f"{it['id']}_근거"] = " / ".join(it["evidence"])
            rec["문항1_합계"] = r1["score"]

            if "문2_1" in df.columns:
                r2 = grade_q2(S, str(row.get("문2_1", "")), str(row.get("문2_2", "")), allow_unlabeled)
                for it in r2["items"]:
                    rec[f"문2_{it['idx']}_방법"] = it["method"] or ""
                    rec[f"문2_{it['idx']}_점수"] = it["score"]
                    rec[f"문2_{it['idx']}_판정"] = it["verdict"]
                    rec[f"문2_{it['idx']}_근거"] = " / ".join(it["evidence"])
                rec["문항2_합계"] = r2["score"]
                rec["중복방법감점"] = r2["penalty"]
            out.append(rec)

        res = pd.DataFrame(out)
        st.dataframe(res, use_container_width=True, hide_index=True)

        flag = res[res.filter(like="_판정").isin([FAIL, REVIEW]).any(axis=1)]
        if len(flag):
            st.warning(f"오답·검토 표시가 있는 답안 {len(flag)}건은 육안 확인을 권합니다.", icon="⚠")

        buf = io.BytesIO()
        res.to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button("채점 결과 내려받기", buf.getvalue(),
                           f"{set_key}_채점결과.csv", "text/csv", type="primary")

# ================================================================ 채점 기준

else:
    st.markdown("### 문항 1 · 빈칸별 기준")
    for b in S["q1"]:
        with st.expander(f"{b['label']}  ({b['max_score']}점)", expanded=True):
            for g in b["groups"]:
                tag = "핵심군" if g.get("core") else "필수군"
                st.write(f"**{tag} [{g['name']}]** {', '.join(g['any'])}")
            for p in b["partial"]:
                st.write(f"**부가 [{p['name']}]** {', '.join(p['any'])}  · 누락 시 −{p['score']}점")
            for pat, why in b["forbidden"]:
                st.write(f"**금칙** `{pat}` — {why}")
            for pat, why in b["crossover"]:
                st.write(f"**교차 오염** `{pat}` — {why}")
            if b["direction"]:
                st.write(f"**결론 방향** {b['direction']['name']}")
                for pat, why in b["direction"]["wrong"]:
                    st.write(f"　· 반대 표현 `{pat}` — {why}")
            st.write("**모범 답안** " + " / ".join(b["model"]))
            if b["note"]:
                st.caption(b["note"])

    st.markdown("### 문항 2 · 선택지별 모범 답안")
    st.dataframe(pd.DataFrame(
        [{"설명 방법": m, "사용": S["q2"]["models"][m][0],
          "모범 답안 / 사유": S["q2"]["models"][m][1]} for m in ALL_METHODS]),
        hide_index=True, use_container_width=True)
    if S["q2"].get("conclusion"):
        st.write(f"**결론 방향** {S['q2']['conclusion']['name']}")

    st.markdown("### 문항 3 · 체크리스트")
    for tag, key in (("Ⓐ 시각", "A"), ("Ⓑ 청각", "B")):
        with st.expander(f"{tag} 요소", expanded=True):
            sp = S["q3"][key]
            st.write("**연출 필수** " + " / ".join(f"[{g['name']}] {', '.join(g['any'])}" for g in sp["plan"]))
            st.write("**효과 필수** " + " / ".join(f"[{g['name']}] {', '.join(g['any'])}" for g in sp["link"]))
            for pat, why in sp["reject"]:
                st.write(f"**오답 후보** `{pat}` — {why}")
            st.write(f"**모범 연출** {sp['model_plan']}")
            st.write(f"**모범 효과** {sp['model_effect']}")
