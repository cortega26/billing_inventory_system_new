import os
import re

def search_string_in_files(root_dir, target_string, file_extensions=None):
    """
    Recursively search for a specific string (as a substring) in files with given extensions 
    within a directory and its subdirectories.
    
    Args:
        root_dir (str): The root directory to start searching.
        target_string (str): The string to search for in files.
        file_extensions (list, optional): List of file extensions to search in (e.g., ['.py', '.txt']). 
                                          Searches all files if None is provided.
    Returns:
        dict: A dictionary with file paths as keys and lists of (line_number, line_content) tuples as values.
        int: Total number of files searched.
        list: List of file paths that were searched.
    """
    if file_extensions is None:
        file_extensions = []  # Search all files if no specific extensions provided

    occurrences = {}
    total_files_searched = 0
    files_searched_list = []
    pattern = re.compile(re.escape(target_string), re.IGNORECASE)  # Case-insensitive search

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            # Check if the file has a desired extension or no filtering is applied
            if not file_extensions or any(filename.endswith(ext) for ext in file_extensions):
                file_path = os.path.join(dirpath, filename)
                files_searched_list.append(file_path)
                total_files_searched += 1
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        for line_num, line in enumerate(file, start=1):
                            if pattern.search(line):
                                if file_path not in occurrences:
                                    occurrences[file_path] = []
                                occurrences[file_path].append((line_num, line.strip()))
                except (UnicodeDecodeError, PermissionError) as e:
                    print(f"Could not read file: {file_path} ({e})")

    return occurrences, total_files_searched, files_searched_list


def print_results(results, total_files, files_searched_list):
    """Prints the results in a user-friendly format."""
    print("\nFiles searched:")
    for file_path in files_searched_list:
        print(f"  {file_path}")
    
    print(f"\nTotal files searched: {total_files}")
    
    if not results:
        print("\nNo occurrences found.")
        return

    print("\nOccurrences found:")
    for file_path, lines in results.items():
        print(f"\nIn file: {file_path}")
        for line_num, line_content in lines:
            print(f"  Line {line_num}: {line_content}")


if __name__ == "__main__":
    # User input for directory, search string, and file extensions
    root_directory = input("Enter the root directory to search: ").strip()
    search_str = input("Enter the string to search for: ").strip()
    extensions = input("Enter file extensions to search (comma-separated, e.g., .py,.txt) or leave blank for all files: ").strip()

    # Convert extensions to a list
    if extensions:
        extensions = [ext.strip() for ext in extensions.split(',')]
    else:
        extensions = None  # Search all files

    # Search and display results
    result, total_files, files_searched = search_string_in_files(root_directory, search_str, extensions)
    print_results(result, total_files, files_searched)
