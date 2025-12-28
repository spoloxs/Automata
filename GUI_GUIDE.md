# Web GUI Guide

## Starting the GUI

```bash
# Option 1: Direct Python
python app.py

# Option 2: Startup script
./start_gui.sh
```

The GUI will be available at: **http://localhost:7860**

## Using the GUI

### Basic Workflow

1. **Enter Target URL**
   - The website you want to automate
   - Must start with `http://` or `https://`

2. **Describe Your Task**
   - Be specific about what you want to do
   - Examples below

3. **Upload Documents (Optional)**
   - Click "Upload Documents" accordion
   - Drag & drop or click to upload PDFs, DOCX, TXT
   - These will be sent directly to Gemini 2.5 Pro

4. **Configure Settings (Optional)**
   - Adjust number of parallel workers (1-8)
   - Toggle headless mode on/off

5. **Click "Run Automation"**
   - Watch real-time status updates
   - View statistics and results

## Document Upload Feature

### Supported Formats
- PDF (.pdf)
- Word Documents (.docx, .doc)
- Text Files (.txt)

### How It Works
Your uploaded documents are sent directly to Gemini 2.5 Pro along with your task. The AI can:
- Read your resume and fill job applications
- Extract data from invoices/forms
- Use information to answer questions
- Copy details from one document to a web form

### Example Use Cases

#### 1. Job Application with Resume
**URL**: `https://company.com/careers/apply`
**Task**: `Fill out the job application form using information from my resume`
**Upload**: Your resume PDF

The AI will:
- Extract your name, email, phone, education, experience
- Fill corresponding form fields automatically
- Use your skills and qualifications appropriately

#### 2. Form Filling from Invoice
**URL**: `https://accounting-system.com/new-invoice`
**Task**: `Create a new invoice entry using the uploaded invoice document`
**Upload**: Invoice PDF

#### 3. Data Transfer
**URL**: `https://crm.example.com/contacts/new`
**Task**: `Add a new contact using the business card information from the uploaded file`
**Upload**: Business card scan or text file

## GUI Features

### Real-Time Status
- ℹ️ Information messages (blue)
- 🔄 Running tasks (blue)
- ✅ Success messages (green)
- ⚠️ Warnings (yellow)
- ❌ Errors (red)

### Statistics Display
- Execution status
- Tasks completed / Total tasks
- Success rate percentage

### Output Section
- Extracted data from web pages
- Final results
- Any messages or errors

## Advanced Settings

### Max Parallel Workers
- **1-2**: Conservative, good for complex sites
- **3-4**: Balanced, recommended for most tasks
- **5-8**: Aggressive, use with caution

Higher values:
- ✅ Faster execution
- ❌ More resource usage
- ❌ Higher chance of issues on fragile sites

### Headless Mode
- **On (Recommended)**: Browser runs in background, faster
- **Off**: See the browser window, good for debugging

## Example Tasks

### Simple Navigation
```
URL: https://www.google.com
Task: Search for "web automation tools" and open the first result
Documents: None
```

### Form Filling
```
URL: https://example.com/contact
Task: Fill the contact form with my information and submit
Documents: resume.pdf (contains your name, email, phone)
```

### Data Extraction
```
URL: https://news.ycombinator.com
Task: Extract the top 10 story headlines and their scores
Documents: None
```

### Complex Workflow
```
URL: https://linkedin.com/jobs
Task: Search for "Python Developer" jobs, filter by Remote, and extract the top 5 job titles with company names
Documents: None
```

### Document-Driven Automation
```
URL: https://application-portal.com
Task: Complete the entire application using all information from my resume and cover letter
Documents: resume.pdf, cover_letter.pdf
```

## Tips for Best Results

### Task Description
1. **Be Specific**: "Click the blue Submit button" vs "Submit the form"
2. **Include Context**: Mention document usage explicitly
3. **Break Down Complex Tasks**: Describe each step
4. **Use Visual Cues**: "The login button in top-right corner"

### Document Upload
1. **File Quality**: Use clear, well-formatted PDFs
2. **Relevant Content**: Only upload documents needed for the task
3. **Multiple Files**: You can upload multiple related documents
4. **File Size**: Keep files under 10MB for best performance

### Troubleshooting
1. **Task Fails**: Try simpler, more specific instructions
2. **Forms Not Filled**: Ensure document contains the needed info
3. **Slow Performance**: Reduce parallel workers
4. **Browser Issues**: Try toggling headless mode

## Keyboard Shortcuts

- **Ctrl+Enter** in text fields: Submit (browser dependent)
- **Ctrl+C** in terminal: Stop the server

## Sharing the GUI

### Local Network Access
By default, the GUI runs on `0.0.0.0:7860`, accessible from:
- Same machine: http://localhost:7860
- Other devices on network: http://YOUR_IP:7860

### Internet Access (Not Recommended for Production)
```python
# In app.py, change:
app.launch(share=True)  # Creates temporary public link
```

**Security Warning**: Only use `share=True` for demos. Your automation will be publicly accessible!

## Stopping the GUI

- Press **Ctrl+C** in the terminal
- Or close the terminal window

## Advanced: Programmatic Access

The GUI is built with Gradio and has an API:

```python
from gradio_client import Client

client = Client("http://localhost:7860")
result = client.predict(
    url="https://example.com",
    task="Search for Python",
    documents=None,
    max_workers=2,
    headless=True,
    api_name="/run_automation"
)
```

## Need Help?

- **Documentation**: [README.md](README.md)
- **CLI Guide**: [CLI_GUIDE.md](CLI_GUIDE.md)
- **Issues**: [GitHub Issues](https://github.com/spoloxs/automata/issues)
- **Discussions**: [GitHub Discussions](https://github.com/spoloxs/automata/discussions)
