# PulseNode Architecture: Distributed Telemetry & Observability Engine

![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen?style=for-the-badge) ![Version](https://img.shields.io/badge/Version-1.0.0-blue?style=for-the-badge) ![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)

**PulseNode** is a high-performance, real-time telemetry agent and distributed observability engine I engineered to capture granular metrics using eBPF, parse system logs, and compute real-time anomaly heuristics prior to forwarding data to a centralized or distributed datastore.

## 🧠 Core Architecture

The system operates across three fundamental tiers:
1. **The Ingestion Layer:** Featuring non-blocking internal threads capturing thousands of data points asynchronously.
2. **The Processing Node:** Where the daemon aggregates metrics into a bespoke time-series format and applies our custom `pulse_anomaly` scoring matrix built in Python.
3. **The Egress Layer:** Capable of high-throughput streaming to external observability dashboards with minimal latency.

```mermaid
flowchart TD
    subgraph HostOS ["Host OS Environment Layer"]
        subgraph Kernel ["Kernel Space"]
            ebpf[eBPF Tracepoints]
            vfs[VFS/Filesystem Hooks]
            net[TCP/UDP Sockets]
        end
        subgraph Userland ["User Space Components"]
            ps[Process Metrics]
            log[Systemd Journal]
            apps[Container Metrics (Docker/K8s)]
        end
    end

    subgraph PulseNode ["PulseNode Agent Core (C)"]
        direction TB
        subgraph Ingestor ["Data Ingestion Pipelines"]
            A1[eBPF Collector]
            A2[cgroups Parsers]
            A3[Log Processor]
        end
        
        subgraph Modules ["Custom Plugins Layer"]
            P[pulse_anomaly.chart.py]
            PY[Python.d Executor]
        end

        subgraph CoreEngine ["PulseNode Telemetry Engine"]
            DB[(Tiered TSDB RAM/ZSTD Disk)]
            Agg[Aggregator & Stream Processor]
            ML[Local Heuristic / Anomaly Detector]
        end

    end

    subgraph Frontend ["Egress & Observability"]
        Api[Asynchronous REST API / WebSocket]
        Exp[Prometheus Exporter Formatter]
        CDNUI[Dynamic Cloud Dashboard]
    end

    %% Data flow mapping
    ebpf --> A1
    net --> A1
    vfs --> A1
    ps --> A2
    apps --> A2
    log --> A3

    A1 --> Agg
    A2 --> Agg
    A3 --> Agg

    Agg --> DB
    DB <--> ML

    PY --> P
    Kernel -. "system states" .-> P
    P --> |"Outputs base threat level"| Agg

    DB --> Api
    ML --> Api
    Api --> CDNUI
    DB --> Exp

    %% Styling
    classDef os fill:#2b3e50,stroke:#34495e,stroke-width:2px,color:#ecf0f1
    classDef agent fill:#16a085,stroke:#1abc9c,stroke-width:4px,color:#fff
    classDef engine fill:#2980b9,stroke:#3498db,stroke-width:3px,color:#fff
    classDef frontend fill:#8e44ad,stroke:#9b59b6,stroke-width:2px,color:#fff
    classDef plugin fill:#d35400,stroke:#e67e22,stroke-width:3px,color:#fff

    class HostOS,Kernel,Userland os
    class PulseNode agent
    class CoreEngine,DB,Agg,ML engine
    class Frontend,Api,Exp,CDNUI frontend
    class Modules,P,PY plugin
```

## 🛠 Features

* **Sub-second Resolution:** Data is gathered and flushed to the time-series db every second without interrupting kernel operations.
* **Custom ML Heuristics:** Built an extensible Python module (`pulse_anomaly`) that runs alongside the daemon to calculate dynamic threat and anomaly scores.
* **Tiered TSDB Storage:** Employs an extremely efficient memory ring-buffer backed by compressed disk storage to preserve historical telemetry data.
* **Zero-Touch Config:** Auto-discovers processes, network interfaces, and container orchestrators upon initial boot sequence.

## 🚀 Building & Running

### Requirements
* Autotools (autoconf, automake, pkg-config)
* Zlib, Libuv, LibJudy, OpenSSL
* GCC or Clang

### Compilation Let's Go:

```bash
# Clone the repository
git clone https://github.com/yourusername/PulseNode.git
cd PulseNode

# Run the autotools configuration and build the agent
./autogen.sh
./configure --prefix=/usr/local/pulsenode
make -j$(nproc)

# Install
sudo make install
```

### Running

To run PulseNode locally in the foreground and see the custom startup sequence:

```bash
/usr/local/pulsenode/sbin/netdata -D
```

You should see our custom initialization logic indicating that `PULSENODE STARTUP` is operational!

## 🧪 Injecting Custom Telemetry

I highly encourage experimenting with the `pulse_anomaly` pipeline! You can adjust the scoring matrix by editing:
`src/collectors/python.d.plugin/pulse_anomaly/pulse_anomaly.chart.py`

*This repository represents my work modifying and abstracting advanced distributed monitoring capabilities to learn systems programming in C.*
