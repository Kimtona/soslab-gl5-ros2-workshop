from setuptools import setup

package_name = 'gl5_subscriber'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='workshop',
    maintainer_email='workshop@example.com',
    description='Workshop exercise: subscribe to the GL5 point cloud and describe it.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'scan_listener = gl5_subscriber.scan_listener:main',
            'scan_listener_solution = gl5_subscriber.scan_listener_solution:main',
        ],
    },
)
