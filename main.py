import os
import requests
import json
import time
from typing import List
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from anthropic import Anthropic
from urllib.parse import urljoin

# Load environment variables
load_dotenv(override=True)

# Get API key from environment variable (more secure)
api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    #print("ERROR: ANTHROPIC_API_KEY not found in environment variables.")
    print("Please add ANTHROPIC_API_KEY=your_key_here to your .env file")
    exit(1)

if api_key and len(api_key) > 10:
    print("API key looks good so far")
else:
    print("There might be a problem with your API key? Please check your .env file.")

# Use the current model instead of deprecated one
MODEL = "claude-3-5-sonnet-20241022"
client = Anthropic(api_key=api_key)

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

def get_links(url):
    try:
        website = Website(url)
        if not website.links:
            print(f"No links found on {url}")
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
        print(f"Response was: {content}")
        return {"links": []}
    except Exception as e:
        print(f"Error getting links: {e}")
        return {"links": []}

def get_all_details(url):
    result = "Landing page:\n"
    main_website = Website(url)
    result += main_website.get_contents()
    
    links_data = get_links(url)
    print("Found links:", links_data)
    
    if "links" in links_data:
        for link in links_data["links"][:5]:  # Limit to 5 additional pages
            try:
                print(f"Scraping: {link['url']}")
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

def get_brochure_user_prompt(company_name, url):
    user_prompt = f"You are analyzing a company called: {company_name}\n"
    user_prompt += f"Website: {url}\n\n"
    user_prompt += "Here are the contents of its landing page and other relevant pages. Use this information to build a comprehensive company brochure in markdown format.\n\n"
    
    details = get_all_details(url)
    # Instead of truncating, let's be smarter about content length
    if len(details) > 15000:
        user_prompt += details[:15000] + "\n\n[Content truncated for length]"
    else:
        user_prompt += details
    
    return user_prompt

def create_brochure(company_name, url):
    try:
        user_prompt = get_brochure_user_prompt(company_name, url)
        
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        result = response.content[0].text
        
        # Save to file instead of using IPython display
        filename = f"{company_name.replace(' ', '_')}_brochure.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(result)
        
        print(f"\nBrochure created successfully! Saved as: {filename}")
        print("\n" + "="*50)
        print(result)
        print("="*50)
        
    except Exception as e:
        print(f"Error creating brochure: {e}")

# Example usage
if __name__ == "__main__":
    create_brochure("HSBC", "https://www.hsbc.co.in")