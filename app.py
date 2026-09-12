# -*- coding: utf-8 -*-
"""서·논술형 답안 연습 — 학생용"""

import io
import pandas as pd
import streamlit as st

from rules import SETS, SET_ORDER, ALL_METHODS
from grader import grade_q1, grade_q2, prefilter_q3, PASS, PARTIAL, FAIL, REVIEW
from review import BLANK_REVIEW, METHOD_REVIEW, METHOD_GENERAL, Q3_REVIEW

st.set_page_config(page_title="서·논술형 답안 연습", page_icon="✎", layout="centered")

TONE = {PASS: "#14655A", PARTIAL: "#96681A", FAIL: "#A6392E", REVIEW: "#4F4A7A"}

st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>
  html, body, [class*="css"], .stApp, button, input, textarea {
      font-family: 'Pretendard Variable', Pretendard, -apple-system, sans-serif;
  }
  .stApp { background:#E9EDEC; }
  .block-container { padding-top:2.2rem; max-width:56rem; }

  .head { font-size:1.55rem; font-weight:700; color:#16232A; letter-spacing:-0.02em; margin:0; }
  .sub  { font-size:0.9rem; color:#5E6E76; margin:2px 0 18px; }

  .track { display:flex; gap:6px; margin:0 0 22px; }
  .tick  { flex:1; height:3px; background:#D5DDDA; border-radius:2px; }
  .tick.on { background:#14655A; }

  .lead { background:#fff; border-left:3px solid #16232A; padding:11px 15px;
          font-size:0.92rem; color:#28353C; margin-bottom:14px; }

  .res { background:#fff; padding:13px 16px; margin:9px 0 4px; border-left:3px solid #D5DDDA; }
  .res .t { font-weight:650; color:#16232A; font-size:0.97rem; }
  .res .s { float:right; color:#5E6E76; font-size:0.88rem; font-variant-numeric:tabular-nums; }
  .tag { display:inline-block; margin-left:7px; padding:0 7px; border-radius:2px;
         color:#fff; font-size:0.72rem; font-weight:600; vertical-align:2px; }

  .ev  { font-size:0.85rem; color:#4A5A62; padding:2px 0 2px 15px; }
  .ev.x { color:#A6392E; }
  .ev::before { content:"·"; margin-right:7px; color:#9FB0AC; }

  .rv { background:#fff; padding:16px 18px; margin-bottom:14px; border-left:3px solid #A6392E; }
  .rv .c { font-size:1.02rem; font-weight:700; color:#16232A; margin-bottom:3px; }
  .rv .w { font-size:0.8rem; color:#8A979D; }
  .rv .mine { background:#F4F6F5; padding:9px 12px; margin:10px 0;
              font-size:0.88rem; color:#3C4A51; }
  .rv .gap { font-size:0.87rem; color:#A6392E; margin:3px 0; }
  .rv li { font-size:0.89rem; color:#33424A; margin-bottom:5px; line-height:1.55; }
  .rv ul { padding-left:19px; margin:9px 0 0; }

  .done { background:#fff; border-left:3px solid #14655A; padding:15px 18px;
          font-size:0.93rem; color:#28353C; }

  .foot { font-size:0.82rem; color:#6C7A80; line-height:1.6; margin-top:26px; }
  .st-key-resetrow button {
      background:#1A66D1 !important; color:#fff !important; border:none !important;
      font-size:0.76rem !important; padding:3px 12px !important; border-radius:3px !important;
      min-height:0 !important; height:auto !important; font-weight:500 !important;
  }
  .st-key-resetrow button:hover { background:#134FA3 !important; }
</style>
""", unsafe_allow_html=True)


def tag(v):
    return f'<span class="tag" style="background:{TONE[v]}">{v}</span>'


BAD = ("금칙", "미충족", "불일치", "오류", "유입", "누락", "의심", "미작성", "불가")


def evidence(lines):
    for e in lines:
        cls = "ev x" if any(k in e for k in BAD) else "ev"
        st.markdown(f'<div class="{cls}">{e}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- 상태

with st.sidebar:
    st.markdown("**서·논술형 답안 연습**")
    set_key = st.radio("지문 세트", SET_ORDER,
                       format_func=lambda k: SETS[k]["title"], label_visibility="collapsed")
    S = SETS[set_key]
    st.divider()
    with st.expander("교사용"):
        code = st.text_input("접근 코드", type="password", label_visibility="collapsed",
                             placeholder="접근 코드")
        try:
            secret = st.secrets.get("TEACHER_CODE", None)
        except Exception:
            secret = None
        teacher = bool(secret) and code == secret
        if not secret:
            st.caption("앱 설정 → Secrets에 `TEACHER_CODE`를 등록하면 교사용 화면이 열립니다.")
        elif code and not teacher:
            st.caption("코드가 맞지 않습니다.")

P = f"{set_key}_"
def slot(q): return f"{P}done_{q}"
def submitted(q): return slot(q) in st.session_state


def reset_set():
    for k in [k for k in st.session_state if k.startswith(P)]:
        del st.session_state[k]


# ---------------------------------------------------------------- 교사용

if teacher:
    st.markdown(f'<p class="head">{S["title"]} · 교사용</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub">일괄 채점과 채점 기준</p>', unsafe_allow_html=True)

    up = st.file_uploader("답안 CSV  (열: 이름, ㄱ, ㄴ, ㄷ, 문2_1, 문2_2)", type=["csv"])
    if up:
        df = pd.read_csv(up).fillna("")
        out = []
        for _, row in df.iterrows():
            rec = {"이름": row.get("이름", "")}
            r1 = grade_q1(S, {b["id"]: str(row.get(b["id"], "")) for b in S["q1"]})
            for it in r1["items"]:
                rec[f"{it['id']}_점수"], rec[f"{it['id']}_판정"] = it["score"], it["verdict"]
                rec[f"{it['id']}_근거"] = " / ".join(it["evidence"])
            rec["문항1"] = r1["score"]
            if "문2_1" in df.columns:
                r2 = grade_q2(S, str(row.get("문2_1", "")), str(row.get("문2_2", "")))
                for it in r2["items"]:
                    rec[f"문2_{it['idx']}_방법"] = it["method"] or ""
                    rec[f"문2_{it['idx']}_점수"], rec[f"문2_{it['idx']}_판정"] = it["score"], it["verdict"]
                    rec[f"문2_{it['idx']}_근거"] = " / ".join(it["evidence"])
                rec["문항2"] = r2["score"]
            out.append(rec)
        res = pd.DataFrame(out)
        st.dataframe(res, use_container_width=True, hide_index=True)
        buf = io.BytesIO(); res.to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button("채점 결과 내려받기", buf.getvalue(),
                           f"{set_key}_채점결과.csv", "text/csv", type="primary")

    st.divider()
    for b in S["q1"]:
        with st.expander(f"{b['label']}  ({b['max_score']}점)"):
            for g in b["groups"]:
                st.write(f"**{'핵심군' if g.get('core') else '필수군'} [{g['name']}]** {', '.join(g['any'])}")
            for p in b["partial"]:
                st.write(f"**부가 [{p['name']}]** {', '.join(p['any'])} · 누락 −{p['score']}")
            for pat, why in b["forbidden"] + b["crossover"]:
                st.write(f"**차단** `{pat}` — {why}")
            if b["direction"]:
                st.write(f"**결론 방향** {b['direction']['name']}")
            st.write("**모범 답안** " + " / ".join(b["model"]))
    with st.expander("문항 2 · 선택지별 모범 답안"):
        st.dataframe(pd.DataFrame(
            [{"방법": m, "사용": S["q2"]["models"][m][0], "모범 답안 / 사유": S["q2"]["models"][m][1]}
             for m in ALL_METHODS]), hide_index=True, use_container_width=True)
    st.stop()

# ---------------------------------------------------------------- 학생용

st.markdown(f'<p class="head">{S["title"]}</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub">{S["topic"]} · 답안을 쓰고 제출하면 결과를 볼 수 있어요</p>',
            unsafe_allow_html=True)
st.markdown('<div class="track">' + "".join(
    f'<div class="tick {"on" if submitted(q) else ""}"></div>' for q in ("q1", "q2", "q3")
) + "</div>", unsafe_allow_html=True)

t1, t2, t3, t4 = st.tabs(["문항 1", "문항 2", "문항 3", "복습할 내용"])

# ------------------------------------------------ 문항 1
with t1:
    st.markdown('<div class="lead">윗글을 요약한 표의 빈칸에 들어갈 내용을 찾아 쓰시오.</div>',
                unsafe_allow_html=True)
    for b in S["q1"]:
        st.text_area(b["label"], key=f"{P}q1_{b['id']}", height=78,
                     disabled=submitted("q1"))

    if not submitted("q1"):
        if st.button("문항 1 제출", type="primary", key=f"{P}sub1"):
            st.session_state[slot("q1")] = grade_q1(
                S, {b["id"]: st.session_state.get(f"{P}q1_{b['id']}", "") for b in S["q1"]})
            st.rerun()
    else:
        r = st.session_state[slot("q1")]
        st.markdown(f"**{r['score']} / {r['max']}점**")
        for it in r["items"]:
            st.markdown(f'<div class="res"><span class="t">{it["label"]}</span>{tag(it["verdict"])}'
                        f'<span class="s">{it["score"]} / {it["max"]}</span></div>',
                        unsafe_allow_html=True)
            evidence(it["evidence"])
            with st.expander("모범 답안"):
                for m in it["model"]:
                    st.write(f"· {m}")

# ------------------------------------------------ 문항 2
with t2:
    st.markdown(f'<div class="lead">{S["q2"]["lead"]}<br>'
                f'이어지는 두 문장을 서로 다른 설명 방법으로 쓰고, 문장 끝 괄호에 방법의 이름을 쓰시오.</div>',
                unsafe_allow_html=True)
    st.text_area("(1)", key=f"{P}q2_1", height=76, disabled=submitted("q2"))
    st.text_area("(2)", key=f"{P}q2_2", height=76, disabled=submitted("q2"))

    if not submitted("q2"):
        if st.button("문항 2 제출", type="primary", key=f"{P}sub2"):
            st.session_state[slot("q2")] = grade_q2(
                S, st.session_state.get(f"{P}q2_1", ""), st.session_state.get(f"{P}q2_2", ""))
            st.rerun()
    else:
        r = st.session_state[slot("q2")]
        st.markdown(f"**{r['score']} / {r['max']}점**")
        for it in r["items"]:
            head = it["method"] or it["raw_label"] or "방법 미확인"
            st.markdown(f'<div class="res"><span class="t">({it["idx"]}) {head}</span>{tag(it["verdict"])}'
                        f'<span class="s">{it["score"]} / {it["max"]}</span></div>',
                        unsafe_allow_html=True)
            evidence(it["evidence"])
        for n in r["notes"]:
            st.markdown(f'<div class="ev x">{n}</div>', unsafe_allow_html=True)
        with st.expander("설명 방법별 모범 답안"):
            st.dataframe(pd.DataFrame(
                [{"방법": m, "사용": S["q2"]["models"][m][0], "모범 답안 / 사유": S["q2"]["models"][m][1]}
                 for m in ALL_METHODS]), hide_index=True, use_container_width=True)

# ------------------------------------------------ 문항 3
with t3:
    st.markdown(f'<div class="lead">[장면 1] {S["q3"]["scene1"]}<br>'
                f'[장면 2]에 들어갈 시각·청각 요소와 그 효과를 쓰시오.</div>', unsafe_allow_html=True)
    for name, key in (("Ⓐ 시각 요소", "A"), ("Ⓑ 청각 요소", "B")):
        st.markdown(f"**{name}**")
        st.text_area("연출 계획", key=f"{P}q3_{key}_p", height=80, disabled=submitted("q3"))
        st.text_area("효과", key=f"{P}q3_{key}_e", height=80, disabled=submitted("q3"))

    if not submitted("q3"):
        if st.button("문항 3 제출", type="primary", key=f"{P}sub3"):
            st.session_state[slot("q3")] = {
                k: prefilter_q3(S["q3"][k],
                                st.session_state.get(f"{P}q3_{k}_p", ""),
                                st.session_state.get(f"{P}q3_{k}_e", ""))
                for k in ("A", "B")}
            st.rerun()
    else:
        r = st.session_state[slot("q3")]
        for name, key in (("Ⓐ 시각 요소", "A"), ("Ⓑ 청각 요소", "B")):
            p = r[key]
            st.markdown(f'<div class="res"><span class="t">{name}</span>'
                        f'<span class="s">{p["hint"]}</span></div>', unsafe_allow_html=True)
            for k, v in p["evidence"]:
                cls = "ev" if k == "충족" else "ev x"
                st.markdown(f'<div class="{cls}">{v}</div>', unsafe_allow_html=True)
            with st.expander("모범 답안"):
                st.write(f"**연출** {p['model_plan']}")
                st.write(f"**효과** {p['model_effect']}")

# ------------------------------------------------ 복습할 내용
with t4:
    if not all(submitted(q) for q in ("q1", "q2", "q3")):
        left = [n for n, q in (("1", "q1"), ("2", "q2"), ("3", "q3")) if not submitted(q)]
        st.markdown(f'<div class="lead">아직 제출하지 않은 문항이 있어요 — 문항 {", ".join(left)}<br>'
                    f'세 문항을 모두 제출하면 복습할 내용이 여기에 정리됩니다.</div>',
                    unsafe_allow_html=True)
    else:
        blocks = []

        r1 = st.session_state[slot("q1")]
        for it in r1["items"]:
            if it["verdict"] == PASS:
                continue
            rv = BLANK_REVIEW.get((set_key, it["id"]), {})
            blocks.append({
                "where": f"문항 1 · {it['label']}",
                "concept": rv.get("concept", "표 요약하기"),
                "mine": st.session_state.get(f"{P}q1_{it['id']}", "") or "(작성하지 않음)",
                "gaps": [e for e in it["evidence"] if any(k in e for k in BAD)],
                "points": rv.get("points", []),
            })

        r2 = st.session_state[slot("q2")]
        for it in r2["items"]:
            if it["verdict"] == PASS:
                continue
            m = it["method"]
            mr = METHOD_REVIEW.get(m)
            pts = ([f"**{m}** — {mr['when']}에 쓴다. {mr['form']} 형태로 쓰고, {mr['check']}"]
                   if mr else []) + METHOD_GENERAL
            blocks.append({
                "where": f"문항 2 · ({it['idx']})",
                "concept": f"설명 방법 — {m}" if m else "설명 방법 고르기",
                "mine": st.session_state.get(f"{P}q2_{it['idx']}", "") or "(작성하지 않음)",
                "gaps": [e for e in it["evidence"] if any(k in e for k in BAD)],
                "points": pts,
            })

        r3 = st.session_state[slot("q3")]
        for name, key in (("Ⓐ 시각 요소", "A"), ("Ⓑ 청각 요소", "B")):
            gaps = [v for k, v in r3[key]["evidence"] if k != "충족"]
            if not gaps:
                continue
            blocks.append({
                "where": f"문항 3 · {name}",
                "concept": Q3_REVIEW["concept"],
                "mine": (st.session_state.get(f"{P}q3_{key}_p", "") or "(작성하지 않음)"),
                "gaps": gaps,
                "points": Q3_REVIEW["points"],
            })

        if not blocks:
            st.markdown('<div class="done">모든 조건을 충족했어요. 복습할 내용이 없습니다.</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<p class="sub">조건을 충족하지 못한 {len(blocks)}개 항목이에요.</p>',
                        unsafe_allow_html=True)
            for b in blocks:
                st.markdown(
                    f'<div class="rv"><div class="w">{b["where"]}</div>'
                    f'<div class="c">{b["concept"]}</div>'
                    f'<div class="mine"><b>내 답안</b><br>{b["mine"]}</div>'
                    + "".join(f'<div class="gap">부족한 부분 — {g}</div>' for g in b["gaps"])
                    + "<ul>" + "".join(f"<li>{p}</li>" for p in b["points"]) + "</ul></div>",
                    unsafe_allow_html=True)

# ------------------------------------------------ 다시 풀기
st.markdown(
    '<p class="foot">모든 문제를 제출하면 복습할 내용 탭에서 틀린 개념을 확인할 수 있어요.<br>'
    '답안을 초기화하고 처음부터 다시 풀고 싶다면 다음의 버튼을 누르세요.</p>',
    unsafe_allow_html=True)
with st.container(key="resetrow"):
    _, right = st.columns([4, 1])
    with right:
        if st.button("처음부터 다시 풀기", key=f"{P}reset"):
            reset_set()
            st.rerun()
