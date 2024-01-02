# Translation Utility

## Overview
This Translation Utility is designed to automate the process of translating JavaScript and JSON files containing language strings. It utilizes the Google Cloud Translation API to translate text from one language to another, handling both quoted and unquoted keys in JavaScript object notation.

## Features
- Translation of JavaScript and JSON files with support for special characters in keys.
- Progress tracking through socket communication.
- Output as a single .zip file containing all translated documents.
- Caching of supported languages to minimize API calls.

## Prerequisites
- Python 3.6+
- Flask
- Flask-SocketIO
- Google Cloud Translation API credentials

## Setup
1. Ensure Python 3.6+ is installed on your system.
2. Install required Python packages:
   \```shell
   pip install flask flask-socketio google-cloud-translate
   \```
3. Place your Google Cloud credentials JSON file in the project root and reference it in the environment variable `GOOGLE_APPLICATION_CREDENTIALS`:
   \```shell
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/credentials.json"
   \```
4. Clone this repository or download the source code.

## Running the Application
To run the application, execute the following command in the terminal:
\```shell
python app.py
\```
This will start a local server, typically hosted at `http://127.0.0.1:5000/`, which you can access using a web browser.

## Usage
1. Navigate to `http://127.0.0.1:5000/` in your web browser.
2. Upload a `.js` or `.json` file containing the language strings to be translated.
3. Select the target languages for translation.
4. Click on the translate button to start the process.
5. The application will display the progress of the translation in real-time.
6. Once the translation is complete, a download link for a zip file containing the translated files will be provided.

## Contributing
Contributions to this project are welcome. Please feel free to fork the repository and submit pull requests.

## License
[MIT License](LICENSE.md)

## Contact
For support or queries, please contact [your-email@example.com](mailto:your-email@example.com).

## Acknowledgements
- Google Cloud Translation API
- Flask and Flask-SocketIO contributors
- All contributors and users of this project
