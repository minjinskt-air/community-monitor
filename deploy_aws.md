# AWS EC2 배포 가이드

## 전체 순서 요약
1. AWS EC2 인스턴스 생성
2. 슬랙 Incoming Webhook URL 발급
3. EC2에 접속 → 코드 업로드
4. 패키지 설치 → 테스트 실행
5. 백그라운드 자동 실행 등록

---

## Step 1. AWS EC2 인스턴스 생성

### 1-1. AWS 계정 로그인 후 EC2 콘솔 접속
- https://console.aws.amazon.com/ec2

### 1-2. "인스턴스 시작" 클릭 후 아래 옵션 선택

| 항목 | 선택값 |
|------|--------|
| Name | community-monitor |
| OS | Ubuntu 22.04 LTS |
| 인스턴스 유형 | t2.micro (프리티어 무료 12개월) |
| 키 페어 | 새 키 페어 생성 → monitor-key.pem 다운로드 |
| 보안 그룹 | SSH(22번 포트) 허용 |
| 스토리지 | 8GB (기본값) |

### 1-3. "인스턴스 시작" 완료 후 퍼블릭 IP 확인
- 예: `13.124.xxx.xxx`

---

## Step 2. 슬랙 Incoming Webhook URL 발급

1. https://api.slack.com/apps 접속
2. "Create New App" → "From scratch"
3. 앱 이름: `알뜰폰 모니터` → 워크스페이스 선택
4. 좌측 메뉴 "Incoming Webhooks" → 활성화 ON
5. "Add New Webhook to Workspace" → 채널 선택
6. 생성된 Webhook URL 복사 (`https://hooks.slack.com/services/...`)

---

## Step 3. EC2 접속 (Windows → SSH)

### 방법 A: Windows 터미널 (PowerShell / CMD)
```bash
# 키 파일 권한 설정 (Windows는 생략 가능)
ssh -i "C:\Users\SKTelecom\Downloads\monitor-key.pem" ubuntu@13.124.xxx.xxx
```

### 방법 B: MobaXterm 또는 PuTTY (GUI 도구)
- MobaXterm 무료 다운로드: https://mobaxterm.mobatek.net
- Host: EC2 퍼블릭 IP, User: ubuntu, Key: monitor-key.pem

---

## Step 4. EC2 환경 세팅 (EC2 접속 후 실행)

```bash
# 패키지 업데이트
sudo apt update && sudo apt upgrade -y

# Python 3 및 pip 설치
sudo apt install python3 python3-pip -y

# 프로젝트 디렉토리 생성
mkdir ~/community-monitor && cd ~/community-monitor
```

---

## Step 5. 코드 업로드

### 방법 A: SCP (터미널)
```bash
# 로컬 PC에서 실행 (PowerShell)
scp -i "C:\Users\SKTelecom\Downloads\monitor-key.pem" -r "C:\Users\SKTelecom\Desktop\antigravity\community-monitor\*" ubuntu@13.124.xxx.xxx:~/community-monitor/
```

### 방법 B: MobaXterm SFTP 탭으로 드래그앤드롭
- 왼쪽 SFTP 창에서 `~/community-monitor/` 폴더로 파일 드래그

---

## Step 6. Python 패키지 설치 및 설정

```bash
cd ~/community-monitor

# 패키지 설치
pip3 install -r requirements.txt

# config.py에 슬랙 Webhook URL 입력
nano config.py
# → SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/여기에_입력"
# Ctrl+X → Y → Enter 로 저장
```

---

## Step 7. 테스트 실행

```bash
# 1회 즉시 실행 (정상 동작 확인)
python3 main.py once
```

정상이면 슬랙 채널에 메시지가 옵니다.

---

## Step 8. 백그라운드 자동 실행 등록 (systemd)

```bash
# 서비스 파일 생성
sudo nano /etc/systemd/system/community-monitor.service
```

아래 내용 붙여넣기:
```ini
[Unit]
Description=Community Monitor Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/community-monitor
ExecStart=/usr/bin/python3 /home/ubuntu/community-monitor/main.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable community-monitor
sudo systemctl start community-monitor

# 상태 확인
sudo systemctl status community-monitor

# 로그 실시간 확인
sudo journalctl -u community-monitor -f
```

---

## 운영 명령어

```bash
# 서비스 재시작 (코드 수정 후)
sudo systemctl restart community-monitor

# 서비스 중지
sudo systemctl stop community-monitor

# 로그 확인
sudo journalctl -u community-monitor -n 100

# 슬랙 Webhook URL 변경
nano ~/community-monitor/config.py
sudo systemctl restart community-monitor
```

---

## 키워드 추가 방법

`config.py`의 `KEYWORDS` 리스트에 추가:

```python
KEYWORDS = [
    "알뜰폰",
    "새로추가할키워드",  # ← 이렇게 추가
    ...
]
```

추가 후 서비스 재시작:
```bash
sudo systemctl restart community-monitor
```

---

## 예상 비용

| 항목 | 비용 |
|------|------|
| EC2 t2.micro | 무료 (12개월 프리티어) |
| 슬랙 Incoming Webhook | 무료 |
| 트래픽 | 월 15GB 무료 |
| **합계** | **0원 (프리티어 기간)** |

프리티어 12개월 이후: 월 약 $8~10 (t2.micro 기준)
