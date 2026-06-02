# Changelog

## [Unreleased]

### Refactor
- Split the Flask app into smaller modules for configuration, repository access, background download management, and routes.
- Replaced the monolithic entry point with a thin app factory wrapper.
- Cleaned up the dashboard JavaScript by centralizing API calls and reducing duplicated request logic.

### Verification
- Verified the refactor with the project test suite using the local virtual environment.
- Current test result: 8 passed in 0.23s.
