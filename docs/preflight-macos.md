# 사전 점검: 맥에서 GL5와 대화가 되는지 확인하기

맥을 라이다 호스트로 쓰려는 모든 시도의 **첫 단계**다. VM도, 도커도, ROS도 필요 없다.

## 왜 이게 첫 단계인가

GL5는 명령과 포인트클라우드를 UDP 소켓 하나로 주고받는다. SDK가 그 소켓을 로컬
주소에 바인딩한 뒤 센서 주소로 `connect()` 하기 때문에, 커널은 소스가 정확히 센서가
아닌 패킷을 전부 버린다.

따라서 **이 도구가 센서 설정을 읽어오면 그 맥은 GL5와 통신할 수 있다는 것이
증명된다.** 그 위에 올리는 VM이든 컨테이너든 전제가 선다. 반대로 이게 안 되면 UTM
설정을 아무리 만져도 소용없다.

덤으로 `ip_port_pc` 값을 알아낸다. 센서는 자기한테 플래시된 `pcPort` 로 스트림을
보내는데, 벤더 launch 파일의 기본값 `0` 은 OS 임의 포트라서 센서가 알 수 없다.
연결은 되는데 데이터만 안 오는 증상의 원인이 대부분 이것이다.

## 빌드

```bash
brew install cmake
git clone https://github.com/Kimtona/soslab-gl5-ros2-workshop.git
cd soslab-gl5-ros2-workshop
./scripts/build_sdk_macos.sh
```

SDK를 받아 macOS용으로 한 줄 고치고 도구를 빌드한다. 벤더 README는 Windows와
Ubuntu만 지원한다고 하지만, 실제로 이식성을 막는 것은 `Netlink.h` 의
`#include <malloc.h>` 하나뿐이고 그 모듈은 `malloc` 계열을 쓰지도 않는다.

빌드 결과는 `.sdk/ethinfo-build/soslab_ethinfo` 다.

## 연결

1. USB-C 이더넷 어댑터를 맥에 꽂고 GL5를 랜 케이블로 직결한다.
2. 어댑터 인터페이스 이름을 확인한다. **재연결이나 재부팅으로 바뀐다.**

```bash
networksetup -listallhardwareports
```

3. 그 인터페이스에 센서와 같은 서브넷 주소를 준다.

```bash
sudo ipconfig set en6 MANUAL 192.168.1.15 255.255.255.0
```

직결 케이블에는 DHCP가 없으므로 수동 설정이 필수다. 설정하지 않으면 macOS가
`169.254.x.x` 를 자가 할당하고 센서와 통신할 수 없다.

## 실행

```bash
./.sdk/ethinfo-build/soslab_ethinfo --ip 192.168.1.10 --port 2000
```

성공하면 이렇게 나온다.

```
  sensor   192.168.1.10:2000
  pc       192.168.1.15:2368
  netmask  255.255.255.0
  gateway  192.168.1.1
  mac      ...
```

`pc` 줄의 포트가 **센서가 스트림을 보내는 목적지**다. 이 값을 적어두고 나중에
`ip_port_pc` 로 넘긴다.

## 실패할 때

센서가 응답하지 않으면 약 45초 뒤에 실패한다. SDK 내부 재시도 타임아웃이라
줄일 수 없다. 기다리면 된다.

출력의 `UDP :: Connected :: <주소>` 줄을 본다. **콜론 앞 주소가 실제로 바인딩된
인터페이스다.** 여기에 와이파이 주소나 센서 서브넷 밖 주소가 찍혀 있으면 그게
원인이다. 위의 3번을 다시 한다.

주소가 맞는데도 실패하면 와이어를 직접 본다.

```bash
sudo tcpdump -ni en6 -vv 'udp and host 192.168.1.10'
```

아무것도 안 잡히면 케이블, 전원, 어댑터 링크 순으로 확인한다.

## 센서 설정 바꾸기

조별로 센서를 같은 주소 체계로 통일하고 싶을 때 쓴다. **쓰기 전에 현재 값을
반드시 적어두어야 한다.**

```bash
./.sdk/ethinfo-build/soslab_ethinfo --ip 192.168.1.10 --port 2000 --set \
  --sensor-ip 192.168.1.10 --sensor-port 2000 \
  --pc-ip 192.168.1.15 --pc-port 2368 \
  --mask 255.255.255.0 --gateway 192.168.1.1
```

적용하려면 센서를 전원 재인가해야 한다.

조별로 센서를 각자 호스트에 직결한다면 링크가 서로 분리돼 있으므로 **모든 센서가
기본 주소 그대로여도 충돌하지 않는다.** 굳이 바꿀 필요가 없다.

## 다음 단계

여기까지 통했다면 맥이 GL5와 통신할 수 있다는 뜻이다. 그 다음은
[host-macos-utm.md](host-macos-utm.md) 로 간다.
