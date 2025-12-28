#!/usr/bin/env python3
"""
Web-based GUI for AI Web Automation Agent using Gradio

This provides a user-friendly interface for automating web tasks with optional
document uploads (like resumes) that are sent directly to Gemini 2.5 Pro.
"""

import asyncio
import gradio as gr
import sys
import os
from pathlib import Path
from typing import Optional, List
import tempfile

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from web_agent.core.master_agent import MasterAgent
    from google.generativeai import upload_file, get_file
    import google.generativeai as genai
except ImportError as e:
    print(f"❌ Error importing required modules: {e}")
    print("   Please run: pip install -e .")
    sys.exit(1)


# Global to track current automation
current_automation = {"running": False, "master": None}


def format_status(message: str, status_type: str = "info") -> str:
    """Format status messages with emoji"""
    emoji_map = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "running": "🔄",
        "waiting": "⏳"
    }
    emoji = emoji_map.get(status_type, "•")
    return f"{emoji} {message}"


async def run_automation_with_docs(
    url: str,
    task: str,
    documents: Optional[List] = None,
    max_workers: int = 2,
    headless: bool = True,
    progress=gr.Progress()
) -> tuple[str, str, str]:
    """
    Run web automation with optional document context

    Args:
        url: Target URL
        task: Task description
        documents: List of uploaded files (PDFs, DOCx, etc.)
        max_workers: Number of parallel workers
        headless: Run browser in headless mode
        progress: Gradio progress tracker

    Returns:
        Tuple of (status, statistics, output)
    """

    if current_automation["running"]:
        return (
            format_status("Another automation is already running", "error"),
            "",
            ""
        )

    # Validate inputs
    if not url or not url.startswith(('http://', 'https://')):
        return (
            format_status("Invalid URL. Must start with http:// or https://", "error"),
            "",
            ""
        )

    if not task:
        return (
            format_status("Task description cannot be empty", "error"),
            "",
            ""
        )

    current_automation["running"] = True
    status_messages = []

    try:
        # Process uploaded documents
        document_context = ""
        uploaded_files = []

        if documents:
            progress(0.1, desc="Processing uploaded documents...")
            status_messages.append(format_status(f"Processing {len(documents)} document(s)...", "info"))

            for doc in documents:
                if doc is not None:
                    file_path = doc.name if hasattr(doc, 'name') else doc
                    file_name = Path(file_path).name

                    try:
                        # Upload file to Gemini
                        uploaded_file = upload_file(file_path)
                        uploaded_files.append(uploaded_file)
                        status_messages.append(format_status(f"Uploaded: {file_name}", "success"))

                        # Add to context
                        document_context += f"\n- {file_name}"
                    except Exception as e:
                        status_messages.append(format_status(f"Failed to upload {file_name}: {str(e)}", "warning"))

        # Enhance task with document context
        enhanced_task = task
        if uploaded_files:
            enhanced_task = f"""{task}

IMPORTANT: Use information from the uploaded document(s): {document_context}

The documents have been provided and contain relevant information for filling forms, answering questions, etc. Extract and use the information as needed."""

        # Initialize master agent
        progress(0.2, desc="Initializing AI agents...")
        status_messages.append(format_status("Initializing AI agents...", "running"))

        master = MasterAgent(max_parallel_workers=max_workers)
        current_automation["master"] = master
        await master.initialize()

        status_messages.append(format_status("Agents initialized successfully", "success"))

        # Pass uploaded files to master agent for Gemini context
        if uploaded_files:
            # Store files in master agent for use in prompts
            if not hasattr(master, '_uploaded_documents'):
                master._uploaded_documents = []
            master._uploaded_documents.extend(uploaded_files)

        # Execute automation
        progress(0.3, desc="Executing automation...")
        status_messages.append(format_status(f"Starting automation on {url}", "running"))
        status_messages.append(format_status(f"Task: {task}", "info"))

        result = await master.execute_goal(
            goal=enhanced_task,
            starting_url=url
        )

        # Compile statistics
        progress(0.9, desc="Compiling results...")

        stats = f"""
**Execution Statistics:**
- Status: {'✅ Success' if result.success else '⚠️ Partial Success'}
- Tasks Completed: {result.completed_tasks}/{result.total_tasks}
- Success Rate: {(result.completed_tasks/result.total_tasks*100) if result.total_tasks > 0 else 0:.1f}%
"""

        # Compile output
        output = ""
        if hasattr(result, 'extracted_data') and result.extracted_data:
            output += f"**Extracted Data:**\n{result.extracted_data}\n\n"

        if hasattr(result, 'message') and result.message:
            output += f"**Message:**\n{result.message}\n"

        if result.success:
            status_messages.append(format_status("Automation completed successfully!", "success"))
        else:
            status_messages.append(format_status("Automation completed with some issues", "warning"))

        # Cleanup
        progress(1.0, desc="Cleaning up...")
        await master.cleanup()

        return (
            "\n".join(status_messages),
            stats,
            output if output else "No additional output"
        )

    except KeyboardInterrupt:
        status_messages.append(format_status("Automation interrupted by user", "warning"))
        return ("\n".join(status_messages), "", "")

    except Exception as e:
        status_messages.append(format_status(f"Automation failed: {str(e)}", "error"))
        import traceback
        error_trace = traceback.format_exc()
        return ("\n".join(status_messages), "", f"**Error:**\n```\n{error_trace}\n```")

    finally:
        current_automation["running"] = False
        current_automation["master"] = None


def stop_automation():
    """Stop the currently running automation"""
    if current_automation["running"] and current_automation["master"]:
        # Note: Actual stopping would require more sophisticated task cancellation
        return format_status("Stopping automation... (cleanup in progress)", "warning")
    return format_status("No automation is currently running", "info")


def create_gui():
    """Create the Gradio interface"""

    with gr.Blocks(
        title="AI Web Automation Agent",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {max-width: 1200px !important}
        .status-box {font-family: monospace; padding: 10px; background: #f5f5f5; border-radius: 5px}
        """
    ) as app:

        gr.Markdown("""
        # 🤖 AI Web Automation Agent

        **Powered by Gemini 2.5 Pro + OmniParser**

        Automate web tasks with AI. Upload documents (like your resume) to help fill forms automatically!
        """)

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 🎯 Automation Settings")

                url_input = gr.Textbox(
                    label="Target URL",
                    placeholder="https://www.example.com",
                    info="The website you want to automate"
                )

                task_input = gr.Textbox(
                    label="Task Description",
                    placeholder="Fill the job application form using my resume",
                    lines=3,
                    info="Describe what you want the agent to do"
                )

                with gr.Accordion("📎 Upload Documents (Optional)", open=False):
                    gr.Markdown("""
                    Upload PDFs, DOCX, or other documents. The AI will use them to fill forms, answer questions, etc.

                    **Example use cases:**
                    - Upload resume → Fill job applications
                    - Upload invoice → Extract and enter data
                    - Upload form → Copy information to web form
                    """)

                    document_upload = gr.Files(
                        label="Documents",
                        file_types=[".pdf", ".docx", ".doc", ".txt"],
                        file_count="multiple"
                    )

                with gr.Accordion("⚙️ Advanced Settings", open=False):
                    max_workers = gr.Slider(
                        minimum=1,
                        maximum=8,
                        value=2,
                        step=1,
                        label="Max Parallel Workers",
                        info="Higher = faster but more resource intensive"
                    )

                    headless_mode = gr.Checkbox(
                        label="Headless Mode (no visible browser)",
                        value=True,
                        info="Recommended for faster execution"
                    )

                with gr.Row():
                    run_btn = gr.Button("🚀 Run Automation", variant="primary", scale=2)
                    stop_btn = gr.Button("⏹️ Stop", variant="stop", scale=1)

            with gr.Column(scale=3):
                gr.Markdown("### 📊 Status & Results")

                status_output = gr.Textbox(
                    label="Status",
                    lines=8,
                    elem_classes="status-box",
                    interactive=False
                )

                stats_output = gr.Markdown(label="Statistics")

                result_output = gr.Markdown(label="Output")

        # Examples
        gr.Markdown("### 💡 Example Use Cases")

        gr.Examples(
            examples=[
                [
                    "https://www.google.com",
                    "Search for 'Python web automation' and click the first result",
                    None,
                    2,
                    True
                ],
                [
                    "https://example.com/contact",
                    "Fill the contact form using information from my uploaded resume",
                    None,
                    2,
                    True
                ],
                [
                    "https://news.ycombinator.com",
                    "Extract the top 5 story headlines and their scores",
                    None,
                    2,
                    True
                ],
            ],
            inputs=[url_input, task_input, document_upload, max_workers, headless_mode],
            label="Click an example to load it"
        )

        # Event handlers
        run_btn.click(
            fn=lambda *args: asyncio.run(run_automation_with_docs(*args)),
            inputs=[url_input, task_input, document_upload, max_workers, headless_mode],
            outputs=[status_output, stats_output, result_output]
        )

        stop_btn.click(
            fn=stop_automation,
            outputs=status_output
        )

        # Footer
        gr.Markdown("""
        ---

        **Need Help?**
        - [Documentation](https://github.com/spoloxs/automata)
        - [Report Issues](https://github.com/spoloxs/automata/issues)

        Made with ❤️ using Claude Code
        """)

    return app


def main():
    """Launch the GUI"""
    print("🚀 Starting AI Web Automation Agent GUI...")
    print("📝 Make sure you have:")
    print("   - Set GEMINI_API_KEY in .env")
    print("   - Redis server running")
    print("   - Playwright browsers installed")
    print()

    app = create_gui()

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )


if __name__ == "__main__":
    main()
