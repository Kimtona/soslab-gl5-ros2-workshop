# syntax=docker/dockerfile:1.7
#
# SOSLAB GL5 ROS2 workshop image.
#
#   --target dev       ROS2 Humble + toolchain + noVNC + unbuilt SDK source
#   --target prebuilt  the above, with the SDK and the `ml` node already built
#
# Base is ros:humble-ros-base-jammy because osrf/ros:humble-desktop has no
# linux/arm64 manifest; rviz2 is installed from apt instead.

ARG SDK_REF=9a1f4c46f0842a8a23e62cab7e8f39da9c09f9ef

# ---------------------------------------------------------------- common ----
FROM ros:humble-ros-base-jammy AS common

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# The vendor CMakeLists find_package()s cv_bridge/OpenCV/PCL/Boost even though
# ml_node.cpp never includes them. Keep them so the vendor's own build steps
# work verbatim during the workshop; the prebuilt target overrides this to 0.
ARG INSTALL_HEAVY_DEPS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git ca-certificates \
      python3-colcon-common-extensions python3-pip \
      ros-humble-rviz2 \
      ros-humble-rmw-zenoh-cpp \
      ros-humble-tf2-ros \
      ros-humble-topic-tools \
      xvfb x11vnc novnc websockify openbox xterm dbus-x11 \
      x11-xserver-utils x11-utils x11-apps \
      libgl1-mesa-dri mesa-utils supervisor \
      iproute2 iputils-ping tcpdump net-tools netcat-openbsd \
      less nano vim-tiny sudo tini \
 && if [ "$INSTALL_HEAVY_DEPS" = "1" ]; then \
      apt-get install -y --no-install-recommends \
        ros-humble-cv-bridge libopencv-dev libpcl-dev libboost-system-dev ; \
    fi \
 && rm -rf /var/lib/apt/lists/*

# noVNC ships vnc.html but no index.html; the redirect saves a support question.
RUN ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# Fixed uid/gid on purpose. This image is pulled from a registry by many people,
# so it must not be built per-host the way race_stack's devcontainer is.
ARG USERNAME=ws
RUN groupadd --gid 1000 ${USERNAME} \
 && useradd --uid 1000 --gid 1000 -m -s /bin/bash ${USERNAME} \
 && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
 && chmod 0440 /etc/sudoers.d/${USERNAME}

COPY supervisord.conf /etc/supervisor/conf.d/workshop.conf
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/ /opt/scripts/
COPY patches/ /opt/patches/
# Pristine copy of the subscriber exercise; `startex` copies it into ~/ws/src.
COPY exercise/ /opt/exercise/
RUN chmod +x /usr/local/bin/entrypoint.sh /opt/scripts/*.sh \
 && ln -sf /opt/scripts/build_sdk.sh  /usr/local/bin/buildsdk \
 && ln -sf /opt/scripts/net_check.sh  /usr/local/bin/netcheck \
 && ln -sf /opt/scripts/start_x11vnc.sh /usr/local/bin/start_x11vnc.sh \
 && ln -sf /opt/scripts/fake_gl5.py    /usr/local/bin/fakegl5 \
 && ln -sf /opt/scripts/start_zenohd.sh /usr/local/bin/start_zenohd.sh \
 && ln -sf /opt/scripts/play_reference.sh /usr/local/bin/play_reference \
 && ln -sf /opt/scripts/start_exercise.sh /usr/local/bin/startex

ENV DISPLAY=:1 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    QT_X11_NO_MITSHM=1 \
    NOVNC_PORT=6080 \
    ROS_DISTRO=humble \
    ROS_DOMAIN_ID=77 \
    RMW_IMPLEMENTATION=rmw_zenoh_cpp \
    SOSLAB_SDK_DIR=/opt/soslab_sdk \
    SOSLAB_WS=/opt/soslab_ws

# Owned by the workshop user so the build can run unprivileged.
RUN mkdir -p ${SOSLAB_WS}/src ${SOSLAB_SDK_DIR} \
 && chown -R 1000:1000 ${SOSLAB_WS} ${SOSLAB_SDK_DIR}

RUN echo 'source /opt/scripts/setup_env.sh' > /etc/profile.d/10-workshop.sh

USER ${USERNAME}
WORKDIR /home/${USERNAME}
RUN mkdir -p /home/${USERNAME}/ws/src \
 && echo 'source /opt/scripts/setup_env.sh' >> /home/${USERNAME}/.bashrc

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["bash"]

# --------------------------------------------------------------- sdk-src ----
FROM common AS sdk-src
ARG SDK_REF
USER root
ADD --chown=ws:ws https://github.com/SOSLAB-github/SOSLAB_SDK/archive/${SDK_REF}.tar.gz /tmp/sdk.tar.gz
RUN mkdir -p ${SOSLAB_SDK_DIR} \
 && tar xzf /tmp/sdk.tar.gz --strip-components=1 -C ${SOSLAB_SDK_DIR} \
 && rm /tmp/sdk.tar.gz

# Applied to the source, not at build time, so that participants who follow the
# vendor README by hand get it too. It un-connect()s the UDP socket, which is
# what lets the stream arrive through Docker Desktop's port publishing.
RUN python3 /opt/scripts/patch_sdk_docker_udp.py ${SOSLAB_SDK_DIR}
COPY tools/soslab_ethinfo/ ${SOSLAB_SDK_DIR}/soslab_ethinfo/
RUN chown -R ws:ws ${SOSLAB_SDK_DIR}
USER ws

# ------------------------------------------------------------- target dev ----
# SDK source is present but deliberately NOT built. Building it is the workshop.
FROM sdk-src AS dev
LABEL org.opencontainers.image.title="SOSLAB GL5 ROS2 workshop (build-it-yourself)"

# ------------------------------------------------------------- sdk-build ----
FROM sdk-src AS sdk-build
RUN /opt/scripts/build_sdk.sh --slim --no-symlink

# -------------------------------------------------------- target prebuilt ----
FROM common AS prebuilt
LABEL org.opencontainers.image.title="SOSLAB GL5 ROS2 workshop (prebuilt)"
USER root
COPY --from=sdk-build --chown=ws:ws /opt/soslab_ws/install /opt/soslab_ws/install
COPY --from=sdk-build --chown=ws:ws /opt/soslab_sdk/_archive_ /opt/soslab_sdk/_archive_
RUN echo /opt/soslab_sdk/_archive_/lib > /etc/ld.so.conf.d/soslab.conf && ldconfig \
 && ln -sf /opt/soslab_sdk/_archive_/bin/soslab_ethinfo /usr/local/bin/soslab_ethinfo
USER ws
