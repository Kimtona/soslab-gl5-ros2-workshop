// soslab_ethinfo -- read (and optionally rewrite) the Ethernet configuration
// stored on a SOSLAB GL-series sensor.
//
// Why this exists: the GL5 carries commands and the point-cloud stream on a
// single UDP socket that the SDK bind()s to pcIp:pcPort and then connect()s to
// the sensor. Nothing in connectLidar() or streamStart() tells the sensor where
// to send the stream, so it uses the pcIp:pcPort flashed in its own config.
// The vendor launch file's `ip_port_pc: 0` asks the OS for an ephemeral port,
// which the sensor has no way of knowing. Read the flashed value with this tool
// and pass it as ip_port_pc.
//
// getEthernetInfo/setEthernetInfo are public GL5 interfaces in Lidar.h.

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

#include "Lidar.h"

namespace {

struct Options {
    std::string lidarIp = "192.168.1.10";
    int lidarPort = 2000;
    std::string bindIp = "0.0.0.0";
    int bindPort = 0;

    bool doSet = false;
    std::string newSensorIp, newPcIp, newMask, newGateway;
    int newSensorPort = -1;
    int newPcPort = -1;
};

void usage(const char* argv0) {
    std::cerr <<
        "usage: " << argv0 << " [options]\n"
        "\n"
        "  --ip ADDR            sensor address      (default 192.168.1.10)\n"
        "  --port N             sensor command port (default 2000)\n"
        "  --bind-ip ADDR       local bind address  (default 0.0.0.0)\n"
        "  --bind-port N        local bind port     (default 0)\n"
        "\n"
        "  --set                rewrite the sensor's Ethernet config; requires\n"
        "                       --sensor-ip --sensor-port --pc-ip --pc-port\n"
        "                       --mask --gateway\n"
        "\n"
        "Reading is safe. --set writes to the device and takes effect after a\n"
        "power cycle; note it down before you change it.\n";
}

bool needValue(int i, int argc, const char* what) {
    if (i >= argc) {
        std::cerr << "missing value for " << what << "\n";
        return false;
    }
    return true;
}

bool parse(int argc, char** argv, Options& o) {
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&](std::string& dst) {
            if (!needValue(i + 1, argc, a.c_str())) return false;
            dst = argv[++i];
            return true;
        };
        auto nextInt = [&](int& dst) {
            if (!needValue(i + 1, argc, a.c_str())) return false;
            dst = std::atoi(argv[++i]);
            return true;
        };

        if (a == "-h" || a == "--help") { usage(argv[0]); std::exit(0); }
        else if (a == "--ip")          { if (!next(o.lidarIp)) return false; }
        else if (a == "--port")        { if (!nextInt(o.lidarPort)) return false; }
        else if (a == "--bind-ip")     { if (!next(o.bindIp)) return false; }
        else if (a == "--bind-port")   { if (!nextInt(o.bindPort)) return false; }
        else if (a == "--set")         { o.doSet = true; }
        else if (a == "--sensor-ip")   { if (!next(o.newSensorIp)) return false; }
        else if (a == "--sensor-port") { if (!nextInt(o.newSensorPort)) return false; }
        else if (a == "--pc-ip")       { if (!next(o.newPcIp)) return false; }
        else if (a == "--pc-port")     { if (!nextInt(o.newPcPort)) return false; }
        else if (a == "--mask")        { if (!next(o.newMask)) return false; }
        else if (a == "--gateway")     { if (!next(o.newGateway)) return false; }
        else {
            std::cerr << "unknown option: " << a << "\n";
            usage(argv[0]);
            return false;
        }
    }
    return true;
}

void report(soslab::Lidar& lidar, const std::string& o_lidarIp) {
    std::string sensorIp, pcIp, mask, gateway, mac;
    int sensorPort = 0, pcPort = 0;

    if (!lidar.getEthernetInfo(sensorIp, sensorPort, pcIp, pcPort, mask, gateway, mac)) {
        // connectLidar() only opens the local socket; it succeeds even with
        // nothing on the other end. This is where a real failure surfaces, so
        // put the diagnosis here rather than there.
        std::cerr <<
            "\ngetEthernetInfo failed - the sensor did not answer.\n"
            "\n"
            "Check the \"UDP :: Connected\" line above. The address before the colon\n"
            "is the interface this socket actually bound to. If it is your wifi or\n"
            "any address outside the sensor's subnet, that is the problem: give the\n"
            "Ethernet interface an address on the sensor's subnet and try again.\n"
            "\n"
            "    networksetup -listallhardwareports\n"
            "    sudo ipconfig set <iface> MANUAL 192.168.1.15 255.255.255.0\n"
            "\n"
            "Otherwise check the cable, that the sensor is powered, and that no\n"
            "firewall is dropping UDP. Watch the wire with:\n"
            "\n"
            "    sudo tcpdump -ni <iface> -vv 'udp and host " << o_lidarIp << "'\n";
        return;
    }

    std::cout << "\n  sensor   " << sensorIp << ":" << sensorPort
              << "\n  pc       " << pcIp << ":" << pcPort
              << "\n  netmask  " << mask
              << "\n  gateway  " << gateway
              << "\n  mac      " << mac
              << "\n\n"
              << "Launch the node with:\n"
              << "  ros2 launch ml gl5_viz.launch.py"
              << " ip_address_device:=" << sensorIp
              << " ip_port_device:=" << sensorPort
              << " ip_port_pc:=" << pcPort << "\n"
              << "and give the host NIC the address " << pcIp << ".\n";
}

}  // namespace

int main(int argc, char** argv) {
    Options o;
    if (!parse(argc, argv, o)) return 2;

    if (o.doSet && (o.newSensorIp.empty() || o.newPcIp.empty() ||
                    o.newMask.empty() || o.newGateway.empty() ||
                    o.newSensorPort < 0 || o.newPcPort < 0)) {
        std::cerr << "--set needs all of --sensor-ip --sensor-port --pc-ip "
                     "--pc-port --mask --gateway\n";
        return 2;
    }

    soslab::lidarParameters params;
    params.lidarTypeValue = soslab::lidarType::GL5;
    params.conectionTypeValue = soslab::connectionType::ETHERNET;  // vendor typo
    params.lidarIP = o.lidarIp;
    params.lidarPort = o.lidarPort;
    params.pcIP = o.bindIp;
    params.pcPort = o.bindPort;

    soslab::Lidar lidar(params);
    std::cout << "SDK " << lidar.getSDKVersion()
              << " -- connecting to " << o.lidarIp << ":" << o.lidarPort
              << " from " << o.bindIp << ":" << o.bindPort << std::endl;

    if (!lidar.connectLidar()) {
        std::cerr << "connectLidar failed. Check cabling, that the host NIC is on "
                     "the sensor's subnet, and that no firewall is dropping UDP.\n";
        return 1;
    }

    std::string serial, fw;
    if (lidar.getSerialNum(serial)) std::cout << "  serial   " << serial << "\n";
    if (lidar.getFWVersion(fw))     std::cout << "  firmware " << fw << "\n";

    report(lidar, o.lidarIp);

    if (o.doSet) {
        std::cout << "\nwriting new Ethernet config ..." << std::endl;
        if (!lidar.setEthernetInfo(o.newSensorIp, o.newSensorPort, o.newPcIp,
                                   o.newPcPort, o.newMask, o.newGateway)) {
            std::cerr << "setEthernetInfo failed\n";
            lidar.disconnectLidar();
            return 1;
        }
        std::cout << "written. Power cycle the sensor for it to take effect.\n";
    }

    lidar.disconnectLidar();
    return 0;
}
