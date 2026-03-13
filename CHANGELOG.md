# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Auto-conversion of non-canonical NodeIds** - Simple tag names like `PET001CalcAlarm` automatically convert to `ns=2;s=PET001CalcAlarm` format (use `--allow-non-canonical` to disable)
- **Enhanced OPC client** - Statistics tracking (`--show-stats`), verbose mode (`--verbose`), and improved monitoring with configurable report frequency
- **Performance improvements** - Faster startup with compact NodeSet generation and optimized data loading

### Changed
- **BREAKING:** Removed `--skip-bad-csv` and `--drop-bad-nodeset-nodeids` flags (no longer needed with auto-conversion)

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
  - `opc-inject` CLI tool for easy override management
- **OPC Client Monitor** - First-class monitoring command
  - Auto-discover namespaces and variables
  - Real-time tag value monitoring
  - `opc-client` CLI tool
- **Robust OPC UA Compliance**
  - Proper SourceTimestamp and ServerTimestamp handling
  - Type inference and casting
  - Graceful error handling for invalid NodeIds

### Package Structure
- Entry points: `opc-replay`, `opc-inject`, `opc-client`
- Comprehensive test suite (unit and integration tests)
- Example data files and demonstration scripts
- CI/CD with GitHub Actions

### Coming Soon
- Docker support
- Performance optimizations for large datasets
- Additional data format support (e.g., JSON, InfluxDB)

## Version Links

[Unreleased]: https://github.com/mieslep/opc-replay/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/mieslep/opc-replay/releases/tag/v0.9.0
