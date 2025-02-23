import gradio as gr
from llm_backend import llm_interface
from file_checker import find_unused_files, delete_unused_files
from repo_file_combiner import RepoFileCombiner
from comment_finder import CommentFinder
from camel_case_finder import CamelCaseFinder
from code_improver import CodeImprover
from repo_analyzer import RepoAnalyzer  # Import the new class
import os

# Create instances of the classes
repo_combiner = RepoFileCombiner()
comment_finder = CommentFinder()
camel_case_finder = CamelCaseFinder()
code_improver = CodeImprover()
repo_analyzer = RepoAnalyzer(github_base_url="https://github.com/user/repo/blob/main")  # Default GitHub URL

# Default mounted path in the container
DEFAULT_MOUNT_PATH = "/app/shared_files"


def update_folder_path(input_path: str) -> str:
    """
    Validates and returns the folder path entered by the user.
    """
    if not input_path.strip():
        return DEFAULT_MOUNT_PATH
    if os.path.isdir(input_path):
        return input_path
    return f"Error: '{input_path}' is not a valid directory. Using default: {DEFAULT_MOUNT_PATH}"


# Define the Gradio interface
with gr.Blocks(title="CodeFixer") as demo:
    gr.Markdown("# CodeFixer")
    gr.Markdown("Interact with an LLM, check for unused files, combine files, find/delete comments, convert to snake_case, improve code quality, or analyze repository structure.")

    # Repository selector with manual input and update button
    with gr.Row():
        repo_input = gr.Textbox(
            label="Repository Path",
            value=DEFAULT_MOUNT_PATH,
            placeholder="Enter a repository folder path from /app/shared_files..."
        )
        update_path_btn = gr.Button("Update Path")

    ext_dropdown = gr.Dropdown(
        label="File Extensions",
        choices=["py", "svelte", "ts", "js", "txt", "md", "html", "css", "json", "xml", "yml", "yaml", "sh", "bat", "cpp", "java", "rb", "go", "rs"],
        value=["py", "svelte", "ts", "js", "txt", "md"],
        multiselect=True
    )

    # Single model dropdown for all tabs
    model_input = gr.Dropdown(
        label="Model",
        choices=["llama3.2:1b", "qwen2.5-coder"],  # Adjust based on available models
        value="llama3.2:1b"
    )

    with gr.Tabs():
        with gr.Tab("LLM Interaction"):
            with gr.Row():
                with gr.Column():
                    prompt_input = gr.Textbox(label="Prompt", placeholder="Enter your prompt here...", lines=3)
                    submit_btn = gr.Button("Submit")
                with gr.Column():
                    llm_output = gr.Textbox(label="LLM Response", lines=10)

            submit_btn.click(
                fn=lambda prompt, model: llm_interface(prompt, model, 0.7, 0.9, 512),
                inputs=[prompt_input, model_input],
                outputs=llm_output
            )

        with gr.Tab("File Checker"):
            with gr.Row():
                with gr.Column():
                    check_btn = gr.Button("Check Unused Files")
                    delete_btn = gr.Button("Delete Unused Files")
                with gr.Column():
                    check_output = gr.Textbox(label="File Check Results", lines=10)

            def check_files(repo_path, exts):
                if not repo_path or not os.path.isdir(repo_path):
                    return "Please enter a valid repository folder path"
                ext_string = ",".join(exts)
                return find_unused_files(repo_path, ext_string)

            def delete_files(repo_path, exts):
                if not repo_path or not os.path.isdir(repo_path):
                    return "Please enter a valid repository folder path"
                ext_string = ",".join(exts)
                return delete_unused_files(repo_path, ext_string, confirm=True)

            check_btn.click(
                fn=check_files,
                inputs=[repo_input, ext_dropdown],
                outputs=check_output
            )
            delete_btn.click(
                fn=delete_files,
                inputs=[repo_input, ext_dropdown],
                outputs=check_output
            )

        with gr.Tab("File Combiner"):
            with gr.Row():
                with gr.Column():
                    combine_btn = gr.Button("Combine Repository Files")
                with gr.Column():
                    combine_output = gr.Textbox(label="Combine Output", lines=10)

            def process_repo_and_combine(repo_path, exts):
                if not repo_path or not os.path.isdir(repo_path):
                    return "Please enter a valid repository folder path"
                repo_combiner.select_repository(repo_path)
                return repo_combiner.combine_files(approved_extensions=exts)

            combine_btn.click(
                fn=process_repo_and_combine,
                inputs=[repo_input, ext_dropdown],
                outputs=combine_output
            )

        with gr.Tab("Comment Finder"):
            with gr.Row():
                with gr.Column():
                    scan_btn = gr.Button("Scan for Comments")
                    delete_comments_btn = gr.Button("Delete Comments")
                    export_btn = gr.Button("Export Results")
                with gr.Column():
                    comment_output = gr.Textbox(label="Comment Finder Results", lines=10)

            def scan_comments(repo_path, exts):
                return comment_finder.scan_directory(repo_path, exts)

            def delete_comments(repo_path):
                return comment_finder.delete_comments(repo_path)

            def export_comments(repo_path):
                return comment_finder.export_results(repo_path)

            scan_btn.click(
                fn=scan_comments,
                inputs=[repo_input, ext_dropdown],
                outputs=comment_output
            )
            delete_comments_btn.click(
                fn=delete_comments,
                inputs=[repo_input],
                outputs=comment_output
            )
            export_btn.click(
                fn=export_comments,
                inputs=[repo_input],
                outputs=comment_output
            )

        with gr.Tab("Snake Case Converter"):
            with gr.Row():
                with gr.Column():
                    scan_snake_btn = gr.Button("Scan for Non-Snake Case")
                    replace_snake_btn = gr.Button("Replace with Snake Case")
                    export_snake_btn = gr.Button("Export Results")
                    load_results_btn = gr.Button("Load Exported Results")
                    results_file_input = gr.File(label="Upload Exported Results File")
                with gr.Column():
                    snake_output = gr.Textbox(label="Snake Case Results", lines=10)

            def scan_snake_case(repo_path, exts, model, progress=gr.Progress()):
                if not repo_path or not os.path.isdir(repo_path):
                    return "Please enter a valid repository folder path"

                exts = [ext if ext.startswith('.') else f'.{ext}' for ext in exts]
                output = ["Scanning for non-snake_case identifiers (classes and library names excluded)..."]
                camel_case_finder.results = {}

                total_files = sum(
                    len([f for f in files if os.path.splitext(f)[1].lower() in exts])
                    for _, _, files in os.walk(repo_path)
                )
                processed_files = 0

                progress(0, desc="Starting scan...")

                for root, _, files in os.walk(repo_path):
                    for file in files:
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in exts:
                            file_path = os.path.join(root, file)
                            non_snake_cases = camel_case_finder.find_non_snake_case(file_path, model)
                            if non_snake_cases:
                                relative_path = os.path.relpath(file_path, repo_path)
                                for original, suggested, line_num, ext in non_snake_cases:
                                    if original not in camel_case_finder.results:
                                        camel_case_finder.results[original] = (suggested, ext)
                                    cache_key = (original, ext)
                                    is_pkg = camel_case_finder.llm_cache.get(cache_key, "Pending")
                                    output.append(f"{relative_path}: Line {line_num} - {original} -> {suggested} (Package: {is_pkg})")

                            processed_files += 1
                            progress(processed_files / total_files, desc=f"Scanned {processed_files}/{total_files} files")

                if not camel_case_finder.results:
                    output.append("No non-snake_case identifiers found.")
                else:
                    output.append(f"\nFound {len(camel_case_finder.results)} unique non-snake_case identifiers across files.")

                return "\n".join(output)

            def replace_snake_case(repo_path, exts):
                return camel_case_finder.replace_with_snake_case(repo_path, exts)

            def export_snake_case(repo_path):
                return camel_case_finder.export_results(repo_path)

            def load_snake_case_results(file):
                if file is None:
                    return "Please upload an exported results file."
                return camel_case_finder.load_results(file.name)

            scan_snake_btn.click(
                fn=scan_snake_case,
                inputs=[repo_input, ext_dropdown, model_input],
                outputs=snake_output
            )
            replace_snake_btn.click(
                fn=replace_snake_case,
                inputs=[repo_input, ext_dropdown],
                outputs=snake_output
            )
            export_snake_btn.click(
                fn=export_snake_case,
                inputs=[repo_input],
                outputs=snake_output
            )
            load_results_btn.click(
                fn=load_snake_case_results,
                inputs=[results_file_input],
                outputs=snake_output
            )

        # Code Improver Tab with Progress Bar
        with gr.Tab("Code Improver"):
            with gr.Row():
                with gr.Column():
                    improvement_options = gr.CheckboxGroup(
                        label="Improvement Options",
                        choices=[
                            "Add Docstrings",
                            "Improve Formatting",
                            "Optimize Code",
                            "Enhance Error Handling",
                            "Verify Documentation",
                            "Remove i18n",
                            "Restrict AI Providers",
                            "Cleanup Dependencies"
                        ],
                        value=["Add Docstrings", "Improve Formatting"]
                    )
                    improve_btn = gr.Button("Improve Code")
                with gr.Column():
                    improve_output = gr.Textbox(label="Improvement Results", lines=10)

            def improve_code(repo_path, exts, options, model, progress=gr.Progress()):
                if not repo_path or not os.path.isdir(repo_path):
                    return "Please enter a valid repository folder path"

                options_dict = {opt: opt in options for opt in [
                    "Add Docstrings", "Improve Formatting", "Optimize Code",
                    "Enhance Error Handling", "Verify Documentation", "Remove i18n",
                    "Restrict AI Providers", "Cleanup Dependencies"
                ]}

                # Convert extensions to set and filter by supported ones
                extensions = {f".{ext}" if not ext.startswith('.') else ext for ext in exts}
                unsupported = extensions - code_improver.SUPPORTED_EXTENSIONS
                if unsupported:
                    extensions -= unsupported

                # Get total number of files to process
                files_to_process = [
                    os.path.join(root, file)
                    for root, _, files in os.walk(repo_path)
                    for file in files
                    if os.path.splitext(file)[1].lower() in extensions
                ]
                total_files = len(files_to_process)

                if total_files == 0:
                    return "No files found matching the selected extensions."

                # Initialize progress and output
                progress(0, desc="Starting code improvement...")
                output = ["Improving scripts..."]
                processed_files = 0

                # Process each file with progress updates
                for file_path in files_to_process:
                    result = code_improver.improve_file(file_path, options_dict, model)
                    output.append(result)
                    processed_files += 1
                    progress(processed_files / total_files, desc=f"Processed {processed_files}/{total_files} files")

                output.append("Improvement complete.")
                return "\n".join(output)

            improve_btn.click(
                fn=improve_code,
                inputs=[repo_input, ext_dropdown, improvement_options, model_input],
                outputs=improve_output
            )

        with gr.Tab("Repository Analyzer"):
            with gr.Row():
                with gr.Column():
                    github_url_input = gr.Textbox(
                        label="GitHub Base URL",
                        value="https://github.com/user/repo/blob/main",
                        placeholder="Enter the GitHub repository base URL..."
                    )
                    analyze_btn = gr.Button("Generate Repository Tree")
                with gr.Column():
                    analyze_output = gr.Textbox(label="Repository Tree", lines=15)

            def analyze_repository(repo_path, exts, github_url, model, progress=gr.Progress()):
                if not repo_path or not os.path.isdir(repo_path):
                    return "Please enter a valid repository folder path"

                repo_analyzer.github_base_url = github_url

                exts = [f".{ext}" if not ext.startswith('.') else ext for ext in exts]
                total_files = sum(
                    len([f for f in files if os.path.splitext(f)[1].lower() in exts])
                    for _, _, files in os.walk(repo_path)
                )
                if total_files == 0:
                    return "No files found matching the selected extensions."

                progress(0, desc="Starting repository analysis...")
                output = ["Analyzing repository structure..."]

                tree, processed_files_count = repo_analyzer.generate_tree(repo_path, exts, model)

                # Save the tree to a Markdown file
                md_file_path = os.path.join(repo_path, "repository_tree.md")
                try:
                    with open(md_file_path, 'w', encoding='utf-8') as md_file:
                        md_file.write(tree)
                    save_message = f"\nRepository tree saved as {md_file_path}"
                except Exception as e:
                    save_message = f"\nFailed to save repository tree: {e}"

                progress(1.0, desc=f"Processed {processed_files_count}/{total_files} files")
                output.append(tree)
                output.append(f"\nProcessed {processed_files_count} new files out of {total_files} total files.")
                output.append(save_message)

                return "\n".join(output)

            analyze_btn.click(
                fn=analyze_repository,
                inputs=[repo_input, ext_dropdown, github_url_input, model_input],
                outputs=analyze_output
            )

    update_path_btn.click(
        fn=update_folder_path,
        inputs=[repo_input],
        outputs=[repo_input]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
