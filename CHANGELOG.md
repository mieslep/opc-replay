# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **MQTT PubSub publishing (OPC UA Part 14)** - Publish replayed tag data to an MQTT broker using OPC UA PubSub JSON message format. Enable with `--mqtt-broker`. Supports configurable topic prefix, QoS, TLS, and authentication. Requires optional `paho-mqtt` dependency (`pip install opc-replay[mqtt]`).

## [0.11.0] - 2026-03-19

### Added
- **Consistent logging across all CLI tools** - All three commands (`opc-replay`, `opc-replay-client`, `opc-replay-inject`) now use Python's standard `logging` module with `--log-level` flag (DEBUG, INFO, WARNING, ERROR)

### Changed
- **BREAKING:** Renamed CLI commands for namespace consistency: `opc-inject` → `opc-replay-inject` and `opc-client` → `opc-replay-client`. The main server command `opc-replay` remains unchanged.
- **BREAKING:** Replaced `--quiet` and `--verbose` flags with `--log-level` for better logging control. Use `--log-level INFO` for standard output (default), `--log-level WARNING` for minimal output, `--log-level DEBUG` for detailed diagnostics.

### Fixed
- **Suppressed opcua library warnings** - Internal opcua library warnings (like "Tried to read attribute" errors when clients read folders) are now hidden in normal operation. Use `--log-level DEBUG` to see full opcua library diagnostics if needed.

## [0.10.0] - 2026-03-16

### Added
- **Auto-conversion of non-canonical NodeIds** - Simple tag names like `MySimpleTag` automatically convert to `ns=2;s=MySimpleTag` format (use `--allow-non-canonical` to disable)
- **Enhanced OPC client** - Statistics tracking (`--show-stats`), verbose mode (`--verbose`), and improved monitoring with configurable report frequency
- **Performance improvements** - Faster startup with compact NodeSet generation and optimized data loading

### Changed
- **BREAKING:** Removed `--skip-bad-csv` and `--drop-bad-nodeset-nodeids` flags (no longer needed with auto-conversion)

### Fixed
- **Statistics poll count reliability** - Fixed intermittent test failure on macOS where extremely fast polls (duration = 0.0s) were not being counted in statistics

## [0.9.0] - 2026-03-13

### Added
- **OPC UA Replay Server** - Replay historical timestamped tag data from CSV/Parquet files
  - Configurable playback speed (1x to 100x+)
  - Loop mode for continuous replay
  - Time offset and max-rows options for data slicing
  - Namespace remapping support
- **Auto-Generate NodeSets** - Create OPC UA address space automatically from data files
  - `--auto-nodeset` flag for automatic generation
  - Optional namespace URI and root name customization
- **Real-Time Tag Injection** - HTTP REST API for overriding tag values on-the-fly
  - Single and batch tag injection support
  - Time-delayed activation with configurable duration
  - `opc-replay-inject` CLI tool for easy override management
- **OPC Client Monitor** - First-class monitoring command
  - Auto-discover namespaces and variables
  - Real-time tag value monitoring
  - `opc-replay-client` CLI tool
- **Robust OPC UA Compliance**
  - Proper SourceTimestamp and ServerTimestamp handling
  - Type inference and casting
  - Graceful error handling for invalid NodeIds

### Package Structure
- Entry points: `opc-replay`, `opc-replay-inject`, `opc-replay-client`
- Comprehensive test suite (unit and integration tests)
- Example data files and demonstration scripts
- CI/CD with GitHub Actions

### Coming Soon
- Docker support
- Performance optimizations for large datasets
- Additional data format support (e.g., JSON, InfluxDB)

## Version Links

[Unreleased]: https://github.com/mieslep/opc-replay/compare/v0.11.0...HEAD
[0.11.0]: https://github.com/mieslep/opc-replay/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/mieslep/opc-replay/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/mieslep/opc-replay/releases/tag/v0.9.0
