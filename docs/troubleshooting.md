# 문제 해결

증상별로 찾아보면 된다. 컨테이너 안에서 `netcheck` 를 먼저 돌려보는 것이 가장
빠르다.

## `ros2 topic hz` 나 `ros2 topic list` 가 아무것도 출력하지 않는다

**노드는 멀쩡한데 CLI 만 조용한 경우다.** `ros2` 커맨드라인은 데몬을 하나 띄워
그래프 정보를 캐시하는데, 컨테이너에서 처음 부를 때 그 데몬이 토픽을 놓치는
일이 있다. 데몬을 끄고 다시 부르면 된다.

```bash
ros2 daemon stop
ros2 topic hz /lidar0/pointcloud
```

정말 데이터가 오는지 먼저 확인하고 싶으면 `echo` 가 데몬을 덜 타므로 더 믿을
만하다.

```bash
ros2 topic echo --once --field header /lidar0/pointcloud
```

## 컨테이너가 172.17.x 주소를 갖는다

Docker 기본 bridge 네트워크에 있다는 뜻이다. **두 가지 경우로 나뉜다.**

리눅스 호스트에서 `--profile lidar` 를 쓰는 중이라면 `--network=host` 가 빠진
것이다. 고쳐야 한다.

Docker Desktop 호스트에서 `--profile lidar-mac` 을 쓰는 중이라면 정상이다.
이 경로는 발행된 UDP 포트로 스트림을 받는다. 대신 세 개의 숫자가 전부 같아야
한다 — 센서에 플래시된 `pcPort`, `docker` 의 `-p <포트>:<포트>/udp`, launch 의
`ip_port_pc`. 하나라도 어긋나면 연결은 성공하고 포인트클라우드만 영영 오지
않는다.

컨테이너 시작 시 출력되는 배너의 `addresses` 줄에서 바로 확인할 수 있다.

## `connectLidar failed`

연결 단계부터 실패한 것이다. 순서대로 확인한다.

```bash
ip -4 -brief addr show          # 센서와 같은 서브넷에 주소가 있는가
ip route get 192.168.1.10       # 경로가 잡히는가
ping -c 3 192.168.1.10          # 응답하는가 (무응답이 항상 치명적이진 않다)
```

케이블, 서브넷 불일치, 방화벽 순으로 흔하다.

## 연결은 되는데 포인트클라우드가 안 온다

**가장 흔한 문제이고, 원인이 거의 항상 `ip_port_pc` 다.**

GL5는 명령과 스트림을 UDP 소켓 하나로 주고받는데, 스트림 목적지를 연결 시점에
알려주지 않는다. 센서에 플래시된 `pcIp:pcPort` 로 쏜다. 벤더 launch 파일의
기본값 `ip_port_pc: 0` 은 "OS가 아무 포트나 골라라"라는 뜻이라 센서가 알 수 없다.

플래시된 값을 읽는다.

```bash
soslab_ethinfo --ip 192.168.1.10 --port 2000
```

출력의 `pc` 줄이 센서가 쏘는 목적지다. 그 포트로 다시 띄운다.

```bash
ros2 launch ml gl5_viz.launch.py ip_port_pc:=<읽은 pcPort>
```

호스트 NIC 주소도 출력된 `pcIp` 와 같아야 한다.

와이어에서 직접 확인하려면:

```bash
sudo tcpdump -ni any -vv 'udp and host 192.168.1.10'
```

스트림 패킷의 목적지 포트가 곧 `ip_port_pc` 에 넣을 값이다.

## 포인트클라우드가 끊기거나 프레임이 빠진다

대역폭은 원인이 아니다. GL5는 2D 스캐너라 데이터가 작다. 와이어 위로 초당 약
0.25 MB, ROS2 토픽으로 약 958 KB/s다. 실측값도 예측과 일치한다. 공유기 와이파이로
조원 여럿이 동시에 봐도 문제가 없다.

거의 항상 수신 버퍼다.

```bash
netstat -su | grep -i 'receive buffer errors'
```

0이 아니면 호스트에서 올린다.

```bash
sudo sysctl -w net.core.rmem_default=8388608 net.core.rmem_max=26214400
```

`rmem_default` 가 핵심이다. SDK가 `setsockopt(SO_RCVBUF)` 를 호출하지 않아
소켓이 시스템 기본값을 그대로 받는다. `rmem_max` 만 올리면 효과가 없다.
`--network=host` 일 때 `docker run --sysctl` 은 거부되므로 호스트에서 해야 한다.

## `colcon build` 가 PCL 이나 OpenCV 를 못 찾는다

의도된 함정이고 실제 ROS 프로젝트에서 흔한 버그다.

벤더의 `examples/ros2_ml/src/ml/CMakeLists.txt` 는 `cv_bridge`, `OpenCV`,
`Boost`, `PCL` 을 `find_package` 하지만 `package.xml` 에는 선언하지 않는다.
그래서 `rosdep install` 로는 절대 설치되지 않는다. 그런데 `ml_node.cpp` 는
`rclcpp`, `sensor_msgs`, `Lidar.h` 만 include한다. **실제로는 하나도 쓰지 않는다.**

두 가지 길이 있다.

```bash
# 의존성을 설치해서 벤더 지침대로 빌드
sudo apt update && sudo apt install -y \
  ros-humble-cv-bridge libopencv-dev libpcl-dev libboost-system-dev

# 또는 안 쓰는 의존성을 제거 (이미지가 1.5~2GB 가벼워진다)
python3 /opt/scripts/slim_cmakelists.py \
  /opt/soslab_sdk/examples/ros2_ml/src/ml/CMakeLists.txt
```

`:dev` 태그에는 의존성이 미리 들어있어서 첫 번째 길이 바로 통한다.

## `ros2 launch` 가 rviz config 를 못 찾는다

벤더의 `ml_viz.py` 가 `'../rviz/config.rviz'` 라는 상대경로를 쓴다. 그래서
`src/ml/launch` 디렉터리 안에서만 실행된다. 대신 패치된 launch를 쓴다.

```bash
ros2 launch ml gl5_viz.launch.py
```

이쪽은 `get_package_share_directory('ml')` 로 경로를 푼다.

## RViz 가 안 뜨거나 Ogre 에러가 난다

```bash
echo $DISPLAY                      # :1 이어야 한다
xdpyinfo -display :1 | head -3     # 가상 디스플레이가 살아있는가
glxinfo | grep "OpenGL renderer"   # llvmpipe 여야 한다
tail /tmp/xvfb.err /tmp/x11vnc.err
```

## 브라우저에서 6080 이 안 열린다

```bash
docker compose ps                  # 컨테이너가 살아있는가
tail /tmp/novnc.log
```

라이다 호스트 컨테이너는 `network_mode: host` 라서 포트 매핑이 없다. 호스트에서
직접 `localhost:6080` 으로 열린다. 뷰어는 매핑을 쓴다.

## 뷰어에서 토픽이 안 보인다

```bash
nc -vz $ROUTER_HOST 7447
echo $ROS_DOMAIN_ID                # 조 전체가 같아야 한다
```

라우터 쪽에서:

```bash
ss -ltnp | grep 7447
```

`nc` 가 실패하면 네트워크 문제다. 행사장 와이파이의 AP 클라이언트 격리가 가장
흔하다. 조별 유선 공유기가 유일한 현실적 대안이다.

## `Unable to connect to a Zenoh router` 경고가 뜬다

노드 시작 직후에 거의 항상 보이는 경고다. 노드는 그대로 초기화를 계속하므로
혼자 쓸 때는 무시해도 된다. 다만 이 상태에서는 **다른 머신이 토픽을 볼 수 없다.**

조 단위로 공유하려면 라이다 호스트에서 라우터를 띄운다.

```bash
ros2 run rmw_zenoh_cpp rmw_zenohd
```

compose의 `lidar` 프로파일에는 `router` 서비스가 이미 포함돼 있다.

재시도 횟수는 `ZENOH_ROUTER_CHECK_ATTEMPTS` 로 늘릴 수 있다. 라우터보다 노드가
먼저 뜨는 경우에 쓸모가 있다.

## 점이 1500개보다 적게 오면 노드가 죽을 수 있다

벤더 코드의 잠재 버그다. `GL5.cpp` 의 `parseStreamData` 가 패킷에서 읽은 개수로
점 벡터를 resize 하면서 `frameData.cols` 는 1500으로 그대로 둔다. `ml_node.cpp` 는
`rows * cols` 로 인덱싱하므로, 센서가 1500개보다 적게 보고하면 벡터 범위를 넘어
읽는다.

정상 동작 중에는 잘 나타나지 않지만, 원인 모를 크래시가 나면 이걸 의심한다.

## 스캔이 너무 어둡게 보인다

벤더 노드가 반사 강도를 회색조로 변환해 `rgb` 필드에 넣는다. 약한 반사는 거의
검은색이 된다. RViz의 PointCloud2 디스플레이에서 **Color Transformer 를 FlatColor**
로 바꾸면 강도와 무관하게 밝은 단색으로 보인다.

Size (Pixels) 를 6~8로 키우는 것도 도움이 된다.

## 화면에 부채꼴 한 줄만 보인다

정상이다. **GL5는 3D가 아니라 2D 스캐너다.** 모든 점의 Z가 0이라 평면에 깔린
270도 부채꼴로 보이고, 나머지 90도는 센서의 사각지대라 비어 있다.

Z축으로 색을 칠하면 모든 값이 같아서 단색이 된다. 기본 설정이 RGB8을 쓰는 이유다.

## 포인트클라우드가 기하학적으로 이상하다 (arm64)

SDK의 `_x64` 접미사는 포인터 크기로만 정해지기 때문에 arm64에서도 같은 파일명이
나오고 링크는 통과한다. 하지만 SOSLAB이 arm64를 검증한 적이 없고 엔디안 처리가
수작업이다. 빌드 성공이 와이어 파싱이 맞다는 증거는 아니다.

x86_64 머신에서 같은 센서를 띄워 비교해보고, 다르면 이슈로 남긴다.
