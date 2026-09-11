# Ubuntu Live USB로 라이다 호스트 만들기

x86 머신을 USB로 부팅해 진짜 리눅스로 만든다. WSL2 mirrored, Hyper-V 방화벽,
Docker Desktop 문제가 전부 사라진다. 컴퓨터실 머신에 관리자 권한을 못 받을 때,
또는 개인 Windows 노트북에서 WSL2 설정이 번거로울 때 쓴다.

**Apple Silicon 맥은 부팅할 수 없다.** x86 전용이다.

## 왜 이게 확실한가

라이다 호스트에 필요한 것은 컨테이너가 센서와 같은 L2 세그먼트에 실제로 존재하는
것뿐이다. 진짜 리눅스에서 `--network=host` 는 네트워크 네임스페이스를 그대로
공유하므로 이 조건이 자동으로 만족된다. 우회도, 설정도, 버전 요구사항도 없다.

## 만들기

현장 와이파이로 조마다 1GB 넘는 이미지를 받는 것은 비현실적이다. **이미지를 미리
넣은 persistent USB** 를 만들어야 한다. 조당 1개씩 5개가 필요하다.

준비물은 64GB USB 3.0 이상. 용량이 작으면 persistent 영역이 부족하다.

### 1. 베이스 만들기

Ubuntu 22.04 LTS **desktop** amd64 ISO를 받는다. server가 아니라 desktop이어야
라이브 세션에서 바로 쓸 수 있다.

persistent 영역을 지원하는 도구로 굽는다. 단순 `dd` 는 persistence가 안 되므로
쓰지 않는다.

- macOS/Linux: [mkusb](https://help.ubuntu.com/community/mkusb) 또는 Ventoy
- Windows: [Rufus](https://rufus.ie/) — "Persistent partition size" 를 16GB 이상으로

### 2. 부팅해서 내용 채우기

만든 USB로 한 번 부팅한 뒤 다음을 실행한다. 이 작업은 인터넷이 되는 곳에서 미리
해둔다.

```bash
# 도커 설치
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"

# 이미지 미리 받기
sudo docker pull ghcr.io/kimtona/soslab-gl5-ros2-workshop:dev
sudo docker pull ghcr.io/kimtona/soslab-gl5-ros2-workshop:prebuilt

# 레포도 미리
git clone https://github.com/Kimtona/soslab-gl5-ros2-workshop.git ~/workshop

# 수신 버퍼를 부팅 때마다 적용
echo 'net.core.rmem_default=8388608' | sudo tee /etc/sysctl.d/99-lidar.conf
echo 'net.core.rmem_max=26214400'   | sudo tee -a /etc/sysctl.d/99-lidar.conf
```

종료할 때 persistence에 저장되도록 정상 종료한다.

### 3. 복제

첫 USB가 완성되면 나머지는 이미지로 복제하는 편이 빠르다.

```bash
sudo dd if=/dev/sdX of=workshop-usb.img bs=4M status=progress
# 나머지 USB에 굽기
sudo dd if=workshop-usb.img of=/dev/sdY bs=4M status=progress
```

`/dev/sdX` 를 반드시 확인하고 쓴다. 틀리면 내장 디스크를 지운다.

## 현장에서 부팅

1. USB를 꽂고 전원을 켠다.
2. 부팅 메뉴 키를 누른다. 제조사마다 다르다. F12가 가장 흔하고 F2, F10, Esc, Del도 쓴다.
3. USB 장치를 고른다. "Try Ubuntu" 를 선택한다. 설치하지 않는다.
4. Secure Boot가 켜져 있어도 Ubuntu는 서명돼 있어 대개 통과한다. 막히면 BIOS에서
   잠시 끈다.

## 라이다 연결

```bash
# 랜 포트 이름 확인
ip -4 -brief addr show

# 센서와 같은 서브넷 주소 부여. 직결에는 DHCP가 없다.
sudo ip addr add 192.168.1.15/24 dev enp0s31f6
sudo ip link set enp0s31f6 up

ping -c 3 192.168.1.10
```

교내망 케이블이 꽂혀 있었다면 빼고 GL5를 연결한다. 인터넷이 끊기지만 이미지를
미리 받아뒀으므로 상관없다.

## 실행

```bash
cd ~/workshop
cp .env.example .env      # ROS_DOMAIN_ID 를 조 번호에 맞게
docker compose --profile lidar up -d
docker compose exec lidar bash
```

컨테이너 안에서:

```bash
soslab_ethinfo --ip 192.168.1.10 --port 2000      # 플래시된 pcPort 확인
ros2 launch ml gl5_viz.launch.py ip_port_pc:=<읽은 값>
```

브라우저에서 `http://localhost:6080/vnc.html?autoconnect=1` 을 연다. 조원들은
이 머신의 LAN 주소로 같은 포트를 연다.

## 주의

**라이브 세션은 종료하면 persistence 영역 밖의 것이 사라진다.** 실습 중 만든
파일을 남기려면 홈 디렉터리에 두거나 따로 복사한다.

메모리를 많이 쓴다. 4GB 미만 머신에서는 빌드 중 멈출 수 있다. 그런 머신에서는
`:prebuilt` 태그를 쓴다.
