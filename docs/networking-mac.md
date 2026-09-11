# Mac: 뷰어로 참여하기

**Docker Desktop만으로는 Mac이 GL5를 직접 받을 수 없다.** 이 문서는 맥을 뷰어로
쓰는 방법을 다룬다. 실습 내용은 뷰어로도 그대로 다 할 수 있다.

맥을 라이다 호스트로 세우는 것 자체는 가능성이 있다. Docker Desktop이 아니라 진짜
VM을 쓰면 된다. 다만 macOS 26에 미해결 버그가 있어 사전 검증이 필수다. 시도하려면
[preflight-macos.md](preflight-macos.md) 로 먼저 맥이 센서와 통신하는지 확인한 뒤
[host-macos-utm.md](host-macos-utm.md) 를 따른다.

## Docker Desktop으로는 왜 안 되는가

Docker Desktop for Mac은 컨테이너를 VM 안에서 돌리고, 그 VM의 유일한 업링크는
NAT된 vmnet 인터페이스다. USB-C 이더넷 어댑터는 macOS 쪽에만 존재하고 컨테이너에서
보이지 않는다.

- `--network=host` 는 Mac에서 L4 포워더일 뿐이라 도움이 안 된다. SDK가
  UDP 소켓을 센서 주소로 `connect()` 하기 때문에, 소스가 포워더로 바뀐 패킷은
  커널이 전부 버린다.
- `macvlan` 은 컨테이너 호스트 네임스페이스에 물리 부모 인터페이스가 있어야
  한다. VM 안에는 없다.
- 포트 포워딩으로도 안 된다. 센서가 자기한테 플래시된 목적지로 스트림을 쏘기
  때문이다.

UTM이나 Lima/Colima의 브리지 모드는 사정이 다르다. `vmnet` 브리지는 진짜 L2
브리지라 게스트가 센서 와이어에 자기 MAC으로 올라가고, 그 안에서는 `--network=host`
가 정상 동작한다. 그쪽 경로는 [host-macos-utm.md](host-macos-utm.md) 에 정리했다.

## 뷰어로 참여하기

조의 라이다 호스트가 Zenoh 라우터를 띄우면, 거기에 TCP로 붙어 같은
포인트클라우드를 받는다. 이 연결은 클라이언트가 먼저 여는 단일 TCP 연결이라
Docker Desktop의 NAT를 그대로 통과한다. Mac 쪽에 포트 개방이 전혀 필요 없다.

```bash
cp .env.example .env
# ROUTER_HOST 를 조의 라이다 호스트 LAN 주소로 수정
docker compose --profile viewer up -d
docker compose exec viewer bash
```

컨테이너 안에서:

```bash
ros2 topic list
ros2 topic hz /lidar0/pointcloud
rviz2 -d /opt/soslab_sdk/examples/ros2_ml/src/ml/rviz/gl5.rviz
```

브라우저에서 `http://localhost:6080/vnc.html?autoconnect=1` 를 연다.

## RViz 설정 두 가지

이미지에 들어있는 `gl5.rviz` 를 쓰면 이미 맞춰져 있지만, 직접 디스플레이를
추가한다면 이 둘을 반드시 맞춰야 한다.

- **Fixed Frame 을 `map` 으로.** 벤더 노드가 모든 클라우드의 `frame_id` 를
  `"map"` 으로 하드코딩한다. 같게 맞추면 tf2가 identity로 풀어서
  `static_transform_publisher` 가 필요 없다.
- **PointCloud2 의 Reliability Policy 를 Best Effort 로.** 노드가 depth 1
  RELIABLE로 퍼블리시하는데, 무선에서 수 MB짜리 클라우드를 RELIABLE로 받으면
  끊긴다. RELIABLE 퍼블리셔는 BEST_EFFORT 구독자를 만족시키므로 안전하다.

## 토픽이 안 보일 때

```bash
# 1. 라우터에 TCP가 닿는지
nc -vz <ROUTER_HOST> 7447

# 2. 환경변수가 맞는지
echo $ZENOH_CONFIG_OVERRIDE $ROS_DOMAIN_ID $RMW_IMPLEMENTATION
```

`nc` 가 실패하면 네트워크 문제다. 행사장 와이파이의 AP 클라이언트 격리가 흔한
원인이고, 이 경우 같은 와이파이에 붙어 있어도 단말끼리 통신이 막힌다. 조별
유선 공유기에 물리면 해결된다.

`ROS_DOMAIN_ID` 는 조 전체가 같아야 한다. 기본값은 77이다.

## arm64 참고

이미지는 arm64 네이티브로 빌드돼서 에뮬레이션 없이 돈다. RViz는 소프트웨어
렌더링(llvmpipe)으로 동작하므로 팬과 줌이 네이티브만큼 매끄럽지는 않다.
확인하려면 컨테이너 안에서:

```bash
glxinfo | grep "OpenGL renderer"
```
