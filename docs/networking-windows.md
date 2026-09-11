# Windows: LiDAR 호스트 만들기

조당 한 대가 이 역할을 맡는다. 이 문서대로 되지 않으면 그 머신은 뷰어로 쓰고
다른 Windows 머신을 라이다 호스트로 세운다.

## 왜 Docker Desktop을 쓰지 않는가

Docker Desktop의 host 네트워킹은 **L4 유저스페이스 포워더**다. 리눅스처럼
네트워크 네임스페이스를 공유하는 것이 아니다. Docker 공식 문서도 TCP/UDP보다
하위 계층 프로토콜은 지원하지 않는다고 명시한다.

GL5 드라이버에는 이게 치명적이다. SDK는 UDP 소켓을 `bind(pcIP, pcPort)` 한 뒤
`connect(lidarIP, 2000)` 한다. 커널은 그 순간부터 소스 주소가 정확히
`192.168.1.10:2000`인 데이터그램만 받아들인다. 포워더를 거친 패킷은 소스가
포워더로 바뀌어 있어 전부 버려진다. 연결은 되는 것처럼 보이는데 포인트클라우드만
안 오는 증상이 여기서 나온다.

그래서 **WSL2 배포판 안에 docker-ce를 직접 설치**한다. 그러면 진짜 리눅스
데몬이라 `--network=host`가 제대로 된 네임스페이스 공유가 된다.

## 요구사항

| 항목 | 최소 |
| --- | --- |
| Windows | 11 22H2 (빌드 22621) 이상 |
| WSL | 2.0.4 이상 |

**Windows 10은 이 역할을 할 수 없다.** mirrored 네트워킹 모드가 없고 우회로도
없다. `netsh interface portproxy`는 TCP 전용이라 도움이 안 된다.

확인:

```powershell
winver          # 빌드 22621 이상
wsl --version   # 2.0.4 이상, 낮으면 wsl --update
```

## 1. mirrored 네트워킹 켜기

`%UserProfile%\.wslconfig` 를 만들거나 편집한다.

```ini
[wsl2]
networkingMode=mirrored
dnsTunneling=true
firewall=true
```

그리고 적용한다.

```powershell
wsl --shutdown
```

## 2. 이더넷 어댑터에 고정 IP 주기

GL5 직결 케이블에는 DHCP가 없다. 관리자 PowerShell에서:

```powershell
New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.1.15 -PrefixLength 24
```

주소는 센서에 플래시된 `pcIp` 와 같아야 한다. 값을 모르면 아래 4번에서
`soslab_ethinfo` 로 읽는다.

## 3. Hyper-V 방화벽 열기

**mirrored 모드에서 가장 흔한 실패 원인이다.** 미러 인터페이스로 들어오는
인바운드는 기본 차단이다. 관리자 PowerShell에서:

```powershell
Get-NetFirewallHyperVVMSetting                       # Name(GUID) 확인
Set-NetFirewallHyperVVMSetting -Name '<위에서 본 GUID>' -DefaultInboundAction Allow
```

Defender 방화벽에도 해당 UDP 포트 인바운드 규칙을 추가한다.

## 4. WSL 안에 docker-ce 설치

Docker Desktop의 WSL 통합이 아니라 배포판 자체의 도커다.

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
# 그룹 반영을 위해 wsl --shutdown 후 다시 진입
```

## 5. 확인

```bash
# WSL 안에서. 172.x 가 아니라 192.168.1.15 가 보여야 한다.
ip -4 -brief addr show

ping -c 3 192.168.1.10

# 컨테이너 안에서도 같은 주소가 보여야 한다.
docker run --rm --network=host <이미지> ip -4 -brief addr show
```

`ip -4 addr` 가 `172.x` 만 보여주면 mirrored 모드가 안 켜진 것이다. 3번의
방화벽을 열었는데도 `tcpdump` 에 아무것도 안 잡히면 VPN 클라이언트가 라우팅을
가로챘을 가능성이 높다. Cisco AnyConnect, GlobalProtect, Zscaler가 흔한 범인이다.

## 6. 수신 버퍼 키우기

```bash
sudo sysctl -w net.core.rmem_default=8388608 net.core.rmem_max=26214400
```

`rmem_default` 가 핵심이다. SDK가 `setsockopt(SO_RCVBUF)` 를 한 번도 호출하지
않아서 소켓이 시스템 기본값을 그대로 쓴다. `rmem_max` 만 올리면 아무 효과가 없다.
`--network=host` 일 때 `docker run --sysctl net.core.*` 는 거부되므로 WSL 호스트
쪽에서 설정해야 한다.

## 7. 실행

```bash
cp .env.example .env      # SOSLAB_* 값을 센서에 맞게 수정
docker compose --profile lidar up -d
docker compose exec lidar bash
```

컨테이너 안에서:

```bash
soslab_ethinfo --ip 192.168.1.10 --port 2000     # 플래시된 pcPort 확인
ros2 launch ml gl5_viz.launch.py ip_port_pc:=<확인한 값>
```

브라우저에서 `http://localhost:6080/vnc.html?autoconnect=1` 를 연다.

막히면 컨테이너 안에서 `netcheck` 를 실행한다.
