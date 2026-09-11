# 실습: 포인트클라우드 구독 노드 직접 만들기

벤더 `ml_node` 는 퍼블리셔다. 이 실습에서는 그 반대쪽, **구독자**를 직접
만든다. RViz 도 구독자이지만 그림만 보여줄 뿐 숫자를 알려주지 않는다.

**라이다가 필요 없다.** `fakegl5` 가 벤더 노드와 바이트 단위로 같은 메시지를
만들어내므로, 센서가 있든 없든 똑같이 진행된다.

## 시작

컨테이너 안에서 한 줄이면 준비가 끝난다.

```bash
startex
```

`/opt/exercise/gl5_subscriber` 를 `~/ws/src` 로 복사한다. `~/ws` 는 컨테이너
환경에서 **가장 마지막에 source 되는 워크스페이스**라서, 여기서 만든 노드가
우리가 넣어둔 것들을 덮어쓴다.

## 데이터 소스 켜기

이미 벤더 노드가 돌고 있으면 건너뛴다. 아니면 가짜 퍼블리셔를 띄운다.

```bash
fakegl5 &
ros2 topic hz /lidar0/pointcloud
```

40 Hz 근처가 나와야 한다.

## 빌드하고 그냥 실행해보기

**고치기 전에 먼저 돌려본다.** 골격 상태로도 수신은 되고 Hz 를 찍는다. 데이터가
흐르는 것을 눈으로 확인한 다음에 코드를 여는 편이 막혔을 때 원인을 좁히기 쉽다.

```bash
cd ~/ws
colcon build --symlink-install --packages-select gl5_subscriber
sauce
ros2 run gl5_subscriber scan_listener
```

이렇게 나온다.

```
[INFO] [scan_listener]: listening on /lidar0/pointcloud
[INFO] [scan_listener]: layout: height=1 width=1500 point_step=16
       fields=[x, y, z, rgb] frame_id=map
[INFO] [scan_listener]:  40.0 Hz (spec 40)      0/1500 valid
       nearest   nan m at     nan deg   max|z| nan m
```

Hz 와 layout 은 이미 맞고, 뒤쪽 세 항목이 비어 있다. 그게 여러분이 채울
부분이다.

## 메시지가 어떻게 생겼나

`ml_node.cpp` 가 만드는 형식이고 `fake_gl5.py` 가 그대로 따라 한다.

| 필드 | 값 | 의미 |
| --- | --- | --- |
| `height` | 1 | 한 줄. GL5 는 2D 스캐너다 |
| `width` | 1500 | 프레임당 점 개수 |
| `point_step` | 16 | 점 하나가 16바이트 |
| `fields` | x, y, z, rgb | x/y/z 는 FLOAT32 (offset 0, 4, 8), rgb 는 UINT32 (offset 12) |
| 단위 | m | 센서는 mm 로 보내고 노드 안에서 변환된다 |
| `frame_id` | `"map"` | 하드코딩돼 있다 |

따라서 i번째 점은 `msg.data[i*16 : i*16+16]` 이고, 앞 12바이트를 읽으면 된다.

```python
x, y, z = struct.unpack_from("<fff", msg.data, i * msg.point_step)
```

## 채울 것 세 가지

`~/ws/src/gl5_subscriber/gl5_subscriber/scan_listener.py` 를 연다. `report()`
안에 TODO 가 세 개 있다.

1. **유효한 점 세기.** x, y, z 가 전부 유한하고 `math.hypot(x, y)` 가
   `MIN_VALID_RANGE` 이상인 점만 센다. 1500 중 몇 개가 실제 반사인가?
2. **가장 가까운 점.** 거리(m)와 방위각. 방위각은
   `math.degrees(math.atan2(y, x))`. 센서 앞에서 손을 흔들면 숫자가 따라 움직여야
   한다.
3. **`abs(z)` 의 최댓값.** 0.000 이 나와야 정상이다. GL5 는 2D 스캐너라
   `GL5.cpp` 가 모든 점의 z 를 0으로 둔다. 이 한 줄이 화면의 부채꼴이 왜
   3D 덩어리가 아닌지 설명해준다.

`--symlink-install` 로 빌드했으므로 **고칠 때마다 다시 빌드하지 않는다.** 노드만
Ctrl-C 로 끄고 다시 실행하면 된다.

## 다 되면

```
[INFO] [scan_listener]:  40.0 Hz (spec 40)   1500/1500 valid
       nearest  1.83 m at   -42.7 deg   max|z| 0.000 m
```

정답과 비교한다.

```bash
ros2 run gl5_subscriber scan_listener_solution
```

## 처음부터 손으로 만들고 싶다면

`startex` 가 주는 골격 없이 `ros2 pkg create` 부터 하는 것도 좋다.

```bash
cd ~/ws/src
ros2 pkg create --build-type ament_python --dependencies rclpy sensor_msgs my_listener
```

`setup.py` 의 `entry_points` 에 실행 파일을 등록하는 것을 잊기 쉽다. 등록하지
않으면 `ros2 run` 이 노드를 찾지 못한다.

```python
entry_points={
    'console_scripts': [
        'listener = my_listener.listener:main',
    ],
},
```

## 더 해볼 것

- 최근접 점이 특정 거리보다 가까우면 경고를 찍는다. 충돌 감지의 가장 단순한 형태다.
- 270도를 구역으로 나눠 구역별 최근접 거리를 찍는다. GL5 의 사각지대 90도가
  어디인지 숫자로 드러난다.
- `sensor_msgs/LaserScan` 으로 변환해 퍼블리시한다. 2D 스캐너이므로 정보 손실이
  없고, `slam_toolbox` 같은 기성 패키지에 바로 물릴 수 있다.
