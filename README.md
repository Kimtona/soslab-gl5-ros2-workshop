# SOSLAB GL5 ROS2 워크샵 이미지

SOSLAB GL5 라이다를 ROS2 Humble에서 띄워보는 워크샵용 도커 이미지다. SDK 설치,
빌드, 노드 실행, 데이터 확인까지 OS에 상관없이 같은 환경에서 진행하기 위한 것이다.

RViz는 컨테이너 안에서 돌고 브라우저로 본다. XQuartz나 VcXsrv를 설치할 필요가 없다.

## 시작하기 전에

**전날 미리 받아두는 편이 낫다.** 압축 상태로도 1GB 안팎이다.

```bash
docker pull ghcr.io/OWNER/soslab-gl5-ros2-workshop:dev
```

| 태그 | 내용 |
| --- | --- |
| `:dev` | ROS2 Humble, 빌드 툴체인, SDK 소스. **빌드는 여러분이 한다.** 실습 본편 |
| `:prebuilt` | 위에 더해 SDK와 `ml` 노드까지 빌드 완료. 막혔을 때 쓰는 백업 |

`linux/amd64` 와 `linux/arm64` 둘 다 제공한다. Apple Silicon에서 에뮬레이션 없이 돈다.

## 조 안에서 두 역할로 나눈다

GL5는 이더넷 UDP 전용이고, SDK가 소켓을 특정 주소에 바인딩한 뒤 센서로
`connect()` 하기 때문에 **컨테이너가 라이다와 같은 네트워크 세그먼트에 실제로
존재해야 한다.** Docker Desktop의 host 네트워킹은 L4 포워더라서 이 조건을
만족하지 못한다.

| 역할 | 누가 | 조건 |
| --- | --- | --- |
| **라이다 호스트** (조당 1대) | GL5가 꽂힌 머신 | Windows 11 22H2+ 에서 WSL2 mirrored + docker-ce |
| **뷰어** (나머지 전원) | Mac 포함 | 제약 없음. 조의 Zenoh 라우터에 TCP로 접속 |

**Mac은 라이다 호스트가 될 수 없다.** 뷰어로 참여하면 실습 내용은 전부 할 수 있다.

- 라이다 호스트 준비: [docs/networking-windows.md](docs/networking-windows.md)
- 뷰어 참여: [docs/networking-mac.md](docs/networking-mac.md)
- 막혔을 때: [docs/troubleshooting.md](docs/troubleshooting.md)

## 라이다 호스트

```bash
git clone https://github.com/OWNER/soslab-gl5-ros2-workshop.git
cd soslab-gl5-ros2-workshop
cp .env.example .env          # IMAGE, SOSLAB_* 수정

# 호스트에서. SDK가 SO_RCVBUF 를 설정하지 않아 시스템 기본값을 그대로 쓴다.
sudo sysctl -w net.core.rmem_default=8388608 net.core.rmem_max=26214400

docker compose --profile lidar up -d
docker compose exec lidar bash
```

컨테이너 안에서 먼저 센서에 뭐가 플래시돼 있는지 읽는다.

```bash
soslab_ethinfo --ip 192.168.1.10 --port 2000
```

그 다음 실습을 시작한다. `:dev` 태그라면 SDK를 직접 빌드한다.

```bash
buildsdk                      # /opt/scripts/build_sdk.sh
source /opt/soslab_ws/install/setup.bash
ros2 launch ml gl5_viz.launch.py ip_port_pc:=<위에서 읽은 pcPort>
```

`:prebuilt` 태그라면 마지막 줄만 실행하면 된다.

브라우저에서 `http://localhost:6080/vnc.html?autoconnect=1` 를 연다.

## 뷰어

```bash
cp .env.example .env          # ROUTER_HOST 를 조의 라이다 호스트 주소로
docker compose --profile viewer up -d
docker compose exec viewer bash
```

```bash
ros2 topic hz /lidar0/pointcloud
rviz2 -d /opt/soslab_sdk/examples/ros2_ml/src/ml/rviz/gl5.rviz
```

브라우저는 똑같이 `http://localhost:6080/vnc.html?autoconnect=1`.

## 컨테이너 안에서 쓸 수 있는 것

| | |
| --- | --- |
| `buildsdk` | SDK와 `ml` 노드를 벤더 README 순서대로 빌드 |
| `netcheck` | 스트림이 안 올 때 원인을 순서대로 점검 |
| `soslab_ethinfo` | 센서에 플래시된 IP/포트 확인 (`:prebuilt` 전용) |
| `sauce` | ROS 환경 다시 source |

## 벤더 코드에서 미리 알아둘 것

워크샵에서 직접 부딪히게 되는 것들이다. 전부 SDK 원본의 성질이고, 이 레포의
`patches/` 에 대응책이 들어있다.

**`ip_port_pc` 가 핵심이다.** GL5는 명령과 스트림을 UDP 소켓 하나로 처리하는데,
스트림을 어디로 보낼지 연결 시점에 알려주지 않는다. 센서에 플래시된
`pcIp:pcPort` 로 쏜다. 벤더 기본값 `0` 은 OS 임의 포트라서 센서가 알 수 없다.
연결은 되는데 포인트클라우드만 안 오면 거의 항상 이것이다.

**`CMakeLists.txt` 와 `package.xml` 이 어긋나 있다.** CMake는 `cv_bridge`,
`OpenCV`, `Boost`, `PCL` 을 찾지만 `package.xml` 에는 없어서 `rosdep install` 로는
안 깔린다. 정작 `ml_node.cpp` 는 그중 무엇도 쓰지 않는다. `:dev` 이미지에는 미리
설치해뒀고, `scripts/slim_cmakelists.py` 로 제거할 수도 있다.

**launch 파일의 RViz 경로가 상대경로다.** 그래서 `src/ml/launch` 안에서만
실행된다. `patches/gl5_viz.launch.py` 는 `get_package_share_directory` 를 쓴다.

**`frame_id` 가 `"map"` 으로 하드코딩돼 있다.** RViz Fixed Frame도 `map` 으로
두면 TF 퍼블리셔가 필요 없다. 타임스탬프는 센서 시각이 아니라 노드 클럭이고,
mm에서 m 변환은 노드 안에서 일어난다.

## 직접 빌드하기

```bash
docker buildx build --target dev      --build-arg INSTALL_HEAVY_DEPS=1 -t soslab-gl5:dev .
docker buildx build --target prebuilt --build-arg INSTALL_HEAVY_DEPS=0 -t soslab-gl5:prebuilt .
```

SDK는 v1.1.0 (`9a1f4c4`) 으로 고정돼 있다. `SDK_REF` 빌드 인자로 바꿀 수 있다.

## 라이선스

이 레포의 파일은 MIT. [SOSLAB SDK](https://github.com/SOSLAB-github/SOSLAB_SDK)
는 BSD 3-Clause이고 이미지 빌드 시 원본 그대로 내려받는다. 벤더 소스를 이 레포에
포함하지 않는다.
