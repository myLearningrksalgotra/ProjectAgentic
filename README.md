# Anthropic API Integration Project

This project demonstrates the integration of the Anthropic API for various tasks, including fetching data, processing it, and interacting with external services. It uses Python and several libraries to streamline API communication and data handling.

## Features

- Secure API key management using environment variables.
- Integration with the Anthropic API.
- Web scraping using BeautifulSoup.
- HTTP requests using the `requests` library.
- Environment variable management with `python-dotenv`.

## Prerequisites

Before running the project, ensure you have the following installed:

- Python 3.8 or higher
- `pip` (Python package manager)

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd <repository-folder>
Create a .env file in the root directory and add your Anthropic API key:

Install the required dependencies:

Usage
Run the application:

If the ANTHROPIC_API_KEY is not set in the .env file, the application will display an error message and exit.

Environment Variables
The project uses the following environment variables:

<vscode_annotation details='%5B%7B%22title%22%3A%22hardcoded-credentials%22%2C%22description%22%3A%22Embedding%20credentials%20in%20source%20code%20risks%20unauthorized%20access%22%7D%5D'>-</vscode_annotation> ANTHROPIC_API_KEY: Your API key for accessing the Anthropic API.

Dependencies
The project uses the following Python libraries:

os: For environment variable management.
requests: For making HTTP requests.
json: For handling JSON data.
time: For time-related operations.
typing: For type hinting.
python-dotenv: For loading environment variables from a .env file.
beautifulsoup4: For web scraping.
anthropic: For interacting with the Anthropic API.
Install all dependencies using:

License
This project is licensed under the MIT License. See the LICENSE file for details.

Contributing
Contributions are welcome! Please submit a pull request or open an issue to discuss changes.

Author
Rajesh Kumar