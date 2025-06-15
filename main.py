import os
import requests
import json
import time
from typing import List, Tuple
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from anthropic import Anthropic
from urllib.parse import urljoin
import gradio as gr
import tempfile

# Load environment variables
load_dotenv(override=True)

# Get API key from environment variable (more secure)
api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    print("Please add ANTHROPIC_API_KEY=your_key_here to your .env file")

# Use the current model instead of deprecated one
MODEL = "claude-3-5-sonnet-20241022"
client = Anthropic(api_key=api_key) if api_key else None

# Enhanced headers to avoid 403 errors
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class Website:
    def __init__(self, url):
        self.url = url
        try:
            # Add a small delay to be respectful to servers
            time.sleep(1)
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            self.body = response.content
            soup = BeautifulSoup(self.body, 'html.parser')
            self.title = soup.title.string if soup.title else "No title found"
            
            if soup.body:
                # Remove unwanted elements
                for tag in soup.body(["script", "style", "img", "input", "button", "nav", "footer"]):
                    tag.decompose()
                self.text = soup.body.get_text(separator="\n", strip=True)
                # Clean up extra whitespace
                self.text = "\n".join(line.strip() for line in self.text.split("\n") if line.strip())
            else:
                self.text = ""
                
            # Extract links
            links = [link.get('href') for link in soup.find_all('a') if link.get('href')]
            self.links = []
            for link in links:
                try:
                    full_url = urljoin(url, link)
                    # Filter out non-http links and fragments
                    if full_url.startswith(('http://', 'https://')) and '#' not in full_url:
                        self.links.append(full_url)
                except:
                    continue
                    
        except requests.exceptions.RequestException as e:
            print(f"Error scraping {url}: {e}")
            self.title = "Error - Could not access page"
            self.text = f"Unable to scrape this page: {str(e)}"
            self.links = []
        except Exception as e:
            print(f"Unexpected error scraping {url}: {e}")
            self.title = "Error"
            self.text = ""
            self.links = []

    def get_contents(self):
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text[:2000]}{'...' if len(self.text) > 2000 else ''}\n\n"

# Prompts
link_system_prompt = """You are provided with a list of links found on a webpage. 
You are able to decide which of the links would be most relevant to include in a brochure about the company, 
such as links to an About page, Company page, Careers/Jobs pages, Enterprise/Business pages, or Contact pages.
Select only the most important 5-7 links that would provide comprehensive information about the company.
Respond in JSON format as in this example:
{
    "links": [
        {"type": "about page", "url": "https://full.url/goes/here/about"},
        {"type": "careers page", "url": "https://another.full.url/careers"}
    ]
}
"""

def get_links_user_prompt(website):
    user_prompt = f"Here is the list of links on the website of {website.url}. "
    user_prompt += "Please decide which of these are relevant web links for a company brochure. "
    user_prompt += "Focus on: About, Company, Careers, Enterprise, Business, Contact, Team, Mission, Values pages. "
    user_prompt += "Do not include: Terms of Service, Privacy, Login, Sign up, Social media, or email links. "
    user_prompt += "Respond with the full https URL in JSON format. Select only the 5-7 most important links.\n"
    user_prompt += "Links:\n" + "\n".join(website.links[:50])  # Limit to first 50 links
    return user_prompt

def get_links(url, progress=gr.Progress()):
    try:
        progress(0.2, desc="Analyzing website links...")
        website = Website(url)
        if not website.links:
            return {"links": []}
            
        user_prompt = get_links_user_prompt(website)
        
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            temperature=0,
            system=link_system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        content = response.content[0].text.strip()
        # Clean up potential markdown formatting
        if content.startswith('```json'):
            content = content.replace('```json', '').replace('```', '').strip()
            
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from Claude's response: {e}")
        return {"links": []}
    except Exception as e:
        print(f"Error getting links: {e}")
        return {"links": []}

def get_all_details(url, progress=gr.Progress()):
    progress(0.3, desc="Scraping main website...")
    result = "Landing page:\n"
    main_website = Website(url)
    result += main_website.get_contents()
    
    progress(0.4, desc="Finding relevant pages...")
    links_data = get_links(url, progress)
    
    if "links" in links_data:
        total_links = len(links_data["links"][:5])
        for i, link in enumerate(links_data["links"][:5]):  # Limit to 5 additional pages
            try:
                progress(0.5 + (i * 0.1), desc=f"Scraping {link['type']}...")
                result += f"\n\n{link['type']}\n"
                result += Website(link["url"]).get_contents()
            except Exception as e:
                print(f"Error processing link {link.get('url', 'unknown')}: {e}")
                continue
    
    return result

system_prompt = """You are an assistant that analyzes the contents of several relevant pages from a company website 
and creates a comprehensive brochure about the company for prospective customers, investors and recruits. 

Create a well-structured markdown document that includes:
- Company overview and mission
- Key products or services
- Company culture and values
- Career opportunities (if available)
- Key customers or market focus (if mentioned)
- Contact information

Make it professional, engaging, and informative. Use proper markdown formatting with headers, bullet points, and emphasis where appropriate."""

def get_brochure_user_prompt(company_name, url, progress=gr.Progress()):
    user_prompt = f"You are analyzing a company called: {company_name}\n"
    user_prompt += f"Website: {url}\n\n"
    user_prompt += "Here are the contents of its landing page and other relevant pages. Use this information to build a comprehensive company brochure in markdown format.\n\n"
    
    details = get_all_details(url, progress)
    # Instead of truncating, let's be smarter about content length
    if len(details) > 15000:
        user_prompt += details[:15000] + "\n\n[Content truncated for length]"
    else:
        user_prompt += details
    
    return user_prompt

def create_brochure_gradio(company_name: str, url: str, progress=gr.Progress()) -> Tuple[str, str]:
    """
    Create brochure for Gradio interface
    Returns: (brochure_content, download_file_path)
    """
    if not api_key:
        return "❌ Error: ANTHROPIC_API_KEY not found. Please add it to your .env file.", None
    
    if not company_name.strip():
        return "❌ Error: Please enter a company name.", None
    
    if not url.strip():
        return "❌ Error: Please enter a website URL.", None
    
    # Add https:// if not present
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        progress(0.1, desc="Starting brochure generation...")
        
        user_prompt = get_brochure_user_prompt(company_name, url, progress)
        
        progress(0.9, desc="Generating brochure with Claude...")
        
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        result = response.content[0].text
        
        # Create a temporary file for download
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
        temp_file.write(result)
        temp_file.close()
        
        progress(1.0, desc="Brochure generated successfully!")
        
        return result, temp_file.name
        
    except Exception as e:
        error_msg = f"❌ Error creating brochure: {str(e)}"
        return error_msg, None

# Create Gradio interface
def create_gradio_interface():
    with gr.Blocks(
        title="🏢 AI Company Brochure Generator",
        theme=gr.themes.Soft(),
        css="""
        .main-header {
            text-align: center;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 0.5em;
        }
        .subtitle {
            text-align: center;
            color: #666;
            font-size: 1.2em;
            margin-bottom: 2em;
        }
        """
    ) as app:
        
        gr.HTML("""
        <div class="main-header">🏢 AI Company Brochure Generator</div>
        <div class="subtitle">Powered by Claude API - Transform any company website into a professional brochure</div>
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML("<h3>📝 Input Details</h3>")
                
                company_name = gr.Textbox(
                    label="Company Name",
                    placeholder="e.g., HSBC, Google, Microsoft",
                    value="",
                    info="Enter the name of the company"
                )
                
                website_url = gr.Textbox(
                    label="Website URL",
                    placeholder="e.g., hsbc.co.in or https://www.google.com",
                    value="",
                    info="Enter the company's website URL (with or without https://)"
                )
                
                generate_btn = gr.Button(
                    "🚀 Generate Brochure",
                    variant="primary",
                    size="lg"
                )
                
                gr.HTML("""
                <div style="margin-top: 2em; padding: 1em; background-color: #f0f9ff; border-radius: 8px; border-left: 4px solid #0ea5e9;">
                    <h4>🤖 How it works:</h4>
                    <ol>
                        <li><strong>Agent 1:</strong> Scrapes the main website</li>
                        <li><strong>Agent 2:</strong> Finds relevant pages (About, Careers, etc.)</li>
                        <li><strong>Agent 3:</strong> Extracts content from selected pages</li>
                        <li><strong>Agent 4:</strong> Creates a professional brochure</li>
                    </ol>
                </div>
                """)
            
            with gr.Column(scale=2):
                gr.HTML("<h3>📄 Generated Brochure</h3>")
                
                brochure_output = gr.Markdown(
                    value="Your generated brochure will appear here...",
                    height=600,
                    show_copy_button=True
                )
                
                download_file = gr.File(
                    label="📥 Download Brochure",
                    visible=False
                )
        
        # Event handlers
        def handle_generation(company, url):
            if not company.strip() or not url.strip():
                return "❌ Please fill in both company name and website URL.", gr.File(visible=False)
            
            brochure_content, file_path = create_brochure_gradio(company, url)
            
            if file_path:
                return brochure_content, gr.File(value=file_path, visible=True)
            else:
                return brochure_content, gr.File(visible=False)
        
        generate_btn.click(
            fn=handle_generation,
            inputs=[company_name, website_url],
            outputs=[brochure_output, download_file],
            show_progress=True
        )
        
        # Example inputs
        gr.HTML("<h3>💡 Try these examples:</h3>")
        
        examples = [
            ["HSBC", "hsbc.co.in"],
            ["Anthropic", "anthropic.com"],
            ["OpenAI", "openai.com"]
        ]
        
        gr.Examples(
            examples=examples,
            inputs=[company_name, website_url],
            outputs=[brochure_output, download_file],
            fn=handle_generation,
            cache_examples=False
        )
    
    return app

# Launch the application
if __name__ == "__main__":
    app = create_gradio_interface()
    app.launch(
        share=True,  # Set to True to create a public link
        server_name="0.0.0.0",  # Allow access from other devices on network
        server_port=7860,
        show_error=True
    )

    