# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-12

### Added - Real-Time Tag Injection (Major Feature)
- **HTTP REST API** for real-time tag value injection on port 8080 (default)
  - `POST /inject` - Add single or batch tag overrides
  - `GET /inject` - List active and pending overrides
  - `DELETE /inject` - Clear all overrides
- **CLI injection tool** - `opc-inject` command for easy tag override management
  - Single tag injection with `--tag`, `--value`, `--duration`
  - Time-delayed activation with `--offset`
  - Batch injection from JSON/CSV files with `--file`
  - List active overrides with `--list`
  - Clear all overrides with `--clear`
- **OverrideStore** - Thread-safe storage for managing tag overrides with automatic expiry
- **Background override applier** - Dedicated thread polling every 100ms for low-latency injection
- **Scheduled injections** - Set time-delayed overrides with configurable duration
- Integration test suite (`tests/test_override.py`) with comprehensive API validation
- Example injection files in JSON and CSV formats
- `--api-port` command-line option (default: 8080, set to 0 to disable API)

### Changed - Enhanced OPC UA Compliance
- **Proper timestamp handling** - Now sets both SourceTimestamp and ServerTimestamp on all writes
  - Critical for SCADA/HMI systems and data historians
  - Ensures proper timestamp propagation to OPC UA clients
- **Override-aware replay loop** - Skips writing CSV values when override is active
  - Eliminates value flicker between override and replay data
  - Cleaner behavior during injection testing
- **Improved type inference** - New `_infer_variant()` function for flexible type handling
- **Namespace remapping optimization** - Pre-computes identity map for performance
- **Enhanced null handling** - Better handling of None values in cast_value()

### Documentation
- Comprehensive API documentation in README.md
- Tag injection usage guide in examples/USAGE.md
- Python integration examples
- REST API endpoint documentation with curl examples
- Migration guide for existing users

### Compatibility
- **Backward compatible** - All existing functionality preserved
- API is enabled by default but can be disabled with `--api-port 0`
- No breaking changes to command-line arguments
- No new dependencies required (uses standard library for API)

### Credits
- Tag injection feature developed by colleague Branislav
- Merged from branislav-opc-sim branch

## [0.1.0] - 2026-03-12

### Added
- Initial project structure for publishable Python package
- Main OPC UA replay server (`opc_replay/server.py`)
  - Support for CSV and Parquet data files
  - NodeSet2 XML import for address space definition
  - Configurable playback speed (1x to 100x+)
  - Loop mode for continuous replay
  - Offset and max-rows options for data slicing
  - Namespace remapping support
  - Error handling for invalid NodeIds
- Utility for generating NodeSet XML from tag catalogs (`opc_replay/csv_to_nodeset.py`)
- Test utilities:
  - `tests/test_client.py` - OPC UA client for testing
  - `tests/test_load_logic.py` - Data loading tests
- Example data files:
  - Simple example with 3 tags (Temperature, Pressure, Flow)
  - simple-nodeset.xml and simple-data.csv for quick testing
  - 6 seconds of sample data (18 rows)
- Documentation:
  - Comprehensive README.md with installation and usage instructions
  - examples/USAGE.md with detailed examples
  - test_install.sh for verifying installation
- Package configuration:
  - pyproject.toml with entry point for `opc-replay` command
  - .gitignore for Python projects
  - LICENSE file

### Migration Notes
- Migrated from ~/python/opc-sim to standalone repository
- Restructured as proper Python package with entry points
- Added comprehensive documentation and examples
- Ready for PyPI publication

## [Unreleased]

### Planned
- Add unit tests
- Add GitHub Actions CI/CD
- Add Docker support
- Add more data format options
- Performance optimizations for large datasets
