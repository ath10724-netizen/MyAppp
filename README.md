# 🛒 쇼핑 리스트

장보기 목록을 추가·수정·삭제하고, 구매한 항목을 체크할 수 있는 가벼운 Streamlit 웹 앱입니다.
자세한 요구사항은 [PRD.md](PRD.md)를 참고하세요.

## 로컬 실행

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 패키지 설치 및 실행
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 http://localhost:8501 로 접속합니다. (Python 3.10 이상 필요)

## 파일 구성

| 파일 | 역할 |
|---|---|
| `app.py` | Streamlit 앱 진입점 (화면, 항목 조작) |
| `storage.py` | 데이터 저장/불러오기 (`data.json`) |
| `requirements.txt` | 의존성 목록 |
| `.streamlit/config.toml` | 테마 색상 등 Streamlit 설정 |
| `PRD.md` | 제품 요구사항 문서 |
| `PROMPTS.md` | 단계별 개발 프롬프트 |

## 배포

Streamlit Community Cloud에 배포합니다. 절차는 PRD 8장을 참고하세요.
