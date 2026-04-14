# GitHub Actions 배포 가이드

## 전체 순서 요약
1. GitHub 계정 만들기
2. 슬랙 Incoming Webhook URL 발급
3. GitHub에 새 저장소(repository) 만들기
4. 코드 파일 올리기
5. Slack Webhook URL을 GitHub Secret에 등록
6. 테스트 실행
7. 완료 → 이후 2시간마다 자동 실행

---

## Step 1. GitHub 계정

https://github.com 에서 계정 생성 (이미 있으면 생략)

---

## Step 2. 슬랙 Incoming Webhook URL 발급

1. https://api.slack.com/apps 접속
2. **"Create New App"** → "From scratch"
3. 앱 이름: `알뜰폰 모니터` → 워크스페이스 선택 → Create
4. 좌측 메뉴 **"Incoming Webhooks"** 클릭
5. 오른쪽 토글 **"Activate Incoming Webhooks" → ON**
6. 하단 **"Add New Webhook to Workspace"** 클릭
7. 결과를 받을 슬랙 채널 선택 (예: #알뜰폰-모니터링)
8. 생성된 **Webhook URL 복사** (`https://hooks.slack.com/services/...`)

---

## Step 3. GitHub 저장소 만들기

1. https://github.com/new 접속
2. 아래 설정으로 생성:

| 항목 | 값 |
|------|----|
| Repository name | community-monitor |
| Visibility | **Private** (권장) |
| Initialize with README | 체크 |

3. **"Create repository"** 클릭

---

## Step 4. 코드 파일 올리기

### 방법: GitHub 웹에서 드래그앤드롭

1. 생성된 저장소 페이지에서 **"uploading an existing file"** 클릭
2. 아래 파일/폴더를 모두 선택해서 드래그앤드롭:

```
community-monitor/
├── .github/workflows/monitor.yml   ← 반드시 포함
├── config.py
├── main.py
├── requirements.txt
├── scrapers/
│   ├── __init__.py
│   ├── ppomppu_scraper.py
│   ├── fmkorea_scraper.py
│   └── dcinside_scraper.py
└── core/
    ├── __init__.py
    ├── db_handler.py
    ├── filter.py
    └── slack_notifier.py
```

> ⚠️ `.github/workflows/monitor.yml` 파일이 핵심입니다. 반드시 포함하세요.

3. 하단 **"Commit changes"** 클릭

---

## Step 5. Slack Webhook URL을 GitHub Secret에 등록

1. 저장소 페이지 상단 **"Settings"** 탭 클릭
2. 좌측 메뉴 **"Secrets and variables" → "Actions"**
3. **"New repository secret"** 클릭
4. 아래 내용 입력:

| 항목 | 값 |
|------|----|
| Name | `SLACK_WEBHOOK_URL` |
| Secret | `https://hooks.slack.com/services/...` (Step 2에서 복사한 URL) |

5. **"Add secret"** 클릭

---

## Step 6. 테스트 실행

1. 저장소 상단 **"Actions"** 탭 클릭
2. 좌측에서 **"알뜰폰 커뮤니티 모니터링"** 클릭
3. 우측 **"Run workflow"** → **"Run workflow"** 클릭
4. 잠시 후 실행 결과 확인 (초록 체크 = 성공)
5. 슬랙 채널에 메시지 확인

---

## 이후 운영

- 자동 실행: 매 2시간마다 GitHub이 알아서 실행
- 실행 내역: Actions 탭에서 로그 확인 가능
- 수동 실행: Actions 탭 → "Run workflow" 버튼

---

## 키워드 추가 방법

1. GitHub 저장소에서 `config.py` 파일 클릭
2. 우측 상단 연필(✏️) 아이콘 클릭
3. `KEYWORDS` 리스트에 키워드 추가
4. 하단 **"Commit changes"** 클릭
5. 다음 실행부터 자동 적용

---

## 비용

| 항목 | 비용 |
|------|------|
| GitHub Actions (private repo) | 월 2,000분 무료 |
| 1회 실행 예상 시간 | 약 3~5분 |
| 월 실행 횟수 | 약 360회 (2시간마다) |
| 월 사용 시간 | 약 1,080~1,800분 → **무료 한도 내** |
| 슬랙 Incoming Webhook | 무료 |
| **합계** | **0원** |
