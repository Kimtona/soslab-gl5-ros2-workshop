# Mac을 라이다 호스트로: UTM 브리지 네트워킹

먼저 [preflight-macos.md](preflight-macos.md) 를 끝내야 한다. 맥이 GL5와 통신하지
못하면 이 문서는 의미가 없다.

## 먼저 읽을 경고

**이 경로는 될 수도 있고 안 될 수도 있다. 워크샵 당일 아침에 시도할 물건이 아니다.**

UTM에 macOS 26(Tahoe) 브리지 네트워킹 버그가 여러 건 **열린 채로** 있다.

- [#7229](https://github.com/utmapp/UTM/issues/7229) macOS 26에서 브리지 인터페이스가
  동작하지 않음. VM이 아예 안 뜨고 `cannot create vmnet interface` 가 난다.
- [#7658](https://github.com/utmapp/UTM/issues/7658) UTM 4.7.5 + macOS 26.3.1에서
  브리지 설정 시 부팅 화면에서 멈춤.
- [#7438](https://github.com/utmapp/UTM/issues/7438) Tahoe 업그레이드 후 브리지
  처리량이 쓸 수 없을 정도로 느려짐.

여기에 macOS 15부터 생긴 **Local Network 권한**이 겹친다. 방화벽을 꺼도 로컬 서브넷
통신이 막힐 수 있고, 재부팅 후 표시상으로는 허용인데 실제로는 차단으로 되돌아가는
사례가 보고돼 있다.

**30분만 시도하고, 안 되면 접는다.** 대안은 컴퓨터실이나 Live USB다.

## USB passthrough는 쓰지 않는다

이더넷 동글을 VM에 통째로 넘기는 방법이 직관적으로 보이지만 쓰면 안 된다.

UTM 공식 문서가 "macOS의 USB 캡처 방식 때문에 제대로 된 하드웨어 리셋이 불가능하고,
따라서 많은 장치가 정상 동작하지 않는다"고 명시한다. 이더넷 동글은 꽂는 순간 macOS
클래스 드라이버가 선점하므로 libusb가 인터페이스를 가져오지 못한다. RTL8153 USB-C
랜 동글로 정확히 같은 시도를 한 사례가 `LIBUSB_ERROR_ACCESS` 로 실패했다
([#5224](https://github.com/utmapp/UTM/issues/5224)).

"시스템 설정에서 인터페이스를 끄면 놓아준다"는 얘기가 돌지만 근거를 찾지 못했다.
민간요법으로 취급한다.

브리지 네트워킹이 구조적으로 맞다. `vmnet` 브리지는 진짜 L2 브리지라 게스트의
virtio NIC이 센서 와이어에 자기 MAC으로 올라간다. ARP가 돌고, 게스트 커널이 보는
소스 주소가 진짜 센서 주소가 된다. macOS는 동글을 계속 붙잡고 있어도 되고, 우리는
L2에서 같은 와이어를 탭할 뿐이다.

## 준비

UTM은 [공식 사이트](https://mac.getutm.app/)나 Mac App Store 어느 쪽이든 된다.
기능은 동일하고 App Store 판은 자동 업데이트가 될 뿐이다. **직접 빌드한 서명 없는
UTM은 안 된다.** 브리지와 USB 기능이 빠져 있다.

브리지에는 `com.apple.vm.networking` 권한이 필요한데 공식 배포판에는 들어 있다.
확인하려면:

```bash
codesign -d --entitlements - /Applications/UTM.app 2>/dev/null | grep vm.networking
```

## VM 만들기

**QEMU 백엔드를 쓴다.** Apple Virtualization 백엔드가 아니다. 이유는 셋이다.
인터페이스 이름을 자유롭게 입력할 수 있고(Apple 백엔드는 시스템이 열거해준 것만
고를 수 있어 동글이 목록에 뜰지 불확실하다), 실패 시 다른 방법으로 갈아탈 여지가
남으며, qcow2라 디스크가 훨씬 작다.

1. UTM → Create a New Virtual Machine → **Virtualize** → Linux
2. Ubuntu 22.04 **arm64** 서버 ISO를 지정한다. Apple Silicon이므로 arm64다.
3. 메모리 4GB 이상, CPU 4코어 이상, 디스크 32GB 정도.
4. 설치를 마치고 VM을 종료한다.

## 브리지 설정

1. 어댑터 인터페이스 이름을 확인한다. **매번 확인해야 한다.** 재연결, 재부팅,
   다른 허브 연결로 바뀐다. 설정한 이름의 인터페이스가 없으면 UTM은 VM을 아예
   시작하지 않는다.

```bash
networksetup -listallhardwareports
```

2. VM Settings → Network
   - Network Mode: **Bridged (Advanced)**
   - Bridged Interface: `en6` (위에서 확인한 이름)
   - Emulated Network Card: `virtio-net-pci`

3. VM을 시작한다. 여기서 안 뜨면 위의 macOS 26 버그다.

## 게스트 설정

직결 케이블에는 DHCP가 없으므로 고정 주소를 준다. **그 인터페이스에는 기본
게이트웨이를 두지 않는다.** 인터넷은 다른 NIC으로 나간다.

```bash
ip -4 -brief addr show                       # 브리지된 인터페이스 이름 확인
sudo ip addr add 192.168.1.15/24 dev enp0s1
sudo ip link set enp0s1 up
```

수신 버퍼를 키운다. SDK가 `setsockopt(SO_RCVBUF)` 를 호출하지 않아 소켓이 시스템
기본값을 그대로 쓴다. `rmem_max` 만 올리면 효과가 없다.

```bash
sudo sysctl -w net.core.rmem_default=8388608 net.core.rmem_max=26214400
```

도커를 설치하고 이미지를 받는다.

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # 재로그인
docker pull ghcr.io/kimtona/soslab-gl5-ros2-workshop:prebuilt
```

## 확인

계층별로 올라가며 본다. 건너뛰면 어디가 문제인지 알 수 없다.

```bash
# 1. 호스트(맥)에서 와이어가 보이는가
sudo tcpdump -ni en6 -vv 'udp and host 192.168.1.10'

# 2. 게스트에서 같은 패킷이 보이는가
sudo tcpdump -ni enp0s1 -vv 'udp and host 192.168.1.10'

# 3. 게스트에서 센서에 닿는가
ping -c 3 192.168.1.10

# 4. 컨테이너 안에서도 주소가 그대로 보이는가
docker run --rm --network=host ghcr.io/kimtona/soslab-gl5-ros2-workshop:prebuilt \
  ip -4 -brief addr show
```

4번에서 `192.168.1.15` 가 아니라 `172.17.x` 만 보이면 `--network=host` 가 빠진
것이다. 도커 NAT가 끼어들면 원래 문제로 돌아간다.

전부 통과하면 실행한다.

```bash
docker run -it --rm --network=host --privileged \
  ghcr.io/kimtona/soslab-gl5-ros2-workshop:prebuilt bash
# 컨테이너 안에서
soslab_ethinfo --ip 192.168.1.10 --port 2000
ros2 launch ml gl5_viz.launch.py ip_port_pc:=<읽은 pcPort>
```

브라우저에서 `http://localhost:6080/vnc.html?autoconnect=1` 을 연다. 조원들은
맥의 LAN 주소로 같은 포트를 열면 된다.

## 안 될 때

| 증상 | 확인 |
| --- | --- |
| VM이 시작조차 안 됨 | macOS 26 버그. Apple VZ 백엔드 브리지를 한 번 시도해보고 안 되면 접는다 |
| `cannot create vmnet interface` | 같은 버그. 또는 인터페이스 이름이 바뀌었다 |
| 부팅 화면에서 멈춤 | 같은 버그 |
| 호스트 tcpdump에는 잡히는데 게스트에는 안 잡힘 | 브리지가 안 선 것. Local Network 권한을 시스템 설정 → 개인정보 보호 및 보안에서 껐다 켠다 |
| 게스트에 보이는데 컨테이너에 안 보임 | `--network=host` 누락 |
| 프레임이 간헐적으로 빠짐 | `net.core.rmem_default` 를 올린다 |

VM이 도는 동안 맥이 잠들면 프레임이 끊긴다. 전원을 연결하고 자동 잠자기를 끄거나
`caffeinate -dimsu` 를 켜둔다.

30분 안에 안 되면 이 경로를 접고 컴퓨터실이나 Live USB로 간다. 그래도 워크샵은
성립한다. SDK 설치와 빌드 실습은 라이다 없이 각자 컨테이너에서 진행되고, 라이브
데이터는 Jetson 기준국에서 볼 수 있다.
