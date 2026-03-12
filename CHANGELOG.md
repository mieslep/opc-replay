# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
