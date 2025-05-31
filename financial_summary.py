# financial_summary.py
# -*- coding: UTF-8 -*-

import os
import sys
import pandas as pd
import requests
import re


def GetNvrEncparam(code: str) -> (str, str):
    """
    네이버금융 종목 페이지(c1010001.aspx)에서 encparam과 id를 추출하여 반환합니다.
    """
    url = f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=10)
    html = resp.text

    re_enc = re.compile(r"encparam: '(.+?)'", re.IGNORECASE)
    re_id  = re.compile(r"id: '([A-Za-z0-9]+)' ?", re.IGNORECASE)

    m_enc = re_enc.search(html)
    m_id  = re_id.search(html)

    if not m_enc or not m_id:
        raise ValueError(f"[GetNvrEncparam] encparam 또는 id를 찾을 수 없습니다. code={code}")

    return m_enc.group(1), m_id.group(1)


def GetNvrFin(code: str, freq_typ: str) -> pd.DataFrame:
    """
    code    : 종목코드 (예: '095660')
    freq_typ: 'A' (전체: 연간+분기), 'Q' (분기만), 'Y' (연간만)

    반환: '주요재무정보'를 인덱스로 갖는 DataFrame
    """
    encparam, encid = GetNvrEncparam(code)

    ajax_url = "https://navercomp.wisereport.co.kr/v2/company/ajax/cF1001.aspx"
    params = {
        "cmp_cd"   : code,
        "fin_typ"  : "0",
        "freq_typ" : freq_typ,
        "extY"     : "0",
        "extQ"     : "0",
        "encparam" : encparam,
        "id"       : encid
    }

    referer_url = f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        ),
        "Referer"   : referer_url,
        "Accept"    : "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    resp = requests.get(ajax_url, params=params, headers=headers, timeout=10)
    raw_html = resp.text

    if not raw_html or raw_html.strip() == "":
        raise ValueError(f"[GetNvrFin] AJAX 응답이 비어 있습니다. code={code}, freq_typ={freq_typ}")

    tables = pd.read_html(raw_html)
    if len(tables) < 2:
        raise ValueError(f"[GetNvrFin] 테이블을 파싱할 수 없습니다. (tables count={len(tables)})")

    fs = tables[1]
    if isinstance(fs.columns, pd.MultiIndex):
        fs.columns = fs.columns.droplevel(0)

    if "주요재무정보" not in fs.columns:
        raise ValueError("[GetNvrFin] '주요재무정보' 컬럼을 찾을 수 없습니다.")
    fs.set_index("주요재무정보", inplace=True)

    return fs.copy()


def main():
    # 1) 커맨드라인 인자로 종목코드를 받는다
    if len(sys.argv) != 2:
        print("사용법: python financial_summary.py <종목코드>")
        print("예시: python financial_summary.py 095660")
        sys.exit(1)

    code = sys.argv[1].strip()

    # 2) “전체” (A)와 “분기” (Q) 데이터를 각각 불러온다
    df_all = GetNvrFin(code, "Y")
    df_qtr = GetNvrFin(code, "Q")

    # 3) 필요한 지표(행)만 추출
    metrics = ["매출액", "영업이익", "당기순이익", "영업이익률", "PER(배)", "PBR(배)"]

    available_all = df_all.index.intersection(metrics)
    df_all_sel    = df_all.loc[available_all].reindex(metrics)

    available_qtr = df_qtr.index.intersection(metrics)
    df_qtr_sel    = df_qtr.loc[available_qtr].reindex(metrics)

    # 4) 컬럼명에 접두어 붙이기
    df_all_sel.columns = [f"Y_{col}" for col in df_all_sel.columns]
    df_qtr_sel.columns = [f"Q_{col}" for col in df_qtr_sel.columns]

    # 5) 수평 병합
    df_merged = pd.concat([df_all_sel, df_qtr_sel], axis=1)

    # 6) output 폴더가 없으면 생성
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # 7) CSV로 저장
    output_path = os.path.join(output_dir, f"{code}.csv")
    df_merged.to_csv(output_path, encoding="utf-8-sig")

    print(f"✓ 저장 완료: {output_path}")


if __name__ == "__main__":
    main()