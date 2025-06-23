# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# macOS/Linux
./setup.sh

# Windows
setup.bat

# Manual setup
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### Running the Application
```bash
# Start development server
python app.py

# The app runs on http://127.0.0.1:5000/
```

### Testing
```bash
# Test Google Cloud credentials
python test_credentials.py

# Test Claude API (if using alternative translation engine)
python translate_claude.py --test

# Check API status
python check_api_status.py
```

## Architecture Overview

This is a Flask-based web application for translating JavaScript and JSON files using Google Cloud Translation API (or Claude API as an alternative).

### Core Components

1. **app.py**: Main Flask application with Socket.IO for real-time progress updates
   - Routes: `/` (upload page), `/translate` (processing), `/success/<filename>` (results)
   - Uses eventlet for async support
   - Real-time progress via Socket.IO

2. **translate.py**: Core translation logic using Google Cloud Translation API
   - Handles nested JSON structures
   - Preserves formatting and special tags
   - Batch processing with retry mechanism
   - Progress callbacks for real-time updates

3. **translate_claude.py**: Alternative translation using Claude API
   - Similar functionality to Google Translate module
   - Configurable via TRANSLATION_ENGINE in config.py

4. **Frontend Architecture**:
   - Modern Material Design-inspired UI
   - Real-time progress tracking with Socket.IO client
   - Drag-and-drop file upload
   - Smart language search with fuzzy matching
   - No frontend framework - vanilla JavaScript

### Key Features to Maintain

1. **File Format Support**: Only .js and .json files
2. **Translation Engines**: 
   - Google Translate API (default)
   - Claude API with multiple model options:
     - Claude Sonnet 4 and Opus 4 (latest generation)
     - Claude 3.5 Sonnet, Haiku
     - Claude 3 Opus, Haiku
   - User can select engine and model via UI
   - Models are loaded dynamically via API
3. **Progress Tracking**: Real-time updates via Socket.IO showing current item being translated
4. **Batch Download**: ZIP file containing all translated versions
5. **Error Handling**: Retry mechanism for API failures, comprehensive error messages
6. **Language Support**: 193 languages with smart search functionality

### Configuration

- **config.py**: Contains all app settings
  - TRANSLATION_ENGINE: 'google' or 'claude' (default: 'google')
  - CLAUDE_API_KEY: API key for Claude (configured)
  - CLAUDE_MODEL: 'claude-3-5-sonnet-latest' (使用最新的 Sonnet 模型)
  - MAX_FILE_SIZE: 10MB limit
  - BATCH_SIZE: 10 items per batch
  - Google credentials path: ./serviceKey.json

### Important Patterns

1. **Session Storage**: Uses Flask sessions to track upload/translation state
2. **File Handling**: Temporary storage in uploads/, results in output/
3. **Progress Updates**: Socket.IO emits 'progress' events with percentage and details
4. **Error Recovery**: Automatic retries for transient API failures

### Development Notes

- No formal testing framework - consider adding pytest if implementing tests
- No linting configuration - code follows standard Python conventions
- Frontend uses inline styles and embedded JavaScript - no build process
- All dependencies are Python-based (no npm/node setup required)

## Claude Memories

- Always response in chinese.