"""GL5 bring-up, fixing three things about the vendor's ml_viz.py.

1. The stock launch file resolves its RViz config with the relative path
   '../rviz/config.rviz', so it only runs from inside src/ml/launch. This one
   uses get_package_share_directory('ml').
2. It defaults to 'MLX'. lidarType is case sensitive and must match the
   connected unit, so this defaults to 'GL5'.
3. It binds ip_address_pc to the literal 192.168.1.15. Binding 0.0.0.0 instead
   is the SDK's own default and removes the need for the container's network
   namespace to own that address.

ip_port_pc is the one to watch. The GL5 streams to the pcIp:pcPort flashed on
the sensor, and 0 means "let the OS pick", which the sensor cannot know. Read
the flashed value with `soslab_ethinfo` and pass it here.
"""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

import os


def generate_launch_description():
    args = [
        DeclareLaunchArgument('lidarType', default_value='GL5',
                              description='GL5 | GL3 | MLX | MLA | MLU (case sensitive)'),
        DeclareLaunchArgument('ip_address_device', default_value='192.168.1.10'),
        DeclareLaunchArgument('ip_port_device', default_value='2000'),
        DeclareLaunchArgument('ip_address_pc', default_value='0.0.0.0'),
        DeclareLaunchArgument('ip_port_pc', default_value='0',
                              description='must match the pcPort flashed on the sensor'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('rviz_config', default_value=os.path.join(
            get_package_share_directory('ml'), 'rviz', 'gl5.rviz')),
    ]

    def as_int(name):
        return ParameterValue(LaunchConfiguration(name), value_type=int)

    ml_node = Node(
        package='ml',
        executable='ml_node',
        name='ml_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'lidarType': LaunchConfiguration('lidarType'),
            'ip_address_device': LaunchConfiguration('ip_address_device'),
            'ip_port_device': as_int('ip_port_device'),
            'ip_address_pc': LaunchConfiguration('ip_address_pc'),
            'ip_port_pc': as_int('ip_port_pc'),
        }],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', LaunchConfiguration('rviz_config')],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    return LaunchDescription(args + [ml_node, rviz_node])
