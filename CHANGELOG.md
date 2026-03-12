# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-03-12

### Added - Hardening & Usability Improvements
- **opc-client CLI tool** - First-class monitoring command for demonstrating server functionality
  - Auto-discover namespaces and variables
  - Monitor tag value changes in real-time
  - Flexible polling configuration
  - Entry point: `opc-client`
- **Auto-generate NodeSets** - Generate OPC UA NodeSet XML automatically from data files
  - New `--auto-nodeset` flag on `opc-replay` command
  - Saves generated NodeSet for reuse (faster subsequent startups)
  - Optional `--root-name` and `--namespace-uri` customization
- **Comprehensive examples/README.md** - Clear documentation of example files and quick start
- **demo_client.py** - Simple Python example showing OPC UA client usage
- **Improved documentation structure**:
  - README.md restructured as marketing/overview (concise, user-focused)
  - examples/USAGE.md expanded as comprehensive developer guide
  - examples/README.md for quick example file reference

### Changed
- **Refactored to_nodeset.py** - Extracted core logic into reusable `generate_nodeset_from_dataframe()` function
  - Enables programmatic NodeSet generation
  - CLI remains available via `python -m opc_replay.to_nodeset`
  - Improved help text and error messages
- **Test improvements** - Replaced hardcoded test data references with example files
  - test_load_logic.py now uses examples/simple-data.csv
  - test_override.py updated to use simple example tags (Temperature, Pressure, Flow)
  - Reduced warmup time from 15s to 3s for faster testing
  - Added clear documentation of test requirements
- **Updated module docstrings** - Server.py cleaned up to remove outdated script name references
- **Terminology clarification** - Removed confusing "tag catalog" concept throughout codebase and docs

### Fixed
- NodeSet requirement now properly validated (require either `--nodeset` or `--auto-nodeset`)
- Test brittleness eliminated by using consistent example data
- Documentation redundancy reduced by clear separation of concerns

### Documentation
- Restructured README.md to 180 lines (was 500+) focused on overview and quick start
- examples/USAGE.md provides comprehensive command reference and patterns
- examples/README.md explains example files and provides quick tutorials
- Architecture diagram added to README
- Clear links between documentation files

### Compatibility
- **Backward compatible** - All existing functionality preserved
- No breaking changes to command-line arguments
- New `--auto-nodeset` is optional; explicit `--nodeset` still supported

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
- Utility for generating NodeSet XML from tag catalogs (`opc_replay/to_nodeset.py`)
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
  - scripts/test_install.sh for verifying installation
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
- Add Docker support for easier deployment
- Add support for additional data formats (JSON, HDF5)
- Performance optimizations for large datasets
- Web-based dashboard for monitoring server status
